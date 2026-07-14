#!/usr/bin/env python3
"""用锁定划分检验 TSP 快速双槽的选择性回退规则。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_route_behaviors as behavior


FEATURE_FIELDS = (
    "instance",
    "instance_sha256",
    "nodes",
    "pair_winner",
    "pair_cost",
    "pair_lower_bound",
    "pair_lower_bound_gap_pct",
    "pair_edge_length_cv",
    "pair_nearest_choice_rate",
    "pair_cost_spread_pct",
    "pair_edge_cv_spread",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"禁止覆盖已有产物：{path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: tuple[str, ...] | list[str], rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"禁止覆盖已有产物：{path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_and_verify_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, str]]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    actual_hashes = {
        "instance_manifest_sha256": sha256_file(args.instance_manifest),
        "route_behavior_metrics_sha256": sha256_file(args.behavior_metrics),
        "pairwise_comparison_sha256": sha256_file(args.pairwise_comparison),
        "archive_metadata_sha256": sha256_file(args.archive_metadata),
    }
    expected_hashes = protocol["inputs"]
    for key, actual in actual_hashes.items():
        if actual != expected_hashes.get(key):
            raise RuntimeError(f"输入 hash 不匹配：{key} expected={expected_hashes.get(key)} actual={actual}")
    return protocol, actual_hashes


def load_alias_hashes(path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            aliases[item["label"]] = item["code_hash"]
    required = {"R2", "R4", "AW1", "AW2", "AW3", "AW4"}
    if set(aliases) != required:
        raise ValueError(f"档案标签不完整：{sorted(aliases)}")
    return aliases


def load_instance_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    instances = payload.get("instances", [])
    if len(instances) != payload.get("instance_count"):
        raise ValueError("实例 manifest 数量不一致")
    for item in instances:
        instance_path = Path(item["path"])
        if sha256_file(instance_path) != item["sha256"]:
            raise RuntimeError(f"实例 hash 不匹配：{item['name']}")
    return instances


def build_locked_split(instances: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    # 只按文件 hash 排序并交替划分，保证样本数平衡且不读取任何胜负标签。
    ordered = sorted(instances, key=lambda item: item["sha256"])
    discovery = ordered[0::2]
    confirmation = ordered[1::2]
    split_protocol = protocol["split"]
    if len(discovery) != split_protocol["expected_discovery_count"] or len(confirmation) != split_protocol[
        "expected_confirmation_count"
    ]:
        raise ValueError("锁定划分数量与协议不一致")
    return {
        "schema_version": "tsp-fast-pair-fallback-router-split/v1",
        "rule": split_protocol["rule"],
        "discovery": [
            {"instance": item["name"], "sha256": item["sha256"]} for item in discovery
        ],
        "confirmation": [
            {"instance": item["name"], "sha256": item["sha256"]} for item in confirmation
        ],
    }


def load_behavior_metrics(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            key = (raw["code_hash"], raw["instance"])
            if key in rows:
                raise ValueError(f"行为坐标重复：{key}")
            rows[key] = {
                "tour_cost": float(raw["tour_cost"]),
                "edge_length_cv": float(raw["edge_length_cv"]),
                "nearest_choice_rate": float(raw["nearest_choice_rate"]),
            }
    return rows


def two_edge_lower_bound(instance_path: Path) -> float:
    data = behavior.load_tsp(instance_path)
    coords = np.asarray(data["coords"], dtype=float)
    node_count = len(coords)
    two_smallest = np.empty((node_count, 2), dtype=float)
    chunk_size = 192
    for start in range(0, node_count, chunk_size):
        end = min(start + chunk_size, node_count)
        distances = np.rint(np.linalg.norm(coords[start:end, None, :] - coords[None, :, :], axis=2))
        local_rows = np.arange(end - start)
        global_rows = np.arange(start, end)
        distances[local_rows, global_rows] = np.inf
        two_smallest[start:end] = np.partition(distances, kth=1, axis=1)[:, :2]
    # 每个城市在任意环路中都有两条边，因此两条最短邻边之和除以二是合法下界。
    return float(math.ceil(float(np.sum(two_smallest)) / 2.0))


def build_pair_features(
    instances: list[dict[str, Any]],
    instance_names: set[str],
    metrics: dict[tuple[str, str], dict[str, Any]],
    aliases: dict[str, str],
) -> list[dict[str, Any]]:
    features = []
    for item in instances:
        instance = item["name"]
        if instance not in instance_names:
            continue
        pair_rows = [(label, metrics[(aliases[label], instance)]) for label in ("R2", "R4")]
        pair_rows.sort(key=lambda entry: (entry[1]["tour_cost"], entry[0]))
        winner_label, winner = pair_rows[0]
        other = pair_rows[1][1]
        lower_bound = two_edge_lower_bound(Path(item["path"]))
        features.append(
            {
                "instance": instance,
                "instance_sha256": item["sha256"],
                "nodes": int(item["dimension"]),
                "pair_winner": winner_label,
                "pair_cost": winner["tour_cost"],
                "pair_lower_bound": lower_bound,
                "pair_lower_bound_gap_pct": (winner["tour_cost"] / lower_bound - 1.0) * 100.0,
                "pair_edge_length_cv": winner["edge_length_cv"],
                "pair_nearest_choice_rate": winner["nearest_choice_rate"],
                "pair_cost_spread_pct": abs(winner["tour_cost"] - other["tour_cost"])
                / winner["tour_cost"]
                * 100.0,
                "pair_edge_cv_spread": abs(winner["edge_length_cv"] - other["edge_length_cv"]),
            }
        )
    return sorted(features, key=lambda row: row["instance"])


def load_pairwise_labels(path: Path, allowed_instances: set[str]) -> dict[str, dict[str, Any]]:
    labels = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            instance = raw["instance"]
            if instance not in allowed_instances:
                continue
            labels[instance] = {
                "direction": raw["direction"],
                "cost_delta_pct": float(raw["cost_delta_pct"]),
            }
    if set(labels) != allowed_instances:
        raise ValueError("配对标签缺失")
    return labels


def percentile(values: list[float], quantile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), quantile))


def evaluate_rule(
    features: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    feature_name: str,
    direction: str,
    threshold: float,
) -> dict[str, Any]:
    decisions = []
    for row in features:
        value = float(row[feature_name])
        accept_pair = value <= threshold if direction == "le" else value >= threshold
        label = labels[row["instance"]]
        router_delta = label["cost_delta_pct"] if accept_pair else 0.0
        decisions.append(
            {
                **row,
                "feature_value": value,
                "accept_pair": accept_pair,
                "pair_direction": label["direction"],
                "pair_cost_delta_pct": label["cost_delta_pct"],
                "router_cost_delta_pct": router_delta,
            }
        )

    accepted = [row for row in decisions if row["accept_pair"]]
    deltas = [row["router_cost_delta_pct"] for row in decisions]
    wins = sum(row["pair_direction"] == "better" for row in accepted)
    losses = sum(row["pair_direction"] == "worse" for row in accepted)
    acceptance_rate = len(accepted) / len(decisions)
    return {
        "feature": feature_name,
        "accept_when": direction,
        "threshold": threshold,
        "instance_count": len(decisions),
        "accepted_count": len(accepted),
        "acceptance_rate": acceptance_rate,
        "fallback_count": len(decisions) - len(accepted),
        "accepted_wins": wins,
        "accepted_same": len(accepted) - wins - losses,
        "accepted_losses": losses,
        "mean_router_cost_delta_pct": statistics.fmean(deltas),
        "median_router_cost_delta_pct": statistics.median(deltas),
        "p90_router_cost_delta_pct": percentile(deltas, 90),
        "max_router_cost_delta_pct": max(deltas),
        "average_code_evaluations": 2.0 + 4.0 * (1.0 - acceptance_rate),
        "decisions": decisions,
    }


def rule_passes(metrics: dict[str, Any], constraints: dict[str, Any]) -> tuple[bool, list[str]]:
    checks = {
        "acceptance_rate": metrics["acceptance_rate"] >= constraints["minimum_acceptance_rate"],
        "wins_exceed_losses": metrics["accepted_wins"] > metrics["accepted_losses"],
        "mean_cost": metrics["mean_router_cost_delta_pct"] <= constraints["maximum_mean_cost_delta_pct"],
        "p90_cost": metrics["p90_router_cost_delta_pct"] <= constraints["maximum_p90_cost_delta_pct"],
        "single_harm": metrics["max_router_cost_delta_pct"] <= constraints["maximum_single_instance_harm_pct"],
    }
    return all(checks.values()), [name for name, passed in checks.items() if not passed]


def fit_rule(args: argparse.Namespace, protocol: dict[str, Any], hashes: dict[str, str]) -> None:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    instances = load_instance_manifest(args.instance_manifest)
    split = build_locked_split(instances, protocol)
    split["protocol_sha256"] = sha256_file(args.protocol)
    split["input_hashes"] = hashes
    split_path = output_dir / "split_manifest.json"
    write_json(split_path, split)

    discovery_names = {item["instance"] for item in split["discovery"]}
    aliases = load_alias_hashes(args.archive_metadata)
    metrics = load_behavior_metrics(args.behavior_metrics)
    features = build_pair_features(instances, discovery_names, metrics, aliases)
    labels = load_pairwise_labels(args.pairwise_comparison, discovery_names)
    write_csv(output_dir / "discovery_features.csv", FEATURE_FIELDS, features)

    candidate_rows = []
    passing = []
    for rule_index, rule in enumerate(protocol["candidate_rules"]):
        feature_name = rule["feature"]
        for threshold in sorted({float(row[feature_name]) for row in features}):
            result = evaluate_rule(features, labels, feature_name, rule["accept_when"], threshold)
            passed, failures = rule_passes(result, protocol["discovery_constraints"])
            result["passes_discovery"] = passed
            result["failed_checks"] = ";".join(failures)
            result["candidate_rule_order"] = rule_index
            candidate_rows.append({key: value for key, value in result.items() if key != "decisions"})
            if passed:
                passing.append(result)

    candidate_fields = list(candidate_rows[0])
    write_csv(output_dir / "discovery_candidate_rules.csv", candidate_fields, candidate_rows)
    if not passing:
        write_json(
            output_dir / "fit_summary.json",
            {
                "schema_version": "tsp-fast-pair-fallback-router-fit/v1",
                "rule_found": False,
                "candidate_count": len(candidate_rows),
                "passing_candidate_count": 0,
                "protocol_sha256": sha256_file(args.protocol),
                "split_manifest_sha256": sha256_file(split_path),
                "next_action": "stop_router_branch",
            },
        )
        print("RULE_FOUND=false")
        return

    # 质量风险优先于省计算量；只有风险相同时才扩大双槽直接接受范围。
    chosen = min(
        passing,
        key=lambda row: (
            row["accepted_losses"],
            row["mean_router_cost_delta_pct"],
            -row["accepted_count"],
            next(
                index
                for index, item in enumerate(protocol["candidate_rules"])
                if item["feature"] == row["feature"] and item["accept_when"] == row["accept_when"]
            ),
            row["threshold"],
        ),
    )
    frozen_rule = {
        "schema_version": "tsp-fast-pair-fallback-router-rule/v1",
        "protocol_sha256": sha256_file(args.protocol),
        "split_manifest_sha256": sha256_file(split_path),
        "input_hashes": hashes,
        "feature": chosen["feature"],
        "accept_when": chosen["accept_when"],
        "threshold": chosen["threshold"],
        "discovery_metrics": {key: value for key, value in chosen.items() if key != "decisions"},
        "confirmation_gate": protocol["confirmation_gate"],
    }
    rule_path = output_dir / "frozen_rule.json"
    write_json(rule_path, frozen_rule)
    write_json(
        output_dir / "fit_summary.json",
        {
            "schema_version": "tsp-fast-pair-fallback-router-fit/v1",
            "rule_found": True,
            "candidate_count": len(candidate_rows),
            "passing_candidate_count": len(passing),
            "protocol_sha256": sha256_file(args.protocol),
            "split_manifest_sha256": sha256_file(split_path),
            "frozen_rule_sha256": sha256_file(rule_path),
            "chosen_discovery_metrics": frozen_rule["discovery_metrics"],
            "next_action": "run_confirmation_once",
        },
    )
    print(f"RULE_FOUND=true\nFROZEN_RULE_SHA256={sha256_file(rule_path)}")


def confirm_rule(args: argparse.Namespace, protocol: dict[str, Any], hashes: dict[str, str]) -> None:
    output_dir = args.output_dir.resolve()
    rule_path = args.rule.resolve()
    actual_rule_hash = sha256_file(rule_path)
    if actual_rule_hash != args.expected_rule_sha256:
        raise RuntimeError("冻结规则 hash 不匹配，禁止读取确认标签")
    rule = json.loads(rule_path.read_text(encoding="utf-8"))
    if rule["protocol_sha256"] != sha256_file(args.protocol) or rule["input_hashes"] != hashes:
        raise RuntimeError("冻结规则的协议或输入版本已变化")

    split_path = output_dir / "split_manifest.json"
    if sha256_file(split_path) != rule["split_manifest_sha256"]:
        raise RuntimeError("锁定划分已变化")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    confirmation_names = {item["instance"] for item in split["confirmation"]}
    instances = load_instance_manifest(args.instance_manifest)
    aliases = load_alias_hashes(args.archive_metadata)
    metrics = load_behavior_metrics(args.behavior_metrics)
    features = build_pair_features(instances, confirmation_names, metrics, aliases)
    labels = load_pairwise_labels(args.pairwise_comparison, confirmation_names)
    result = evaluate_rule(features, labels, rule["feature"], rule["accept_when"], rule["threshold"])
    passed, failures = rule_passes(result, rule["confirmation_gate"])

    decision_fields = FEATURE_FIELDS + (
        "feature_value",
        "accept_pair",
        "pair_direction",
        "pair_cost_delta_pct",
        "router_cost_delta_pct",
    )
    write_csv(output_dir / "confirmation_decisions.csv", decision_fields, result.pop("decisions"))
    result["passes_confirmation"] = passed
    result["failed_checks"] = failures
    result["feasible_rate"] = 1.0
    write_json(
        output_dir / "confirmation_summary.json",
        {
            "schema_version": "tsp-fast-pair-fallback-router-confirmation/v1",
            "frozen_rule_sha256": actual_rule_hash,
            "confirmation_metrics": result,
            "decision": "keep_exploratory_router" if passed else "stop_router_branch",
            "default_archive_changed": False,
        },
    )
    print(f"PASSES_CONFIRMATION={str(passed).lower()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("fit", "confirm"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--instance-manifest", type=Path, required=True)
    parser.add_argument("--behavior-metrics", type=Path, required=True)
    parser.add_argument("--pairwise-comparison", type=Path, required=True)
    parser.add_argument("--archive-metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rule", type=Path)
    parser.add_argument("--expected-rule-sha256")
    args = parser.parse_args()
    if args.phase == "confirm" and (args.rule is None or not args.expected_rule_sha256):
        parser.error("confirm 阶段必须同时提供 --rule 和 --expected-rule-sha256")
    return args


def main() -> None:
    args = parse_args()
    protocol, hashes = load_and_verify_inputs(args)
    if args.phase == "fit":
        fit_rule(args, protocol, hashes)
    else:
        confirm_rule(args, protocol, hashes)


if __name__ == "__main__":
    main()
