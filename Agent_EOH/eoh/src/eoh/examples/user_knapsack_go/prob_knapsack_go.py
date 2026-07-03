"""
模块：prob_knapsack_go（0/1 背包问题的 Go 求解器评测器）
功能：把大模型生成的 Go 语言 `SelectItems` 启发式函数编译并运行，返回该启发式在测试实例上的目标成本，作为进化优化的适应度。
职责：
    - 定位项目根目录与背包问题的 Go 求解器模板、测试数据文件；
    - 将生成的函数体替换进求解器模板，用受限环境变量安全地编译、运行 Go 程序；
    - 从程序输出里解析 "final cost" 数值，并在编译/运行失败时给出惩罚分。
接口：
    - class Evaluation：核心评测类，主入口方法 evaluate(code_string) -> float。
    - GetPrompts（来自 prompts_knapsack_go）：提供任务提示词。
输入：
    - code_string：一段包含 `func SelectItems(items []Item, capacity int) []bool` 的 Go 代码字符串；
    - 文件依赖：eoh_rag_workspace/problems/knapsack/ 下的 knapsack_solver.go 与 testdata/testdata_01.json；
    - 环境变量：仅透传 PATH、GOCACHE、GOPATH 等编译所需的白名单变量。
输出：
    - 浮点数适应度（成本）。数值越小代表启发式越好；失败时返回 per_instance_penalty（默认 1e9）。
示例：
    >>> ev = Evaluation()
    >>> ev.evaluate("func SelectItems(items []Item, capacity int) []bool { ... }")
    123.0
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

from prompts_knapsack_go import GetPrompts


# 允许透传给子进程（go build / 运行）的环境变量白名单。
# 只保留编译与缓存必需的变量，避免把无关或敏感的环境变量泄露给外部命令。
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
    """从 start_dir 向上逐级查找项目根目录。

    根目录的判定标准：该目录下同时存在 eoh_rag_workspace/ 和 eoh_rag/ 两个子目录。
    最多向上查找 max_depth 层；若没找到，则回退到相对当前文件的默认层级路径。

    参数：
        start_dir：起始搜索目录，通常传入本文件所在目录。
    返回：
        推断出的项目根目录绝对路径。
    """
    cur = os.path.abspath(start_dir)
    for _ in range(max_depth):
        # 命中根目录标志：两个特征子目录都存在
        if os.path.isdir(os.path.join(cur, "eoh_rag_workspace")) and os.path.isdir(os.path.join(cur, "eoh_rag")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:  # 已到达文件系统顶层，停止上溯
            break
        cur = parent
    # 兜底：按固定层级回退（本文件位于示例目录较深处）
    return os.path.abspath(os.path.join(start_dir, "..", "..", "..", "..", "..", ".."))


def _safe_subprocess_env() -> dict[str, str]:
    """构造传给子进程的最小环境变量集合，只保留白名单内的键。"""
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
    """在指定工作目录执行命令，捕获输出并处理超时。

    参数：
        cmd：命令及其参数列表；cwd：工作目录；timeout_s：超时秒数。
    返回：
        字典 {returncode, stdout, stderr, timeout}。超时时 returncode 为 None、timeout 为 True。
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_safe_subprocess_env(),  # 使用白名单环境变量，隔离外部环境
        preexec_fn=_posix_resource_limits(max(1, int(timeout_s)) + 30),  # POSIX 资源上限
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return {"returncode": proc.returncode, "stdout": stdout or "", "stderr": stderr or "", "timeout": False}
    except subprocess.TimeoutExpired:
        # 超时则强制结束进程，再收集残余输出，避免进程挂起
        try:
            proc.kill()
        except OSError:
            pass
        stdout, stderr = proc.communicate()
        return {"returncode": None, "stdout": stdout or "", "stderr": stderr or "", "timeout": True}


def _parse_final_cost(output: str) -> float | None:
    """从程序输出文本中解析形如 "final cost 123.0" 的最终成本数值。

    返回解析到的浮点数；若未匹配或转换失败，返回 None。
    """
    # 匹配 "final cost" 后跟随的整数或小数（允许负号）
    match = re.search(r"final cost\s+(-?\d+(?:\.\d+)?)", output)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _replace_select_items(solver_path: str, method_go: str) -> None:
    """把 Go 求解器文件里现有的 SelectItems 函数整体替换为新的实现。

    参数：
        solver_path：knapsack_solver.go 的路径；
        method_go：新的 SelectItems 函数体（完整的 func 定义）。
    异常：
        若在源文件中找不到 SelectItems 定义，抛出 ValueError。
    """
    text = open(solver_path, "r", encoding="utf-8").read()
    # 正则匹配从 `func SelectItems(...)` 到与之配对的收尾大括号（含）为止的整段函数
    pat = r"func\s+SelectItems\s*\(\s*items\s+\[\]Item\s*,\s*capacity\s+int\s*\)\s*\[\]bool\s*\{[\s\S]*?\n\}"
    match = re.search(pat, text)
    if not match:
        raise ValueError("SelectItems method not found in knapsack_solver.go")
    # 用新函数体替换匹配区间，保留其前后的其余代码
    patched = text[: match.start()] + method_go.strip() + "\n" + text[match.end() :]
    with open(solver_path, "w", encoding="utf-8") as f:
        f.write(patched)


class Evaluation:
    """0/1 背包问题的适应度评测器。

    负责把生成的 Go `SelectItems` 函数编译、运行在固定测试实例上，并把解析出的
    最终成本作为适应度返回。编译或运行失败时返回统一的惩罚分。
    """

    def __init__(
        self,
        per_instance_penalty: float = 1e9,
        build_timeout_s: int = 30,
        run_timeout_s: int = 10,
    ):
        """初始化评测器并解析各类路径。

        参数：
            per_instance_penalty：编译/运行失败时返回的惩罚成本（越大越差）。
            build_timeout_s：go build 编译超时（秒）。
            run_timeout_s：可执行文件运行超时（秒）。
        异常：
            若求解器模板或测试数据文件不存在，抛出 FileNotFoundError。
        """
        self.prompts = GetPrompts()
        self._last_error = None       # 记录最近一次失败原因，便于外部排查
        self._last_traceback = None   # 记录最近一次失败的详细信息
        base_dir = os.path.dirname(__file__)
        self.project_root = _find_project_root(base_dir)
        # Go 求解器模板：其中的 SelectItems 会被生成代码替换
        self.solver_path = os.path.join(self.project_root, "eoh_rag_workspace", "problems", "knapsack", "knapsack_solver.go")
        # 固定测试实例（背包物品与容量）
        self.instance_path = os.path.join(
            self.project_root,
            "eoh_rag_workspace",
            "problems",
            "knapsack",
            "testdata",
            "testdata_01.json",
        )
        self.per_instance_penalty = float(per_instance_penalty)
        self.build_timeout_s = int(build_timeout_s)
        self.run_timeout_s = int(run_timeout_s)
        # 显式校验路径：若关键文件缺失（例如项目根目录解析有误），
        # 应在此立即报错，而不是等到 evaluate() 里被静默吞成 per_instance_penalty(1e9)。
        if not os.path.exists(self.solver_path):
            raise FileNotFoundError(
                f"Solver not found: {self.solver_path} (project_root={self.project_root})"
            )
        if not os.path.exists(self.instance_path):
            raise FileNotFoundError(
                f"Instance not found: {self.instance_path} (project_root={self.project_root})"
            )

    def _build_and_run(self, method_go: str) -> float | None:
        """在临时目录里编译并运行带有给定 SelectItems 实现的求解器。

        流程：拷贝模板到临时目录 → 替换 SelectItems → go build → 运行 → 解析成本。
        参数：
            method_go：待评测的 Go 函数体。
        返回：
            成功时返回解析出的成本浮点数；编译失败、运行失败或无法解析成本时返回 None。
            无论成功与否，临时目录都会被清理。
        """
        tmp = tempfile.mkdtemp(prefix="eoh_knapsack_go_")
        try:
            # 把模板复制到隔离的临时目录，避免污染原始文件
            shutil.copy2(self.solver_path, os.path.join(tmp, "knapsack_solver.go"))
            solver = os.path.join(tmp, "knapsack_solver.go")
            _replace_select_items(solver, method_go)
            # 第一步：编译 Go 源码为可执行文件
            build = _run_command(
                ["go", "build", "-o", "knapsack_solver", "knapsack_solver.go"],
                cwd=tmp,
                timeout_s=self.build_timeout_s,
            )
            if build["returncode"] != 0:  # 编译不通过
                self._last_error = "Go build failed"
                self._last_traceback = json.dumps(build, ensure_ascii=True)
                return None
            # 第二步：运行可执行文件，传入测试实例路径
            run = _run_command(
                [os.path.join(tmp, "knapsack_solver"), self.instance_path],
                cwd=tmp,
                timeout_s=self.run_timeout_s,
            )
            # 合并标准输出与错误输出后再解析成本
            output = (run["stdout"] or "") + "\n" + (run["stderr"] or "")
            cost = _parse_final_cost(output)
            self._last_traceback = json.dumps({"run": run, "output": output}, ensure_ascii=True)
            if run["returncode"] != 0 or cost is None:  # 运行失败或未解析到成本
                self._last_error = "Run failed"
                return None
            return float(cost)
        finally:
            # 始终清理临时目录，忽略清理过程中的错误
            shutil.rmtree(tmp, ignore_errors=True)

    def evaluate(self, code_string):
        """评测入口：给定一段 Go 代码字符串，返回其适应度（成本）。

        参数：
            code_string：包含 `func SelectItems(...)` 定义的 Go 代码字符串。
        返回：
            成功时返回运行得到的成本；缺少函数定义、编译/运行失败或发生异常时，
            统一返回 per_instance_penalty。
        """
        self._last_error = None
        self._last_traceback = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # 前置检查：代码里必须包含目标函数定义
                if "func SelectItems" not in code_string:
                    self._last_error = "Missing SelectItems method definition"
                    return self.per_instance_penalty
                fitness = self._build_and_run(code_string)
                if fitness is None:  # 编译或运行失败，返回惩罚分
                    return self.per_instance_penalty
                return fitness
        except Exception as exc:
            # 兜底：任何未预期异常都转成惩罚分，保证评测流程不中断
            self._last_error = f"General error: {exc}"
            self._last_traceback = traceback.format_exc()
            return self.per_instance_penalty
