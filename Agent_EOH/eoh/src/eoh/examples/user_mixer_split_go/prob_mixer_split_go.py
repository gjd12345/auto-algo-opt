"""
模块：prob_mixer_split_go
功能：评测 LLM 生成的 Go 语言 SplitOrders 启发式函数在“搅拌车订单拆分”优化问题上的表现。
职责：
    - 定位工程根目录、Go 求解器源码与测试算例；
    - 把候选启发式代码替换进 Go 求解器，编译并运行；
    - 从运行输出中解析目标代价（final cost）作为适应度。
接口：
    - Evaluation：评测器类；核心方法 evaluate(code_string) -> float，返回代价（越小越好）；
      失败时返回惩罚值 per_instance_penalty。
输入：
    - 依赖工程内 eoh_rag_workspace/problems/mixer_split 下的 Go 求解器与 testdata 算例；
    - 需要本机可用的 Go 工具链（命令 go build / 运行可执行文件）；
    - code_string：待评测的 Go 版 SplitOrders 函数完整定义。
输出：
    - evaluate 返回一个浮点数适应度（求解代价）；失败返回惩罚值。
示例：
    >>> ev = Evaluation()
    >>> ev.evaluate("func SplitOrders(orders []Order, vehicles []Vehicle, workHours float64) []SubOrder { ... }")
    123.45
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

from prompts_mixer_split_go import GetPrompts


# 子进程环境变量白名单：编译/运行 Go 时只透传这些必要的键，
# 避免把无关或敏感的环境变量泄露给外部进程。
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
    """从 start_dir 逐级向上查找工程根目录。

    以同时存在 eoh_rag_workspace 与 eoh_rag 两个目录作为根目录的判定标志；
    最多向上 max_depth 层。若始终未命中，则回退为相对 start_dir 上溯若干层的路径。
    返回：工程根目录的绝对路径。
    """
    cur = os.path.abspath(start_dir)
    for _ in range(max_depth):
        # 命中判定：当前目录下同时含有这两个标志目录即认为是工程根
        if os.path.isdir(os.path.join(cur, "eoh_rag_workspace")) and os.path.isdir(os.path.join(cur, "eoh_rag")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:  # 已到达文件系统根，无法再向上
            break
        cur = parent
    # 兜底：按固定层数上溯，保证总能返回一个绝对路径
    return os.path.abspath(os.path.join(start_dir, "..", "..", "..", "..", "..", ".."))


def _safe_subprocess_env() -> dict[str, str]:
    """按白名单过滤当前环境变量，得到一份供子进程使用的最小环境。"""
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
    """在指定工作目录下运行外部命令，带超时控制。

    参数：
        cmd：命令及其参数列表；cwd：工作目录；timeout_s：超时秒数。
    返回：
        dict，含 returncode / stdout / stderr / timeout 四个字段；
        超时时会杀掉进程，returncode 记为 None、timeout 记为 True。
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_safe_subprocess_env(),  # 仅透传白名单内的环境变量
        preexec_fn=_posix_resource_limits(max(1, int(timeout_s)) + 30),  # POSIX 资源上限
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        return {"returncode": proc.returncode, "stdout": stdout or "", "stderr": stderr or "", "timeout": False}
    except subprocess.TimeoutExpired:
        # 超时：尝试终止进程并回收剩余输出
        try:
            proc.kill()
        except OSError:
            pass
        stdout, stderr = proc.communicate()
        return {"returncode": None, "stdout": stdout or "", "stderr": stderr or "", "timeout": True}


def _parse_final_cost(output: str) -> float | None:
    """从求解器输出文本中解析形如 “final cost <数值>” 的目标代价。

    命中则返回该浮点数；未命中或转换失败返回 None。
    """
    match = re.search(r"final cost\s+(-?\d+(?:\.\d+)?)", output)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _replace_split_orders(solver_path: str, method_go: str) -> None:
    """把 Go 求解器源码中的 SplitOrders 函数整体替换为 method_go。

    参数：
        solver_path：mixer_split_solver.go 的路径；
        method_go：待写入的完整 SplitOrders 函数定义（Go 代码字符串）。
    找不到原函数定义时抛出 ValueError。
    """
    text = open(solver_path, "r", encoding="utf-8").read()
    # 正则匹配 SplitOrders 的完整签名及函数体（从 func 起到与之匹配的结尾 } 为止）
    pat = (
        r"func\s+SplitOrders\s*\(\s*orders\s+\[\]Order\s*,\s*vehicles\s+\[\]Vehicle\s*,"
        r"\s*workHours\s+float64\s*\)\s*\[\]SubOrder\s*\{[\s\S]*?\n\}"
    )
    match = re.search(pat, text)
    if not match:
        raise ValueError("SplitOrders method not found in mixer_split_solver.go")
    # 用新函数体替换匹配区间，保留前后其余源码不变
    patched = text[: match.start()] + method_go.strip() + "\n" + text[match.end() :]
    with open(solver_path, "w", encoding="utf-8") as f:
        f.write(patched)


class Evaluation:
    """搅拌车订单拆分问题的评测器。

    将候选的 Go 版 SplitOrders 启发式代码注入求解器，编译并在测试算例上运行，
    以解析出的目标代价作为适应度（越小越优）。构造时即校验求解器与算例文件是否存在。
    """

    def __init__(
        self,
        per_instance_penalty: float = 1e9,
        build_timeout_s: int = 30,
        run_timeout_s: int = 10,
    ):
        """初始化评测器并定位所需资源。

        参数：
            per_instance_penalty：评测失败（缺函数/编译失败/运行失败等）时返回的惩罚值；
            build_timeout_s：Go 编译超时秒数；
            run_timeout_s：求解器运行超时秒数。
        """
        self.prompts = GetPrompts()
        self._last_error = None  # 最近一次失败的简要原因
        self._last_traceback = None  # 最近一次失败的详细信息（编译/运行输出）
        base_dir = os.path.dirname(__file__)
        self.project_root = _find_project_root(base_dir)
        # Go 求解器源码路径
        self.solver_path = os.path.join(
            self.project_root,
            "eoh_rag_workspace",
            "problems",
            "mixer_split",
            "mixer_split_solver.go",
        )
        # 测试算例路径
        self.instance_path = os.path.join(
            self.project_root,
            "eoh_rag_workspace",
            "problems",
            "mixer_split",
            "testdata",
            "testdata_01.json",
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
        """在临时目录中编译并运行注入了 method_go 的求解器，返回目标代价。

        流程：拷贝求解器源码到临时目录 → 替换其中的 SplitOrders → go build 编译 →
        运行可执行文件传入测试算例 → 解析 final cost。
        任一环节失败（编译失败/运行非零退出/无法解析代价）返回 None，
        失败原因记录在 self._last_error 与 self._last_traceback 中。
        """
        tmp = tempfile.mkdtemp(prefix="eoh_mixer_split_go_")
        try:
            # 拷贝一份源码到临时目录，避免污染原始求解器文件
            shutil.copy2(self.solver_path, os.path.join(tmp, "mixer_split_solver.go"))
            solver = os.path.join(tmp, "mixer_split_solver.go")
            _replace_split_orders(solver, method_go)  # 注入候选启发式
            # 编译 Go 源码
            build = _run_command(
                ["go", "build", "-o", "mixer_split_solver", "mixer_split_solver.go"],
                cwd=tmp,
                timeout_s=self.build_timeout_s,
            )
            if build["returncode"] != 0:  # 编译失败
                self._last_error = "Go build failed"
                self._last_traceback = json.dumps(build, ensure_ascii=True)
                return None
            # 运行可执行文件，传入测试算例路径
            run = _run_command(
                [os.path.join(tmp, "mixer_split_solver"), self.instance_path],
                cwd=tmp,
                timeout_s=self.run_timeout_s,
            )
            # 合并标准输出与标准错误后解析代价
            output = (run["stdout"] or "") + "\n" + (run["stderr"] or "")
            cost = _parse_final_cost(output)
            self._last_traceback = json.dumps({"run": run, "output": output}, ensure_ascii=True)
            if run["returncode"] != 0 or cost is None:  # 运行失败或无法解析代价
                self._last_error = "Run failed"
                return None
            return float(cost)
        finally:
            # 无论成功与否都清理临时目录
            shutil.rmtree(tmp, ignore_errors=True)

    def evaluate(self, code_string):
        """评测入口：对候选 Go 代码打分，返回适应度（越小越优）。

        参数：
            code_string：包含完整 SplitOrders 函数定义的 Go 代码字符串。
        返回：
            成功时返回求解代价（float）；缺少函数定义、编译/运行失败或发生异常时，
            返回惩罚值 self.per_instance_penalty。
        """
        self._last_error = None
        self._last_traceback = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # 前置检查：代码里必须包含 SplitOrders 函数定义
                if "func SplitOrders" not in code_string:
                    self._last_error = "Missing SplitOrders method definition"
                    return self.per_instance_penalty
                fitness = self._build_and_run(code_string)
                if fitness is None:  # 编译或运行失败
                    return self.per_instance_penalty
                return fitness
        except Exception as exc:
            # 兜底：任何未预期异常都转为惩罚值，保证评测流程不中断
            self._last_error = f"General error: {exc}"
            self._last_traceback = traceback.format_exc()
            return self.per_instance_penalty
