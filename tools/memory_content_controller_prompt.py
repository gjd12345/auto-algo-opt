"""Build one arm/round controller prompt with an auditable material receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_skill_loop import session_runtime as runtime
from agent_skill_loop.study_materials import prepare_material, verify_delivery


BATCH = ROOT / "outputs/island605-bp-memory-content-v1"
PYTHON = "C:/Python314/python.exe"


def build(seed: int, arm: str, round_id: int) -> dict:
    if seed not in (2658045112, 2210285944, 3138250455) or arm not in ("R", "F", "M") or round_id not in (1, 2, 3, 4):
        raise ValueError("unregistered_controller_assignment")
    run = BATCH / "runs" / f"seed_{seed}" / arm
    state = runtime.read_state(run=run)
    expected_state = "WAITING_FOR_EVALUATION" if round_id == 1 else "WAITING_FOR_PLAN"
    if state["round_id"] != round_id or state["state"] != expected_state:
        raise ValueError("controller_round_state_mismatch")
    material = None if round_id == 1 else prepare_material(run, round_id)
    prelude = f"""You are the independent outer controller for the frozen island605 BP memory-content study.
Model identity for every turn: gpt-5.5. Your assignment is seed {seed}, arm {arm}, round {round_id} only.
Session root: {run.as_posix()}
Use {PYTHON} for official Session commands and the installed algorithm-optimization skill.
Before every Session command in this Windows shell, set PYTHONPATH to {ROOT.as_posix()} so the frozen study problem is loaded from this checkout. Keep the working directory in this arm's Session root.
Read only the shared first-round facts and this branch's own files. Do not inspect other arms, other seeds, prior studies, or heldout data.
Do not edit code, frozen configuration, evaluator, suite, budget, or experiment manifests. Never send an independent provider request.
Use the official Session state, collect, read-evaluation, submit-evaluation, finish-round actions. Ground observations and hypotheses in the exact evidence refs. Distinguish actual candidate changes from the Plan's intended mechanism.
The current study tests controller use of historical material. Keep plan.memory_basis empty, including in arm M: historical material must not be injected into EoH. Do not force a Memory write when evidence is not reusable. Any published Memory body must be at most 1200 Unicode characters and include applicability and limitations.
Finish exactly round {round_id}, then stop. For rounds 1-3, leave the Session in WAITING_FOR_PLAN for the next round. For round 4, complete the Session. Do not start the next round in this turn.
Report the official final state, solver-call count, objective, source refs, and any failure. Do not interpret other arms.
"""
    if round_id == 1:
        instructions = """
The imported shared first round is already collected. Read its evaluation facts and comparison packet. Submit a specific evidence-bound research note for this branch, including a genuine next question. For arm M, publish one scoped insight only if supported; otherwise select none with a reason. Then finish the round with continue.
"""
    else:
        assert material is not None
        arm_rule = {
            "R": "No additional historical material is supplied; form the next Plan from current evidence and the accepted prior note.",
            "F": "The appended observations are factual excerpts only. They are not hypotheses or instructions; judge their relevance yourself.",
            "M": "The appended run-internal insight is advisory only. Judge its applicability and limits yourself; do not put its ref in plan.memory_basis.",
        }[arm]
        instructions = f"""
{arm_rule}
MATERIAL SHA256: {material['body_sha256']}
MATERIAL BODY:
{material['body']}

Read current official state and accepted prior note. Form a candidate-specific Plan that states a testable distinction, submit it, execute the official EoH once, wait for terminal state, collect, and read deterministic evaluation. Submit a new evidence-bound research note and a scoped Memory decision if enabled. Finish this round with {'complete' if round_id == 4 else 'continue'}.
"""
    prompt = prelude + instructions
    path = BATCH / "controller_prompts" / f"seed_{seed}" / f"{arm}_round_{round_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prompt, encoding="utf-8")
    delivery = verify_delivery(run, round_id, path) if material is not None else None
    return {"prompt": str(path), "prompt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "delivery": delivery, "run": str(run), "state": state["state"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--round-id", required=True, type=int)
    args = parser.parse_args()
    print(json.dumps(build(args.seed, args.arm, args.round_id), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
