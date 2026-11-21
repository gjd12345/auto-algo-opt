"""Stage 2 Track B: Multi-scale 5-factor CVRP performance matrix (288 instances).

Five orthogonal factors crossed (seed 20261122, completely disjoint from Stage 1
seed 20261121, cvrp_construct_mini, and frozen P0 held-out suites):
    size         in {50, 100, 200}
    spatial      in {uniform, clustered}   (4 Gaussian clusters, sigma=0.06)
    depot        in {centre (0.5,0.5), eccentric (0.05,0.95)}
    capacity     in {loose 45, tight 28}
    demand_dist  in {uniform U{1..9}, bimodal {1,2,8,9}}  (both exact mean 5.0)

48 cells x 6 instances = 288 instances.

Includes:
- 8 pointwise constructive rules: nn, savings, dd_load, radial, plus frozen PoC
  rules A, B, C, V0 (all SHA-256 verified against reports/evidence/cvrp_p0_p1_p2_20261107).
- Optional extra rules from `extra_rules.json` (used in Stage 2C to close the
  Direction 1 -> Direction 2 loop without modifying this script).
- Classic parallel Clarke-Wright merge (`cw_merge`) evaluated as a separate
  non-pointwise reference column (NOT mixed into pointwise VBS/SBS).
- 12 pre-solve instance features + measured feature extraction time `feat_s`.
- Pure pre-compiled solve time `{rule}_solve_s` (best of 3 repeats after warmup)
  and exact AST/safety verification via frozen `evaluator.evaluate_candidate_request`.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402
from agent_skill_loop.problems.cvrp import suite_hash  # noqa: E402

OUT = REPO / "experiments/cvrp_midterm/selection_s2"
EXTRA_RULES_PATH = OUT / "extra_rules.json"
FROZEN_P0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code"
FROZEN_V0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p1/V0.py"

SEED = 20261122
PER_CELL = 6

FROZEN_SHA256 = {
    "a": "ccdab29f7d08ab162145ae7e468e47a5488b696d9a644bb7e793ab5c2665a866",
    "b": "68cd510af3df75d8f1b45182b248f07d7e38cedc4bfc1d74f5669a6b9ad81727",
    "c": "141d99b6f7c62e60313feb2c520889a957da9ae00fd5138798f4de3c30e25627",
}

BASE_ALGORITHMS = {
    "nn": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])
""",
    "savings": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node]
    dep = distance_matrix[depot]
    saving = cur[depot] + dep[unvisited_nodes] - cur[unvisited_nodes]
    top = saving.max()
    tied = unvisited_nodes[saving == top]
    if tied.size > 1:
        return int(tied[np.argmax(dep[tied])])
    return int(unvisited_nodes[np.argmax(saving)])
""",
    "dd_load": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    slack = (rest_capacity - dem) / max(rest_capacity, 1e-9)
    score = cur - 0.15 * dep - 0.1 * (1.0 - slack) * dep
    return int(unvisited_nodes[np.argmin(score)])
""",
    "radial": """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    score = cur - 2.0 * dep + 0.02 * demands[unvisited_nodes]
    return int(unvisited_nodes[np.argmin(score)])
""",
}

FACTORS = {
    "size": (50, 100, 200),
    "spatial": ("uniform", "clustered"),
    "depot": ("centre", "eccentric"),
    "capacity": ("loose", "tight"),
    "demand_dist": ("uniform", "bimodal"),
}
CAPACITY_LEVELS = {"loose": 45, "tight": 28}
FEATURE_NAMES = (
    "mean_demand",
    "cv_demand",
    "capacity_ratio",
    "cluster_tendency",
    "radial_std",
    "depot_eccentricity",
    "x_spread",
    "y_spread",
    "log_n",
    "demand_bimodality",
    "nn_dist_cv",
    "depot_angle_disp",
)


def load_all_algorithms() -> tuple[dict[str, str], dict[str, dict], list[str]]:
    algos = dict(BASE_ALGORITHMS)
    provenance: dict[str, dict] = {}
    for name in ("a", "b", "c"):
        path = FROZEN_P0 / f"{name.upper()}.py"
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != FROZEN_SHA256[name]:
            raise SystemExit(f"Frozen {name.upper()} hash mismatch: {digest}")
        algos[name] = raw.decode("utf-8")
        provenance[name] = {
            "path": str(path.relative_to(REPO)).replace("\\", "/"),
            "sha256": digest,
            "bytes": len(raw),
        }
    v0_raw = FROZEN_V0.read_bytes()
    algos["v0"] = v0_raw.decode("utf-8")
    provenance["v0"] = {
        "path": str(FROZEN_V0.relative_to(REPO)).replace("\\", "/"),
        "sha256": hashlib.sha256(v0_raw).hexdigest(),
        "bytes": len(v0_raw),
    }
    extra_names: list[str] = []
    if EXTRA_RULES_PATH.is_file():
        extra_spec = json.loads(EXTRA_RULES_PATH.read_text(encoding="utf-8"))
        for item in extra_spec.get("rules", []):
            rname = str(item["name"])
            rpath = (REPO / item["path"]).resolve()
            raw = rpath.read_bytes()
            algos[rname] = raw.decode("utf-8")
            extra_names.append(rname)
            provenance[rname] = {
                "path": str(rpath.relative_to(REPO)).replace("\\", "/"),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "origin": item.get("origin", "stage2_search"),
            }
    return algos, provenance, extra_names


def _rng(seed: int, cell: str, index: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{cell}|{index}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _coords(spatial: str, rng: random.Random, size: int) -> list[list[float]]:
    if spatial == "uniform":
        return [[rng.random(), rng.random()] for _ in range(size)]
    if spatial == "clustered":
        centres = [(rng.random(), rng.random()) for _ in range(4)]
        coords = []
        for _ in range(size):
            cx, cy = centres[rng.randrange(4)]
            coords.append([
                min(1.0, max(0.0, rng.gauss(cx, 0.06))),
                min(1.0, max(0.0, rng.gauss(cy, 0.06))),
            ])
        return coords
    raise ValueError(spatial)


def _demands(dist: str, rng: random.Random, size: int) -> list[int]:
    if dist == "uniform":
        return [rng.randint(1, 9) for _ in range(size)]
    if dist == "bimodal":
        choices = (1, 2, 8, 9)
        return [choices[rng.randrange(4)] for _ in range(size)]
    raise ValueError(dist)


def build_instances() -> list[dict]:
    out: list[dict] = []
    for size in FACTORS["size"]:
        for spatial in FACTORS["spatial"]:
            for depot in FACTORS["depot"]:
                for cap in FACTORS["capacity"]:
                    for ddist in FACTORS["demand_dist"]:
                        cell = f"n{size}_{spatial}_{depot}_{cap}_{ddist}"
                        for idx in range(PER_CELL):
                            rng = _rng(SEED, cell, idx)
                            coords = _coords(spatial, rng, size)
                            dep = [0.5, 0.5] if depot == "centre" else [0.05, 0.95]
                            out.append({
                                "instance_id": f"{cell}-{idx}",
                                "cell": cell,
                                "size": size,
                                "spatial": spatial,
                                "depot_style": depot,
                                "capacity_level": cap,
                                "demand_dist": ddist,
                                "depot": dep,
                                "customer_coordinates": [[round(x, 8), round(y, 8)] for x, y in coords],
                                "demands": _demands(ddist, rng, size),
                                "capacity": CAPACITY_LEVELS[cap],
                            })
    return out


def extract_features(inst: dict) -> tuple[dict[str, float], float]:
    t0 = time.perf_counter()
    depot = np.asarray(inst["depot"], dtype=float)
    coords = np.asarray(inst["customer_coordinates"], dtype=float)
    demands = np.asarray(inst["demands"], dtype=float)
    n = coords.shape[0]
    diff_dep = coords - depot
    dist_depot = np.linalg.norm(diff_dep, axis=1)
    dmat = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
    np.fill_diagonal(dmat, np.inf)
    nearest = dmat.min(axis=1)
    mean_pair = float(dmat[dmat != np.inf].mean())
    unit_vec = diff_dep / np.maximum(dist_depot[:, None], 1e-12)
    resultant = float(np.linalg.norm(unit_vec.mean(axis=0)))
    feats = {
        "mean_demand": float(demands.mean()),
        "cv_demand": float(demands.std() / max(float(demands.mean()), 1e-9)),
        "capacity_ratio": float(demands.sum() / inst["capacity"]),
        "cluster_tendency": float(nearest.mean() / max(mean_pair, 1e-9)),
        "radial_std": float(dist_depot.std()),
        "depot_eccentricity": float(dist_depot.mean()),
        "x_spread": float(coords[:, 0].std()),
        "y_spread": float(coords[:, 1].std()),
        "log_n": float(math.log(n)),
        "demand_bimodality": float(np.mean((demands <= 2) | (demands >= 8))),
        "nn_dist_cv": float(nearest.std() / max(float(nearest.mean()), 1e-9)),
        "depot_angle_disp": float(max(0.0, 1.0 - resultant)),
    }
    elapsed = time.perf_counter() - t0
    return feats, elapsed


def solve_clarke_wright_parallel(inst: dict) -> float:
    """Classic parallel Clarke-Wright savings merge (exact non-pointwise CVRP reference)."""
    depot = np.asarray(inst["depot"], dtype=float)
    coords = np.asarray(inst["customer_coordinates"], dtype=float)
    points = np.vstack([depot, coords])
    dmat = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    dem = [0.0] + [float(d) for d in inst["demands"]]
    cap = float(inst["capacity"])
    n = len(inst["demands"])

    # Vectorized upper-triangle savings computation
    iu, ju = np.triu_indices(n, k=1)
    i_idx = iu + 1
    j_idx = ju + 1
    sav = dmat[0, i_idx] + dmat[0, j_idx] - dmat[i_idx, j_idx]
    pos = sav > 1e-12
    i_idx, j_idx, sav = i_idx[pos], j_idx[pos], sav[pos]
    order = np.argsort(-sav, kind="mergesort")

    routes: dict[int, list[int]] = {i: [i] for i in range(1, n + 1)}
    route_load: dict[int, float] = {i: dem[i] for i in range(1, n + 1)}
    owner: list[int] = list(range(n + 1))

    for k in order:
        i = int(i_idx[k])
        j = int(j_idx[k])
        ri = owner[i]
        rj = owner[j]
        if ri == rj:
            continue
        if route_load[ri] + route_load[rj] > cap + 1e-12:
            continue
        seq_i = routes[ri]
        seq_j = routes[rj]
        # Both i and j must be route endpoints
        i_start = seq_i[0] == i
        i_end = seq_i[-1] == i
        j_start = seq_j[0] == j
        j_end = seq_j[-1] == j
        if not ((i_start or i_end) and (j_start or j_end)):
            continue
        if i_start and not i_end:
            seq_i = seq_i[::-1]
        if j_end and not j_start:
            seq_j = seq_j[::-1]
        merged = seq_i + seq_j
        routes[ri] = merged
        route_load[ri] += route_load[rj]
        for node in seq_j:
            owner[node] = ri
        del routes[rj]
        del route_load[rj]

    # Exact objective + feasibility check
    visited = 0
    total = 0.0
    for rid, seq in routes.items():
        if route_load[rid] > cap + 1e-9:
            raise RuntimeError("CW capacity violation")
        visited += len(seq)
        total += float(dmat[0, seq[0]]) + float(dmat[seq[-1], 0])
        for a, b in zip(seq[:-1], seq[1:]):
            total += float(dmat[a, b])
    if visited != n:
        raise RuntimeError(f"CW visit mismatch: {visited} != {n}")
    return total


def compile_rule(code: str, name: str):
    ns = {"np": np, "numpy": np, "math": math}
    exec(compile(code, f"rule_{name}", "exec"), ns)  # noqa: S102
    return ns["select_next_node"]


def verify_and_eval_rule(name: str, code: str, instances: list[dict], repeats: int = 3) -> tuple[list[float], list[float]]:
    # 1. Verify AST/sandbox contract via frozen evaluator on first 3 instances (one per scale)
    sample = [instances[0], instances[96], instances[192]]
    suite = {"problem": "cvrp_construct", "split": "dev_train", "instances": sample}
    suite["content_hash"] = suite_hash("cvrp_construct", "dev_train", sample)
    res = evaluator.evaluate_candidate_request({"problem": "cvrp_construct", "suite": suite, "code": code})
    if not res["valid"]:
        raise RuntimeError(f"Rule {name} failed frozen evaluator validation: {res}")

    fn = compile_rule(code, name)
    # Warm-up
    evaluator._evaluate_cvrp_instances(fn, [instances[0]])

    objs: list[float] = []
    times: list[float] = []
    for inst in instances:
        best_t = float("inf")
        obj = 0.0
        for _ in range(repeats):
            t0 = time.perf_counter()
            vals, _ = evaluator._evaluate_cvrp_instances(fn, [inst])
            obj = float(vals[0])
            dt = time.perf_counter() - t0
            if dt < best_t:
                best_t = dt
        objs.append(obj)
        times.append(best_t)

    # Spot-check exact match with frozen evaluator sample
    sample_mean = float(np.mean([objs[0], objs[96], objs[192]]))
    if abs(sample_mean - float(res["objective"])) > 1e-9:
        raise RuntimeError(f"Rule {name} objective mismatch: {sample_mean} vs {res['objective']}")
    return objs, times


def portfolio_summary(rows: list[dict], members: list[str]) -> dict:
    totals = {n: float(sum(float(r[n]) for r in rows)) for n in members}
    best = min(members, key=lambda n: totals[n])
    vbs = float(sum(min(float(r[n]) for n in members) for r in rows))
    counts = {n: 0 for n in members}
    for r in rows:
        counts[min(members, key=lambda n: (float(r[n]), n))] += 1
    headroom = totals[best] - vbs
    return {
        "instances": len(rows),
        "members": list(members),
        "vbs": round(vbs, 4),
        "sbs": round(totals[best], 4),
        "sbs_algorithm": best,
        "sbs_gap_to_vbs": round(headroom / vbs, 6),
        "headroom": round(headroom, 4),
        "oracle_counts": {k: v for k, v in counts.items() if v},
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    algos, provenance, extra_names = load_all_algorithms()
    instances = build_instances()
    base_members = ["nn", "savings", "dd_load", "radial", "a", "b", "c", "v0"]
    all_members = base_members + extra_names

    # Evaluate all pointwise rules
    rule_objs: dict[str, list[float]] = {}
    rule_times: dict[str, list[float]] = {}
    for name in all_members:
        objs, times = verify_and_eval_rule(name, algos[name], instances, repeats=3)
        rule_objs[name] = objs
        rule_times[name] = times

    # Evaluate classic parallel Clarke-Wright merge reference
    solve_clarke_wright_parallel(instances[0])  # warmup
    cw_objs: list[float] = []
    cw_times: list[float] = []
    for inst in instances:
        best_t = float("inf")
        val = 0.0
        for _ in range(3):
            t0 = time.perf_counter()
            val = solve_clarke_wright_parallel(inst)
            dt = time.perf_counter() - t0
            if dt < best_t:
                best_t = dt
        cw_objs.append(val)
        cw_times.append(best_t)

    # Extract features (warmup + best of 2 for timing stability)
    extract_features(instances[0])
    rows: list[dict] = []
    for idx, inst in enumerate(instances):
        f1, t1 = extract_features(inst)
        _, t2 = extract_features(inst)
        feat_s = min(t1, t2)
        row: dict = {
            "instance_id": inst["instance_id"],
            "cell": inst["cell"],
            "size": inst["size"],
            "spatial": inst["spatial"],
            "depot_style": inst["depot_style"],
            "capacity_level": inst["capacity_level"],
            "demand_dist": inst["demand_dist"],
            "capacity": inst["capacity"],
            "feat_s": round(feat_s, 6),
            **f1,
        }
        for name in all_members:
            row[name] = round(rule_objs[name][idx], 6)
            row[f"{name}_solve_s"] = round(rule_times[name][idx], 6)
        row["cw_merge"] = round(cw_objs[idx], 6)
        row["cw_merge_solve_s"] = round(cw_times[idx], 6)
        for name in all_members:
            row[f"{name}_rank"] = 1 + sum(
                1 for other in all_members if row[other] < row[name] - 1e-12
            )
        row["oracle_base"] = min(base_members, key=lambda n: (row[n], n))
        row["oracle_all"] = min(all_members, key=lambda n: (row[n], n))
        rows.append(row)

    (OUT / "matrix_s2.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (OUT / "matrix_s2.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    portfolios_def = {"pointwise_base": base_members}
    if extra_names:
        portfolios_def["pointwise_plus_s2"] = all_members

    by_scale: dict[str, dict] = {}
    for sz in FACTORS["size"]:
        sub = [r for r in rows if r["size"] == sz]
        by_scale[str(sz)] = {
            "instances": len(sub),
            "rule_mean": {n: round(float(np.mean([r[n] for r in sub])), 4) for n in all_members},
            "rule_mean_rank": {n: round(float(np.mean([r[f"{n}_rank"] for r in sub])), 3) for n in all_members},
            "rule_mean_solve_ms": {n: round(1000.0 * float(np.mean([r[f"{n}_solve_s"] for r in sub])), 3) for n in all_members},
            "cw_merge_mean": round(float(np.mean([r["cw_merge"] for r in sub])), 4),
            "cw_merge_solve_ms": round(1000.0 * float(np.mean([r["cw_merge_solve_s"] for r in sub])), 3),
            "feat_ms": round(1000.0 * float(np.mean([r["feat_s"] for r in sub])), 3),
            "portfolios": {p: portfolio_summary(sub, m) for p, m in portfolios_def.items()},
        }

    by_spatial: dict[str, dict] = {}
    for sp in FACTORS["spatial"]:
        sub = [r for r in rows if r["spatial"] == sp]
        by_spatial[sp] = {
            "instances": len(sub),
            "rule_mean": {n: round(float(np.mean([r[n] for r in sub])), 4) for n in all_members},
            "cw_merge_mean": round(float(np.mean([r["cw_merge"] for r in sub])), 4),
            "portfolios": {p: portfolio_summary(sub, m) for p, m in portfolios_def.items()},
        }

    by_size_spatial: dict[str, dict] = {}
    for sz in FACTORS["size"]:
        for sp in FACTORS["spatial"]:
            sub = [r for r in rows if r["size"] == sz and r["spatial"] == sp]
            by_size_spatial[f"n{sz}_{sp}"] = {
                "instances": len(sub),
                "rule_mean": {n: round(float(np.mean([r[n] for r in sub])), 4) for n in all_members},
                "cw_merge_mean": round(float(np.mean([r["cw_merge"] for r in sub])), 4),
                "portfolios": {p: portfolio_summary(sub, m) for p, m in portfolios_def.items()},
            }

    summary = {
        "script": "experiments/cvrp_midterm/selection_s2/run_matrix_s2.py",
        "seed": SEED,
        "instances": len(rows),
        "factors": {k: list(v) for k, v in FACTORS.items()},
        "capacity_levels": CAPACITY_LEVELS,
        "features": list(FEATURE_NAMES),
        "base_members": base_members,
        "extra_members": extra_names,
        "all_members": all_members,
        "provenance": provenance,
        "overall": {
            "rule_mean": {n: round(float(np.mean([r[n] for r in rows])), 4) for n in all_members},
            "rule_mean_rank": {n: round(float(np.mean([r[f"{n}_rank"] for r in rows])), 3) for n in all_members},
            "rule_mean_solve_ms": {n: round(1000.0 * float(np.mean([r[f"{n}_solve_s"] for r in rows])), 3) for n in all_members},
            "cw_merge_mean": round(float(np.mean([r["cw_merge"] for r in rows])), 4),
            "cw_merge_total": round(float(sum(r["cw_merge"] for r in rows)), 4),
            "cw_merge_solve_ms": round(1000.0 * float(np.mean([r["cw_merge_solve_s"] for r in rows])), 3),
            "feat_ms": round(1000.0 * float(np.mean([r["feat_s"] for r in rows])), 3),
            "portfolios": {p: portfolio_summary(rows, m) for p, m in portfolios_def.items()},
        },
        "by_scale": by_scale,
        "by_spatial": by_spatial,
        "by_size_spatial": by_size_spatial,
    }
    (OUT / "summary_s2.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "instances": summary["instances"],
        "overall_portfolios": summary["overall"]["portfolios"],
        "overall_rule_mean": summary["overall"]["rule_mean"],
        "cw_merge_mean": summary["overall"]["cw_merge_mean"],
        "cw_merge_solve_ms": summary["overall"]["cw_merge_solve_ms"],
        "feat_ms": summary["overall"]["feat_ms"],
        "by_scale_sbs_vbs": {
            sz: {
                "sbs": v["portfolios"]["pointwise_base"]["sbs_algorithm"],
                "gap": v["portfolios"]["pointwise_base"]["sbs_gap_to_vbs"],
                "oracle": v["portfolios"]["pointwise_base"]["oracle_counts"],
                "cw_mean": v["cw_merge_mean"],
                "sbs_mean": round(v["portfolios"]["pointwise_base"]["sbs"] / v["instances"], 4),
            }
            for sz, v in by_scale.items()
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
