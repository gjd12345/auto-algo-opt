"""Multi-problem (CVRP / TSP / OBP) three-tier benchmark suite generators and registry builder.

Materializes all 13 Milestone-1 frozen benchmark suites + machine-readable
``published_results/*.json`` under ``benchmarks/cvrp_workbench/`` without
touching any byte of read-only ``benchmarks/eohs_v1/`` or ``reports/evidence/``.

Three benchmark tiers:
1. ``top_venue_protocol``: ``cvrp_ext_eohs_256``, ``cvrp_ext_reevo_scale``,
   ``tsp_ext_eohs_128``, ``obp_ext_eoh_weibull``
2. ``or_gold_standard``: ``cvrp_ext_cvrplib_abp_74``, ``cvrp_ext_cvrplib_x_100``,
   ``tsp_ext_tsplib_euc2d``, ``obp_ext_bpplib``
3. ``local_controlled``: ``cvrp_dev_hetero_24``, ``cvrp_select_multiscale_64``,
   ``cvrp_hist_p0_120``, ``cvrp_hist_hetero_288``, ``cvrp_final_accept_120``
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import pickle
import random
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from agent_skill_loop.benchmark.contracts import BenchmarkSpec, MetricSpec

from .protocol import compute_distance_matrix, normalize_routes, verify_cvrp_solution
from .published_results import materialize_published_results
from .solvers import evaluate_algorithm_on_instance
from .tsp_obp import compute_tsp_distance_matrix
from .upstream_rules import (
    UPSTREAM_BPPLIB_COMMIT,
    UPSTREAM_EOH_COMMIT,
    UPSTREAM_EOHS_COMMIT,
    UPSTREAM_REEVO_COMMIT,
)

_REPO = Path(__file__).resolve().parents[2]
BENCHMARK_ID = "cvrp_workbench_v1"
WORKBENCH_BENCHMARKS_DIR = _REPO / "benchmarks" / "cvrp_workbench"
MANIFESTS_DIR = WORKBENCH_BENCHMARKS_DIR / "manifests"
REGISTRY_PATH = WORKBENCH_BENCHMARKS_DIR / "registry.json"

FROZEN_P0_DIR = _REPO / "reports" / "evidence" / "cvrp_p0_p1_p2_20261107" / "p0"
SHARED_DIAGNOSTIC_6_PATH = _REPO / "reports" / "evidence" / "cvrp_super_agent_reference_20261107" / "dev_suite.json"
MATRIX_S2_PATH = _REPO / "experiments" / "cvrp_midterm" / "selection_s2" / "matrix_s2.json"

EXPECTED_HETERO_288_RAW_SHA256 = "1c7ee3a778433a98bac7e3f9e9e2b75dd96cfc822e20bdabd98e73b1453e12d6"
CAPACITY_LEVELS = {"loose": 45, "tight": 28}

# Official Heidelberg TSPLIB OPT values for all 18 EUC_2D instances with .opt.tour.gz
OFFICIAL_TSPLIB_OPT: dict[str, int] = {
    "a280": 2579,
    "berlin52": 7542,
    "ch130": 6110,
    "ch150": 6528,
    "eil101": 629,
    "eil51": 426,
    "eil76": 538,
    "kroA100": 21282,
    "kroC100": 20749,
    "kroD100": 21294,
    "lin105": 14379,
    "pcb442": 50778,
    "pr1002": 259045,
    "pr2392": 378032,
    "pr76": 108159,
    "rd100": 7910,
    "st70": 675,
    "tsp225": 3916,
}


def _seeded_rng(seed: int, cell: str, index: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{cell}|{index}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _gen_coords(spatial: str, rng: random.Random, size: int) -> list[list[float]]:
    if spatial == "uniform":
        return [[round(rng.random(), 8), round(rng.random(), 8)] for _ in range(size)]
    if spatial == "clustered":
        centres = [(rng.random(), rng.random()) for _ in range(4)]
        coords = []
        for _ in range(size):
            cx, cy = centres[rng.randrange(4)]
            coords.append([
                round(min(1.0, max(0.0, rng.gauss(cx, 0.06))), 8),
                round(min(1.0, max(0.0, rng.gauss(cy, 0.06))), 8),
            ])
        return coords
    if spatial == "mixed":
        n_cl = size // 2
        n_un = size - n_cl
        centres = [(rng.random(), rng.random()) for _ in range(4)]
        coords = []
        for _ in range(n_cl):
            cx, cy = centres[rng.randrange(4)]
            coords.append([
                round(min(1.0, max(0.0, rng.gauss(cx, 0.06))), 8),
                round(min(1.0, max(0.0, rng.gauss(cy, 0.06))), 8),
            ])
        for _ in range(n_un):
            coords.append([round(rng.random(), 8), round(rng.random(), 8)])
        rng.shuffle(coords)
        return coords
    raise ValueError(f"unsupported_spatial:{spatial}")


def _gen_demands(dist: str, rng: random.Random, size: int) -> list[int]:
    if dist == "uniform":
        return [rng.randint(1, 9) for _ in range(size)]
    if dist == "bimodal":
        choices = (1, 2, 8, 9)
        return [choices[rng.randrange(4)] for _ in range(size)]
    raise ValueError(f"unsupported_demand_dist:{dist}")


def _nn_reference(instance: Mapping[str, Any], distance_convention: str = "euc_2d_float") -> float:
    res = evaluate_algorithm_on_instance(
        "nn",
        instance,
        distance_convention=distance_convention,
        record_trace=False,
    )
    if not res["valid"] or res["tour_length"] is None:
        raise RuntimeError(f"nn_reference_failed:{instance.get('instance_id')}:{res}")
    return float(res["tour_length"])


def _attach_nn_references(instances: list[dict[str, Any]], distance_convention: str = "euc_2d_float") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for inst in instances:
        ref_val = _nn_reference(inst, distance_convention=distance_convention)
        enriched = dict(inst)
        enriched["reference_objective"] = ref_val
        enriched["reference_kind"] = "solver_reference"
        out.append(enriched)
    return out


def _scale_instance(inst: Mapping[str, Any], scale: float, suffix: str) -> dict[str, Any]:
    scaled = dict(inst)
    scaled["instance_id"] = f"{inst['instance_id']}__{suffix}"
    scaled["parent_instance_id"] = str(inst["instance_id"])
    scaled["coord_scale"] = float(scale)
    scaled["is_scale_stress"] = True
    scaled["depot"] = [round(float(x) * scale, 12) for x in inst["depot"]]
    scaled["customer_coordinates"] = [
        [round(float(x) * scale, 12), round(float(y) * scale, 12)]
        for x, y in inst["customer_coordinates"]
    ]
    if isinstance(inst.get("reference_objective"), (int, float)):
        scaled["reference_objective"] = float(inst["reference_objective"]) * float(scale)
    return scaled


# ---------------------------------------------------------------------------
# Tier 3: Local Controlled CVRP Suites (unchanged exact seeds & hashes)
# ---------------------------------------------------------------------------

def build_cvrp_dev_hetero_24(seed: int = 20261130) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_16 = [
        (sp, dp, cp, dd)
        for sp in ("uniform", "clustered")
        for dp in ("centre", "eccentric")
        for cp in ("loose", "tight")
        for dd in ("uniform", "bimodal")
    ]
    even_8 = [c for i, c in enumerate(base_16) if (bin(i).count("1") % 2) == 0]
    odd_8 = [c for i, c in enumerate(base_16) if (bin(i).count("1") % 2) == 1]
    design = [(50, *c) for c in even_8 + odd_8[:4]] + [(100, *c) for c in odd_8 + even_8[:4]]
    assert len(design) == 24

    instances: list[dict[str, Any]] = []
    for idx, (size, spatial, depot_style, cap_lvl, ddist) in enumerate(design):
        cell = f"n{size}_{spatial}_{depot_style}_{cap_lvl}_{ddist}"
        rng = _seeded_rng(seed, cell, idx)
        depot = [0.5, 0.5] if depot_style == "centre" else [0.05, 0.95]
        instances.append({
            "instance_id": f"dev24_{cell}-{idx:02d}",
            "cell": cell,
            "size": size,
            "spatial": spatial,
            "depot_style": depot_style,
            "capacity_level": cap_lvl,
            "demand_dist": ddist,
            "source_tag": "generated_dev_hetero_24",
            "depot": depot,
            "customer_coordinates": _gen_coords(spatial, rng, size),
            "demands": _gen_demands(ddist, rng, size),
            "capacity": CAPACITY_LEVELS[cap_lvl],
        })
    instances = _attach_nn_references(instances, distance_convention="euc_2d_float")
    stress_instances = [_scale_instance(instances[i], 1e-3, "scale_1e-3") for i in (0, 8, 12, 20)]
    return instances, stress_instances


def build_cvrp_select_multiscale_64(seed: int = 20261131) -> list[dict[str, Any]]:
    cells_spec: list[tuple[int, str, str, str, str]] = []
    for size in (50, 100):
        for spatial in ("uniform", "clustered", "mixed"):
            for depot_style in ("centre", "eccentric"):
                for cap_lvl in ("loose", "tight"):
                    for ddist in ("uniform", "bimodal"):
                        cells_spec.append((size, spatial, depot_style, cap_lvl, ddist))
    for i, (sp_base, dp, cp, dd) in enumerate(
        (sp, dp, cp, dd)
        for sp in ("uniform", "clustered")
        for dp in ("centre", "eccentric")
        for cp in ("loose", "tight")
        for dd in ("uniform", "bimodal")
    ):
        spatial = "mixed" if (i % 4 == 3) else sp_base
        cells_spec.append((200, spatial, dp, cp, dd))
    assert len(cells_spec) == 64

    instances: list[dict[str, Any]] = []
    for idx, (size, spatial, depot_style, cap_lvl, ddist) in enumerate(cells_spec):
        cell = f"n{size}_{spatial}_{depot_style}_{cap_lvl}_{ddist}"
        rng = _seeded_rng(seed, cell, idx)
        depot = [0.5, 0.5] if depot_style == "centre" else [0.05, 0.95]
        instances.append({
            "instance_id": f"sel64_{cell}-{idx:02d}",
            "cell": cell,
            "size": size,
            "spatial": spatial,
            "depot_style": depot_style,
            "capacity_level": cap_lvl,
            "demand_dist": ddist,
            "source_tag": "generated_select_multiscale_64",
            "depot": depot,
            "customer_coordinates": _gen_coords(spatial, rng, size),
            "demands": _gen_demands(ddist, rng, size),
            "capacity": CAPACITY_LEVELS[cap_lvl],
        })
    return _attach_nn_references(instances, distance_convention="euc_2d_float")


def build_cvrp_hist_p0_120() -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for size in (50, 100, 200):
        src = FROZEN_P0_DIR / f"suite_{size}.json"
        payload = json.loads(src.read_text(encoding="utf-8"))
        for raw in payload["instances"]:
            depot = [float(x) for x in raw["depot"]]
            depot_style = "centre" if math.hypot(depot[0] - 0.5, depot[1] - 0.5) < 0.25 else "eccentric"
            cap = int(raw["capacity"])
            instances.append({
                "instance_id": str(raw["instance_id"]),
                "cell": f"p0_n{size}_uniform_{depot_style}_q{cap}",
                "size": size,
                "spatial": "uniform",
                "depot_style": depot_style,
                "capacity_level": "medium" if cap == 40 else ("loose" if cap >= 45 else "tight"),
                "demand_dist": "uniform",
                "source_tag": "frozen_p0_120",
                "depot": depot,
                "customer_coordinates": [[float(x), float(y)] for x, y in raw["customer_coordinates"]],
                "demands": [int(d) for d in raw["demands"]],
                "capacity": cap,
            })
    assert len(instances) == 120
    return _attach_nn_references(instances, distance_convention="euc_2d_float")


def build_cvrp_hist_hetero_288() -> tuple[list[dict[str, Any]], str]:
    from experiments.cvrp_midterm.selection_s2.run_matrix_s2 import build_instances

    raw_instances = build_instances()
    assert len(raw_instances) == 288
    canonical_sha = hashlib.sha256(
        json.dumps(raw_instances, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if canonical_sha != EXPECTED_HETERO_288_RAW_SHA256:
        raise RuntimeError(
            f"hetero_288_canonical_sha_mismatch:{canonical_sha} != {EXPECTED_HETERO_288_RAW_SHA256}"
        )

    if MATRIX_S2_PATH.is_file():
        matrix_rows = json.loads(MATRIX_S2_PATH.read_text(encoding="utf-8"))
        matrix_ids = [str(r["instance_id"]) for r in matrix_rows]
        gen_ids = [str(r["instance_id"]) for r in raw_instances]
        if gen_ids != matrix_ids:
            raise RuntimeError("hetero_288_id_order_mismatch_vs_matrix_s2")

    enriched: list[dict[str, Any]] = []
    for raw in raw_instances:
        item = dict(raw)
        item["source_tag"] = "historical_hetero_288_seed_20261122"
        enriched.append(item)
    return _attach_nn_references(enriched, distance_convention="euc_2d_float"), canonical_sha


def build_cvrp_final_accept_120(seed: int = 20261201) -> list[dict[str, Any]]:
    base_16 = [
        (sp, dp, cp, dd)
        for sp in ("uniform", "clustered")
        for dp in ("centre", "eccentric")
        for cp in ("loose", "tight")
        for dd in ("uniform", "bimodal")
    ]
    mixed_8 = [
        ("mixed", dp, cp, dd)
        for dp in ("centre", "eccentric")
        for cp in ("loose", "tight")
        for dd in ("uniform", "bimodal")
    ]
    instances: list[dict[str, Any]] = []
    for size in (50, 100, 200):
        per_scale_idx = 0
        for sp, dp, cp, dd in base_16:
            cell = f"n{size}_{sp}_{dp}_{cp}_{dd}"
            for rep in range(2):
                rng = _seeded_rng(seed, f"final|{cell}", rep)
                depot = [0.5, 0.5] if dp == "centre" else [0.05, 0.95]
                instances.append({
                    "instance_id": f"accept120_{cell}-{rep}",
                    "cell": cell,
                    "size": size,
                    "spatial": sp,
                    "depot_style": dp,
                    "capacity_level": cp,
                    "demand_dist": dd,
                    "source_tag": "fresh_final_accept_120",
                    "depot": depot,
                    "customer_coordinates": _gen_coords(sp, rng, size),
                    "demands": _gen_demands(dd, rng, size),
                    "capacity": CAPACITY_LEVELS[cp],
                })
                per_scale_idx += 1
        for sp, dp, cp, dd in mixed_8:
            cell = f"n{size}_{sp}_{dp}_{cp}_{dd}"
            rng = _seeded_rng(seed, f"final|{cell}", 0)
            depot = [0.5, 0.5] if dp == "centre" else [0.05, 0.95]
            instances.append({
                "instance_id": f"accept120_{cell}-0",
                "cell": cell,
                "size": size,
                "spatial": sp,
                "depot_style": dp,
                "capacity_level": cp,
                "demand_dist": dd,
                "source_tag": "fresh_final_accept_120",
                "depot": depot,
                "customer_coordinates": _gen_coords(sp, rng, size),
                "demands": _gen_demands(dd, rng, size),
                "capacity": CAPACITY_LEVELS[cp],
            })
            per_scale_idx += 1
        assert per_scale_idx == 40
    assert len(instances) == 120
    return _attach_nn_references(instances, distance_convention="euc_2d_float")


# ---------------------------------------------------------------------------
# Tier 1: Top-Venue Protocol Suites (EoH-S / ReEvo / EoH / FunSearch)
# ---------------------------------------------------------------------------

def build_cvrp_ext_eohs_256(eohs_repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pkl_path = Path(eohs_repo_root) / "examples" / "training" / "cvrp_set" / "data_cvrp_10_150_256_withbaseline.pkl"
    if not pkl_path.is_file():
        raise FileNotFoundError(f"eohs_cvrp_dataset_not_found:{pkl_path}")
    raw_bytes = pkl_path.read_bytes()
    pkl_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    raw_data = pickle.loads(raw_bytes)
    instances: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_data):
        coords_arr, _dist_arr, demands_arr, cap_raw, baseline_raw = item
        coords = np.asarray(coords_arr, dtype=np.float64)
        demands = np.asarray(demands_arr, dtype=np.int64)
        n_cust = int(coords.shape[0] - 1)
        capacity = int(cap_raw)
        depot = [round(float(coords[0, 0]), 8), round(float(coords[0, 1]), 8)]
        cust_coords = [[round(float(coords[i, 0]), 8), round(float(coords[i, 1]), 8)] for i in range(1, n_cust + 1)]
        cust_demands = [int(demands[i]) for i in range(1, n_cust + 1)]
        depot_style = "centre" if math.hypot(depot[0] - 0.5, depot[1] - 0.5) < 0.25 else "eccentric"
        cap_lvl = "tight" if capacity <= 40 else ("medium" if capacity <= 90 else "loose")
        size_bin = "small" if n_cust <= 60 else ("medium" if n_cust <= 130 else "large")
        instances.append({
            "instance_id": f"eohs_cvrp_{idx:03d}_n{n_cust}_q{capacity}",
            "cell": f"eohs_{size_bin}_{depot_style}_{cap_lvl}",
            "size": n_cust,
            "spatial": "uniform",
            "depot_style": depot_style,
            "capacity_level": cap_lvl,
            "demand_dist": "eohs_skewed_1_9",
            "source_tag": "upstream_eohs_cvrp_256",
            "depot": depot,
            "customer_coordinates": cust_coords,
            "demands": cust_demands,
            "capacity": capacity,
            "reference_objective": float(baseline_raw),
            "reference_kind": "lkh_reference",
        })
    meta = {
        "upstream_paper": "EoH-S (Liu et al., AAAI 2026 / arXiv:2508.03082)",
        "upstream_repo": "https://github.com/FeiLiu36/EoH-S",
        "upstream_commit": UPSTREAM_EOHS_COMMIT,
        "download_date": "2026-11-21",
        "bks_version": "FeiLiu36/EoH-S@7d4b1f77 LKH baseline embedded in data_cvrp_10_150_256_withbaseline.pkl",
        "source_path": "examples/training/cvrp_set/data_cvrp_10_150_256_withbaseline.pkl",
        "source_sha256": pkl_sha256,
        "instance_count": len(instances),
    }
    return instances, meta


def build_cvrp_ext_reevo_scale() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """ReEvo (NeurIPS 2024, ai4co/reevo) multi-scale CVRP protocol (n=50/100/200, C=50, depot=[0.5,0.5])."""
    rng = np.random.default_rng(1234)
    instances: list[dict[str, Any]] = []
    for size in (50, 100, 200):
        for idx in range(16):
            coords = [[round(float(x), 8), round(float(y), 8)] for x, y in rng.random((size, 2))]
            demands = [int(d) for d in rng.integers(1, 10, size=size)]
            instances.append({
                "instance_id": f"reevo_cvrp_n{size}_{idx:02d}",
                "cell": f"reevo_n{size}_uniform_centre_q50",
                "size": size,
                "spatial": "uniform",
                "depot_style": "centre",
                "capacity_level": "q50",
                "demand_dist": "uniform_1_9",
                "source_tag": "reevo_cvrp_scale_protocol",
                "depot": [0.5, 0.5],
                "customer_coordinates": coords,
                "demands": demands,
                "capacity": 50,
            })
    instances = _attach_nn_references(instances, distance_convention="euc_2d_float")
    meta = {
        "upstream_paper": "ReEvo (Ye et al., NeurIPS 2024 / arXiv:2402.01145)",
        "upstream_repo": "https://github.com/ai4co/reevo",
        "upstream_commit": UPSTREAM_REEVO_COMMIT,
        "download_date": "2026-11-21",
        "bks_version": "Deterministic NN solver_reference on local CPU (ReEvo Table 3 NCO values kept separately in published_results/reevo_2024_tables.json)",
        "protocol": "Exact ai4co/reevo problems/cvrp_aco/gen_inst.py parameters: CAPACITY=50, DEPOT=[0.5,0.5], DEMAND in [1..9], n in {50,100,200} x 16 = 48 instances.",
        "instance_count": len(instances),
    }
    return instances, meta


def build_tsp_ext_eohs_128(eohs_repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import all 128 authentic EoH-S multi-distribution TSP instances with upstream LKH baselines."""
    tsp_dir = Path(eohs_repo_root) / "datasets" / "tsp"
    files = [
        ("dataset_tsp_3_0.03_32_training.pkl", "clusters3_std003"),
        ("dataset_tsp_3_0.07_32_training.pkl", "clusters3_std007"),
        ("dataset_tsp_10_0.03_32_training.pkl", "clusters10_std003"),
        ("dataset_tsp_10_0.07_32_training.pkl", "clusters10_std007"),
    ]
    instances: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    for fname, regime in files:
        p = tsp_dir / fname
        if not p.is_file():
            raise FileNotFoundError(f"eohs_tsp_dataset_not_found:{p}")
        raw = p.read_bytes()
        source_hashes[fname] = hashlib.sha256(raw).hexdigest()
        rows = pickle.loads(raw)
        for idx, (coords_arr, _dmat_arr, baseline_raw) in enumerate(rows):
            coords = [[round(float(x), 8), round(float(y), 8)] for x, y in np.asarray(coords_arr, dtype=np.float64)]
            n = len(coords)
            size_bin = "small" if n <= 60 else ("medium" if n <= 130 else "large")
            instances.append({
                "instance_id": f"eohs_tsp_{regime}_{idx:02d}_n{n}",
                "cell": f"eohs_tsp_{regime}_{size_bin}",
                "size": n,
                "spatial": regime,
                "source_tag": "upstream_eohs_tsp_128",
                "coordinates": coords,
                "reference_objective": float(baseline_raw),
                "reference_kind": "lkh_reference",
            })
    assert len(instances) == 128
    meta = {
        "upstream_paper": "EoH-S (Liu et al., AAAI 2026 / arXiv:2508.03082)",
        "upstream_repo": "https://github.com/FeiLiu36/EoH-S",
        "upstream_commit": UPSTREAM_EOHS_COMMIT,
        "download_date": "2026-11-21",
        "bks_version": "FeiLiu36/EoH-S@7d4b1f77 LKH reference embedded in datasets/tsp/*.pkl",
        "source_sha256s": source_hashes,
        "instance_count": len(instances),
    }
    return instances, meta


def build_obp_ext_eoh_weibull(eohs_repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import EoH-S 128 OBP training + 30 Weibull test (C=200/500) + 15 EoH Weibull C=100 instances."""
    obp_dir = Path(eohs_repo_root) / "datasets" / "obp"
    train_p = obp_dir / "dataset_100_2k_128_5_80_training.pkl"
    test_p = obp_dir / "dataset_testing.pkl"
    train_raw = train_p.read_bytes()
    test_raw = test_p.read_bytes()
    train_doc = pickle.loads(train_raw)
    test_doc = pickle.loads(test_raw)

    instances: list[dict[str, Any]] = []
    # 1. All 128 EoH-S training instances
    for key in sorted(train_doc.keys(), key=lambda s: int(s.split("_")[-1])):
        rec = train_doc[key]
        cap = int(rec["capacity"])
        items = [int(x) for x in rec["items"]]
        l1 = int(math.ceil(sum(items) / cap - 1e-12))
        instances.append({
            "instance_id": f"eohs_obp_train_{key}",
            "cell": f"eohs_train_c{cap}",
            "obp_regime": "EoH-S_Train_128",
            "size": len(items),
            "capacity": cap,
            "weibull_shape": float(rec.get("weibull_shape") or 0.0),
            "weibull_scale": float(rec.get("weibull_scale") or 0.0),
            "source_tag": "upstream_eohs_obp_train128",
            "items": items,
            "l1_lower_bound": l1,
            "reference_objective": float(l1),
            "reference_kind": "theoretical_lb",
        })

    # 2. All 30 authentic EoH-S Weibull test instances (1k / 5k / 10k x C=200, 500)
    for key, rec in sorted(test_doc.items()):
        if not key.startswith("instance_weibull_"):
            continue
        cap = int(rec["capacity"])
        items = [int(x) for x in rec["items"]]
        l1 = int(math.ceil(sum(items) / cap - 1e-12))
        n = len(items)
        instances.append({
            "instance_id": f"eohs_obp_{key}",
            "cell": f"weibull_n{n}_c{cap}",
            "obp_regime": f"Weibull_{n//1000}k_C{cap}",
            "size": n,
            "capacity": cap,
            "weibull_shape": float(rec.get("weibull_shape") or 3.0),
            "weibull_scale": float(rec.get("weibull_scale") or 45.0),
            "source_tag": "upstream_eohs_obp_weibull_test",
            "items": items,
            "l1_lower_bound": l1,
            "reference_objective": float(l1),
            "reference_kind": "theoretical_lb",
        })

    # 3. 15 EoH / FunSearch Weibull C=100 instances (1k / 5k / 10k x 5, shape=3, scale=45, max=100)
    rng = np.random.default_rng(20240101)
    for n in (1000, 5000, 10000):
        for rep in range(5):
            samples = np.clip(rng.weibull(3.0, n) * 45.0, 1.0, 100.0)
            items = [max(1, int(round(float(x)))) for x in samples]
            cap = 100
            l1 = int(math.ceil(sum(items) / cap - 1e-12))
            instances.append({
                "instance_id": f"eoh_obp_weibull_{n}_100_{rep}",
                "cell": f"weibull_n{n}_c100",
                "obp_regime": f"Weibull_{n//1000}k_C100",
                "size": n,
                "capacity": cap,
                "weibull_shape": 3.0,
                "weibull_scale": 45.0,
                "source_tag": "eoh_funsearch_weibull_c100",
                "items": items,
                "l1_lower_bound": l1,
                "reference_objective": float(l1),
                "reference_kind": "theoretical_lb",
            })

    meta = {
        "upstream_paper": "FunSearch (Nature 2024) / EoH (ICML 2024) / EoH-S (AAAI 2026)",
        "upstream_repo": "https://github.com/FeiLiu36/EoH-S",
        "upstream_commit": UPSTREAM_EOHS_COMMIT,
        "download_date": "2026-11-21",
        "bks_version": "Theoretical L1 lower bound ceil(sum(items)/C)",
        "source_sha256s": {
            "dataset_100_2k_128_5_80_training.pkl": hashlib.sha256(train_raw).hexdigest(),
            "dataset_testing.pkl": hashlib.sha256(test_raw).hexdigest(),
        },
        "instance_count": len(instances),
    }
    return instances, meta


# ---------------------------------------------------------------------------
# Tier 2: OR Gold Standard Libraries (CVRPLib A/B/P 74, Set X 100, TSPLIB 18, BPPLib 70)
# ---------------------------------------------------------------------------

def _parse_k_vehicles(name: str) -> int | None:
    m = re.search(r"-k(\d+)$", name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _x_size_tier(n_cust: int) -> str:
    if n_cust <= 250:
        return "X-S (100-250)"
    if n_cust <= 500:
        return "X-M (251-500)"
    return "X-L (501-1000)"


def _import_cvrplib_sets(
    cvrplib_repo_root: Path,
    sets: Sequence[str],
    *,
    strict_zero_header_error: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import vrplib

    root = Path(cvrplib_repo_root)
    if not root.is_dir():
        raise FileNotFoundError(f"cvrplib_root_not_found:{root}")

    instances: list[dict[str, Any]] = []
    discrepancies: list[dict[str, Any]] = []
    set_counts: dict[str, int] = {}

    for set_name in sets:
        inst_dir = root / set_name / "Instances"
        vrps = sorted(inst_dir.glob("*.vrp"))
        sol_map = {p.stem: p for p in (root / set_name).rglob("*.sol")}
        count = 0
        for vp in vrps:
            stem = vp.stem
            sp = sol_map.get(stem)
            if sp is None:
                raise FileNotFoundError(f"missing_sol_for:{stem}")
            parsed = vrplib.read_instance(vp, compute_edge_weights=False)
            sol = vrplib.read_solution(sp)
            coords = np.asarray(parsed["node_coord"], dtype=np.float64)
            demands = np.asarray(parsed["demand"], dtype=np.int64)
            capacity = int(parsed["capacity"])
            n_cust = int(coords.shape[0] - 1)
            depot = [float(coords[0, 0]), float(coords[0, 1])]
            cust_coords = [[float(coords[i, 0]), float(coords[i, 1])] for i in range(1, n_cust + 1)]
            cust_demands = [int(demands[i]) for i in range(1, n_cust + 1)]

            dmat_nint = compute_distance_matrix(depot, cust_coords, distance_convention="euc_2d_nint")
            bks_routes_raw = [[int(c) for c in r] for r in sol["routes"]]
            # Repair two known 1995 Augerat Set B archive .sol defects so all 74/74 Set A/B/P
            # routes are 100% feasible and match official BKS (1312 and 1153) with 0.0 error:
            # 1) B-n50-k8.sol Route #3 starts with customer 2 (duplicating customer 2 on Route #6
            #    and omitting customer 3; length 1319). Restoring first customer 2 -> 3 per the
            #    published optimal solution yields a feasible solution of exact length 1312.
            # 2) B-n57-k7.sol Route #5 [37, 39, 52, 50, 42, 30, 2, 55, 1] is un-2-opted (length 1155);
            #    restoring the 2-opt+relocate optimal sequence [52, 50, 37, 39, 42, 30, 2, 55, 1]
            #    yields a feasible solution of exact official optimal length 1153.
            bks_repair_note: str | None = None
            if stem == "B-n50-k8" and len(bks_routes_raw) >= 3 and bks_routes_raw[2] and bks_routes_raw[2][0] == 2:
                bks_routes_raw[2] = [3] + bks_routes_raw[2][1:]
                bks_repair_note = "Repaired upstream B-n50-k8.sol Route #3 archive typo (first customer 2 -> 3, fixing duplicate node 2 / missing node 3); feasible euc_2d_nint cost = 1312 == official BKS."
                discrepancies.append({
                    "instance_id": stem,
                    "set": set_name,
                    "bks_reported_cost": float(sol["cost"]),
                    "bks_archive_raw_cost": 1319.0,
                    "bks_recomputed_nint_cost": 1312.0,
                    "note": bks_repair_note,
                })
            elif stem == "B-n57-k7":
                for r_idx, raw_r in enumerate(bks_routes_raw):
                    if raw_r == [37, 39, 52, 50, 42, 30, 2, 55, 1]:
                        bks_routes_raw[r_idx] = [52, 50, 37, 39, 42, 30, 2, 55, 1]
                        break
                bks_repair_note = "Repaired upstream B-n57-k7.sol Route #5 archive sequence ([37,39,52,50,42,30,2,55,1] -> [52,50,37,39,42,30,2,55,1], 1155 -> 1153); feasible euc_2d_nint cost = 1153 == official BKS."
                discrepancies.append({
                    "instance_id": stem,
                    "set": set_name,
                    "bks_reported_cost": float(sol["cost"]),
                    "bks_archive_raw_cost": 1155.0,
                    "bks_recomputed_nint_cost": 1153.0,
                    "note": bks_repair_note,
                })

            bks_routes = normalize_routes(bks_routes_raw)
            recomputed_bks = float(
                sum(dmat_nint[a, b] for r in bks_routes for a, b in zip(r[:-1], r[1:]))
            )
            reported_bks = float(sol["cost"])
            if abs(recomputed_bks - reported_bks) > 1e-6:
                raise RuntimeError(f"cvrplib_sol_nint_mismatch:{stem}:{recomputed_bks}!={reported_bks}")

            ver = verify_cvrp_solution(
                {
                    "depot": depot,
                    "customer_coordinates": cust_coords,
                    "demands": cust_demands,
                    "capacity": capacity,
                },
                bks_routes,
                distance_convention="euc_2d_nint",
            )
            if not ver["valid"]:
                raise RuntimeError(f"cvrplib_bks_route_infeasible:{stem}:{ver['error_code']}")

            k_veh = _parse_k_vehicles(stem)
            xs, ys = coords[:, 0], coords[:, 1]
            cx = (float(xs.min()) + float(xs.max())) * 0.5
            cy = (float(ys.min()) + float(ys.max())) * 0.5
            span = max(float(xs.max() - xs.min()), float(ys.max() - ys.min()), 1e-9)
            dep_norm_d = math.hypot(depot[0] - cx, depot[1] - cy) / span
            depot_style = "centre" if dep_norm_d < 0.2 else "eccentric"
            size_bin = "small" if n_cust <= 60 else ("medium" if n_cust <= 200 else ("large" if n_cust <= 500 else "xlarge"))
            entry: dict[str, Any] = {
                "instance_id": stem,
                "cvrplib_set": set_name,
                "cell": f"cvrplib_{set_name}_{size_bin}",
                "size": n_cust,
                "spatial": "cvrplib_real",
                "depot_style": depot_style,
                "capacity_level": f"Q{capacity}",
                "demand_dist": "cvrplib_standard",
                "source_tag": f"cvrplib_set_{set_name}",
                "edge_weight_type": str(parsed.get("edge_weight_type", "EUC_2D")),
                "k_vehicles": k_veh,
                "bks_routes_count": len(bks_routes),
                "bks_routes": bks_routes,
                "bks_reported_cost": reported_bks,
                "bks_recomputed_nint_cost": recomputed_bks,
                "raw_vrp_sha256": hashlib.sha256(vp.read_bytes()).hexdigest(),
                "raw_sol_sha256": hashlib.sha256(sp.read_bytes()).hexdigest(),
                "depot": depot,
                "customer_coordinates": cust_coords,
                "demands": cust_demands,
                "capacity": capacity,
                "reference_objective": recomputed_bks,
                "reference_kind": "best_known",
            }
            if set_name == "X":
                entry["x_tier"] = _x_size_tier(n_cust)
            instances.append(entry)
            count += 1
        set_counts[set_name] = count

    meta = {
        "upstream_repo": "https://github.com/vidalt/CVRPLIB",
        "upstream_commit": "34985dd200238b69b8eb18abb8e4b0f6fd8b9257",
        "download_date": "2026-11-21",
        "bks_version": "vidalt/CVRPLIB@34985dd2 (official CVRPLib .sol files)",
        "distance_convention": "euc_2d_nint (TSPLIB floor(sqrt(dx^2+dy^2)+0.5))",
        "set_counts": set_counts,
        "bks_nint_discrepancies": discrepancies,
        "sol_recompute_zero_error_count": len(instances),
        "instance_count": len(instances),
    }
    return instances, meta


def build_cvrp_ext_cvrplib_abp_74(cvrplib_repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    instances, meta = _import_cvrplib_sets(cvrplib_repo_root, ("A", "B", "P"), strict_zero_header_error=False)
    assert len(instances) == 74
    meta["upstream_paper"] = "Augerat et al. (1995), CVRPLib Sets A (27), B (23), P (24)"
    return instances, meta


def build_cvrp_ext_cvrplib_x_100(cvrplib_repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    instances, meta = _import_cvrplib_sets(cvrplib_repo_root, ("X",), strict_zero_header_error=True)
    assert len(instances) == 100
    meta["upstream_paper"] = "Uchoa et al. (2017 EJOR), CVRPLib Set X (all 100 instances, n=100..1000)"
    meta["x_tier_counts"] = {
        tier: sum(1 for inst in instances if inst["x_tier"] == tier)
        for tier in ("X-S (100-250)", "X-M (251-500)", "X-L (501-1000)")
    }
    return instances, meta


def build_tsp_ext_tsplib_euc2d(eoh_repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import all 18 classic TSPLIB EUC_2D instances with official .opt.tour.gz & verify 0.0 OPT error."""
    tsp_dir = Path(eoh_repo_root) / "examples" / "tsp_gls_numba" / "evaluation" / "ALL_tsp"
    if not tsp_dir.is_dir():
        raise FileNotFoundError(f"tsplib_dir_not_found:{tsp_dir}")

    instances: list[dict[str, Any]] = []
    for name in sorted(OFFICIAL_TSPLIB_OPT.keys(), key=lambda k: (int(re.search(r"\d+", k).group(0)), k)):
        tspp = tsp_dir / f"{name}.tsp.gz"
        optp = tsp_dir / f"{name}.opt.tour.gz"
        raw_tsp_bytes = tspp.read_bytes()
        raw_opt_bytes = optp.read_bytes()
        lines = gzip.decompress(raw_tsp_bytes).decode("latin-1").splitlines()
        coords: list[list[float]] = []
        in_sec = False
        for line in lines:
            s = line.strip()
            if s.startswith("NODE_COORD_SECTION"):
                in_sec = True
                continue
            if s == "EOF" or (in_sec and not s):
                break
            if in_sec:
                parts = s.split()
                if len(parts) >= 3:
                    coords.append([float(parts[1]), float(parts[2])])

        tlines = gzip.decompress(raw_opt_bytes).decode("latin-1").splitlines()
        opt_tour: list[int] = []
        in_t = False
        for line in tlines:
            s = line.strip()
            if s.startswith("TOUR_SECTION"):
                in_t = True
                continue
            if s == "-1" or s == "EOF":
                break
            if in_t:
                for tok in s.split():
                    v = int(tok)
                    if v == -1:
                        break
                    opt_tour.append(v - 1)

        dmat = compute_tsp_distance_matrix(coords, distance_convention="euc_2d_nint")
        n = len(opt_tour)
        recomputed_opt = int(sum(dmat[opt_tour[i], opt_tour[(i + 1) % n]] for i in range(n)))
        official_opt = OFFICIAL_TSPLIB_OPT[name]
        if recomputed_opt != official_opt:
            raise RuntimeError(f"tsplib_opt_mismatch:{name}:{recomputed_opt}!={official_opt}")

        size_bin = "small" if n <= 100 else ("medium" if n <= 300 else "large")
        instances.append({
            "instance_id": name,
            "cell": f"tsplib_euc2d_{size_bin}",
            "size": n,
            "spatial": "tsplib_real",
            "edge_weight_type": "EUC_2D",
            "source_tag": "tsplib_official_euc2d",
            "coordinates": coords,
            "opt_tour": opt_tour,
            "opt_recomputed_nint": recomputed_opt,
            "raw_tsp_sha256": hashlib.sha256(raw_tsp_bytes).hexdigest(),
            "raw_opt_sha256": hashlib.sha256(raw_opt_bytes).hexdigest(),
            "reference_objective": float(official_opt),
            "reference_kind": "best_known",
        })

    meta = {
        "upstream_paper": "Reinelt (1991), TSPLIB — A Traveling Salesman Problem Library",
        "upstream_repo": "https://github.com/FeiLiu36/EoH",
        "upstream_commit": UPSTREAM_EOH_COMMIT,
        "download_date": "2026-11-21",
        "bks_version": "Official Heidelberg TSPLIB95 .opt.tour.gz (18/18 exact euc_2d_nint zero-error verified)",
        "distance_convention": "euc_2d_nint (TSPLIB floor(sqrt(dx^2+dy^2)+0.5))",
        "opt_recompute_zero_error_count": len(instances),
        "instance_count": len(instances),
    }
    return instances, meta


def _parse_bpplib_solutions_xlsx(xlsx_path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not xlsx_path.is_file():
        return out
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(xlsx_path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        sheets = [s.attrib["name"] for s in wb.findall(".//m:sheet", ns)]
        ss: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.findall(".//m:si", ns):
                ss.append("".join(t.text or "" for t in si.findall(".//m:t", ns)))
        for idx, sname in enumerate(sheets, 1):
            if not any(k in sname.lower() for k in ("scholl", "hard")):
                continue
            root = ET.fromstring(zf.read(f"xl/worksheets/sheet{idx}.xml"))
            for row in root.findall(".//m:row", ns)[1:]:
                vals: list[str] = []
                for c in row.findall("m:c", ns):
                    t = c.attrib.get("t")
                    v = c.find("m:v", ns)
                    val = v.text if v is not None else ""
                    if t == "s" and val.isdigit():
                        val = ss[int(val)]
                    vals.append(val)
                if len(vals) >= 4 and vals[0]:
                    stem = Path(vals[0]).stem
                    try:
                        lb = int(float(vals[1]))
                        ub = int(float(vals[2]))
                    except ValueError:
                        continue
                    out[stem] = {"opt_lb": lb, "opt_ub": ub, "status": vals[3]}
    return out


def build_obp_ext_bpplib(
    bpplib_extracted_root: Path,
    solutions_xlsx_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Import authentic Delorme BPPLIB Sch_1 (24), Sch_2 (24), and Scholl_H (10 Scholl_3 + 12 Hard28 = 22)."""
    root = Path(bpplib_extracted_root)
    sol_map = _parse_bpplib_solutions_xlsx(solutions_xlsx_path)

    sch1_all = sorted((root / "Scholl" / "Scholl_1").glob("*.txt"))
    sch2_all = sorted((root / "Scholl" / "Scholl_2").glob("*.txt"))
    sch3_all = sorted((root / "Scholl" / "Scholl_3").glob("*.txt"))
    hard28_all = sorted((root / "Hard28").glob("*.txt"))
    if not sch1_all or not sch2_all or not sch3_all:
        raise FileNotFoundError(f"bpplib_extracted_incomplete:{root}")

    # Deterministic evenly stratified picks covering all N/C/W classes in Sch_1 & Sch_2
    def _stratified(files: list[Path], k: int) -> list[Path]:
        step = max(1, len(files) // k)
        return [files[min(len(files) - 1, i * step)] for i in range(k)]

    selected: list[tuple[str, Path]] = (
        [("Sch_1", p) for p in _stratified(sch1_all, 24)]
        + [("Sch_2", p) for p in _stratified(sch2_all, 24)]
        + [("Scholl_H", p) for p in sch3_all]
        + [("Scholl_H", p) for p in _stratified(hard28_all, 12)]
    )

    instances: list[dict[str, Any]] = []
    subset_counts: dict[str, int] = {"Sch_1": 0, "Sch_2": 0, "Scholl_H": 0}
    for subset, path in selected:
        raw_bytes = path.read_bytes()
        nums = [int(tok) for tok in raw_bytes.decode("utf-8", errors="ignore").split()]
        n_items = nums[0]
        capacity = nums[1]
        items_sorted = nums[2 : 2 + n_items]
        if len(items_sorted) != n_items:
            raise ValueError(f"bpplib_parse_mismatch:{path}:{len(items_sorted)}!={n_items}")
        # Deterministic online arrival order seeded from filename SHA-256 (avoids descending offline bias)
        seed_int = int(hashlib.sha256(path.stem.encode("utf-8")).hexdigest()[:16], 16)
        rng = random.Random(seed_int)
        items_online = list(items_sorted)
        rng.shuffle(items_online)

        l1_lb = int(math.ceil(sum(items_online) / capacity - 1e-12))
        sol_info = sol_map.get(path.stem, {})
        instances.append({
            "instance_id": f"bpplib_{subset}_{path.stem}",
            "bpplib_subset": subset,
            "obp_regime": f"BPPLib_{subset}",
            "cell": f"bpplib_{subset}_c{capacity}",
            "size": n_items,
            "capacity": capacity,
            "source_tag": f"bpplib_{subset.lower()}",
            "raw_txt_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "items": items_online,
            "l1_lower_bound": l1_lb,
            "known_optimum_bins": sol_info.get("opt_ub"),
            "optimum_status": sol_info.get("status", "unknown"),
            "reference_objective": float(l1_lb),
            "reference_kind": "theoretical_lb",
        })
        subset_counts[subset] += 1

    meta = {
        "upstream_paper": "Delorme, Iori & Martello (2018 INFORMS JOC), BPPLIB (Scholl 1997 / Hard28)",
        "upstream_repo": "https://github.com/mdelorme2/BPPLIB",
        "upstream_commit": UPSTREAM_BPPLIB_COMMIT,
        "download_date": "2026-11-21",
        "bks_version": "mdelorme2/BPPLIB Solutions.xlsx exact OPT + L1 lower bound (EoH-S Table 3 online protocol)",
        "subset_counts": subset_counts,
        "online_order_note": "Raw BPPLIB .txt files list items in descending order; each instance is deterministically permuted via SHA-256(name) for fair online arrival evaluation.",
        "instance_count": len(instances),
    }
    return instances, meta


def load_shared_diagnostic_6() -> list[dict[str, Any]]:
    payload = json.loads(SHARED_DIAGNOSTIC_6_PATH.read_text(encoding="utf-8"))
    instances: list[dict[str, Any]] = []
    for raw in payload["instances"]:
        instances.append({
            "instance_id": str(raw["instance_id"]),
            "cell": "shared6_n50_uniform_centre_q40",
            "size": len(raw["customer_coordinates"]),
            "spatial": "uniform",
            "depot_style": "centre",
            "capacity_level": "medium",
            "demand_dist": "uniform",
            "source_tag": "shared_diagnostic_6",
            "depot": [float(x) for x in raw["depot"]],
            "customer_coordinates": [[float(x), float(y)] for x, y in raw["customer_coordinates"]],
            "demands": [int(d) for d in raw["demands"]],
            "capacity": int(raw["capacity"]),
        })
    return _attach_nn_references(instances, distance_convention="euc_2d_float")


def _write_lf_json(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_compact_lf_json(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lock_sentinel(profile: str, split: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "algorithm-optimization-benchmark-lock/v1",
        "benchmark_id": BENCHMARK_ID,
        "profile": profile,
        "split": split,
        "locked": True,
        "reason": reason,
    }


def materialize_cvrp_workbench_registry(
    *,
    eohs_repo_root: Path,
    cvrplib_repo_root: Path,
    eoh_repo_root: Path,
    bpplib_extracted_root: Path,
    bpplib_solutions_xlsx: Path,
    output_dir: Path = WORKBENCH_BENCHMARKS_DIR,
) -> dict[str, Any]:
    """Generate and freeze all 13 multi-problem suites, published_results/*.json, and registry.json."""
    manifests_dir = output_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    # 1. Materialize published_results/*.json first so registry.json binds exact SHA-256 hashes
    pub_info = materialize_published_results(output_dir)

    # 2. Build all 13 suites across 3 tiers and 3 problem families
    dev24, dev24_stress = build_cvrp_dev_hetero_24()
    sel64 = build_cvrp_select_multiscale_64()
    p0_120 = build_cvrp_hist_p0_120()
    hetero288, hetero288_raw_sha = build_cvrp_hist_hetero_288()
    accept120 = build_cvrp_final_accept_120()
    eohs_cvrp_256, eohs_cvrp_meta = build_cvrp_ext_eohs_256(eohs_repo_root)
    reevo_cvrp_48, reevo_cvrp_meta = build_cvrp_ext_reevo_scale()
    cvrplib_abp_74, cvrplib_abp_meta = build_cvrp_ext_cvrplib_abp_74(cvrplib_repo_root)
    cvrplib_x_100, cvrplib_x_meta = build_cvrp_ext_cvrplib_x_100(cvrplib_repo_root)
    tsp_eohs_128, tsp_eohs_meta = build_tsp_ext_eohs_128(eohs_repo_root)
    tsp_tsplib_18, tsp_tsplib_meta = build_tsp_ext_tsplib_euc2d(eoh_repo_root)
    obp_weibull_173, obp_weibull_meta = build_obp_ext_eoh_weibull(eohs_repo_root)
    obp_bpplib_70, obp_bpplib_meta = build_obp_ext_bpplib(bpplib_extracted_root, bpplib_solutions_xlsx)

    suite_defs: list[dict[str, Any]] = [
        # ---- TIER 1: Top-Venue Protocol ----
        {
            "profile": "cvrp_ext_eohs_256",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "top_venue_protocol",
            "primary_split": "heldout",
            "suite_role": "external_top_venue",
            "exposure_status": "public_standard",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "lkh_reference",
            "asset_status": "original_verified",
            "upstream_repo": eohs_cvrp_meta["upstream_repo"],
            "upstream_commit": eohs_cvrp_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "eohs_2025_tables_1_3.json",
            "instances": eohs_cvrp_256,
            "metadata": eohs_cvrp_meta,
            "deviations": ["imported verbatim from FeiLiu36/EoH-S data_cvrp_10_150_256_withbaseline.pkl (256 instances, euc_2d_float, LKH baseline)"],
        },
        {
            "profile": "cvrp_ext_reevo_scale",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "top_venue_protocol",
            "primary_split": "heldout",
            "suite_role": "external_top_venue",
            "exposure_status": "public_standard",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "solver_reference",
            "asset_status": "regenerated_protocol_compatible",
            "upstream_repo": reevo_cvrp_meta["upstream_repo"],
            "upstream_commit": reevo_cvrp_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "reevo_2024_tables.json",
            "instances": reevo_cvrp_48,
            "metadata": reevo_cvrp_meta,
            "deviations": ["aligned to ai4co/reevo CVRP C=50, depot=[0.5,0.5], n in {50,100,200}; local baseline uses NN solver_reference while ReEvo Table 3 NCO reference stays in published_results/reevo_2024_tables.json"],
        },
        {
            "profile": "tsp_ext_eohs_128",
            "problem_id": "tsp_construct",
            "problem_family": "tsp",
            "benchmark_tier": "top_venue_protocol",
            "primary_split": "heldout",
            "suite_role": "external_top_venue",
            "exposure_status": "public_standard",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "not_applicable",
            "reference_kind": "lkh_reference",
            "asset_status": "original_verified",
            "upstream_repo": tsp_eohs_meta["upstream_repo"],
            "upstream_commit": tsp_eohs_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "eohs_2025_tables_1_3.json",
            "instances": tsp_eohs_128,
            "metadata": tsp_eohs_meta,
            "deviations": ["imported verbatim from FeiLiu36/EoH-S datasets/tsp/*.pkl (4 cluster regimes x 32 = 128 instances with LKH baseline)"],
        },
        {
            "profile": "obp_ext_eoh_weibull",
            "problem_id": "obp_online",
            "problem_family": "obp",
            "benchmark_tier": "top_venue_protocol",
            "primary_split": "heldout",
            "suite_role": "external_top_venue",
            "exposure_status": "public_standard",
            "distance_convention": "not_applicable",
            "vehicle_limit_policy": "not_applicable",
            "reference_kind": "theoretical_lb",
            "asset_status": "original_verified",
            "upstream_repo": obp_weibull_meta["upstream_repo"],
            "upstream_commit": obp_weibull_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "funsearch_eoh_2024_tables.json",
            "instances": obp_weibull_173,
            "metadata": obp_weibull_meta,
            "compact_manifest": True,
            "deviations": ["combines EoH-S 128 OBP training + 30 EoH-S Weibull test (1k/5k/10k x C=200,500) + 15 EoH/FunSearch Weibull C=100 (1k/5k/10k) = 173 instances"],
        },
        # ---- TIER 2: OR Gold Standard Libraries ----
        {
            "profile": "cvrp_ext_cvrplib_abp_74",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "or_gold_standard",
            "primary_split": "heldout",
            "suite_role": "external_or_standard",
            "exposure_status": "public_standard",
            "distance_convention": "euc_2d_nint",
            "vehicle_limit_policy": "min_vehicles_advisory",
            "reference_kind": "best_known",
            "asset_status": "original_verified",
            "upstream_repo": cvrplib_abp_meta["upstream_repo"],
            "upstream_commit": cvrplib_abp_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "eohs_2025_tables_1_3.json",
            "instances": cvrplib_abp_74,
            "metadata": cvrplib_abp_meta,
            "deviations": ["full CVRPLib Augerat Set A (27) + Set B (23) + Set P (24) = 74 instances with official .sol routes verified to 0.0 euc_2d_nint error"],
        },
        {
            "profile": "cvrp_ext_cvrplib_x_100",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "or_gold_standard",
            "primary_split": "heldout",
            "suite_role": "external_or_standard",
            "exposure_status": "public_standard",
            "distance_convention": "euc_2d_nint",
            "vehicle_limit_policy": "min_vehicles_advisory",
            "reference_kind": "best_known",
            "asset_status": "original_verified",
            "upstream_repo": cvrplib_x_meta["upstream_repo"],
            "upstream_commit": cvrplib_x_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "eohs_2025_tables_1_3.json",
            "instances": cvrplib_x_100,
            "metadata": cvrplib_x_meta,
            "compact_manifest": True,
            "deviations": ["complete Uchoa et al. 2017 Set X (all 100 instances, n=100..1000, X-S/X-M/X-L tiers) with 100/100 official .sol routes verified to strict 0.0 euc_2d_nint error"],
        },
        {
            "profile": "tsp_ext_tsplib_euc2d",
            "problem_id": "tsp_construct",
            "problem_family": "tsp",
            "benchmark_tier": "or_gold_standard",
            "primary_split": "heldout",
            "suite_role": "external_or_standard",
            "exposure_status": "public_standard",
            "distance_convention": "euc_2d_nint",
            "vehicle_limit_policy": "not_applicable",
            "reference_kind": "best_known",
            "asset_status": "original_verified",
            "upstream_repo": tsp_tsplib_meta["upstream_repo"],
            "upstream_commit": tsp_tsplib_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "heuragenix_cobench_2025_tables.json",
            "instances": tsp_tsplib_18,
            "metadata": tsp_tsplib_meta,
            "compact_manifest": True,
            "deviations": ["18 classic TSPLIB EUC_2D instances (eil51..pr2392) with official .opt.tour.gz verified 18/18 to strict 0.0 euc_2d_nint OPT error"],
        },
        {
            "profile": "obp_ext_bpplib",
            "problem_id": "obp_online",
            "problem_family": "obp",
            "benchmark_tier": "or_gold_standard",
            "primary_split": "heldout",
            "suite_role": "external_or_standard",
            "exposure_status": "public_standard",
            "distance_convention": "not_applicable",
            "vehicle_limit_policy": "not_applicable",
            "reference_kind": "theoretical_lb",
            "asset_status": "original_verified",
            "upstream_repo": obp_bpplib_meta["upstream_repo"],
            "upstream_commit": obp_bpplib_meta["upstream_commit"],
            "heldout_policy": "open_public_standard",
            "published_file": "eohs_2025_tables_1_3.json",
            "instances": obp_bpplib_70,
            "metadata": obp_bpplib_meta,
            "compact_manifest": True,
            "deviations": ["authentic Delorme BPPLIB Sch_1 (24) + Sch_2 (24) + Scholl_H (10 Scholl_3 + 12 Hard28) = 70 instances with deterministic online arrival permutation & Solutions.xlsx OPT"],
        },
        # ---- TIER 3: Local Controlled CVRP Suites ----
        {
            "profile": "cvrp_dev_hetero_24",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "local_controlled",
            "primary_split": "dev_train",
            "suite_role": "dev_search",
            "exposure_status": "fresh_isolated",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "solver_reference",
            "asset_status": "regenerated_protocol_compatible",
            "upstream_repo": "https://github.com/gjd12345/auto-algo-opt",
            "upstream_commit": "5215ebd",
            "heldout_policy": "locked_no_access_diagnostic",
            "instances": dev24,
            "scale_stress_instances": dev24_stress,
            "metadata": {
                "seed": 20261130,
                "description": "24-instance stratified 5-factor dev search suite + 4 paired 1e-3 scale-stress checks.",
                "scale_stress_count": len(dev24_stress),
            },
            "deviations": ["independent seed 20261130 disjoint from cvrp_construct_mini, P0-120, ana72, and hetero-288"],
        },
        {
            "profile": "cvrp_select_multiscale_64",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "local_controlled",
            "primary_split": "selection",
            "suite_role": "selection_tuning",
            "exposure_status": "fresh_isolated",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "solver_reference",
            "asset_status": "regenerated_protocol_compatible",
            "upstream_repo": "https://github.com/gjd12345/auto-algo-opt",
            "upstream_commit": "5215ebd",
            "heldout_policy": "locked_no_access_diagnostic",
            "instances": sel64,
            "metadata": {
                "seed": 20261131,
                "description": "64-instance multi-scale selection & selector-training suite covering uniform/clustered/mixed and n in {50,100,200}.",
            },
            "deviations": ["registered with an independent selection split and selection_manifest_hash separate from dev_train and heldout"],
        },
        {
            "profile": "cvrp_hist_p0_120",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "local_controlled",
            "primary_split": "heldout",
            "suite_role": "historical_regression",
            "exposure_status": "historically_exposed",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "solver_reference",
            "asset_status": "original_verified",
            "upstream_repo": "https://github.com/gjd12345/auto-algo-opt",
            "upstream_commit": "5215ebd",
            "heldout_policy": "open_historical_regression",
            "instances": p0_120,
            "metadata": {
                "source_files": [
                    "reports/evidence/cvrp_p0_p1_p2_20261107/p0/suite_50.json",
                    "reports/evidence/cvrp_p0_p1_p2_20261107/p0/suite_100.json",
                    "reports/evidence/cvrp_p0_p1_p2_20261107/p0/suite_200.json",
                ],
                "description": "Historically evaluated Stage-2 P0-120 blind suite (n=50/100/200 x 40) preserved for exact regression alignment.",
            },
            "deviations": ["historically evaluated in Stage-2 midterm reporting; retained as a regression benchmark rather than a fresh blind test"],
        },
        {
            "profile": "cvrp_hist_hetero_288",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "local_controlled",
            "primary_split": "heldout",
            "suite_role": "historical_regression",
            "exposure_status": "historically_exposed",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "solver_reference",
            "asset_status": "original_verified",
            "upstream_repo": "https://github.com/gjd12345/auto-algo-opt",
            "upstream_commit": "5215ebd",
            "heldout_policy": "open_historical_regression",
            "instances": hetero288,
            "metadata": {
                "seed": 20261122,
                "canonical_raw_instances_sha256": hetero288_raw_sha,
                "generator": "experiments/cvrp_midterm/selection_s2/run_matrix_s2.py:build_instances",
                "description": "Full coordinate/depot/demand snapshot of the 288-instance 5-factor Direction-2 regression suite (48 cells x 6).",
            },
            "deviations": [
                "historically exposed to Direction-2 RF/ridge/pairwise out-of-fold evaluation; must not be treated as a fresh blind acceptance set",
                f"canonical raw instances SHA-256 verified as {hetero288_raw_sha}",
            ],
        },
        {
            "profile": "cvrp_final_accept_120",
            "problem_id": "cvrp_construct",
            "problem_family": "cvrp",
            "benchmark_tier": "local_controlled",
            "primary_split": "heldout",
            "suite_role": "final_acceptance",
            "exposure_status": "fresh_isolated",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "solver_reference",
            "asset_status": "original_verified",
            "upstream_repo": "https://github.com/gjd12345/auto-algo-opt",
            "upstream_commit": "5215ebd",
            "heldout_policy": "open_final_acceptance",
            "instances": accept120,
            "metadata": {
                "seed": 20261201,
                "description": "Fresh strictly isolated 120-instance multi-scale 5-factor final acceptance suite (n=50/100/200 x 40).",
            },
            "deviations": ["generated with brand-new independent seed 20261201; evaluated only after solver pool and selectors are frozen"],
        },
    ]

    registry_entries: list[dict[str, Any]] = []
    for cfg in suite_defs:
        profile = cfg["profile"]
        primary_split = cfg["primary_split"]
        instances = cfg["instances"]
        ref_kind = cfg["reference_kind"]
        problem_id = cfg["problem_id"]
        writer = _write_compact_lf_json if cfg.get("compact_manifest") else _write_lf_json

        ref_manifest = {
            "schema_version": "algorithm-optimization-benchmark-reference-manifest/v1",
            "benchmark_id": BENCHMARK_ID,
            "profile": profile,
            "problem": problem_id,
            "problem_family": cfg["problem_family"],
            "reference_kind": ref_kind,
            "distance_convention": cfg["distance_convention"],
            "instances": {inst["instance_id"]: inst["reference_objective"] for inst in instances},
        }
        ref_rel = f"manifests/{profile}_references.json"
        ref_hash = _write_lf_json(output_dir / ref_rel, ref_manifest)

        manifest_payload: dict[str, Any] = {
            "schema_version": "algorithm-optimization-benchmark-manifest/v1",
            "benchmark_id": BENCHMARK_ID,
            "profile": profile,
            "problem": problem_id,
            "problem_family": cfg["problem_family"],
            "benchmark_tier": cfg["benchmark_tier"],
            "split": primary_split,
            "suite_role": cfg["suite_role"],
            "exposure_status": cfg["exposure_status"],
            "distance_convention": cfg["distance_convention"],
            "vehicle_limit_policy": cfg["vehicle_limit_policy"],
            "reference_kind": ref_kind,
            "metadata": cfg["metadata"],
            "instances": instances,
        }
        if "scale_stress_instances" in cfg:
            manifest_payload["scale_stress_instances"] = cfg["scale_stress_instances"]

        manifest_paths: dict[str, str] = {"reference": ref_rel}
        manifest_hashes: dict[str, str] = {"reference_hash": ref_hash}

        if primary_split == "dev_train":
            train_rel = f"manifests/{profile}_train.json"
            train_hash = writer(output_dir / train_rel, manifest_payload)
            lock_rel = f"manifests/{profile}_heldout_locked.json"
            lock_hash = _write_lf_json(output_dir / lock_rel, _lock_sentinel(profile, "heldout", "dev_search_suite_only"))
            manifest_paths.update({"dev_train": train_rel, "train": train_rel, "heldout": lock_rel, "test": lock_rel})
            manifest_hashes.update({"train_hash": train_hash, "test_hash": lock_hash})
        elif primary_split == "selection":
            sel_rel = f"manifests/{profile}_selection.json"
            sel_hash = writer(output_dir / sel_rel, manifest_payload)
            train_lock_rel = f"manifests/{profile}_train_locked.json"
            train_lock_hash = _write_lf_json(output_dir / train_lock_rel, _lock_sentinel(profile, "dev_train", "selection_split_only"))
            test_lock_rel = f"manifests/{profile}_heldout_locked.json"
            test_lock_hash = _write_lf_json(output_dir / test_lock_rel, _lock_sentinel(profile, "heldout", "selection_split_only"))
            manifest_paths.update({
                "dev_train": train_lock_rel,
                "train": train_lock_rel,
                "selection": sel_rel,
                "heldout": test_lock_rel,
                "test": test_lock_rel,
            })
            manifest_hashes.update({
                "train_hash": train_lock_hash,
                "selection_hash": sel_hash,
                "test_hash": test_lock_hash,
            })
        else:
            test_rel = f"manifests/{profile}_heldout.json"
            test_hash = writer(output_dir / test_rel, manifest_payload)
            train_lock_rel = f"manifests/{profile}_train_locked.json"
            train_lock_hash = _write_lf_json(output_dir / train_lock_rel, _lock_sentinel(profile, "dev_train", f"{cfg['suite_role']}_heldout_only"))
            manifest_paths.update({"dev_train": train_lock_rel, "train": train_lock_rel, "heldout": test_rel, "test": test_rel})
            manifest_hashes.update({"train_hash": train_lock_hash, "test_hash": test_hash})

        pub_path = None
        pub_hash = None
        if cfg.get("published_file") and cfg["published_file"] in pub_info:
            pub_path = pub_info[cfg["published_file"]]["rel_path"]
            pub_hash = pub_info[cfg["published_file"]]["sha256"]

        metric = MetricSpec(
            metric_id="instance_relative_gap",
            version="v1",
            direction="minimize",
            aggregation="mean_instance_relative_gap",
            reference_kind=ref_kind,
            reference_manifest_hash=ref_hash,
            config={
                "numerator": "raw_objective-reference_objective",
                "denominator": "reference_objective",
                "distance_convention": cfg["distance_convention"],
                "vehicle_limit_policy": cfg["vehicle_limit_policy"],
            },
        )
        spec = BenchmarkSpec(
            benchmark_id=BENCHMARK_ID,
            profile=profile,
            problem_id=problem_id,
            upstream_repo=cfg["upstream_repo"],
            upstream_commit=cfg["upstream_commit"],
            train_manifest_hash=manifest_hashes["train_hash"],
            test_manifest_hash=manifest_hashes["test_hash"],
            reference_manifest_hash=ref_hash,
            metric_spec_hash=metric.content_hash,
            asset_status=cfg["asset_status"],
            upstream_code_profile=f"{cfg['problem_family']}_workbench",
            paper_protocol_profile=cfg["suite_role"],
            deviations=tuple(cfg["deviations"]),
            selection_manifest_hash=manifest_hashes.get("selection_hash"),
            suite_role=cfg["suite_role"],
            exposure_status=cfg["exposure_status"],
            distance_convention=cfg["distance_convention"],
            vehicle_limit_policy=cfg["vehicle_limit_policy"],
            problem_family=cfg["problem_family"],
            benchmark_tier=cfg["benchmark_tier"],
            published_results_path=pub_path,
            published_results_hash=pub_hash,
        )

        entry_obj: dict[str, Any] = {
            "benchmark_id": BENCHMARK_ID,
            "profile": profile,
            "problem_id": problem_id,
            "problem_family": cfg["problem_family"],
            "benchmark_tier": cfg["benchmark_tier"],
            "primary_split": primary_split,
            "suite_role": cfg["suite_role"],
            "exposure_status": cfg["exposure_status"],
            "distance_convention": cfg["distance_convention"],
            "vehicle_limit_policy": cfg["vehicle_limit_policy"],
            "instance_count": len(instances),
            "upstream_repo": cfg["upstream_repo"],
            "upstream_commit": cfg["upstream_commit"],
            "asset_status": cfg["asset_status"],
            "upstream_code_profile": f"{cfg['problem_family']}_workbench",
            "paper_protocol_profile": cfg["suite_role"],
            "heldout_policy": cfg["heldout_policy"],
            "manifest_paths": manifest_paths,
            "manifests": manifest_hashes,
            "metric_spec_hash": metric.content_hash,
            "metric_spec": metric.as_dict(),
            "benchmark_spec_hash": spec.content_hash,
            "deviations": cfg["deviations"],
        }
        if pub_path is not None:
            entry_obj["published_results_path"] = pub_path
            entry_obj["published_results_hash"] = pub_hash
        registry_entries.append(entry_obj)

    registry = {
        "schema_version": "algorithm-optimization-benchmark-registry/v1.3",
        "benchmark_id": BENCHMARK_ID,
        "published_results_index_path": pub_info["index.json"]["rel_path"],
        "published_results_index_hash": pub_info["index.json"]["sha256"],
        "published_results_files": pub_info,
        "benchmarks": registry_entries,
    }
    reg_hash = _write_lf_json(output_dir / "registry.json", registry)
    return {
        "ok": True,
        "registry_path": str(output_dir / "registry.json"),
        "registry_sha256": reg_hash,
        "suite_count": len(registry_entries),
        "published_results_files": pub_info,
        "suites": [
            {
                "profile": e["profile"],
                "problem_family": e["problem_family"],
                "benchmark_tier": e["benchmark_tier"],
                "suite_role": e["suite_role"],
                "exposure_status": e["exposure_status"],
                "primary_split": e["primary_split"],
                "instance_count": e["instance_count"],
                "distance_convention": e["distance_convention"],
                "reference_kind": e["metric_spec"]["reference_kind"],
            }
            for e in registry_entries
        ],
    }
