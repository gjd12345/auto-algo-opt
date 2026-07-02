from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import traceback
import warnings

from prompts_bin_packing_go import GetPrompts


_SUBPROCESS_ENV_ALLOWLIST = {
    "PATH",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "GOCACHE",
    "GOPATH",
    "GOMODCACHE",
    "LOCALAPPDATA",
    "USERPROFILE",
}


def _find_project_root(start_dir: str, max_depth: int = 12) -> str:
    cur = os.path.abspath(start_dir)
    for _ in range(max_depth):
        if os.path.isdir(os.path.join(cur, "eoh_rag_workspace")) and os.path.isdir(os.path.join(cur, "eoh_rag")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(os.path.join(start_dir, "..", "..", "..", "..", "..", ".."))


def _safe_subprocess_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key in _SUBPROCESS_ENV_ALLOWLIST}


def _run_command(cmd: list[str], cwd: str, timeout_s: int) -> dict:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_safe_subprocess_env(),
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return {"returncode": proc.returncode, "stdout": stdout or "", "stderr": stderr or "", "timeout": False}
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass
        stdout, stderr = proc.communicate()
        return {"returncode": None, "stdout": stdout or "", "stderr": stderr or "", "timeout": True}


def _parse_final_cost(output: str) -> float | None:
    match = re.search(r"final cost\s+(-?\d+(?:\.\d+)?)", output)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _replace_score_bin(solver_path: str, method_go: str) -> None:
    text = open(solver_path, "r", encoding="utf-8").read()
    pat = r"func\s+ScoreBin\s*\(\s*item\s+int\s*,\s*remaining\s+\[\]int\s*,\s*capacity\s+int\s*\)\s*\[\]float64\s*\{[\s\S]*?\n\}"
    match = re.search(pat, text)
    if not match:
        raise ValueError("ScoreBin method not found in bin_packing_solver.go")
    patched = text[: match.start()] + method_go.strip() + "\n" + text[match.end() :]
    with open(solver_path, "w", encoding="utf-8") as f:
        f.write(patched)


class Evaluation:
    def __init__(
        self,
        per_instance_penalty: float = 1e9,
        build_timeout_s: int = 30,
        run_timeout_s: int = 10,
    ):
        self.prompts = GetPrompts()
        self._last_error = None
        self._last_traceback = None
        base_dir = os.path.dirname(__file__)
        self.project_root = _find_project_root(base_dir)
        self.solver_path = os.path.join(
            self.project_root,
            "eoh_rag_workspace",
            "problems",
            "bin_packing_online",
            "bin_packing_solver.go",
        )
        self.instance_path = os.path.join(
            self.project_root,
            "eoh_rag_workspace",
            "problems",
            "bin_packing_online",
            "testdata",
            "obp_5x60_c100.json",
        )
        self.per_instance_penalty = float(per_instance_penalty)
        self.build_timeout_s = int(build_timeout_s)
        self.run_timeout_s = int(run_timeout_s)
        # 显式校验：路径解析错误（如子目录单独拷贝、未来 rename）应立即报错，
        # 而非在 evaluate() 里被静默吞成 per_instance_penalty(1e9)。
        if not os.path.exists(self.solver_path):
            raise FileNotFoundError(
                f"Solver not found: {self.solver_path} (project_root={self.project_root})"
            )
        if not os.path.exists(self.instance_path):
            raise FileNotFoundError(
                f"Instance not found: {self.instance_path} (project_root={self.project_root})"
            )

    def _build_and_run(self, method_go: str) -> float | None:
        tmp = tempfile.mkdtemp(prefix="eoh_obp_go_")
        try:
            shutil.copy2(self.solver_path, os.path.join(tmp, "bin_packing_solver.go"))
            solver = os.path.join(tmp, "bin_packing_solver.go")
            _replace_score_bin(solver, method_go)
            build = _run_command(["go", "build", "-o", "bin_packing_solver", "bin_packing_solver.go"], cwd=tmp, timeout_s=self.build_timeout_s)
            if build["returncode"] != 0:
                self._last_error = "Go build failed"
                self._last_traceback = json.dumps(build, ensure_ascii=True)
                return None
            run = _run_command([os.path.join(tmp, "bin_packing_solver"), self.instance_path], cwd=tmp, timeout_s=self.run_timeout_s)
            output = (run["stdout"] or "") + "\n" + (run["stderr"] or "")
            cost = _parse_final_cost(output)
            self._last_traceback = json.dumps({"run": run, "output": output}, ensure_ascii=True)
            if run["returncode"] != 0 or cost is None:
                self._last_error = "Run failed"
                return None
            return float(cost)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def evaluate(self, code_string):
        self._last_error = None
        self._last_traceback = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if "func ScoreBin" not in code_string:
                    self._last_error = "Missing ScoreBin method definition"
                    return self.per_instance_penalty
                fitness = self._build_and_run(code_string)
                if fitness is None:
                    return self.per_instance_penalty
                return fitness
        except Exception as exc:
            self._last_error = f"General error: {exc}"
            self._last_traceback = traceback.format_exc()
            return self.per_instance_penalty
