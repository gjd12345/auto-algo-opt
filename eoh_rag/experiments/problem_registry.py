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
    name: str
    example_dir: str
    metric_name: str
    objective_direction: str
    target_function: str


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


def _safe_float(value: str) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def parse_bp_online_output(output: str) -> dict[str, Any]:
    rows = []
    for line in output.splitlines():
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
    values = [row["excess_percent"] for row in rows if row["excess_percent"] is not None]
    return {
        "metric_name": "avg_excess_percent",
        "objective": sum(values) / len(values) if values else None,
        "rows": rows,
    }


def parse_tsp_construct_output(output: str) -> dict[str, Any]:
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


PARSERS = {
    "bp_online": parse_bp_online_output,
    "tsp_construct": parse_tsp_construct_output,
    "cvrp_construct": parse_cvrp_construct_output,
}


def _read_heuristic(example_root: Path) -> str | None:
    heuristic = example_root / "evaluation" / "heuristic.py"
    if not heuristic.exists():
        return None
    return heuristic.read_text(encoding="utf-8")


def run_problem(official_root: Path, python_exe: Path, problem: str, timeout_s: int) -> dict[str, Any]:
    spec = PROBLEMS[problem]
    example_root = official_root / "examples" / spec.example_dir
    eval_root = example_root / "evaluation"
    started = time.time()
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
    if not eval_root.exists():
        result["failure_reason"] = "missing_evaluation_dir"
        return result
    try:
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
        result["failure_reason"] = "timeout"
        result["stdout"] = exc.stdout or ""
        result["stderr"] = exc.stderr or ""
        result["runtime_seconds"] = round(time.time() - started, 3)
        return result

    result["stdout"] = proc.stdout
    result["stderr"] = proc.stderr
    result["return_code"] = proc.returncode
    result["runtime_seconds"] = round(time.time() - started, 3)
    if proc.returncode != 0:
        result["failure_reason"] = f"return_code_{proc.returncode}"
        return result
    parsed = PARSERS[problem](proc.stdout)
    result.update(parsed)
    result["ok"] = parsed.get("objective") is not None
    if not result["ok"]:
        result["failure_reason"] = "unparsed_output"
    return result


def _markdown_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Problem | OK | Metric | Objective | Target | Runtime | Failure |",
        "|---|---:|---|---:|---|---:|---|",
    ]
    for item in results:
        objective = item.get("objective")
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
    official_root = Path(args.official_root).resolve()
    python_exe = Path(args.python)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    problems = args.problem if args.problem else list(PROBLEMS)
    payload = {
        "official_root": str(official_root),
        "python_exe": str(python_exe),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": [run_problem(official_root, python_exe, problem, args.timeout_s) for problem in problems],
    }
    json_path = output_dir / "official_eoh_smoke_summary.json"
    md_path = output_dir / "official_eoh_smoke_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    _write_markdown(md_path, payload)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-root", default=os.environ.get("EOH_OFFICIAL_ROOT", "/private/tmp/EoH-main"))
    parser.add_argument("--python", default=os.environ.get("EOH_OFFICIAL_PYTHON", "/private/tmp/eoh_official_venv/bin/python"))
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/official_eoh_smoke")
    parser.add_argument("--problem", choices=sorted(PROBLEMS), action="append")
    parser.add_argument("--timeout-s", type=int, default=120)
    run_smoke(parser.parse_args())


if __name__ == "__main__":
    main()
