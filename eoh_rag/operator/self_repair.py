"""
模块：self_repair（编译自修复循环）
功能：当 LLM 生成的 Go 代码 `go build` 失败时，把编译器的报错信息回传给 LLM 进行修复，
      并最多重试 3 次，从而把因编译失败/格式错误而无法评测的启发式函数救回来。
职责：管理「打补丁 → 编译 → 收集报错 → 请 LLM 修复」的整条重试逻辑，并在临时目录中隔离编译，
      同时负责从 LLM 回复中抽取纯代码、自动注入缺失的 import 与辅助类型。
接口：
    - repair_compile_errors(code, project_root, ...) -> dict：对外主入口，尝试编译并按需修复，
      返回 final_code / compiled / repair_count / repair_log 等字段。
    - 其余以下划线开头的函数为内部辅助（调用 LLM、抽取代码、编译、替换函数、注入 import 等）。
输入：待修复的 InsertShips Go 代码字符串、Go 工程根目录（含 main.go / routing.go / go.mod 等）、
      可选的 LLM API 参数（api_key / api_endpoint / model）。
输出：一个结果字典，包含最终代码、是否编译成功、修复次数以及每一步的日志。
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

# 单次修复流程中，允许请 LLM 修改并重新编译的最大次数（不含最初的那次编译）。
REPAIR_MAX_ATTEMPTS = 3

# 交给 LLM 的系统提示：约束它只修编译错误、不改算法逻辑，并严格给出 InsertShips 的函数签名、
# 可用的类型/方法/常量清单，避免它凭空造出不存在的 API。
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
    """调用 LLM 接口并返回回复文本。

    携带上面的 REPAIR_SYSTEM_PROMPT 作为系统消息、prompt 作为用户消息发起对话。
    未指定 model 时回退到默认模型；若底层调用抛出 RuntimeError，则返回 None 表示本次不可用。
    """
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
    """从 LLM 回复中抽取纯 Go 函数代码，兼容 markdown 代码围栏。

    先尝试剥掉 ```go ... ``` 之类的围栏；再从 `func InsertShips(...) Dispatch {` 处截断，
    丢弃函数之前的多余文字。若最终文本里不含 InsertShips 函数则返回 None。
    """
    code = response.strip()

    # 尝试从 markdown 代码块中提取内容
    m = re.search(r"```(?:go|golang)?\s*\n(.*?)```", code, re.DOTALL)
    if m:
        code = m.group(1).strip()

    # 确保代码从 func InsertShips 开始（截掉前面的说明性文字）
    func_match = re.search(
        r"func\s+InsertShips\s*\(.*?\)\s*Dispatch\s*\{",
        code, re.DOTALL
    )
    if func_match:
        code = code[func_match.start():]

    # 校验是否确实包含目标函数
    if "func InsertShips" not in code:
        return None

    return code.strip()


def _try_compile(project_dir: str) -> dict[str, Any]:
    """在指定工程目录里执行 `go build`，返回编译结果字典。

    结果含 ok（是否成功）、returncode、stdout、stderr。超时（120s）或找不到 go 编译器时，
    ok 为 False，并在 stderr 中给出对应说明。
    """
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
    """把 main.go 文本里已有的 InsertShips 函数整体替换成新版本 new_func。

    用正则匹配旧函数（含固定签名，一直到函数体收尾的 `\\n}`）并替换；找不到则抛 ValueError。
    替换后按需自动补齐 import：新代码用到 sort 就注入 "sort"，用到 SortManager 却未定义时注入其类型声明。
    """
    pat = r"func\s+InsertShips\s*\(\s*dispatch\s+Dispatch\s*,\s*oris\s*,\s*dess\s*\[\]Station\s*,\s*total_ship\s+int\s*\)\s*Dispatch\s*\{[\s\S]*?\n\}"
    matched = re.search(pat, main_go_text)
    if not matched:
        raise ValueError("InsertShips method not found in main.go")
    result = main_go_text[:matched.start()] + new_func.strip() + "\n" + main_go_text[matched.end():]

    # 根据新代码用到的符号自动注入依赖
    if "sort." in new_func:
        result = _ensure_go_import(result, "sort")
    if "SortManager" in new_func and "type SortManager struct" not in result:
        result = _inject_sort_manager(result)

    return result


def _ensure_go_import(go_text: str, pkg_name: str) -> str:
    """确保 Go 源码的 import 块中包含 pkg_name；若已存在或找不到 import 块则原样返回。

    只处理 `import ( ... )` 形式的分组导入，把包名追加到括号内。
    """
    import_block = re.search(r"import\s*\(([^)]*)\)", go_text, flags=re.DOTALL)
    if not import_block:
        return go_text
    body = import_block.group(1)
    if re.search(rf'^\s*"{re.escape(pkg_name)}"\s*$', body, flags=re.MULTILINE):
        return go_text
    updated_body = body.rstrip() + f'\n    "{pkg_name}"\n'
    return go_text[:import_block.start(1)] + updated_body + go_text[import_block.end(1):]


def _inject_sort_manager(go_text: str) -> str:
    """在 InsertShips 函数定义之前，注入一个实现了 sort.Interface 的 SortManager 辅助类型。

    LLM 生成的代码有时会引用 SortManager 却忘了定义它，这里补上其结构体与 Len/Swap/Less 方法，
    以便按 values 对下标 inds 排序。找不到插入锚点时原样返回。
    """
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
    尝试编译给定的 InsertShips 代码；若编译失败，就把编译器报错发给 LLM 修复，最多重试 max_attempts 次。

    关键参数：
        - code：待编译/修复的 InsertShips 函数源码。
        - project_root：Go 工程根目录，用于读取 main.go 及拷贝 routing.go/go.mod/go.sum 等依赖文件。
        - api_key / api_endpoint / model：LLM 调用参数，仅在需要修复时使用。
        - max_attempts：最多修复次数；实际循环会多跑一轮用于「最初的编译」。
        - base_main_go：可直接传入 main.go 文本；为 None 时自动从 project_root 读取。

    返回一个字典：
        - final_code：最终（可能已被修复）的 Go 代码。
        - compiled：是否最终编译成功。
        - repair_count：实际发生的修复尝试次数。
        - repair_log：每一步的日志列表（含 attempt、stage、error 等字段）。
        - patched_main_go：仅在编译成功时给出，为打好补丁的完整 main.go 文本。
    """
    log: list[dict[str, Any]] = []
    current_code = code.strip()

    # 未显式传入 main.go 文本时，从工程目录读取；找不到则直接判定失败返回
    if base_main_go is None:
        main_go_path = os.path.join(project_root, "go_solver", "main.go")
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

    for attempt in range(max_attempts + 1):  # +1 是为了第 0 次的初始编译
        # 每一轮都在独立临时目录中构建，彼此隔离
        tmp = tempfile.mkdtemp(prefix="eoh_repair_")
        try:
            # 把当前代码打进 main.go；替换失败（如签名对不上）则终止并返回
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

            # 拷贝编译所需的配套文件（存在才拷）
            for fname in ["routing.go", "go.mod", "go.sum"]:
                src = os.path.join(project_root, "go_solver", fname)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(tmp, fname))

            # 执行编译
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

            # 编译失败——若已用尽重试次数则停止
            if attempt >= max_attempts:
                log.append({
                    "attempt": attempt,
                    "compiled": False,
                    "error": build_result.get("stderr", ""),
                    "stage": "build_max_attempts",
                })
                break

            # 把编译器报错拼进提示词，请 LLM 修复（报错截断到 2000 字以内）
            error_text = build_result.get("stderr", "") or build_result.get("stdout", "")
            repair_prompt = (
                f"The following Go code failed to compile:\n\n"
                f"```go\n{current_code}\n```\n\n"
                f"Compiler error:\n```\n{error_text[:2000]}\n```\n\n"
                f"Fix ONLY the compilation error. Return the complete fixed function."
            )

            fixed = _call_llm(repair_prompt, api_key, api_endpoint, model)
            if not fixed:
                # LLM 不可用，无法继续修复
                log.append({
                    "attempt": attempt,
                    "compiled": False,
                    "error": "LLM repair call failed",
                    "stage": "llm_unavailable",
                })
                break

            extracted = _extract_code_from_response(fixed)
            if not extracted:
                # 回复里抽不出可用代码
                log.append({
                    "attempt": attempt,
                    "compiled": False,
                    "error": "Could not extract code from LLM response",
                    "llm_response": fixed[:500],
                    "stage": "extract",
                })
                break

            # 记下本轮修复，并用修复后的代码进入下一轮编译
            log.append({
                "attempt": attempt,
                "compiled": False,
                "error": error_text[:500],
                "stage": "repaired",
            })
            current_code = extracted

        finally:
            # 无论成败都清理本轮临时目录
            shutil.rmtree(tmp, ignore_errors=True)

    # 循环结束仍未成功：返回最后一版代码与完整日志
    return {
        "final_code": current_code,
        "compiled": False,
        "repair_count": max_attempts,
        "repair_log": log,
    }
