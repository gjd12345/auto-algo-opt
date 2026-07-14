#!/usr/bin/env python3
"""先冻结廉价合成探针的路线签名，再验证其对真实路线相似度的预测能力。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

import analyze_tsp_functional_diversity as diversity
import evaluate_tsp_archive_core12 as archive
import intervene_tsp_edge_variability as intervention


def load_protocol(args: argparse.Namespace, include_real: bool) -> dict[str, Any]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    checks = {
        "archive_metadata_sha256": intervention.sha256_file(args.archive_metadata),
        "code_catalog_sha256": intervention.sha256_file(args.code_catalog),
    }
    if include_real:
        checks["real_pairwise_similarity_sha256"] = intervention.sha256_file(
            args.real_pairwise_similarity
        )
    for key, actual in checks.items():
        if protocol["inputs"].get(key) != actual:
            raise RuntimeError(f"冻结输入 hash 不匹配：{key}")
    return protocol


def load_candidates(metadata_path: Path, catalog_path: Path) -> list[dict[str, Any]]:
    labels_by_hash = {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                labels_by_hash[item["code_hash"]] = item["label"]
    candidates = archive.resolve_archive_candidates(metadata_path, catalog_path)
    labeled = [{**item, "label": labels_by_hash[item["code_hash"]]} for item in candidates]
    if sorted(item["label"] for item in labeled) != ["AW1", "AW2", "AW3", "AW4", "R2", "R4"]:
        raise ValueError("冻结联合档案标签不完整")
    return sorted(labeled, key=lambda item: item["label"])


def generate_coords(probe: dict[str, Any], generator: dict[str, Any]) -> np.ndarray:
    rng = np.random.default_rng(int(probe["seed"]))
    node_count = int(probe["nodes"])
    geometry = probe["geometry"]
    if geometry == "uniform":
        coords = rng.uniform(0, 10000, size=(node_count, 2))
    elif geometry == "clustered":
        centers = rng.uniform(1500, 8500, size=(int(generator["cluster_count"]), 2))
        assignments = np.arange(node_count) % len(centers)
        rng.shuffle(assignments)
        coords = centers[assignments] + rng.normal(
            0, float(generator["cluster_sigma"]), size=(node_count, 2)
        )
        coords = np.clip(coords, 0, 10000)
    elif geometry == "ring":
        base_angles = 2 * np.pi * np.arange(node_count) / node_count
        angle_jitter = (
            2
            * np.pi
            / node_count
            * float(generator["ring_angular_jitter_fraction"])
        )
        angles = base_angles + rng.normal(0, angle_jitter, size=node_count)
        radii = float(generator["ring_radius"]) + rng.normal(
            0, float(generator["ring_radial_sigma"]), size=node_count
        )
        center = np.asarray(generator["ring_center"], dtype=float)
        coords = center + np.column_stack((np.cos(angles), np.sin(angles))) * radii[:, None]
        coords = np.clip(coords, 0, 10000)
    else:
        raise ValueError(f"未知探针几何：{geometry}")
    rounded = np.rint(coords).astype(np.int64)
    if len({tuple(row) for row in rounded.tolist()}) != node_count:
        raise RuntimeError(f"探针产生重复坐标：{probe['name']}")
    return rounded


def route_edges(route: np.ndarray) -> set[tuple[int, int]]:
    return {
        (min(int(left), int(right)), max(int(left), int(right)))
        for left, right in zip(route, np.roll(route, -1))
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"禁止覆盖已有探针产物：{path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_probe(args: argparse.Namespace) -> None:
    protocol = load_protocol(args, include_real=False)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_path = output_dir / "probe_pairwise_similarity.csv"
    if aggregate_path.exists():
        raise FileExistsError(f"探针相似度已存在：{aggregate_path}")

    candidates = load_candidates(args.archive_metadata, args.code_catalog)
    compiled = [(item, intervention.compile_heuristic(item["code"])) for item in candidates]
    labels = [item["label"] for item in candidates]
    probe_rows = []
    code_rows = []
    manifest_rows = []
    for probe in protocol["probes"]:
        coords = generate_coords(probe, protocol["generator"])
        coordinate_hash = hashlib.sha256(coords.tobytes()).hexdigest()
        manifest_rows.append({**probe, "coordinate_sha256": coordinate_hash})
        distances = intervention.build_distance_matrix(coords.astype(float))
        edges = {}
        for candidate, heuristic in compiled:
            route, cost = intervention.build_route(heuristic, distances)
            edges[candidate["label"]] = route_edges(route)
            code_rows.append(
                {
                    "probe": probe["name"],
                    "geometry": probe["geometry"],
                    "nodes": probe["nodes"],
                    "label": candidate["label"],
                    "tour_cost": cost,
                    "route_hash": intervention.route_hash(route),
                }
            )
        for left, right in itertools.combinations(labels, 2):
            probe_rows.append(
                {
                    "probe": probe["name"],
                    "left_label": left,
                    "right_label": right,
                    "edge_jaccard": len(edges[left] & edges[right])
                    / len(edges[left] | edges[right]),
                    "identical_route": edges[left] == edges[right],
                }
            )

    aggregate_rows = []
    for left, right in itertools.combinations(labels, 2):
        values = [
            float(row["edge_jaccard"])
            for row in probe_rows
            if row["left_label"] == left and row["right_label"] == right
        ]
        aggregate_rows.append(
            {
                "left_label": left,
                "right_label": right,
                "mean_probe_edge_jaccard": statistics.fmean(values),
                "median_probe_edge_jaccard": statistics.median(values),
                "min_probe_edge_jaccard": min(values),
                "max_probe_edge_jaccard": max(values),
                "identical_probe_count": sum(
                    row["identical_route"] == "True" or row["identical_route"] is True
                    for row in probe_rows
                    if row["left_label"] == left and row["right_label"] == right
                ),
                "predicted_redundant": statistics.fmean(values)
                >= float(protocol["signature"]["predicted_redundant_threshold"]),
            }
        )

    write_csv(output_dir / "probe_code_results.csv", code_rows)
    write_csv(output_dir / "probe_similarity_by_probe.csv", probe_rows)
    write_csv(aggregate_path, aggregate_rows)
    manifest_path = output_dir / "probe_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "tsp-cheap-functional-probe-manifest/v1",
                "protocol_sha256": intervention.sha256_file(args.protocol),
                "probes": manifest_rows,
                "probe_count": len(manifest_rows),
                "route_coordinate_count": len(code_rows),
                "pair_coordinate_count": len(probe_rows),
                "real_similarity_read": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    frozen = {
        "schema_version": "tsp-cheap-functional-probe-frozen/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "probe_manifest_sha256": intervention.sha256_file(manifest_path),
        "probe_pairwise_similarity_sha256": intervention.sha256_file(aggregate_path),
        "predicted_redundant_pairs": [
            f"{row['left_label']}/{row['right_label']}"
            for row in aggregate_rows
            if row["predicted_redundant"]
        ],
        "real_similarity_read": False,
        "next_action": "validate_once_with_expected_probe_sha256",
    }
    frozen_path = output_dir / "frozen_probe_summary.json"
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"PROBE_PAIRWISE_SHA256={frozen['probe_pairwise_similarity_sha256']}\n"
        f"PREDICTED_REDUNDANT_PAIRS={','.join(frozen['predicted_redundant_pairs'])}"
    )


def load_pairwise(path: Path, value_field: str) -> dict[tuple[str, str], float]:
    rows = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = tuple(sorted((row["left_label"], row["right_label"])))
            rows[key] = float(row[value_field])
    return rows


def run_validation(args: argparse.Namespace) -> None:
    protocol = load_protocol(args, include_real=True)
    probe_path = args.probe_pairwise_similarity.resolve()
    if intervention.sha256_file(probe_path) != args.expected_probe_sha256:
        raise RuntimeError("冻结探针相似度 hash 不匹配，禁止验证")
    output_path = args.output_dir.resolve() / "probe_validation_summary.json"
    if output_path.exists():
        raise FileExistsError(f"验证结果已存在：{output_path}")

    probe = load_pairwise(probe_path, "mean_probe_edge_jaccard")
    real = load_pairwise(args.real_pairwise_similarity, "mean_edge_jaccard")
    if set(probe) != set(real) or len(probe) != 15:
        raise ValueError("探针与真实代码对不一致")
    keys = sorted(probe)
    correlation = diversity.spearman([probe[key] for key in keys], [real[key] for key in keys])
    predicted_threshold = float(protocol["signature"]["predicted_redundant_threshold"])
    real_threshold = float(protocol["signature"]["real_redundant_threshold"])
    predicted = {key for key in keys if probe[key] >= predicted_threshold}
    actual = {key for key in keys if real[key] >= real_threshold}
    true_positive = len(predicted & actual)
    false_positive = len(predicted - actual)
    false_negative = len(actual - predicted)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(actual) if actual else 0.0
    gate = protocol["validation_gate"]
    checks = {
        "spearman": correlation >= gate["spearman_probe_vs_real_min"],
        "precision": precision >= gate["redundant_pair_precision_min"],
        "recall": recall >= gate["redundant_pair_recall_min"],
        "aw1_aw3_identical": probe[("AW1", "AW3")] == 1.0,
        "r2_r4_not_redundant": ("R2", "R4") not in predicted,
    }
    summary = {
        "schema_version": "tsp-cheap-functional-probe-validation/v1",
        "protocol_sha256": intervention.sha256_file(args.protocol),
        "probe_pairwise_similarity_sha256": intervention.sha256_file(probe_path),
        "real_pairwise_similarity_sha256": intervention.sha256_file(
            args.real_pairwise_similarity
        ),
        "metrics": {
            "pair_count": len(keys),
            "spearman_probe_vs_real": correlation,
            "predicted_redundant_pair_count": len(predicted),
            "real_redundant_pair_count": len(actual),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "true_negative": len(keys) - true_positive - false_positive - false_negative,
            "precision": precision,
            "recall": recall,
            "predicted_redundant_pairs": ["/".join(key) for key in sorted(predicted)],
            "real_redundant_pairs": ["/".join(key) for key in sorted(actual)],
        },
        "checks": checks,
        "decision": (
            "cheap_functional_signature_supported_for_offline_curation"
            if all(checks.values())
            else "cheap_functional_signature_research_only"
        ),
        "default_pool_behavior": "unchanged",
    }
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("probe", "validate"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--archive-metadata", type=Path, required=True)
    parser.add_argument("--code-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--real-pairwise-similarity", type=Path)
    parser.add_argument("--probe-pairwise-similarity", type=Path)
    parser.add_argument("--expected-probe-sha256")
    args = parser.parse_args()
    if args.phase == "validate" and (
        args.real_pairwise_similarity is None
        or args.probe_pairwise_similarity is None
        or not args.expected_probe_sha256
    ):
        parser.error("validate 必须提供真实相似度、冻结探针相似度及其预期 hash")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.phase == "probe":
        run_probe(parsed)
    else:
        run_validation(parsed)
