"""
模块：problem_registry（优化问题注册表与冒烟评测）
功能：登记本框架支持的组合优化问题，并对每个问题运行一次“只评测、不调用大模型”的冒烟测试，收集其种子启发式的目标值。
职责：
  - 维护问题元信息（示例目录、指标名、优化方向、目标函数名）。
  - 调用各问题示例自带的 runEval.py 子进程，采集标准输出。
  - 用正则解析不同问题的评测输出，算出统一的目标值（objective）。
  - 汇总为 JSON 与 Markdown 报告落盘并打印。
接口：
  - OfficialProblemSpec：问题规格数据类（frozen dataclass）。
  - PROBLEMS：问题名 -> 规格 的字典；PARSERS：问题名 -> 输出解析函数 的字典。
  - run_problem(official_root, python_exe, problem, timeout_s) -> dict：跑单个问题并返回结构化结果。
  - run_smoke(args) -> dict：批量跑多个问题并写出报告。
  - main()：命令行入口，解析参数后调用 run_smoke。
输入：
  - 命令行参数 / 环境变量 EOH_OFFICIAL_ROOT（示例代码根目录）、EOH_OFFICIAL_PYTHON（运行评测所用的 Python 解释器）。
  - 每个问题目录下的 examples/<问题>/evaluation/runEval.py 与 heuristic.py。
输出：
  - 在 --output-dir 下生成 official_eoh_smoke_summary.json 与 .md 两份汇总报告，并把 JSON 打印到标准输出。
示例：
  python problem_registry.py --problem bp_online --timeout-s 60
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OfficialProblemSpec:
    """单个优化问题的规格描述（不可变）。

    字段说明：
      - name：问题标识名（如 bp_online）。
      - example_dir：示例代码所在的子目录名。
      - metric_name：评测指标名称（如平均距离、平均超载百分比）。
      - objective_direction："minimize" 或 "maximize"，表示目标越小越好还是越大越好。
      - target_function：该问题待进化启发式的核心函数名（如 score、select_next_node）。
    """

    name: str
    example_dir: str
    metric_name: str
    objective_direction: str
    target_function: str


# 已支持的优化问题注册表：问题名 -> 规格。
# bp_online（在线装箱）、tsp_construct（TSP 构造式求解）、cvrp_construct（CVRP 构造式求解）。
PROBLEMS: dict[str, OfficialProblemSpec] = {
    "bp_online": OfficialProblemSpec(
        name="bp_online",
        example_dir="bp_online",
        metric_name="avg_excess_percent",
        objective_direction="minimize",
        target_function="score",
    ),
    "tsp_construct": OfficialProblemSpec(
        name="tsp_construct",
        example_dir="tsp_construct",
        metric_name="avg_distance",
        objective_direction="minimize",
        target_function="select_next_node",
    ),
    "cvrp_construct": OfficialProblemSpec(
        name="cvrp_construct",
        example_dir="cvrp_construct",
        metric_name="avg_distance",
        objective_direction="minimize",
        target_function="select_next_node",
    ),
}

# 单次进化运行器还支持只在框架内使用的控制器问题。它没有传统 examples/evaluation
# 冒烟入口，因此不放进 PROBLEMS，避免默认问题冒烟把它误当成构造式基准。
RUNNABLE_PROBLEMS = tuple(PROBLEMS) + ("tsp_search_controller",)


def _safe_float(value: str) -> float | None:
    """把字符串安全转成浮点数；转换失败时返回 None，避免解析异常中断整个流程。"""
    try:
        return float(value)
    except Exception:
        return None


def parse_bp_online_output(output: str) -> dict[str, Any]:
    """解析在线装箱（bp_online）评测输出。

    逐行匹配形如 "数据集, 容量, Excess: 3.14%" 的记录，提取每行的超载百分比，
    最后取所有有效行的平均值作为目标值（objective，越小越好）。
    返回：{"metric_name", "objective", "rows"}。
    """
    rows = []
    for line in output.splitlines():
        # 匹配：数据集名, 容量整数, Excess: 百分数%
        match = re.search(r"^([^,]+),\s*(\d+),\s*Excess:\s*([-+]?\d+(?:\.\d+)?)%", line.strip())
        if not match:
            continue
        rows.append(
            {
                "dataset": match.group(1),
                "capacity": int(match.group(2)),
                "excess_percent": _safe_float(match.group(3)),
            }
        )
    # 只对成功解析出的数值求平均
    values = [row["excess_percent"] for row in rows if row["excess_percent"] is not None]
    return {
        "metric_name": "avg_excess_percent",
        "objective": sum(values) / len(values) if values else None,
        "rows": rows,
    }


def parse_tsp_construct_output(output: str) -> dict[str, Any]:
    """解析 TSP 构造式求解（tsp_construct）评测输出。

    逐行匹配形如 "Average dis on N instance with size M is: 12.3" 的记录，
    提取每个规模的平均距离，取平均作为目标值（objective，越小越好）。
    返回：{"metric_name", "objective", "rows"}。
    """
    rows = []
    for line in output.splitlines():
        match = re.search(
            r"Average dis on\s+(\d+)\s+instance with size\s+(\d+)\s+is:\s*([-+]?\d+(?:\.\d+)?)",
            line.strip(),
        )
        if not match:
            continue
        rows.append(
            {
                "instances": int(match.group(1)),
                "size": int(match.group(2)),
                "avg_distance": _safe_float(match.group(3)),
            }
        )
    values = [row["avg_distance"] for row in rows if row["avg_distance"] is not None]
    return {
        "metric_name": "avg_distance",
        "objective": sum(values) / len(values) if values else None,
        "rows": rows,
    }


def parse_cvrp_construct_output(output: str) -> dict[str, Any]:
    """解析 CVRP 构造式求解（cvrp_construct）评测输出。

    在整段输出中匹配 "Avg distance on N instances, M customers: 45.6"，
    直接取其平均距离作为目标值（objective，越小越好）。
    返回：{"metric_name", "objective", "rows"}。
    """
    # 该问题只输出一行汇总，因此对整段文本做一次匹配即可
    match = re.search(
        r"Avg distance on\s+(\d+)\s+instances,\s+(\d+)\s+customers:\s*([-+]?\d+(?:\.\d+)?)",
        output,
    )
    rows = []
    if match:
        rows.append(
            {
                "instances": int(match.group(1)),
                "customers": int(match.group(2)),
                "avg_distance": _safe_float(match.group(3)),
            }
        )
    return {
        "metric_name": "avg_distance",
        "objective": rows[0]["avg_distance"] if rows else None,
        "rows": rows,
    }


# 问题名 -> 对应的输出解析函数，run_problem 会据此选择解析器。
PARSERS = {
    "bp_online": parse_bp_online_output,
    "tsp_construct": parse_tsp_construct_output,
    "cvrp_construct": parse_cvrp_construct_output,
}


def _read_heuristic(example_root: Path) -> str | None:
    """读取问题示例目录下的种子启发式源码（evaluation/heuristic.py）；文件不存在则返回 None。"""
    heuristic = example_root / "evaluation" / "heuristic.py"
    if not heuristic.exists():
        return None
    return heuristic.read_text(encoding="utf-8")


def run_problem(official_root: Path, python_exe: Path, problem: str, timeout_s: int) -> dict[str, Any]:
    """对单个问题执行一次评测冒烟测试并返回结构化结果。

    流程：定位问题的 evaluation 目录 -> 在该目录内以子进程方式运行 runEval.py ->
    采集标准输出/错误 -> 用对应解析器算出目标值。全程不调用大模型。

    参数：
      - official_root：示例代码根目录（其下有 examples/<问题>/evaluation）。
      - python_exe：运行 runEval.py 所用的 Python 解释器路径。
      - problem：问题名，必须是 PROBLEMS 中的键。
      - timeout_s：子进程超时秒数。

    返回：包含问题元信息、命令、stdout/stderr、runtime、目标值等的字典；
    其中 ok 表示是否成功解析出目标值，failure_reason 记录失败原因（None 表示成功）。
    """
    spec = PROBLEMS[problem]
    example_root = official_root / "examples" / spec.example_dir
    eval_root = example_root / "evaluation"
    started = time.time()
    # 先填好所有元信息与默认（失败）状态，后续按执行情况逐步更新
    result: dict[str, Any] = {
        "problem": problem,
        "official_problem_name": spec.name,
        "target_function": spec.target_function,
        "objective_direction": spec.objective_direction,
        "metric_name": spec.metric_name,
        "example_root": str(example_root),
        "evaluation_root": str(eval_root),
        "command": [str(python_exe), "runEval.py"],
        "ok": False,
        "failure_reason": None,
        "runtime_seconds": None,
        "stdout": "",
        "stderr": "",
        "heuristic_code": _read_heuristic(example_root),
    }
    # evaluation 目录缺失则直接判失败，不再尝试运行
    if not eval_root.exists():
        result["failure_reason"] = "missing_evaluation_dir"
        return result
    try:
        # 在 evaluation 目录内运行 runEval.py，捕获输出，超时则抛异常
        proc = subprocess.run(
            [str(python_exe), "runEval.py"],
            cwd=str(eval_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # 超时：保留已产生的部分输出并记录耗时后返回
        result["failure_reason"] = "timeout"
        result["stdout"] = exc.stdout or ""
        result["stderr"] = exc.stderr or ""
        result["runtime_seconds"] = round(time.time() - started, 3)
        return result

    result["stdout"] = proc.stdout
    result["stderr"] = proc.stderr
    result["return_code"] = proc.returncode
    result["runtime_seconds"] = round(time.time() - started, 3)
    # 非零退出码视为运行失败
    if proc.returncode != 0:
        result["failure_reason"] = f"return_code_{proc.returncode}"
        return result
    # 用对应问题的解析器提取目标值，并合并进结果
    parsed = PARSERS[problem](proc.stdout)
    result.update(parsed)
    # 能解析出 objective 才算成功；否则标记为输出无法解析
    result["ok"] = parsed.get("objective") is not None
    if not result["ok"]:
        result["failure_reason"] = "unparsed_output"
    return result


def _markdown_table(results: list[dict[str, Any]]) -> str:
    """把多个问题的结果渲染成一张 Markdown 表格（表头 + 每问题一行）。"""
    lines = [
        "| Problem | OK | Metric | Objective | Target | Runtime | Failure |",
        "|---|---:|---|---:|---|---:|---|",
    ]
    for item in results:
        objective = item.get("objective")
        # 数值目标格式化为 6 位小数，缺失则用 "-" 占位
        objective_text = f"{objective:.6f}" if isinstance(objective, (float, int)) else "-"
        lines.append(
            "| {problem} | {ok} | {metric} | {objective} | {target} | {runtime} | {failure} |".format(
                problem=item.get("problem"),
                ok="yes" if item.get("ok") else "no",
                metric=item.get("metric_name"),
                objective=objective_text,
                target=item.get("target_function"),
                runtime=item.get("runtime_seconds"),
                failure=item.get("failure_reason") or "-",
            )
        )
    return "\n".join(lines)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    """把汇总结果写成一份 Markdown 报告：头部元信息 + 结果表格 + 各问题种子启发式源码。"""
    lines = [
        "# 官方 EoH Benchmark Seed/Evaluation Smoke",
        "",
        "本文记录官方 EoH examples 的 evaluation-only smoke 结果，不包含 LLM 调用。",
        "",
        f"- official_root: `{payload['official_root']}`",
        f"- python: `{payload['python_exe']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
        _markdown_table(payload["results"]),
        "",
        "## Official Seed Heuristic Code",
        "",
    ]
    for item in payload["results"]:
        lines.extend(
            [
                f"### {item['problem']}",
                "",
                "```python",
                (item.get("heuristic_code") or "").strip(),
                "```",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    """按命令行参数批量运行冒烟测试，落盘 JSON/Markdown 报告并返回汇总数据。

    未指定 --problem 时默认跑注册表里的全部问题；每个问题各跑一次 run_problem。
    产物写入 --output-dir，同时把 JSON 打印到标准输出。
    """
    official_root = Path(args.official_root).resolve()
    python_exe = Path(args.python)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # 未指定问题则跑全部注册问题
    problems = args.problem if args.problem else list(PROBLEMS)
    payload = {
        "official_root": str(official_root),
        "python_exe": str(python_exe),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": [run_problem(official_root, python_exe, problem, args.timeout_s) for problem in problems],
    }
    json_path = output_dir / "official_eoh_smoke_summary.json"
    md_path = output_dir / "official_eoh_smoke_summary.md"
    # 同时输出机器可读（JSON）与人类可读（Markdown）两份报告
    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    _write_markdown(md_path, payload)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return payload


def main() -> None:
    """命令行入口：定义并解析参数，然后调用 run_smoke。

    参数默认值优先取环境变量（EOH_OFFICIAL_ROOT / EOH_OFFICIAL_PYTHON）；
    --problem 可重复指定以只跑部分问题，--timeout-s 控制单个问题的子进程超时。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-root", default=os.environ.get("EOH_OFFICIAL_ROOT", "") or str(Path(__file__).resolve().parents[2] / "official_eoh"))
    parser.add_argument("--python", default=os.environ.get("EOH_OFFICIAL_PYTHON", "") or sys.executable)
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/official_eoh_smoke")
    # 可多次传入 --problem 累加成列表；不传则跑全部
    parser.add_argument("--problem", choices=sorted(PROBLEMS), action="append")
    parser.add_argument("--timeout-s", type=int, default=120)
    run_smoke(parser.parse_args())


if __name__ == "__main__":
    main()
