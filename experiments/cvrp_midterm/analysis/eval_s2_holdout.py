"""Stage 2 Independent Multi-Scale Held-Out Evaluator & Search Trajectory Analyzer.

Evaluates:
- Frozen references: NN, savings, A, B, C, V0, V0_decoupled (theory baseline), cw_merge
- All valid unique generated candidates from `s2_autonomous_math_r8` and `s2_control_r8`
  (trajectory across rounds 1..8, budget parity audit, prompt-truncation check,
  distinct-plan/hypothesis audit)
- Top structurally distinct rules from both arms evaluated on:
  1. Session dev suite (4 instances, cvrp_construct_mini)
  2. Shared 6-instance dev suite across 4 coordinate scales {1, 0.01, 0.001, 1000}
  3. Independent frozen P0 held-out suites: suite_50 (40), suite_100 (40), suite_200 (40)
     = 120 unseen instances with 10,000-draw paired Bootstrap 95% CIs and pure solve ms.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402
from experiments.cvrp_midterm.analysis.boundary_analysis import build_analysis_instances  # noqa: E402
from experiments.cvrp_midterm.selection_s2.run_matrix_s2 import solve_clarke_wright_parallel  # noqa: E402

OUT_JSON = REPO / "experiments/cvrp_midterm/analysis/s2_holdout_eval.json"
FROZEN_P0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0"
FROZEN_V0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p1/V0.py"
SHARED_DEV = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"
RUNS_DIR = REPO / "experiments/cvrp_midterm/runs"

AUTO_DIR = RUNS_DIR / "s2_autonomous_math_r8"
CTRL_DIR = RUNS_DIR / "s2_control_r8"

V0_DECOUPLED_CODE = """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    if current_node == depot:
        fill = demands[unvisited_nodes].astype(float) / max(float(rest_capacity), 1e-9)
        dmax = max(float(np.max(d_dep)), 1e-9)
        sc = (1.0 + 0.35 * fill * fill) * (1.0 + 0.20 * (d_dep / dmax))
        return int(unvisited_nodes[int(np.argmax(sc))])
    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    return int(unvisited_nodes[int(np.argmin(d_cur - 0.6 * d_dep))])
"""

SAVINGS_CODE = """
def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):
    cur = distance_matrix[current_node]
    dep = distance_matrix[depot]
    saving = cur[depot] + dep[unvisited_nodes] - cur[unvisited_nodes]
    top = saving.max()
    tied = unvisited_nodes[saving == top]
    if tied.size > 1:
        return int(tied[np.argmax(dep[tied])])
    return int(unvisited_nodes[np.argmax(saving)])
"""


def compile_rule(code: str, name: str):
    ns = {"np": np, "numpy": np, "math": math}
    exec(compile(code, f"holdout_{name}", "exec"), ns)  # noqa: S102
    return ns["select_next_node"]


def eval_suite(code: str, name: str, instances: list[dict], *, measure_time: bool = False) -> tuple[list[float], float]:
    fn = compile_rule(code, name)
    if measure_time:
        evaluator._evaluate_cvrp_instances(fn, [instances[0]])
        t0 = time.perf_counter()
        vals, _ = evaluator._evaluate_cvrp_instances(fn, instances)
        dt_ms = (time.perf_counter() - t0) * 1000.0 / len(instances)
        return [float(v) for v in vals], dt_ms
    vals, _ = evaluator._evaluate_cvrp_instances(fn, instances)
    return [float(v) for v in vals], 0.0


def scale_suite(instances: list[dict], scale: float) -> list[dict]:
    out = []
    for inst in instances:
        c = dict(inst)
        c["depot"] = [float(x) * scale for x in inst["depot"]]
        c["customer_coordinates"] = [[float(x) * scale, float(y) * scale] for x, y in inst["customer_coordinates"]]
        out.append(c)
    return out


def paired_bootstrap_delta(a: list[float], b: list[float], n_boot: int = 10000) -> dict:
    """Relative improvement of a over b: (sum(b) - sum(a)) / sum(b); positive = a better."""
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    n = va.size
    point = float((vb.sum() - va.sum()) / vb.sum())
    rng = np.random.default_rng(20261124)
    idx = rng.integers(0, n, size=(n_boot, n))
    sb = vb[idx].sum(axis=1)
    sa = va[idx].sum(axis=1)
    boot = (sb - sa) / sb
    lo, hi = np.quantile(boot, [0.025, 0.975])
    p_one = float(np.mean(boot <= 0.0))
    wins = int(np.sum(va < vb - 1e-12))
    losses = int(np.sum(va > vb + 1e-12))
    ties = n - wins - losses
    return {
        "rel_gain": round(point, 6),
        "ci95": [round(float(lo), 6), round(float(hi), 6)],
        "p_boot_one_sided": round(p_one, 4),
        "wtl": {"wins": wins, "ties": ties, "losses": losses},
    }


def load_run_trajectory(run_dir: Path) -> dict:
    """Extract per-round trajectory, budget accounting, and all unique valid generated rules."""
    dev_instances = json.loads((run_dir / "dev_suite.json").read_text(encoding="utf-8"))["instances"]
    ledger = json.loads((run_dir / "budget_ledger.json").read_text(encoding="utf-8"))
    rounds_out = []
    unique_generated: dict[str, dict] = {}
    distinct_directions: set[str] = set()
    distinct_findings: set[str] = set()
    nonempty_eval_hypotheses_rounds = 0
    truncated_rounds = 0

    for r in range(1, 20):
        rd = run_dir / f"rounds/round_{r:04d}"
        if not rd.is_dir():
            break
        facts_p = rd / "evaluation_facts.json"
        if not facts_p.is_file():
            break
        facts = json.loads(facts_p.read_text(encoding="utf-8"))
        plan_p = run_dir / f"plan_{r}.json"
        if plan_p.is_file():
            pl = json.loads(plan_p.read_text(encoding="utf-8"))
            distinct_directions.add(str(pl.get("direction") or ""))
            ra = pl.get("research_activity") or {}
            if ra.get("mode") == "used" and ra.get("finding_summary"):
                distinct_findings.add(str(ra["finding_summary"]))
        ctx_p = rd / "round_context.json"
        if ctx_p.is_file():
            ctx = json.loads(ctx_p.read_text(encoding="utf-8"))
            if ctx.get("research_finding_truncated"):
                truncated_rounds += 1
        eval_p = run_dir / f"evaluation_{r}.json"
        if eval_p.is_file():
            ev_doc = json.loads(eval_p.read_text(encoding="utf-8"))
            if ev_doc.get("hypotheses"):
                nonempty_eval_hypotheses_rounds += 1

        # Collect generated candidates from evaluation_facts.json (carries full code!)
        gen_valid = []
        for cand in facts.get("candidates") or []:
            if cand.get("origin") != "generated" or not cand.get("valid"):
                continue
            code = cand.get("code")
            if not isinstance(code, str) or not code.strip():
                continue
            sha = str(cand.get("code_sha256") or hashlib.sha256(code.encode("utf-8")).hexdigest())
            raw_objs = (cand.get("metrics") or {}).get("raw_objectives")
            raw_mean = float(np.mean(raw_objs)) if isinstance(raw_objs, list) and raw_objs else None
            gen_valid.append({
                "candidate_id": cand.get("candidate_id"),
                "objective_gap": float(cand["objective"]),
                "raw_dev_mean": round(raw_mean, 4) if raw_mean is not None else None,
                "code_sha256": sha,
            })
            if sha not in unique_generated:
                unique_generated[sha] = {
                    "first_round": r,
                    "candidate_id": cand.get("candidate_id"),
                    "objective_gap": float(cand["objective"]),
                    "raw_dev_mean": round(raw_mean, 4) if raw_mean is not None else None,
                    "code_sha256": sha,
                    "code": code,
                }
        inc = facts.get("incumbent_after") or {}
        inc_raw = None
        for cand in facts.get("candidates") or []:
            if cand.get("code_sha256") == inc.get("code_sha256") and cand.get("valid"):
                ro = (cand.get("metrics") or {}).get("raw_objectives")
                if isinstance(ro, list) and ro:
                    inc_raw = round(float(np.mean(ro)), 4)
                    break
        rounds_out.append({
            "round_id": r,
            "terminal_reason": facts.get("terminal_reason"),
            "incumbent_gap": inc.get("objective"),
            "incumbent_raw_dev_mean": inc_raw,
            "incumbent_sha256": inc.get("code_sha256"),
            "valid_generated_count": len(gen_valid),
            "best_generated_gap": min((g["objective_gap"] for g in gen_valid), default=None),
            "best_generated_raw_dev_mean": min((g["raw_dev_mean"] for g in gen_valid if g["raw_dev_mean"] is not None), default=None),
        })

    ranked_gen = sorted(unique_generated.values(), key=lambda x: x["objective_gap"])
    return {
        "run_dir": str(run_dir.relative_to(REPO)).replace("\\", "/"),
        "rounds_completed": len(rounds_out),
        "requests_spent": ledger.get("requests_spent"),
        "input_tokens_total": ledger.get("input_tokens_total"),
        "output_tokens_total": ledger.get("output_tokens_total"),
        "solver_seconds_total": ledger.get("solver_seconds_total"),
        "distinct_directions": len(distinct_directions),
        "distinct_findings": len(distinct_findings),
        "nonempty_eval_hypotheses_rounds": nonempty_eval_hypotheses_rounds,
        "truncated_rounds": truncated_rounds,
        "unique_valid_generated": len(ranked_gen),
        "trajectory": rounds_out,
        "ranked_generated": ranked_gen,
        "dev_instances": dev_instances,
    }


def main() -> int:
    auto = load_run_trajectory(AUTO_DIR)
    ctrl = load_run_trajectory(CTRL_DIR)

    shared_6 = json.loads(SHARED_DEV.read_text(encoding="utf-8"))["instances"]
    p0_50 = json.loads((FROZEN_P0 / "suite_50.json").read_text(encoding="utf-8"))["instances"]
    p0_100 = json.loads((FROZEN_P0 / "suite_100.json").read_text(encoding="utf-8"))["instances"]
    p0_200 = json.loads((FROZEN_P0 / "suite_200.json").read_text(encoding="utf-8"))["instances"]
    dev_4 = auto["dev_instances"]
    ana_72 = build_analysis_instances()

    # Score every unique valid generated candidate from both arms on ana_72 (disjoint from P0!)
    # so we can cleanly select BOTH dev4-best AND ana72-best with zero P0 peeking.
    for arm_data in (auto, ctrl):
        for cand in arm_data["ranked_generated"]:
            v_ana, _ = eval_suite(cand["code"], "ana_rank", ana_72)
            cand["ana72_mean"] = round(float(np.mean(v_ana)), 4)

    auto_by_ana = sorted(auto["ranked_generated"], key=lambda x: x["ana72_mean"])
    ctrl_by_ana = sorted(ctrl["ranked_generated"], key=lambda x: x["ana72_mean"])

    # Build evaluation slate: frozen baselines + top 5 dev4 + top 3 ana72 from each arm (deduped)
    slate: dict[str, dict] = {
        "NN": {"code": (FROZEN_P0 / "frozen_code/NN.py").read_text(encoding="utf-8"), "origin": "frozen_baseline"},
        "savings": {"code": SAVINGS_CODE, "origin": "baseline"},
        "A": {"code": (FROZEN_P0 / "frozen_code/A.py").read_text(encoding="utf-8"), "origin": "frozen_poc"},
        "B": {"code": (FROZEN_P0 / "frozen_code/B.py").read_text(encoding="utf-8"), "origin": "frozen_poc"},
        "C": {"code": (FROZEN_P0 / "frozen_code/C.py").read_text(encoding="utf-8"), "origin": "frozen_poc"},
        "V0": {"code": FROZEN_V0.read_text(encoding="utf-8"), "origin": "frozen_poc"},
        "V0_decoupled_theory": {"code": V0_DECOUPLED_CODE, "origin": "stage2a_theory_ablation"},
    }
    sha_to_key: dict[str, str] = {}

    def register_arm_picks(prefix: str, arm_origin: str, by_dev: list[dict], by_ana: list[dict]):
        dev_keys, ana_keys = [], []
        for i, cand in enumerate(by_dev[:5], 1):
            sha = cand["code_sha256"]
            key = f"{prefix}_dev{i}_r{cand['first_round']}"
            slate[key] = {
                "code": cand["code"],
                "origin": arm_origin,
                "selection_criterion": f"dev4_rank_{i}",
                "first_round": cand["first_round"],
                "candidate_id": cand["candidate_id"],
                "code_sha256": sha,
                "ana72_mean": cand["ana72_mean"],
            }
            sha_to_key[sha] = key
            dev_keys.append(key)
        for i, cand in enumerate(by_ana[:3], 1):
            sha = cand["code_sha256"]
            if sha in sha_to_key:
                ana_keys.append(sha_to_key[sha])
                continue
            key = f"{prefix}_ana{i}_r{cand['first_round']}"
            slate[key] = {
                "code": cand["code"],
                "origin": arm_origin,
                "selection_criterion": f"ana72_rank_{i}",
                "first_round": cand["first_round"],
                "candidate_id": cand["candidate_id"],
                "code_sha256": sha,
                "ana72_mean": cand["ana72_mean"],
            }
            sha_to_key[sha] = key
            ana_keys.append(key)
        return dev_keys, ana_keys

    auto_dev_keys, auto_ana_keys = register_arm_picks("auto", "s2_autonomous_math_r8", auto["ranked_generated"], auto_by_ana)
    ctrl_dev_keys, ctrl_ana_keys = register_arm_picks("ctrl", "s2_control_r8", ctrl["ranked_generated"], ctrl_by_ana)

    # Evaluate every candidate on dev_4, shared_6 (4 scales), and independent P0 (50, 100, 200)
    per_inst_p0: dict[str, dict[str, list[float]]] = {}
    results: dict[str, dict] = {}
    scales = (1.0, 0.01, 0.001, 1000.0)
    scaled_shared = {s: scale_suite(shared_6, s) for s in scales}

    for name, info in slate.items():
        code = info["code"]
        d4, _ = eval_suite(code, name, dev_4)
        sh_by_s = {}
        for s in scales:
            vals, _ = eval_suite(code, name, scaled_shared[s])
            sh_by_s[str(s)] = round(float(np.mean(vals)) / s, 4)
        s_vals = list(sh_by_s.values())
        spread = (max(s_vals) - min(s_vals)) / min(s_vals)

        v50, t50 = eval_suite(code, name, p0_50, measure_time=True)
        v100, t100 = eval_suite(code, name, p0_100, measure_time=True)
        v200, t200 = eval_suite(code, name, p0_200, measure_time=True)
        per_inst_p0[name] = {"50": v50, "100": v100, "200": v200, "all": v50 + v100 + v200}

        results[name] = {
            "origin": info["origin"],
            "first_round": info.get("first_round"),
            "candidate_id": info.get("candidate_id"),
            "code_sha256": info.get("code_sha256") or hashlib.sha256(code.encode("utf-8")).hexdigest(),
            "dev4_mean": round(float(np.mean(d4)), 4),
            "shared6_s1": sh_by_s["1.0"],
            "shared6_by_scale": sh_by_s,
            "scale_spread": round(float(spread), 6),
            "p0_50_mean": round(float(np.mean(v50)), 4),
            "p0_100_mean": round(float(np.mean(v100)), 4),
            "p0_200_mean": round(float(np.mean(v200)), 4),
            "p0_120_mean": round(float(np.mean(v50 + v100 + v200)), 4),
            "p0_solve_ms": {"50": round(t50, 3), "100": round(t100, 3), "200": round(t200, 3)},
        }

    # Add non-pointwise Clarke-Wright reference on P0 suites
    cw_50 = [solve_clarke_wright_parallel(inst) for inst in p0_50]
    cw_100 = [solve_clarke_wright_parallel(inst) for inst in p0_100]
    cw_200 = [solve_clarke_wright_parallel(inst) for inst in p0_200]
    results["cw_merge_ref"] = {
        "origin": "non_pointwise_reference",
        "dev4_mean": round(float(np.mean([solve_clarke_wright_parallel(x) for x in dev_4])), 4),
        "shared6_s1": round(float(np.mean([solve_clarke_wright_parallel(x) for x in shared_6])), 4),
        "p0_50_mean": round(float(np.mean(cw_50)), 4),
        "p0_100_mean": round(float(np.mean(cw_100)), 4),
        "p0_200_mean": round(float(np.mean(cw_200)), 4),
        "p0_120_mean": round(float(np.mean(cw_50 + cw_100 + cw_200)), 4),
    }

    # Identify leak-free selected rules per arm: (1) pure dev4 top-1, (2) offline ana72 top-1
    auto_dev_best = auto_dev_keys[0] if auto_dev_keys else None
    ctrl_dev_best = ctrl_dev_keys[0] if ctrl_dev_keys else None
    auto_ana_best = auto_ana_keys[0] if auto_ana_keys else None
    ctrl_ana_best = ctrl_ana_keys[0] if ctrl_ana_keys else None

    auto_names = [k for k in results if k.startswith("auto_")]
    ctrl_names = [k for k in results if k.startswith("ctrl_")]
    auto_p0_best = min(auto_names, key=lambda k: results[k]["p0_120_mean"]) if auto_names else None
    ctrl_p0_best = min(ctrl_names, key=lambda k: results[k]["p0_120_mean"]) if ctrl_names else None

    comparisons: dict[str, dict] = {}
    def add_cmp(label: str, k1: str | None, k2: str | None):
        if k1 and k2 and k1 in per_inst_p0 and k2 in per_inst_p0:
            comparisons[label] = {
                "a": k1,
                "b": k2,
                "p0_50": paired_bootstrap_delta(per_inst_p0[k1]["50"], per_inst_p0[k2]["50"]),
                "p0_100": paired_bootstrap_delta(per_inst_p0[k1]["100"], per_inst_p0[k2]["100"]),
                "p0_200": paired_bootstrap_delta(per_inst_p0[k1]["200"], per_inst_p0[k2]["200"]),
                "p0_all120": paired_bootstrap_delta(per_inst_p0[k1]["all"], per_inst_p0[k2]["all"]),
            }

    add_cmp("auto_dev_best_vs_ctrl_dev_best", auto_dev_best, ctrl_dev_best)
    add_cmp("auto_dev_best_vs_A", auto_dev_best, "A")
    add_cmp("auto_dev_best_vs_B", auto_dev_best, "B")
    add_cmp("auto_dev_best_vs_C", auto_dev_best, "C")
    add_cmp("auto_dev_best_vs_savings", auto_dev_best, "savings")
    add_cmp("auto_ana_best_vs_ctrl_ana_best", auto_ana_best, ctrl_ana_best)
    add_cmp("auto_ana_best_vs_A", auto_ana_best, "A")
    add_cmp("auto_ana_best_vs_B", auto_ana_best, "B")
    add_cmp("auto_ana_best_vs_C", auto_ana_best, "C")
    add_cmp("auto_ana_best_vs_savings", auto_ana_best, "savings")
    add_cmp("V0_decoupled_vs_V0", "V0_decoupled_theory", "V0")
    add_cmp("V0_decoupled_vs_A", "V0_decoupled_theory", "A")
    add_cmp("V0_decoupled_vs_savings", "V0_decoupled_theory", "savings")

    payload = {
        "script": "experiments/cvrp_midterm/analysis/eval_s2_holdout.py",
        "auto_arm": {k: v for k, v in auto.items() if k not in ("ranked_generated", "dev_instances")},
        "ctrl_arm": {k: v for k, v in ctrl.items() if k not in ("ranked_generated", "dev_instances")},
        "auto_dev_best": auto_dev_best,
        "ctrl_dev_best": ctrl_dev_best,
        "auto_ana_best": auto_ana_best,
        "ctrl_ana_best": ctrl_ana_best,
        "auto_p0_best": auto_p0_best,
        "ctrl_p0_best": ctrl_p0_best,
        "results": results,
        "comparisons": comparisons,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== INDEPENDENT MULTI-SCALE HELD-OUT EVALUATION (120 UNSEEN P0 INSTANCES) ===")
    print(f"{'Rule':22s} | {'dev4':7s} | {'sh6':7s} | {'spread':7s} | {'P0-50':7s} | {'P0-100':7s} | {'P0-200':7s} | {'P0-120':7s}")
    for k, r in sorted(results.items(), key=lambda kv: kv[1]["p0_120_mean"]):
        sp = f"{r['scale_spread']*100:5.2f}%" if "scale_spread" in r else "   -  "
        print(
            f"{k:22s} | {r['dev4_mean']:7.4f} | {r['shared6_s1']:7.4f} | {sp:7s} | "
            f"{r['p0_50_mean']:7.4f} | {r['p0_100_mean']:7.4f} | {r['p0_200_mean']:7.4f} | {r['p0_120_mean']:7.4f}"
        )
    print("\n=== KEY PAIRED BOOTSTRAP COMPARISONS (P0 ALL 120) ===")
    for lbl, c in comparisons.items():
        m = c["p0_all120"]
        lo, hi = m["ci95"]
        print(f"  {lbl:34s}: {m['rel_gain']*100:+6.2f}% [{lo*100:+5.2f}%, {hi*100:+5.2f}%] p={m['p_boot_one_sided']:.4f} W/T/L={m['wtl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
