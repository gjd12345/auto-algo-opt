"""
模块：solver_adapter（Go 求解器适配层）
功能：为 Python 侧提供一个稳定的接口，用来调用外部的 Go 动态调度/路由求解器。
职责：封装子进程调用、超时控制与输出解析，屏蔽底层命令行与二进制路径的细节；
      所有需要调用 Go 求解器的 Python 代码都应经由本模块，而不要自行拼命令或解析 Go 的内部输出。
接口：run_go_solver(input_path, output_path, *, solver_binary='', timeout_s=120, multi=1) -> dict
输入：输入实例 JSON 文件路径、结果输出路径、可选的求解器二进制路径等参数。
输出：统一结构的结果字典（含 ok / objective / runtime_ms / error 等键）。

说明：Go 求解器解决的是动态调度/路由问题，与本框架中面向组合优化（在线装箱、TSP、
CVRP、InsertShips 等）的启发式演化流程是两类不同的问题，二者互不相关、不应混淆。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


# 求解器二进制文件的默认相对路径；当调用方未显式指定时使用它。
DEFAULT_SOLVER_BINARY = "bin/agent-go-solver"


def run_go_solver(
    input_path: str | Path,
    output_path: str | Path,
    *,
    solver_binary: str = "",
    timeout_s: int = 120,
    multi: int = 1,
) -> dict[str, Any]:
    """在给定输入实例上运行 Go 调度求解器。

    参数
    ----------
    input_path : 输入 JSON 的路径（包含批次数据与求解参数）
    output_path : 结果 JSON 的写出路径
    solver_binary : 已编译求解器二进制的路径（默认取 bin/agent-go-solver）
    timeout_s : 最长执行时间（秒），超时则返回错误
    multi : 传给求解器的车辆数倍增参数

    返回
    -------
    统一结构的字典，包含 ok、objective、runtime_ms、error 等键：
    - ok 为 True 时携带求解器返回的结果字段；
    - ok 为 False 时通过 error 说明失败原因（非零退出码 / 超时 / 二进制缺失 / 输出非 JSON）。
    """
    # 优先使用调用方传入的二进制路径，否则回退到默认路径。
    binary = solver_binary or DEFAULT_SOLVER_BINARY
    if not Path(binary).exists():
        # 二进制不存在时，退回到用 `go run` 直接从源码运行求解器。
        cmd = ["go", "run", ".", str(input_path), str(multi)]
    else:
        # 二进制已存在，直接执行编译好的求解器。
        cmd = [str(binary), str(input_path), str(multi)]

    try:
        # 以子进程方式运行求解器，捕获标准输出/错误，并施加超时限制。
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            # 非零退出码视为求解失败，截取部分 stderr 便于排查。
            return {
                "ok": False,
                "error": f"solver exit code {proc.returncode}: {proc.stderr[:200]}",
                "objective": None,
                "runtime_ms": None,
            }

        # 解析输出：当前约定求解器把结果 JSON 打印到 stdout。
        try:
            # 解析成功则补上 ok 标记，原样返回求解器给出的结果字段。
            result = json.loads(proc.stdout)
            result["ok"] = True
            return result
        except json.JSONDecodeError:
            # stdout 不是合法 JSON，作为失败处理并保留部分原始输出供调试。
            return {
                "ok": False,
                "error": "solver stdout is not valid JSON (legacy format)",
                "raw_stdout": proc.stdout[:500],
                "objective": None,
                "runtime_ms": None,
            }

    except subprocess.TimeoutExpired:
        # 超过 timeout_s 未完成，返回超时错误。
        return {
            "ok": False,
            "error": f"solver timeout after {timeout_s}s",
            "objective": None,
            "runtime_ms": None,
        }
    except FileNotFoundError:
        # 命令无法定位（如二进制或 go 均不可用），返回文件缺失错误。
        return {
            "ok": False,
            "error": f"solver binary not found: {binary}",
            "objective": None,
            "runtime_ms": None,
        }
