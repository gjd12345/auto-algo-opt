"""Generate one bounded, isolated R/F/M controller decision prompt."""

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
from tools.memory_content_brief import build as build_brief, write as write_brief


BATCH = ROOT / "outputs/island605-bp-memory-content-v2"
SEEDS = (2658045112, 2210285944, 3138250455)
ARMS = ("R", "F", "M")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prior_note(run: Path, round_id: int) -> tuple[dict, dict]:
    import sqlite3

    with sqlite3.connect(run / "session.sqlite3") as con:
        row = con.execute(
            "SELECT submitted_evaluation_ref,submitted_evaluation_sha256 FROM rounds WHERE round_id=?",
            (round_id,),
        ).fetchone()
    if not row or not row[0] or not row[1]:
        raise ValueError("accepted_prior_note_missing")
    path = (run / row[0]).resolve()
    if not path.is_relative_to(run.resolve()) or not path.is_file() or _sha(path) != row[1]:
        raise ValueError("accepted_prior_note_identity_failed")
    return json.loads(path.read_text(encoding="utf-8")), {"ref": row[0], "sha256": row[1]}


def build(seed: int, arm: str, round_id: int, phase: str) -> dict:
    if seed not in SEEDS or arm not in ARMS or round_id not in (1, 2, 3, 4) or phase not in {"reflection", "plan"}:
        raise ValueError("unregistered_controller_assignment")
    if phase == "plan" and round_id == 1:
        raise ValueError("first_round_plan_is_common_and_frozen")
    run = BATCH / "runs" / f"seed_{seed}" / arm
    state = runtime.read_state(run=run)
    expected = "WAITING_FOR_EVALUATION" if phase == "reflection" else "WAITING_FOR_PLAN"
    if state["round_id"] != round_id or state["state"] != expected:
        raise ValueError("controller_phase_state_mismatch")
    fact_round = round_id if phase == "reflection" else round_id - 1
    brief_receipt = write_brief(run, fact_round)
    brief = build_brief(run, fact_round)
    common = (
        "You are the independent gpt-5.5 analysis controller for exactly this seed, arm and phase. "
        "Use only the evidence printed below. Do not run tools, browse, inspect files, or request other material. "
        "Return exactly one JSON object and no prose. The evidence is descriptive; do not invent an improvement, "
        "candidate identity, behavior relation, or causal mechanism. Heldout data is unavailable.\n"
        f"SEED={seed} ARM={arm} ROUND={round_id} PHASE={phase}\n"
        f"BRIEF REF={brief_receipt['ref']} SHA256={brief_receipt['sha256']}\n"
        "COMMON EVIDENCE BRIEF JSON:\n"
        + json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    )
    material = None
    if phase == "reflection":
        instruction = (
            "Return fields plan_alignment (aligned|partial|misaligned|unknown), observations "
            "(1-4 objects with claim and nonempty evidence_refs), hypotheses (0-3 objects with "
            "claim, confidence low|medium|high, evidence_refs), next_search_advice ({direction}), "
            "and memory_action. Cite only exact evaluation:<evaluation_id>, comparison packet or execution "
            "delta refs listed above. A behavior-equivalent source rewrite is not an improvement. "
            "State an unresolved next question specific to the evidence. "
        )
        if arm == "M":
            instruction += (
                "For memory_action choose kind=none with reason, or kind=insight with name, description, "
                "project=bp_online_island605, scene=score, evidence_ref, and body <=1200 Unicode chars. "
                "Use an ASCII letter or digit followed by at most 79 ASCII letters, digits, underscores or hyphens for name. "
                "An insight body must contain **Why:**, **How to apply:**, **Applicability:** and "
                "**Limitations:**. Publish only a reusable, bounded inference supported by this round."
            )
        else:
            instruction += 'Set memory_action to {"kind":"disabled"}.'
    else:
        note, note_ref = _prior_note(run, round_id - 1)
        material = prepare_material(run, round_id)
        instruction = (
            "The accepted previous note contributes its hypotheses and next question to every arm. "
            "Only F and M receive the additional historical material below. The model must decide whether "
            "that material is applicable; it is not an execution command.\n"
            "PRIOR NOTE BASIS: " + json.dumps(note_ref, ensure_ascii=False, sort_keys=True) + "\n"
            "PRIOR HYPOTHESES AND QUESTION: " + json.dumps({
                "hypotheses": note.get("hypotheses", []),
                "next_search_advice": note.get("next_search_advice"),
            }, ensure_ascii=False, sort_keys=True) + "\n"
            f"MATERIAL SHA256: {material['body_sha256']}\n"
            f"MATERIAL BODY:\n{material['body']}\n"
            "Return exactly direction, operations (1-3 objects with type add|remove|replace|preserve, "
            "target, mechanism), preserve, hypothesis, search_intent ({phase: exploration|exploitation}), "
            "and reference_skill_ref (a listed prior incumbent or best-generated ref, or null). "
            "Choose a testable next mechanism; do not claim that intended operations were already executed. "
            "Do not include round_id, feedback_basis, reflection_basis, memory_basis, budget or model; "
            "the host will attach the exact verified bindings."
        )
    prompt = common + instruction + "\n"
    path = BATCH / "controller_prompts" / f"seed_{seed}" / f"{arm}_{phase}_{round_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != prompt:
        raise ValueError("controller_prompt_existing_content_conflict")
    path.write_text(prompt, encoding="utf-8")
    delivery = verify_delivery(run, round_id, path) if material is not None else None
    return {
        "prompt": str(path), "prompt_sha256": _sha(path), "brief": brief_receipt,
        "delivery": delivery, "run": str(run), "state": state["state"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--arm", required=True, choices=ARMS)
    parser.add_argument("--round-id", required=True, type=int)
    parser.add_argument("--phase", required=True, choices=("reflection", "plan"))
    args = parser.parse_args()
    print(json.dumps(build(args.seed, args.arm, args.round_id, args.phase), ensure_ascii=False))
