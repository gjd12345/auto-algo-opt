"""在全新生成的 CVRP 实例上配对复核候选，不读取 held-out。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable

import numpy as np


def code_sha256(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest().upper()


def exact_sign_test_p(wins: int, losses: int) -> float:
    """计算双侧精确符号检验；平局不进入有效样本数。"""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = min(wins, losses)
    probability = 2.0 * sum(math.comb(n, k) for k in range(tail + 1)) / (2 ** n)
    return min(1.0, probability)


def compile_heuristic(code: str) -> Callable[..., int]:
    namespace: dict[str, Any] = {"np": np}
    exec(code, namespace)
    heuristic = namespace.get("select_next_node")
    if not callable(heuristic):
        raise ValueError("select_next_node is missing")
    return heuristic


def generate_instance(environment: dict[str, Any], seed: int) -> tuple[np.ndarray, np.ndarray]:
    """按冻结环境生成坐标和需求；同一 seed 在所有候选间严格复用。"""
    rng = np.random.default_rng(seed)
    n_customers = int(environment["n_customers"])
    geometry = environment["geometry"]
    if geometry == "uniform_square":
        coords = rng.uniform(0, 100, (n_customers + 1, 2))
    elif geometry == "clustered":
        centers = rng.uniform(15, 85, (4, 2))
        assignments = rng.integers(0, len(centers), n_customers + 1)
        coords = centers[assignments] + rng.normal(0, 8, (n_customers + 1, 2))
        coords = np.clip(coords, 0, 100)
        coords[0] = np.array([50.0, 50.0])
    elif geometry == "rectangular":
        coords = np.column_stack(
            (rng.uniform(0, 300, n_customers + 1), rng.uniform(0, 50, n_customers + 1))
        )
    else:
        raise ValueError(f"unknown geometry: {geometry}")

    demands = np.zeros(n_customers + 1, dtype=int)
    demands[1:] = rng.integers(1, int(environment["demand_max"]) + 1, n_customers)
    return coords, demands


def distance_matrix(coords: np.ndarray) -> np.ndarray:
    delta = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(delta * delta, axis=2))


def evaluate_instance(
    heuristic: Callable[..., int],
    coords: np.ndarray,
    demands: np.ndarray,
    capacity: int,
) -> float | None:
    """用与构造问题相同的接口生成路线，并显式检查覆盖和容量。"""
    dist = distance_matrix(coords)
    n = len(coords)
    route = [0]
    load = 0
    current = 0
    unvisited = set(range(1, n))
    max_steps = n * n

    for _ in range(max_steps):
        if not unvisited:
            break
        feasible = np.array(
            sorted(node for node in unvisited if load + int(demands[node]) <= capacity),
            dtype=int,
        )
        if len(feasible) == 0:
            if current == 0:
                return None
            route.append(0)
            load = 0
            current = 0
            continue
        try:
            next_node = int(
                heuristic(current, 0, feasible, float(capacity - load), demands.copy(), dist.copy())
            )
        except Exception:
            return None
        if next_node == 0:
            if current == 0:
                return None
            route.append(0)
            load = 0
            current = 0
            continue
        if next_node not in unvisited or next_node not in feasible:
            return None
        route.append(next_node)
        load += int(demands[next_node])
        current = next_node
        unvisited.remove(next_node)
    if unvisited:
        return None
    if route[-1] != 0:
        route.append(0)
    if set(route) != set(range(n)):
        return None
    return float(sum(dist[start, end] for start, end in zip(route, route[1:])))


def paired_summary(seed_costs: list[float], candidate_costs: list[float]) -> dict[str, Any]:
    if len(seed_costs) != len(candidate_costs):
        raise ValueError("paired cost lengths differ")
    relative = [
        100.0 * (seed_cost - candidate_cost) / seed_cost
        for seed_cost, candidate_cost in zip(seed_costs, candidate_costs)
    ]
    wins = sum(candidate < seed - 1e-9 for seed, candidate in zip(seed_costs, candidate_costs))
    losses = sum(candidate > seed + 1e-9 for seed, candidate in zip(seed_costs, candidate_costs))
    ties = len(seed_costs) - wins - losses
    effective = wins + losses
    return {
        "pairs": len(seed_costs),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_rate_non_ties": wins / effective if effective else 0.0,
        "mean_relative_improvement_pct": mean(relative),
        "median_relative_improvement_pct": median(relative),
        "sign_test_p_two_sided": exact_sign_test_p(wins, losses),
    }


def select_passing_candidate(reports: dict[str, dict[str, Any]]) -> str | None:
    """双通过时按冻结规则选择中位相对改善更高的候选。"""
    passed = [candidate_id for candidate_id, report in reports.items() if report["passed"]]
    if not passed:
        return None
    return max(
        passed,
        key=lambda candidate_id: reports[candidate_id]["overall"][
            "median_relative_improvement_pct"
        ],
    )


def load_candidates(path: Path) -> list[dict[str, Any]]:
    candidates = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidate file must contain a non-empty list")
    for candidate in candidates:
        actual_hash = code_sha256(candidate["code"])
        if actual_hash != candidate["code_sha256"]:
            raise ValueError(f"candidate hash mismatch: {candidate.get('candidate_id')}")
    if sum(candidate.get("role") == "seed" for candidate in candidates) != 1:
        raise ValueError("candidate file must contain exactly one seed")
    return candidates


def run_diagnostic(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    candidate_path = (repo_root / manifest["candidate_file"]).resolve()
    candidates = load_candidates(candidate_path)
    heuristics = {item["candidate_id"]: compile_heuristic(item["code"]) for item in candidates}
    seed_id = next(item["candidate_id"] for item in candidates if item["role"] == "seed")

    costs: dict[str, dict[str, list[float]]] = {
        item["candidate_id"]: {} for item in candidates
    }
    feasibility: dict[str, int] = {item["candidate_id"]: 0 for item in candidates}
    paired_rows: list[dict[str, Any]] = []

    for environment in manifest["environments"]:
        env_name = environment["name"]
        instance_count = int(environment["instances"])
        for candidate in candidates:
            costs[candidate["candidate_id"]][env_name] = []
        for index in range(instance_count):
            instance_seed = int(environment["seed_start"]) + index
            coords, demands = generate_instance(environment, instance_seed)
            row_costs: dict[str, float | None] = {}
            for candidate in candidates:
                candidate_id = candidate["candidate_id"]
                cost = evaluate_instance(
                    heuristics[candidate_id], coords, demands, int(environment["capacity"])
                )
                if cost is None:
                    row_costs[candidate_id] = None
                else:
                    feasibility[candidate_id] += 1
                    costs[candidate_id][env_name].append(cost)
                    row_costs[candidate_id] = cost
            paired_rows.append({"environment": env_name, "seed": instance_seed, "costs": row_costs})

    total_instances = sum(int(environment["instances"]) for environment in manifest["environments"])
    gate = manifest["gate"]
    reports: dict[str, Any] = {}
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        if candidate_id == seed_id:
            continue
        environment_reports: dict[str, Any] = {}
        valid_all = feasibility[candidate_id] == total_instances and feasibility[seed_id] == total_instances
        for environment in manifest["environments"]:
            env_name = environment["name"]
            if valid_all:
                environment_reports[env_name] = paired_summary(
                    costs[seed_id][env_name], costs[candidate_id][env_name]
                )
            else:
                environment_reports[env_name] = {"valid": False}

        if valid_all:
            seed_all = sum((costs[seed_id][env["name"]] for env in manifest["environments"]), [])
            candidate_all = sum(
                (costs[candidate_id][env["name"]] for env in manifest["environments"]), []
            )
            overall = paired_summary(seed_all, candidate_all)
            positive_environments = sum(
                report["mean_relative_improvement_pct"] > 0
                for report in environment_reports.values()
            )
        else:
            overall = {"pairs": total_instances}
            positive_environments = 0

        passed = bool(
            valid_all
            and overall["mean_relative_improvement_pct"] > float(gate["mean_relative_improvement_pct_min"])
            and overall["win_rate_non_ties"] >= float(gate["win_rate_non_ties_min"])
            and overall["sign_test_p_two_sided"] <= float(gate["sign_test_p_max"])
            and positive_environments >= int(gate["positive_environments_min"])
        )
        reports[candidate_id] = {
            "code_sha256": candidate["code_sha256"],
            "feasible_instances": feasibility[candidate_id],
            "total_instances": total_instances,
            "positive_environments": positive_environments,
            "overall": overall,
            "by_environment": environment_reports,
            "passed": passed,
        }

    # manifest 已冻结双通过时按中位相对改善选择，避免运行后临时改规则。
    selected_candidate = select_passing_candidate(reports)

    return {
        "suite": manifest["suite"],
        "candidate_file": manifest["candidate_file"],
        "candidate_file_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest().upper(),
        "held_out_used": False,
        "total_instances": total_instances,
        "seed_id": seed_id,
        "seed_feasible_instances": feasibility[seed_id],
        "gate": gate,
        "candidates": reports,
        "selected_candidate": selected_candidate,
        "paired_rows": paired_rows,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# CVRP fresh 生成诊断",
        "",
        "结论：" + (
            "至少一个候选通过预注册门槛。"
            if any(item["passed"] for item in result["candidates"].values())
            else "没有候选通过预注册门槛。"
        ),
        "",
        "| 候选 | 胜/负/平 | 平均相对改善 | 正向环境 | p 值 | 通过 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for candidate_id, report in result["candidates"].items():
        overall = report["overall"]
        if report["feasible_instances"] != report["total_instances"]:
            lines.append(f"| {candidate_id} | 不全可行 | — | — | — | 否 |")
            continue
        lines.append(
            f"| {candidate_id} | {overall['wins']}/{overall['losses']}/{overall['ties']} | "
            f"{overall['mean_relative_improvement_pct']:.4f}% | "
            f"{report['positive_environments']} | {overall['sign_test_p_two_sided']:.6g} | "
            f"{'是' if report['passed'] else '否'} |"
        )
    lines.extend(["", "held-out 未参与生成、评估或选择。", ""])
    return "\n".join(lines)


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = Path(args.output_dir).resolve()
    json_path = output_dir / "cvrp_fresh_diagnostic.json"
    markdown_path = output_dir / "cvrp_fresh_diagnostic.md"
    if not args.force and (json_path.exists() or markdown_path.exists()):
        raise FileExistsError(f"diagnostic output already exists: {output_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = run_diagnostic(manifest, repo_root)
    result["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest().upper()
    write_atomic(json_path, json.dumps(result, ensure_ascii=False, indent=2))
    write_atomic(markdown_path, render_markdown(result))
    print(json.dumps({
        "output": str(json_path),
        "passed": [key for key, value in result["candidates"].items() if value["passed"]],
        "selected_candidate": result["selected_candidate"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
