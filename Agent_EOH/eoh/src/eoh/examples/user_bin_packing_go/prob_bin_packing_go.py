"""
模块：prob_bin_packing_go
功能：为「在线装箱（online bin packing）」问题提供评测器，把 LLM 生成的 Go 语言启发式函数编译运行后打分。
职责：
    - 定位工程根目录及 Go 求解器源码、测试实例文件；
    - 将候选启发式（Go 的 ScoreBin 函数体）替换进求解器模板，编译并在测试实例上运行；
    - 解析运行输出中的 final cost，作为该候选启发式的适应度（越小越好）。
接口：
    - Evaluation 类：evaluate(code_string) -> float，评测一段包含 ScoreBin 函数的 Go 代码，返回代价。
输入：
    - LLM 产出的 Go 代码字符串（须包含 func ScoreBin(...) []float64）；
    - 工程内的 Go 求解器模板 bin_packing_solver.go 与测试实例 obp_5x60_c100.json；
    - 本机可用的 go 命令。
输出：
    - 适应度分数（float）；出错或超时时返回惩罚值 per_instance_penalty。
示例：
    >>> ev = Evaluation()
    >>> cost = ev.evaluate(go_code_with_score_bin)
"""

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


# 允许透传给子进程（go build / 运行求解器）的环境变量白名单。
# 只保留 Go 工具链和临时目录所需的变量，避免把无关或敏感的环境变量带入子进程。
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
    """从 start_dir 逐层向上查找工程根目录。

    以「同时存在 eoh_rag_workspace 与 eoh_rag 两个子目录」作为根目录的判定特征，
    最多向上回溯 max_depth 层。若都没命中，则退回到相对当前文件上溯若干层的默认路径。

    参数:
        start_dir: 起始查找目录（通常是本文件所在目录）。
        max_depth: 最大向上回溯层数。
    返回:
        工程根目录的绝对路径。
    """
    cur = os.path.abspath(start_dir)
    for _ in range(max_depth):
        # 命中判定特征即认为找到工程根目录。
        if os.path.isdir(os.path.join(cur, "eoh_rag_workspace")) and os.path.isdir(os.path.join(cur, "eoh_rag")):
            return cur
        parent = os.path.dirname(cur)
        # 已到达文件系统顶层，无法继续上溯。
        if parent == cur:
            break
        cur = parent
    # 兜底：按固定层级向上推算，保证始终返回一个路径。
    return os.path.abspath(os.path.join(start_dir, "..", "..", "..", "..", "..", ".."))


def _safe_subprocess_env() -> dict[str, str]:
    """构造传给子进程的最小环境变量集合。

    仅保留白名单 _SUBPROCESS_ENV_ALLOWLIST 中列出的变量，其余一律过滤掉。
    返回:
        过滤后的 {变量名: 变量值} 字典。
    """
    return {key: value for key, value in os.environ.items() if key in _SUBPROCESS_ENV_ALLOWLIST}


# 传给评测子进程的资源上限：限 CPU 秒与单文件大小，防止失控候选耗尽 CPU 或写满磁盘。
# 不限制地址空间/线程数，以免破坏内存与多线程密集的 Go 工具链。
_SUBPROCESS_MAX_FILE_BYTES = 1 << 30  # 单文件最大 1 GiB


def _posix_resource_limits(cpu_seconds: int):
    """返回在 POSIX 子进程 exec 前施加资源上限的回调；非 POSIX 平台返回 None。"""
    if os.name == "nt":
        return None
    import resource

    def _apply() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (_SUBPROCESS_MAX_FILE_BYTES, _SUBPROCESS_MAX_FILE_BYTES))

    return _apply


def _run_command(cmd: list[str], cwd: str, timeout_s: int) -> dict:
    """在指定工作目录下运行外部命令，并带超时保护。

    参数:
        cmd: 命令及其参数列表（如 ["go", "build", ...]）。
        cwd: 命令执行的工作目录。
        timeout_s: 超时秒数，超时则强制结束进程。
    返回:
        字典，含 returncode、stdout、stderr、timeout 四个键；
        超时时 returncode 为 None、timeout 为 True。
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_safe_subprocess_env(),
        preexec_fn=_posix_resource_limits(max(1, int(timeout_s)) + 30),  # POSIX 资源上限
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return {"returncode": proc.returncode, "stdout": stdout or "", "stderr": stderr or "", "timeout": False}
    except subprocess.TimeoutExpired:
        # 超时后杀掉进程并回收其残留输出，避免僵尸进程与管道阻塞。
        try:
            proc.kill()
        except OSError:
            pass
        stdout, stderr = proc.communicate()
        return {"returncode": None, "stdout": stdout or "", "stderr": stderr or "", "timeout": True}


def _parse_final_cost(output: str) -> float | None:
    """从求解器输出文本中解析最终代价（final cost）。

    匹配形如 "final cost 123.45" 的片段并转成浮点数。
    参数:
        output: 求解器的 stdout/stderr 合并文本。
    返回:
        解析到的代价（float）；未匹配到或转换失败时返回 None。
    """
    match = re.search(r"final cost\s+(-?\d+(?:\.\d+)?)", output)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _replace_score_bin(solver_path: str, method_go: str) -> None:
    """把求解器模板中的 ScoreBin 函数整体替换为候选实现。

    读取 solver_path 的 Go 源码，用正则定位原有 ScoreBin 函数并替换为 method_go 内容，
    再写回原文件。若源码中找不到 ScoreBin 函数则抛出 ValueError。

    参数:
        solver_path: Go 求解器源文件路径（临时副本）。
        method_go: 新的 ScoreBin 函数完整 Go 代码。
    """
    text = open(solver_path, "r", encoding="utf-8").read()
    # 匹配 func ScoreBin(item int, remaining []int, capacity int) []float64 { ... } 整个函数体。
    pat = r"func\s+ScoreBin\s*\(\s*item\s+int\s*,\s*remaining\s+\[\]int\s*,\s*capacity\s+int\s*\)\s*\[\]float64\s*\{[\s\S]*?\n\}"
    match = re.search(pat, text)
    if not match:
        raise ValueError("ScoreBin method not found in bin_packing_solver.go")
    # 用候选函数替换掉原函数所在区间，其余代码保持不变。
    patched = text[: match.start()] + method_go.strip() + "\n" + text[match.end() :]
    with open(solver_path, "w", encoding="utf-8") as f:
        f.write(patched)


class Evaluation:
    """在线装箱问题的评测器。

    负责把一段候选 Go 启发式（ScoreBin 函数）注入求解器模板、编译、在测试实例上运行，
    并解析出最终代价作为适应度分数。编译/运行失败或超时时返回惩罚值。

    关键参数:
        per_instance_penalty: 评测失败时返回的惩罚代价（越大越差）。
        build_timeout_s: go build 编译的超时秒数。
        run_timeout_s: 运行求解器可执行文件的超时秒数。
    """

    def __init__(
        self,
        per_instance_penalty: float = 1e9,
        build_timeout_s: int = 30,
        run_timeout_s: int = 10,
    ):
        self.prompts = GetPrompts()
        # 保存最近一次评测的错误信息与详细堆栈，便于外部调试排查。
        self._last_error = None
        self._last_traceback = None
        base_dir = os.path.dirname(__file__)
        self.project_root = _find_project_root(base_dir)
        # Go 求解器模板：候选 ScoreBin 会被注入到它的一个临时副本中再编译。
        self.solver_path = os.path.join(
            self.project_root,
            "eoh_rag_workspace",
            "problems",
            "bin_packing_online",
            "bin_packing_solver.go",
        )
        # 评测所用的固定测试实例（5 组 × 60 件物品，箱容 100）。
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
        # 显式校验：路径解析错误应立即报错，
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
        """在隔离的临时目录中编译并运行注入了候选 ScoreBin 的求解器。

        流程：拷贝求解器模板到临时目录 -> 替换 ScoreBin -> go build 编译 ->
        运行可执行文件并传入测试实例 -> 解析 final cost。无论成败都会清理临时目录。

        参数:
            method_go: 候选 ScoreBin 函数的 Go 代码。
        返回:
            解析到的代价（float）；编译失败、运行失败或未解析到代价时返回 None。
        """
        tmp = tempfile.mkdtemp(prefix="eoh_obp_go_")
        try:
            # 在临时目录内操作副本，避免污染工程内的求解器模板。
            shutil.copy2(self.solver_path, os.path.join(tmp, "bin_packing_solver.go"))
            solver = os.path.join(tmp, "bin_packing_solver.go")
            _replace_score_bin(solver, method_go)
            build = _run_command(["go", "build", "-o", "bin_packing_solver", "bin_packing_solver.go"], cwd=tmp, timeout_s=self.build_timeout_s)
            # 编译不通过（如候选代码语法错误）：记录错误并返回 None。
            if build["returncode"] != 0:
                self._last_error = "Go build failed"
                self._last_traceback = json.dumps(build, ensure_ascii=True)
                return None
            run = _run_command([os.path.join(tmp, "bin_packing_solver"), self.instance_path], cwd=tmp, timeout_s=self.run_timeout_s)
            # 合并标准输出与标准错误，便于统一提取 final cost。
            output = (run["stdout"] or "") + "\n" + (run["stderr"] or "")
            cost = _parse_final_cost(output)
            self._last_traceback = json.dumps({"run": run, "output": output}, ensure_ascii=True)
            # 运行返回非零或未解析到代价：视为失败。
            if run["returncode"] != 0 or cost is None:
                self._last_error = "Run failed"
                return None
            return float(cost)
        finally:
            # 无论成功与否都清理临时目录，避免磁盘残留。
            shutil.rmtree(tmp, ignore_errors=True)

    def evaluate(self, code_string):
        """评测一段候选 Go 代码并返回适应度。

        先做基本校验（必须包含 func ScoreBin），再交由 _build_and_run 编译运行。
        任何异常或失败都会被捕获并返回惩罚值，保证评测过程不会因单个坏样本而中断。

        参数:
            code_string: 待评测的 Go 代码字符串。
        返回:
            适应度分数（越小越好）；缺少 ScoreBin、编译/运行失败或发生异常时返回
            per_instance_penalty。
        """
        self._last_error = None
        self._last_traceback = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # 前置校验：候选代码必须定义 ScoreBin 函数，否则无从注入。
                if "func ScoreBin" not in code_string:
                    self._last_error = "Missing ScoreBin method definition"
                    return self.per_instance_penalty
                fitness = self._build_and_run(code_string)
                # 编译或运行失败时以惩罚值兜底。
                if fitness is None:
                    return self.per_instance_penalty
                return fitness
        except Exception as exc:
            # 捕获所有异常，记录后返回惩罚值，避免中断整体评测流程。
            self._last_error = f"General error: {exc}"
            self._last_traceback = traceback.format_exc()
            return self.per_instance_penalty
