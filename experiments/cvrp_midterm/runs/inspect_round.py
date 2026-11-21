"""Offline inter-round mathematical inspector for Stage 2 autonomous search.

Reads evaluation_facts.json of a completed round and inspects every valid
generated candidate:
- Full Python source code
- dev4 per-instance gaps
- shared6 (6-instance reference dev suite) at s=1.0 and s=0.01 (scale invariance!)
- ana72 (72 fresh multi-scale analysis instances n=50/100/200, seed 20261123;
  disjoint from P0 held-out suites) broken down by uniform vs clustered & n=50/100/200
- Voluntary early-return count (how often the rule actually returned 0 mid-route!)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402
from experiments.cvrp_midterm.analysis.boundary_analysis import build_analysis_instances  # noqa: E402

SHARED_DEV = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"


def compile_rule(code: str):
    ns = {"np": np, "numpy": np, "math": math}
    exec(compile(code, "cand_inspect", "exec"), ns)  # noqa: S102
    return ns["select_next_node"]


def count_early_returns(fn, instances: list[dict]) -> tuple[int, int]:
    """Count (early_returns, total_mid_steps) across instances."""
    early = 0
    mid_steps = 0
    for inst in instances:
        coords = np.vstack([
            np.asarray(inst["depot"], dtype=float),
            np.asarray(inst["customer_coordinates"], dtype=float),
        ])
        dmat = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=2)
        dem = np.asarray([0.0] + [float(d) for d in inst["demands"]], dtype=float)
        cap = float(inst["capacity"])
        unv = set(range(1, len(inst["demands"]) + 1))
        cur, rcap = 0, cap
        while unv:
            feas = np.array(sorted(u for u in unv if dem[u] <= rcap), dtype=int)
            if feas.size == 0:
                cur, rcap = 0, cap
                continue
            nxt = int(fn(cur, 0, feas, rcap, dem, dmat))
            if cur != 0:
                mid_steps += 1
            if nxt == 0:
                if cur != 0:
                    early += 1
                cur, rcap = 0, cap
                continue
            unv.remove(nxt)
            rcap -= float(dem[nxt])
            cur = nxt
    return early, mid_steps


def scale_suite(instances: list[dict], scale: float) -> list[dict]:
    out = []
    for inst in instances:
        c = dict(inst)
        c["depot"] = [float(x) * scale for x in inst["depot"]]
        c["customer_coordinates"] = [[float(x) * scale, float(y) * scale] for x, y in inst["customer_coordinates"]]
        out.append(c)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--show-code", action="store_true")
    args = parser.parse_args()

    rd = Path(args.run_dir) / f"rounds/round_{args.round:04d}"
    facts = json.loads((rd / "evaluation_facts.json").read_text(encoding="utf-8"))
    shared6 = json.loads(SHARED_DEV.read_text(encoding="utf-8"))["instances"]
    shared6_s001 = scale_suite(shared6, 0.01)
    ana72 = build_analysis_instances()

    inc = facts.get("incumbent_after") or {}
    print(f"=== ROUND {args.round} | incumbent={inc.get('objective'):.5f} ({str(inc.get('code_sha256'))[:8]}, origin={inc.get('origin')}) ===")
    for c in facts.get("candidates") or []:
        if c.get("origin") != "generated":
            continue
        cid = c.get("candidate_id")
        if not c.get("valid"):
            print(f"\n[{cid}] INVALID: {c.get('error_code')} {c.get('error_detail')}")
            continue
        code = c.get("code") or ""
        fn = compile_rule(code)
        sh1, _ = evaluator._evaluate_cvrp_instances(fn, shared6)
        sh001, _ = evaluator._evaluate_cvrp_instances(fn, shared6_s001)
        a72, _ = evaluator._evaluate_cvrp_instances(fn, ana72)
        early, mid = count_early_returns(fn, shared6)
        m1 = float(np.mean(sh1))
        m001 = float(np.mean(sh001)) / 0.01
        ratio = m001 / max(m1, 1e-12)
        a_u = float(np.mean([v for v, x in zip(a72, ana72) if x["spatial"] == "uniform"]))
        a_c = float(np.mean([v for v, x in zip(a72, ana72) if x["spatial"] == "clustered"]))
        a200 = float(np.mean([v for v, x in zip(a72, ana72) if x["size"] == 200]))
        print(
            f"\n[{cid}] dev4={c['objective']:+.5f} {[round(x,4) for x in c.get('instance_objectives') or []]}"
            f" | sh6={m1:.4f} (s001/s1={ratio:.5f})"
            f" | ana72={float(np.mean(a72)):.4f} (uni={a_u:.3f}, clu={a_c:.3f}, n200={a200:.3f})"
            f" | early_ret={early}/{mid}"
        )
        if args.show_code:
            print(code.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
