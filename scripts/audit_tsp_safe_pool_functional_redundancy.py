#!/usr/bin/env python3
"""用冻结的廉价探针审计 TSP 历史安全代码池的功能冗余。"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import itertools
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import intervene_tsp_edge_variability as intervention
import validate_tsp_cheap_functional_probe as cheap_probe


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """核对所有冻结文件，避免无意中更换安全代码或探针坐标。"""
    protocol = load_json(args.protocol)
    checks = {
        "safe_probe_results_sha256": intervention.sha256_file(args.safe_probe_results),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
        "cheap_probe_protocol_sha256": intervention.sha256_file(args.cheap_probe_protocol),
        "cheap_probe_manifest_sha256": intervention.sha256_file(args.cheap_probe_manifest),
    }
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")

    probe_protocol = load_json(args.cheap_probe_protocol)
    probe_manifest = load_json(args.cheap_probe_manifest)
    manifest_by_name = {item["name"]: item for item in probe_manifest["probes"]}
    if len(probe_protocol["probes"]) != 6 or len(manifest_by_name) != 6:
        raise ValueError("冻结探针数量必须为 6")
    return protocol, probe_protocol, manifest_by_name


def load_safe_candidates(
    safe_probe_results: Path,
    code_catalog: Path,
    expected_count: int,
) -> list[dict[str, Any]]:
    """从 Stage AW 中只选目标规模已通过的代码，并从只读目录解析源码。"""
    safe_by_hash: dict[str, dict[str, Any]] = {}
    with safe_probe_results.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["feasible"].strip().lower() != "true":
                continue
            code_hash = row["code_hash"]
            if code_hash in safe_by_hash:
                raise ValueError(f"安全代码 hash 重复：{code_hash}")
            safe_by_hash[code_hash] = {
                "code_hash": code_hash,
                "objective": float(row["objective"]),
                "original_index": int(row["original_index"]),
                "ast_nodes": int(row["ast_nodes"]),
            }
    if len(safe_by_hash) != expected_count:
        raise ValueError(f"安全代码数量应为 {expected_count}，实际为 {len(safe_by_hash)}")

    catalog_by_hash = {}
    with code_catalog.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                catalog_by_hash[item["code_hash"]] = item

    missing = sorted(set(safe_by_hash) - set(catalog_by_hash))
    if missing:
        raise ValueError(f"历史目录缺少 {len(missing)} 条安全代码")

    candidates = []
    for code_hash, safe in safe_by_hash.items():
        catalog = catalog_by_hash[code_hash]
        code = catalog["code"]
        if hashlib.sha256(code.encode("utf-8")).hexdigest() != code_hash:
            raise RuntimeError(f"源码 hash 不匹配：{code_hash}")
        ast_text = ast.dump(ast.parse(code), include_attributes=False)
        candidates.append(
            {
                **safe,
                "code": code,
                "ast_sha256": hashlib.sha256(ast_text.encode("utf-8")).hexdigest(),
            }
        )
    return sorted(candidates, key=lambda item: (item["original_index"], item["code_hash"]))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if path.exists():
        raise FileExistsError(f"禁止覆盖已有结果：{path}")
    if not rows and fieldnames is None:
        raise ValueError(f"空结果缺少列定义：{path}")
    columns = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def exact_signature(route_hashes: list[str]) -> str:
    return hashlib.sha256("\n".join(route_hashes).encode("utf-8")).hexdigest()


class UnionFind:
    """只用于连接相似代码；连通分量不等同于任意两点都相似。"""

    def __init__(self, nodes: list[str]) -> None:
        self.parent = {node: node for node in nodes}

    def find(self, node: str) -> str:
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def evaluate_probes(
    candidates: list[dict[str, Any]],
    probe_protocol: dict[str, Any],
    manifest_by_name: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, set[tuple[int, int]]]], dict[str, list[str]]]:
    """执行固定的小规模探针；单条失败只排除该代码，不替换候选。"""
    compiled: dict[str, Any] = {}
    compile_errors: dict[str, Exception] = {}
    for candidate in candidates:
        try:
            compiled[candidate["code_hash"]] = intervention.compile_heuristic(candidate["code"])
        except Exception as exc:  # 历史代码可能存在运行环境依赖，必须保留失败坐标。
            compile_errors[candidate["code_hash"]] = exc

    rows: list[dict[str, Any]] = []
    edge_sets: dict[str, dict[str, set[tuple[int, int]]]] = defaultdict(dict)
    route_hashes: dict[str, list[str]] = defaultdict(list)
    for probe in probe_protocol["probes"]:
        coords = cheap_probe.generate_coords(probe, probe_protocol["generator"])
        coordinate_hash = hashlib.sha256(coords.tobytes()).hexdigest()
        expected_hash = manifest_by_name[probe["name"]]["coordinate_sha256"]
        if coordinate_hash != expected_hash:
            raise RuntimeError(f"探针坐标 hash 不匹配：{probe['name']}")
        distances = intervention.build_distance_matrix(coords.astype(float))

        for candidate in candidates:
            code_hash = candidate["code_hash"]
            error = compile_errors.get(code_hash)
            try:
                if error is not None:
                    raise error
                route, cost = intervention.build_route(compiled[code_hash], distances)
                edges = cheap_probe.route_edges(route)
                route_digest = intervention.route_hash(route)
                edge_sets[code_hash][probe["name"]] = edges
                route_hashes[code_hash].append(route_digest)
                row = {
                    "code_hash": code_hash,
                    "objective": candidate["objective"],
                    "original_index": candidate["original_index"],
                    "ast_nodes": candidate["ast_nodes"],
                    "probe": probe["name"],
                    "geometry": probe["geometry"],
                    "nodes": probe["nodes"],
                    "feasible": True,
                    "error_type": "",
                    "tour_cost": cost,
                    "route_hash": route_digest,
                }
            except Exception as exc:  # 探针审计不能因一条历史代码失败而丢失全池统计。
                row = {
                    "code_hash": code_hash,
                    "objective": candidate["objective"],
                    "original_index": candidate["original_index"],
                    "ast_nodes": candidate["ast_nodes"],
                    "probe": probe["name"],
                    "geometry": probe["geometry"],
                    "nodes": probe["nodes"],
                    "feasible": False,
                    "error_type": type(exc).__name__,
                    "tour_cost": "",
                    "route_hash": "",
                }
            rows.append(row)
    return rows, edge_sets, route_hashes


def build_pair_rows(
    complete: list[dict[str, Any]],
    probes: list[dict[str, Any]],
    edge_sets: dict[str, dict[str, set[tuple[int, int]]]],
    threshold: float,
) -> list[dict[str, Any]]:
    rows = []
    probe_names = [probe["name"] for probe in probes]
    for left, right in itertools.combinations(complete, 2):
        values = []
        identical_count = 0
        for probe_name in probe_names:
            left_edges = edge_sets[left["code_hash"]][probe_name]
            right_edges = edge_sets[right["code_hash"]][probe_name]
            values.append(len(left_edges & right_edges) / len(left_edges | right_edges))
            identical_count += left_edges == right_edges
        mean_similarity = statistics.fmean(values)
        rows.append(
            {
                "left_code_hash": left["code_hash"],
                "right_code_hash": right["code_hash"],
                "mean_probe_edge_jaccard": mean_similarity,
                "median_probe_edge_jaccard": statistics.median(values),
                "min_probe_edge_jaccard": min(values),
                "max_probe_edge_jaccard": max(values),
                "identical_probe_count": identical_count,
                "redundant": mean_similarity >= threshold,
            }
        )
    return rows


def build_clusters(
    complete: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    route_hashes: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    by_hash = {item["code_hash"]: item for item in complete}
    union_find = UnionFind(sorted(by_hash))
    for row in pair_rows:
        if row["redundant"]:
            union_find.union(row["left_code_hash"], row["right_code_hash"])

    components: dict[str, list[str]] = defaultdict(list)
    for code_hash in sorted(by_hash):
        components[union_find.find(code_hash)].append(code_hash)
    ordered_components = sorted(
        components.values(),
        key=lambda members: (-len(members), min(by_hash[item]["original_index"] for item in members)),
    )

    code_rows = []
    summary_rows = []
    cluster_by_code: dict[str, int] = {}
    for cluster_id, members in enumerate(ordered_components, start=1):
        member_items = [by_hash[item] for item in members]
        representative = sorted(
            member_items,
            key=lambda item: (-item["objective"], item["original_index"], item["code_hash"]),
        )[0]
        signatures = {exact_signature(route_hashes[item]) for item in members}
        objectives = [item["objective"] for item in member_items]
        for item in sorted(member_items, key=lambda value: value["original_index"]):
            cluster_by_code[item["code_hash"]] = cluster_id
            code_rows.append(
                {
                    "code_hash": item["code_hash"],
                    "objective": item["objective"],
                    "original_index": item["original_index"],
                    "ast_nodes": item["ast_nodes"],
                    "ast_sha256": item["ast_sha256"],
                    "exact_functional_signature": exact_signature(route_hashes[item["code_hash"]]),
                    "cluster_id": cluster_id,
                    "cluster_size": len(members),
                    "is_representative": item["code_hash"] == representative["code_hash"],
                }
            )
        summary_rows.append(
            {
                "cluster_id": cluster_id,
                "cluster_size": len(members),
                "representative_code_hash": representative["code_hash"],
                "representative_objective": representative["objective"],
                "objective_min": min(objectives),
                "objective_max": max(objectives),
                "objective_distinct_count": len(set(objectives)),
                "ast_signature_count": len({item["ast_sha256"] for item in member_items}),
                "exact_functional_signature_count": len(signatures),
            }
        )
    return code_rows, summary_rows, cluster_by_code


def run(args: argparse.Namespace) -> None:
    protocol, probe_protocol, manifest_by_name = verify_inputs(args)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_count = int(protocol["candidate_selection"]["expected_code_count"])
    candidates = load_safe_candidates(args.safe_probe_results, args.code_catalog, expected_count)

    probe_rows, edge_sets, route_hashes = evaluate_probes(
        candidates, probe_protocol, manifest_by_name
    )
    probe_count = len(probe_protocol["probes"])
    complete = [item for item in candidates if len(edge_sets[item["code_hash"]]) == probe_count]
    threshold = float(protocol["functional_signature"]["redundancy_threshold"])
    pair_rows = build_pair_rows(complete, probe_protocol["probes"], edge_sets, threshold)
    code_rows, cluster_rows, cluster_by_code = build_clusters(complete, pair_rows, route_hashes)

    write_csv(output_dir / "safe_pool_probe_code_results.csv", probe_rows)
    write_csv(output_dir / "safe_pool_pairwise_similarity.csv", pair_rows)
    write_csv(output_dir / "safe_pool_code_clusters.csv", code_rows)
    write_csv(output_dir / "safe_pool_cluster_summary.csv", cluster_rows)

    signature_counts: dict[str, int] = defaultdict(int)
    for row in code_rows:
        signature_counts[row["exact_functional_signature"]] += 1
    duplicate_group_sizes = [count for count in signature_counts.values() if count > 1]
    similarity_by_pair = {
        tuple(sorted((row["left_code_hash"], row["right_code_hash"]))): float(
            row["mean_probe_edge_jaccard"]
        )
        for row in pair_rows
    }
    component_pair_minima = []
    non_clique_component_count = 0
    for cluster in cluster_rows:
        members = [
            row["code_hash"]
            for row in code_rows
            if row["cluster_id"] == cluster["cluster_id"]
        ]
        if len(members) < 2:
            continue
        values = [
            similarity_by_pair[tuple(sorted(pair))]
            for pair in itertools.combinations(members, 2)
        ]
        component_pair_minima.append(min(values))
        non_clique_component_count += any(value < threshold for value in values)
    top20 = sorted(complete, key=lambda item: (-item["objective"], item["original_index"]))[:20]
    cluster_sizes = [int(row["cluster_size"]) for row in cluster_rows]
    summary = {
        "schema_version": "tsp-safe-pool-functional-redundancy-summary/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "inputs": {
            "safe_probe_results_sha256": intervention.sha256_file(args.safe_probe_results),
            "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
            "cheap_probe_protocol_sha256": intervention.sha256_file(args.cheap_probe_protocol),
            "cheap_probe_manifest_sha256": intervention.sha256_file(args.cheap_probe_manifest),
        },
        "metrics": {
            "candidate_code_count": len(candidates),
            "probe_count": probe_count,
            "route_coordinate_count": len(probe_rows),
            "valid_route_coordinate_count": sum(row["feasible"] for row in probe_rows),
            "complete_code_count": len(complete),
            "failed_code_count": len(candidates) - len(complete),
            "pair_count": len(pair_rows),
            "redundant_pair_count": sum(row["redundant"] for row in pair_rows),
            "component_count": len(cluster_rows),
            "singleton_component_count": sum(size == 1 for size in cluster_sizes),
            "nontrivial_component_code_count": sum(size for size in cluster_sizes if size > 1),
            "largest_component_size": max(cluster_sizes, default=0),
            "exact_functional_signature_count": len(signature_counts),
            "exact_duplicate_group_count": len(duplicate_group_sizes),
            "code_count_in_exact_duplicate_groups": sum(duplicate_group_sizes),
            "exact_duplicate_excess_code_count": sum(count - 1 for count in duplicate_group_sizes),
            "component_reduction_fraction": (
                1 - len(cluster_rows) / len(complete) if complete else 0.0
            ),
            "non_clique_component_count": non_clique_component_count,
            "minimum_nontrivial_component_pair_similarity": min(
                component_pair_minima, default=1.0
            ),
            "top20_objective_component_count": len(
                {cluster_by_code[item["code_hash"]] for item in top20}
            ),
            "multi_objective_component_count": sum(
                int(row["objective_distinct_count"]) > 1 for row in cluster_rows
            ),
            "ast_signature_count": len({item["ast_sha256"] for item in complete}),
        },
        "checks": {
            "candidate_count_matches_protocol": len(candidates) == expected_count,
            "all_probe_coordinates_complete": len(probe_rows)
            == int(protocol["failure_policy"]["expected_complete_route_coordinates"]),
            "all_codes_complete": len(complete) == len(candidates),
            "pair_count_matches_protocol": len(pair_rows)
            == int(protocol["failure_policy"]["expected_pair_count_if_complete"]),
        },
        "interpretation_guard": "连通分量允许相似链，不能理解为簇内任意两条代码都达到阈值。",
        "default_pool_behavior": "unchanged",
        "record_deletion": False,
    }
    summary_path = output_dir / "safe_pool_functional_redundancy_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"禁止覆盖已有结果：{summary_path}")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--safe-probe-results", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--cheap-probe-protocol", type=Path, required=True)
    parser.add_argument("--cheap-probe-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
