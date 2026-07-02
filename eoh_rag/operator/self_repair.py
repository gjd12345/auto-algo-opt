"""
Compile self-repair loop: when LLM-generated Go code fails go build,
send the compiler error back to the LLM for repair (max 3 attempts).

This directly addresses the ~43% exclusion rate caused by compilation
failures and malformed Go code.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Any

REPAIR_MAX_ATTEMPTS = 3

REPAIR_SYSTEM_PROMPT = """You are a Go compiler expert. You will receive Go code for an InsertShips function that failed to compile, along with the compiler error.

Fix ONLY the compilation error. Do NOT change the algorithm or logic.
Do NOT add new imports unless absolutely required by the fix.
Return ONLY the complete fixed function, nothing else.

The function must have this exact signature:
func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch { ... }

Available types and methods:
- Dispatch: Assigns [MAXASSIGNS]Assign, AssignsLen int, TotalCost float64
  - func (dispatch *Dispatch) RenewnTotalCost()
- Assign: embeds RoutingTask and RoutingResult
  - NextSta int, NextTime int, StaIndexes [MAXSHIPS]Ship, StaIndexesLen int, AccumulatedCost float64
  - func (assign *Assign) AddShip(id int, ori, des Station) bool
  - func (assign *Assign) RemoveShip(id int)
  - func (assign *Assign) GenRoute()
  - Cost float64, StationsLen int, TimeCurrent int, StationCurrent Station
- Station: X int, Y int, TimeStart int, TimeEnd int, ReqCode int, Load int
- Ship: Id int, Ori int, Des int, Load int
- Utility: func cal_dis(st1, st2 Station) float64, func Abs(x int) int
- Constants: MAXASSIGNS=64, MAXSHIPS=8
"""


def _call_llm(prompt: str, api_key: str = "", api_endpoint: str = "",
              model: str = "", timeout: int = 60) -> str | None:
    """Call LLM API and return response text."""
    from eoh_rag.llm.client import chat_completion

    try:
        return chat_completion(
            messages=[
                {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            api_key=api_key,
            endpoint=api_endpoint,
            model=model or "deepseek-v4-flash",
            temperature=0.2,
            timeout_s=timeout,
            max_retries=3,
        )
    except RuntimeError:
        return None


def _extract_code_from_response(response: str) -> str | None:
    """Extract Go function code from LLM response, handling markdown fences."""
    code = response.strip()

    # Try to extract from markdown code block
    m = re.search(r"```(?:go|golang)?\s*\n(.*?)```", code, re.DOTALL)
    if m:
        code = m.group(1).strip()

    # Ensure it starts with func InsertShips
    func_match = re.search(
        r"func\s+InsertShips\s*\(.*?\)\s*Dispatch\s*\{",
        code, re.DOTALL
    )
    if func_match:
        code = code[func_match.start():]

    # Check we have valid code
    if "func InsertShips" not in code:
        return None

    return code.strip()


def _try_compile(project_dir: str) -> dict[str, Any]:
    """Try to compile a Go project. Returns build result dict."""
    try:
        proc = subprocess.run(
            ["go", "build", "-o", "mainbin.exe", "."],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "go build timed out"}
    except FileNotFoundError:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "go compiler not found"}


def _replace_insertships_func(main_go_text: str, new_func: str) -> str:
    """Replace InsertShips function in main.go text."""
    pat = r"func\s+InsertShips\s*\(\s*dispatch\s+Dispatch\s*,\s*oris\s*,\s*dess\s*\[\]Station\s*,\s*total_ship\s+int\s*\)\s*Dispatch\s*\{[\s\S]*?\n\}"
    matched = re.search(pat, main_go_text)
    if not matched:
        raise ValueError("InsertShips method not found in main.go")
    result = main_go_text[:matched.start()] + new_func.strip() + "\n" + main_go_text[matched.end():]

    # Auto-inject imports
    if "sort." in new_func:
        result = _ensure_go_import(result, "sort")
    if "SortManager" in new_func and "type SortManager struct" not in result:
        result = _inject_sort_manager(result)

    return result


def _ensure_go_import(go_text: str, pkg_name: str) -> str:
    import_block = re.search(r"import\s*\(([^)]*)\)", go_text, flags=re.DOTALL)
    if not import_block:
        return go_text
    body = import_block.group(1)
    if re.search(rf'^\s*"{re.escape(pkg_name)}"\s*$', body, flags=re.MULTILINE):
        return go_text
    updated_body = body.rstrip() + f'\n    "{pkg_name}"\n'
    return go_text[:import_block.start(1)] + updated_body + go_text[import_block.end(1):]


def _inject_sort_manager(go_text: str) -> str:
    insert_pos = go_text.find("func InsertShips(")
    if insert_pos < 0:
        return go_text
    block = (
        "type SortManager struct {\n"
        "    inds []int\n"
        "    values []float64\n"
        "}\n\n"
        "func (sm *SortManager) Len() int { return len(sm.inds) }\n\n"
        "func (sm *SortManager) Swap(i, j int) { sm.inds[i], sm.inds[j] = sm.inds[j], sm.inds[i] }\n\n"
        "func (sm *SortManager) Less(i, j int) bool {\n"
        "    return sm.values[sm.inds[i]] < sm.values[sm.inds[j]]\n"
        "}\n\n"
    )
    return go_text[:insert_pos] + block + go_text[insert_pos:]


def repair_compile_errors(
    code: str,
    project_root: str,
    api_key: str = "",
    api_endpoint: str = "",
    model: str = "",
    max_attempts: int = REPAIR_MAX_ATTEMPTS,
    base_main_go: str | None = None,
) -> dict[str, Any]:
    """
    Attempt to compile the given InsertShips code. If it fails, send the error
    to the LLM for repair, and retry up to max_attempts times.

    Returns dict with:
        - final_code: the (possibly repaired) Go code
        - compiled: whether it finally compiled
        - repair_count: number of repair attempts made
        - repair_log: list of (attempt, error, repaired_code) tuples
    """
    log: list[dict[str, Any]] = []
    current_code = code.strip()

    # Read main.go if not provided
    if base_main_go is None:
        main_go_path = os.path.join(project_root, "main.go")
        if os.path.exists(main_go_path):
            with open(main_go_path, "r", encoding="utf-8") as f:
                base_main_go = f.read()
        else:
            return {
                "final_code": current_code,
                "compiled": False,
                "repair_count": 0,
                "repair_log": [{"error": "main.go not found", "stage": "setup"}],
            }

    for attempt in range(max_attempts + 1):  # +1 for initial compile
        # Build temporary project
        tmp = tempfile.mkdtemp(prefix="eoh_repair_")
        try:
            # Patch main.go with current code
            try:
                patched = _replace_insertships_func(base_main_go, current_code)
            except ValueError as e:
                log.append({"attempt": attempt, "error": str(e), "stage": "patch"})
                return {
                    "final_code": current_code,
                    "compiled": False,
                    "repair_count": attempt,
                    "repair_log": log,
                }

            (Path(tmp) / "main.go").write_text(patched, encoding="utf-8")

            # Copy supporting files
            for fname in ["routing.go", "go.mod", "go.sum"]:
                src = os.path.join(project_root, fname)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(tmp, fname))

            # Try compile
            build_result = _try_compile(tmp)
            if build_result["ok"]:
                log.append({"attempt": attempt, "compiled": True, "stage": "build"})
                return {
                    "final_code": current_code,
                    "compiled": True,
                    "repair_count": attempt,
                    "repair_log": log,
                    "patched_main_go": patched,
                }

            # Compile failed - if max attempts reached, stop
            if attempt >= max_attempts:
                log.append({
                    "attempt": attempt,
                    "compiled": False,
                    "error": build_result.get("stderr", ""),
                    "stage": "build_max_attempts",
                })
                break

            # Send error to LLM for repair
            error_text = build_result.get("stderr", "") or build_result.get("stdout", "")
            repair_prompt = (
                f"The following Go code failed to compile:\n\n"
                f"```go\n{current_code}\n```\n\n"
                f"Compiler error:\n```\n{error_text[:2000]}\n```\n\n"
                f"Fix ONLY the compilation error. Return the complete fixed function."
            )

            fixed = _call_llm(repair_prompt, api_key, api_endpoint, model)
            if not fixed:
                log.append({
                    "attempt": attempt,
                    "compiled": False,
                    "error": "LLM repair call failed",
                    "stage": "llm_unavailable",
                })
                break

            extracted = _extract_code_from_response(fixed)
            if not extracted:
                log.append({
                    "attempt": attempt,
                    "compiled": False,
                    "error": "Could not extract code from LLM response",
                    "llm_response": fixed[:500],
                    "stage": "extract",
                })
                break

            log.append({
                "attempt": attempt,
                "compiled": False,
                "error": error_text[:500],
                "stage": "repaired",
            })
            current_code = extracted

        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return {
        "final_code": current_code,
        "compiled": False,
        "repair_count": max_attempts,
        "repair_log": log,
    }
