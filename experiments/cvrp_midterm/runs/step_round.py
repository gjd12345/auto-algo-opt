"""Stage 2 Track A: Round-by-round Session stepper for autonomous math analysis & paired control.

Starts from the frozen 4-rule SOTA frontier via `inheritance_mode="explicit_seeds"`
(frozen PoC rules C, A, B, V0 — SHA-256 verified) on `eohs_v1/cvrp_construct_mini`
with strict budget parity:
    max_rounds             = 8
    eoh_round_max_requests = 6
    eoh_max_requests       = 48
    round_budget           = 30 solver calls
    max_solver_calls       = 240 solver calls
    eoh_model              = deepseek-flash
    eoh_thinking           = disabled
    memory_enabled         = False

Subcommands:
    init         --run-dir <dir> --tag <id> [--max-rounds 8]
    run-round    --run-dir <dir> --plan <plan.json>
    finish-round --run-dir <dir> --eval <eval.json> --decision <continue|complete>
    run-control  --run-dir <dir> --tag <id> [--max-rounds 8]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

import agent_skill_loop.evaluator as evaluator  # noqa: E402
import agent_skill_loop.session_actions as actions  # noqa: E402
import agent_skill_loop.session_runtime as db  # noqa: E402

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
KEY_CANDIDATES = (
    REPO / ".secrets" / "deepseek.key",
    Path(r"C:\Users\24294\Projects\aao-e2e\.secrets\deepseek.key"),
)
FROZEN_P0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code"
FROZEN_V0 = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p1/V0.py"
SHARED_DEV_SUITE = REPO / "reports/evidence/cvrp_super_agent_reference_20261107/dev_suite.json"

REQUESTS_PER_ROUND = 6
SOLVER_PER_ROUND = 30
ROUND_WALL = 600.0
ENGINE_WALL = 4800.0

EXACT_SHA = {
    "Frozen_C": "141d99b6f7c62e60313feb2c520889a957da9ae00fd5138798f4de3c30e25627",
    "Frozen_A": "ccdab29f7d08ab162145ae7e468e47a5488b696d9a644bb7e793ab5c2665a866",
    "Frozen_B": "68cd510af3df75d8f1b45182b248f07d7e38cedc4bfc1d74f5669a6b9ad81727",
}


def load_key() -> str:
    # Prefer the repo-local gitignored key file first (the shell env may hold a stale key).
    for path in KEY_CANDIDATES:
        if path.is_file():
            key = path.read_text(encoding="utf-8").strip()
            if key:
                return key
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    raise SystemExit("no provider key: write .secrets/deepseek.key or set DEEPSEEK_API_KEY")


def setup_env() -> None:
    os.environ["DEEPSEEK_API_KEY"] = load_key()
    for name in ("NO_PROXY", "no_proxy"):
        os.environ[name] = "*"


def build_explicit_seeds() -> list[dict[str, str]]:
    items = [
        ("Frozen_C", FROZEN_P0 / "C.py", EXACT_SHA["Frozen_C"],
         "Linear distance minus 0.6*depot_dist with gated near-tie capacity-fit adjustment."),
        ("Frozen_A", FROZEN_P0 / "A.py", EXACT_SHA["Frozen_A"],
         "Absolute Clarke-Wright savings with 2% near-tie normalized-saving minus 0.1*fill refinement."),
        ("Frozen_B", FROZEN_P0 / "B.py", EXACT_SHA["Frozen_B"],
         "Multiplicative normalized-savings, quadratic fill pressure, and radial far-first modulation."),
        ("Frozen_V0", FROZEN_V0, None,
         "Linear score d_cur - 0.6*d_dep - 1e-6*dem without capacity gate."),
    ]
    out: list[dict[str, str]] = []
    for name, path, expected, desc in items:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected is not None and digest != expected:
            raise SystemExit(f"Frozen seed hash mismatch for {name}: {digest} != {expected}")
        out.append({
            "algorithm": f"{name}: {desc}",
            "code": raw.decode("utf-8"),
        })
    return out


def wait_exit(root: Path, deadline: float) -> None:
    while time.time() < deadline:
        state = db.read_state(run=root)
        task = state.get("task") or {}
        if task.get("state") == "EXITED":
            return
        time.sleep(2.0)
    raise SystemExit("task did not exit before round deadline")


def round_accounting(root: Path, round_id: int) -> dict:
    base = root / f"rounds/round_{round_id:04d}/eoh_run/results"
    requests = []
    path = base / "requests.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                requests.append(json.loads(line))
    completed = [r for r in requests if r.get("state") == "complete"]
    elapsed = []
    evals_path = base / "evaluations.jsonl"
    if evals_path.is_file():
        for line in evals_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                value = (row.get("evaluation") or {}).get("elapsed_seconds")
                if isinstance(value, (int, float)):
                    elapsed.append(float(value))
    return {
        "round_id": round_id,
        "requests_completed": len(completed),
        "requests_reserved": len(requests),
        "input_tokens": sum(int(r.get("input_tokens") or 0) for r in completed),
        "output_tokens": sum(int(r.get("output_tokens") or 0) for r in completed),
        "provider_errors": sorted({str(r.get("error_code")) for r in completed if r.get("error_code")}),
        "evaluations": len(elapsed),
        "solver_seconds": round(sum(elapsed), 3),
    }


def _scale_instances(instances: list[dict], scale: float) -> list[dict]:
    out = []
    for inst in instances:
        c = dict(inst)
        c["depot"] = [float(x) * scale for x in inst["depot"]]
        c["customer_coordinates"] = [[float(x) * scale, float(y) * scale] for x, y in inst["customer_coordinates"]]
        out.append(c)
    return out


def _eval_code_on_instances(code: str, instances: list[dict]) -> list[float] | None:
    try:
        ns = {"np": np, "numpy": np, "math": math}
        exec(compile(code, "cand_diag", "exec"), ns)  # noqa: S102
        fn = ns["select_next_node"]
        vals, _ = evaluator._evaluate_cvrp_instances(fn, instances)
        return [float(v) for v in vals]
    except Exception:
        return None


def build_round_digest(root: Path, round_id: int) -> dict:
    """Create an offline diagnostic digest of all candidates generated in this round."""
    rd_dir = root / f"rounds/round_{round_id:04d}"
    facts = json.loads((rd_dir / "evaluation_facts.json").read_text(encoding="utf-8"))
    sess_suite = json.loads((root / "dev_suite.json").read_text(encoding="utf-8"))["instances"]
    shared_suite = json.loads(SHARED_DEV_SUITE.read_text(encoding="utf-8"))["instances"]
    shared_s001 = _scale_instances(shared_suite, 0.01)

    evals_path = rd_dir / "eoh_run/results/evaluations.jsonl"
    cand_rows = []
    if evals_path.is_file():
        for line in evals_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            ev = row.get("evaluation") or {}
            cid = str(row.get("candidate_id") or "")
            code_ref = row.get("code_ref")
            code_text = None
            if isinstance(code_ref, str):
                p = rd_dir / "eoh_run" / code_ref
                if not p.is_file():
                    p = root / code_ref
                if p.is_file():
                    code_text = p.read_text(encoding="utf-8")
            entry = {
                "candidate_id": cid,
                "origin": row.get("origin"),
                "valid": bool(ev.get("valid")),
                "objective": ev.get("objective"),
                "error_code": ev.get("error_code"),
                "code_sha256": row.get("code_sha256"),
                "code_ref": code_ref,
                "code_bytes": len(code_text.encode("utf-8")) if code_text else 0,
                "per_instance_session_dev": None,
                "shared_6_s1": None,
                "shared_6_s001_norm": None,
                "scale_ratio_001": None,
            }
            if entry["valid"] and code_text:
                s_vals = _eval_code_on_instances(code_text, sess_suite)
                sh1 = _eval_code_on_instances(code_text, shared_suite)
                sh001 = _eval_code_on_instances(code_text, shared_s001)
                if s_vals is not None:
                    entry["per_instance_session_dev"] = [round(v, 4) for v in s_vals]
                if sh1 is not None:
                    entry["shared_6_s1"] = round(float(np.mean(sh1)), 4)
                if sh001 is not None:
                    norm001 = float(np.mean(sh001)) / 0.01
                    entry["shared_6_s001_norm"] = round(norm001, 4)
                    if entry["shared_6_s1"] and entry["shared_6_s1"] > 0:
                        entry["scale_ratio_001"] = round(norm001 / entry["shared_6_s1"], 5)
            cand_rows.append(entry)

    ctx_path = rd_dir / "round_context.json"
    ctx_trunc = None
    if ctx_path.is_file():
        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        ctx_trunc = ctx.get("research_finding_truncated")

    digest = {
        "round_id": round_id,
        "terminal_reason": facts.get("terminal_reason"),
        "research_finding_truncated": ctx_trunc,
        "baseline": facts.get("baseline"),
        "incumbent_before": facts.get("incumbent_before"),
        "incumbent_after": facts.get("incumbent_after"),
        "evidence_refs": facts.get("evidence_refs"),
        "accounting": round_accounting(root, round_id),
        "candidates": cand_rows,
    }
    (rd_dir / "round_digest.json").write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    return digest


def update_ledger(root: Path, round_id: int) -> dict:
    ledger_path = root / "budget_ledger.json"
    if ledger_path.is_file():
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    else:
        data = {"rounds": [], "requests_spent": 0}
    acct = round_accounting(root, round_id)
    rounds = [r for r in data.get("rounds", []) if r.get("round_id") != round_id]
    rounds.append(acct)
    rounds.sort(key=lambda r: int(r["round_id"]))
    spent = sum(int(r["requests_completed"]) for r in rounds)
    data["rounds"] = rounds
    data["requests_spent"] = spent
    data["input_tokens_total"] = sum(int(r["input_tokens"]) for r in rounds)
    data["output_tokens_total"] = sum(int(r["output_tokens"]) for r in rounds)
    data["solver_seconds_total"] = round(sum(float(r["solver_seconds"]) for r in rounds), 3)
    ledger_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def cmd_init(args: argparse.Namespace) -> int:
    setup_env()
    root = Path(args.run_dir).resolve()
    if root.exists():
        raise SystemExit(f"run_dir already exists: {root}")
    seeds = build_explicit_seeds()
    max_rounds = int(args.max_rounds)
    req_total = max_rounds * REQUESTS_PER_ROUND
    solver_total = max_rounds * SOLVER_PER_ROUND
    res = db.initialize_session(
        output=root,
        operation_id=f"{args.tag}-init",
        problem="cvrp_construct",
        eoh_model=MODEL,
        eoh_endpoint=ENDPOINT,
        eoh_max_requests=req_total,
        eoh_round_max_requests=REQUESTS_PER_ROUND,
        engine_wall_seconds=ENGINE_WALL,
        round_wall_seconds=ROUND_WALL,
        max_solver_calls=solver_total,
        round_budget=SOLVER_PER_ROUND,
        benchmark_id="eohs_v1",
        benchmark_profile_name="cvrp_construct_mini",
        inheritance_mode="explicit_seeds",
        explicit_seed_set=seeds,
        memory_enabled=False,
        eoh_thinking="disabled",
        max_rounds=max_rounds,
        request_timeout=600.0,
    )
    print(json.dumps({
        "ok": True,
        "run_dir": str(root),
        "run_id": res["run_id"],
        "state": res["state"],
        "state_version": res["state_version"],
        "seeds": [s["algorithm"].split(":")[0] for s in seeds],
        "max_rounds": max_rounds,
        "eoh_max_requests": req_total,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_run_round(args: argparse.Namespace) -> int:
    setup_env()
    root = Path(args.run_dir).resolve()
    state = db.read_state(run=root)
    round_id = int(state["round_id"])
    plan_path = Path(args.plan).resolve()
    plan_obj = json.loads(plan_path.read_text(encoding="utf-8"))
    if round_id > 1 and "feedback_basis" not in plan_obj:
        prev_file = root / f"rounds/round_{round_id - 1:04d}/evaluation_facts.json"
        prev = json.loads(prev_file.read_text(encoding="utf-8"))
        plan_obj["feedback_basis"] = {
            "round_id": round_id - 1,
            "evaluation_ref": f"rounds/round_{round_id - 1:04d}/evaluation_facts.json",
            "suite_hash": prev["suite_hash"],
        }
    saved_plan = root / f"plan_{round_id}.json"
    saved_plan.write_text(json.dumps(plan_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    actions.submit_plan(
        run=root,
        operation_id=f"plan-{round_id}",
        expected_state_version=state["state_version"],
        file=saved_plan,
    )
    # Verify zero silent truncation of research_finding before spending LLM requests
    ctx_path = root / f"rounds/round_{round_id:04d}/round_context.json"
    if ctx_path.is_file():
        ctx = json.loads(ctx_path.read_text(encoding="utf-8"))
        if ctx.get("research_finding_truncated"):
            raise SystemExit(f"ABORT: round {round_id} research_finding was truncated!")

    state = db.read_state(run=root)
    actions.execute(
        run=root,
        operation_id=f"exec-{round_id}",
        expected_state_version=state["state_version"],
    )
    wait_exit(root, time.time() + ROUND_WALL)
    state = db.read_state(run=root)
    actions.collect(
        run=root,
        operation_id=f"collect-{round_id}",
        expected_state_version=state["state_version"],
    )
    ledger = update_ledger(root, round_id)
    digest = build_round_digest(root, round_id)
    print(json.dumps({
        "round_id": round_id,
        "terminal_reason": digest["terminal_reason"],
        "research_finding_truncated": digest["research_finding_truncated"],
        "incumbent_before": digest["incumbent_before"],
        "incumbent_after": digest["incumbent_after"],
        "accounting": digest["accounting"],
        "requests_spent_total": ledger["requests_spent"],
        "generated_summary": [
            {
                "id": c["candidate_id"],
                "origin": c["origin"],
                "valid": c["valid"],
                "obj": c["objective"],
                "shared_s1": c["shared_6_s1"],
                "scale_001": c["scale_ratio_001"],
                "err": c["error_code"],
            }
            for c in digest["candidates"]
            if c.get("origin") == "generated"
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_finish_round(args: argparse.Namespace) -> int:
    root = Path(args.run_dir).resolve()
    state = db.read_state(run=root)
    round_id = int(state["round_id"])
    eval_src = Path(args.eval).resolve()
    eval_dst = root / f"evaluation_{round_id}.json"
    eval_dst.write_text(eval_src.read_text(encoding="utf-8"), encoding="utf-8")
    actions.submit_evaluation(
        run=root,
        operation_id=f"eval-{round_id}",
        expected_state_version=state["state_version"],
        file=eval_dst,
    )
    state = db.read_state(run=root)
    res = actions.finish_round(
        run=root,
        operation_id=f"finish-{round_id}",
        expected_state_version=state["state_version"],
        decision=args.decision,
    )
    print(json.dumps({
        "finished_round": round_id,
        "decision": args.decision,
        "next_round": res["round_id"],
        "run_state": res["run_state"],
        "state": res["state"],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_run_control(args: argparse.Namespace) -> int:
    """Run paired same-budget neutral control across all rounds (explicit_seeds=[C,A,B,V0])."""
    setup_env()
    root = Path(args.run_dir).resolve()
    max_rounds = int(args.max_rounds)
    if not root.exists():
        init_ns = argparse.Namespace(run_dir=str(root), tag=args.tag, max_rounds=max_rounds)
        cmd_init(init_ns)

    for round_id in range(1, max_rounds + 1):
        state = db.read_state(run=root)
        if state["run_state"] != "RUNNING":
            break
        cur_r = int(state["round_id"])
        if cur_r > round_id:
            continue
        if state["state"] == "WAITING_FOR_PLAN":
            plan = {
                "round_id": round_id,
                "direction": "Explore improved priority rules for CVRP greedy construction.",
                "operations": [
                    {
                        "type": "replace",
                        "target": "priority score",
                        "mechanism": "Try alternative combinations of distance, depot distance, demand, and remaining capacity.",
                    }
                ],
                "preserve": "The problem interface, the evaluator, and the search policy.",
                "hypothesis": "Alternative combinations of distance, depot distance, and load yield shorter CVRP routes.",
                "research_activity": {
                    "mode": "not_used",
                    "trigger": "not_applicable",
                    "finding_status": "not_applicable",
                    "decision": "not_applicable",
                },
            }
            p_path = root / f"_ctrl_plan_{round_id}.json"
            p_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            cmd_run_round(argparse.Namespace(run_dir=str(root), plan=str(p_path)))
            state = db.read_state(run=root)

        if state["state"] == "WAITING_FOR_EVALUATION":
            facts = actions.read_evaluation(run=root)["result"]
            ev_refs = [r for r in (facts.get("evidence_refs") or []) if isinstance(r, str)]
            inc = (facts.get("incumbent_after") or {}).get("objective")
            base = (facts.get("baseline") or {}).get("objective")
            evaluation = {
                "plan_alignment": "aligned",
                "observations": [
                    {
                        "claim": f"round={round_id} baseline={base} incumbent={inc} terminal={facts.get('terminal_reason')}",
                        "evidence_refs": [ev_refs[0]] if ev_refs else [],
                    }
                ] if ev_refs else [],
                "hypotheses": [],
                "next_search_advice": {"direction": "continue within the remaining budget"},
                "memory_action": {"kind": "disabled"},
            }
            e_path = root / f"_ctrl_eval_{round_id}.json"
            e_path.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
            dec = "continue" if round_id < max_rounds else "complete"
            cmd_finish_round(argparse.Namespace(run_dir=str(root), eval=str(e_path), decision=dec))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--run-dir", required=True)
    p_init.add_argument("--tag", required=True)
    p_init.add_argument("--max-rounds", type=int, default=8)

    p_run = sub.add_parser("run-round")
    p_run.add_argument("--run-dir", required=True)
    p_run.add_argument("--plan", required=True)

    p_fin = sub.add_parser("finish-round")
    p_fin.add_argument("--run-dir", required=True)
    p_fin.add_argument("--eval", required=True)
    p_fin.add_argument("--decision", choices=("continue", "complete"), required=True)

    p_ctrl = sub.add_parser("run-control")
    p_ctrl.add_argument("--run-dir", required=True)
    p_ctrl.add_argument("--tag", required=True)
    p_ctrl.add_argument("--max-rounds", type=int, default=8)

    args = parser.parse_args()
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "run-round":
        return cmd_run_round(args)
    if args.cmd == "finish-round":
        return cmd_finish_round(args)
    if args.cmd == "run-control":
        return cmd_run_control(args)
    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
