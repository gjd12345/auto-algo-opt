"""Build each round's research activity from that round's *measured* candidates.

Batch 4/5 shipped the same static finding text in all four rounds: nothing in the
plan could react to what the search actually produced, so a reader could not tell
whether the agent ignored the finding or never received a new one.  This module
closes that gap:

*   every candidate of round ``r`` is replayed offline on the shared six-instance
    suite at the nominal scale and at ``1e-3`` of it (zero provider calls);
*   the round's evidence updates a small hypothesis ledger
    (``hypotheses_state.json``), whose statuses are ``open`` / ``supported`` /
    ``refuted`` with one transition record per round;
*   the next round's ``research_activity`` is rendered from those measurements:
    which candidates were scale-invariant, which paid for it at the nominal
    scale, which simply repeated a refuted shape, and the one constraint the next
    candidate has to meet.

Measured, not asserted: every number in the rendered text comes from the replay,
and a field that could not be measured is omitted rather than guessed.

    python experiments/cvrp_midterm/runs/round_activity.py --run runs/a5_finding_only
    python experiments/cvrp_midterm/runs/round_activity.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/analysis"))
sys.path.insert(0, str(HERE))

from score_probe import build_matrix, load_candidate, simulate  # noqa: E402
from tradeoff_probe import FROZEN_DIR, SUITE, scaled  # noqa: E402

NOMINAL_SCALE = 1.0
SCALED_SCALE = 1e-3
INVARIANT_MAX_SPREAD_PCT = 1.0
NOMINAL_TOLERANCE_PCT = 1.0
REFUTED_SPREAD_PCT = 5.0
REFERENCE_CACHE = HERE.parent / "_reference.json"

HYPOTHESES = {
    "H-SCALE-FREE": (
        "A candidate can hold its 1e-3 spread under {inv:.0f}% while staying within "
        "{tol:.0f}% of the frozen reference at the nominal scale."
    ),
    "H-NO-REPEAT": (
        "The generator stops resubmitting code it already produced and stops "
        "reproducing the refuted pure-width swap."
    ),
    "H-BEAT-REF": "Some generated rule beats the frozen reference on the shared suite.",
}


# ---------------------------------------------------------------- measurement


def _instances() -> list[dict]:
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    return list(suite["instances"])


def _score_source(code: str, instances: list[dict], scales: tuple[float, ...]) -> dict:
    """Replay one candidate at the requested scales; report normalised objectives."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(code, encoding="utf-8")
        fn = load_candidate(path)
        rows: dict[str, float] = {}
        for scale in scales:
            objectives = []
            for instance in instances:
                shifted_instance = scaled(instance, scale)
                try:
                    result = simulate(
                        fn,
                        shifted_instance,
                        matrix=build_matrix(shifted_instance),
                    )
                except (ValueError, RuntimeError, IndexError) as exc:
                    return {
                        "feasible": False,
                        "scale": scale,
                        "reason": f"{type(exc).__name__}: {exc}",
                    }
                served = [node for node in result.route if node != 0]
                expected = len(instance["customer_coordinates"])
                if len(served) != expected or len(set(served)) != expected:
                    return {
                        "feasible": False,
                        "scale": scale,
                        "served": len(served),
                        "expected": expected,
                    }
                objectives.append(float(result.objective) / scale)
            rows[f"{scale:g}"] = float(np.mean(objectives))
    return {"feasible": True, "objectives": rows}


def reference_nominal(instances: list[dict] | None = None, force: bool = False) -> float:
    """Nominal objective of frozen C on the shared suite (cached, deterministic)."""
    if REFERENCE_CACHE.is_file() and not force:
        cached = json.loads(REFERENCE_CACHE.read_text(encoding="utf-8"))
        return float(cached["c_nominal"])
    instances = instances or _instances()
    refreshed = measure_reference(instances)
    try:
        suite = SUITE.resolve().relative_to(REPO).as_posix()
    except ValueError:
        suite = str(SUITE)
    REFERENCE_CACHE.write_text(
        json.dumps(
            {
                "c_nominal": refreshed["nominal"],
                "c_scaled": refreshed["scaled"],
                "c_spread_pct": refreshed["spread_pct"],
                "suite": suite,
                "instances": len(instances),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return float(refreshed["nominal"])


def _delta(candidate: dict, reference: float) -> float:
    value = candidate.get("delta_vs_reference_pct")
    if value is None:
        value = (candidate["nominal"] - reference) / reference * 100.0
    return float(value)


def _spread(candidate: dict) -> float:
    value = candidate.get("spread_pct")
    if value is None:
        value = (candidate["scaled"] - candidate["nominal"]) / candidate["nominal"] * 100.0
    return float(value)


def measure_reference(instances: list[dict] | None = None) -> dict:
    """Score frozen C at both scales: the measurement available before round 1."""
    instances = instances or _instances()
    code = (FROZEN_DIR / "C.py").read_text(encoding="utf-8")
    measured = _score_source(code, instances, (NOMINAL_SCALE, SCALED_SCALE))
    if not measured["feasible"]:
        raise SystemExit(f"frozen C is infeasible on the shared suite: {measured}")
    nominal = measured["objectives"][f"{NOMINAL_SCALE:g}"]
    scaled_value = measured["objectives"][f"{SCALED_SCALE:g}"]
    return {
        "nominal": nominal,
        "scaled": scaled_value,
        "spread_pct": (scaled_value - nominal) / nominal * 100.0,
    }


def cold_start_activity(reference: dict, round_id: int = 1) -> dict:
    """Round 1 activity: the only facts that exist before any candidate is written."""
    summary = (
        f"Measured before any generation: the frozen reference scores "
        f"{reference['nominal']:.4f} on the shared suite at nominal scale and "
        f"{reference['scaled']:.4f} when the same instances are re-expressed at 1e-3, "
        f"i.e. {reference['spread_pct']:+.2f}%. No candidate exists yet, so the first "
        f"test is whether a rule can keep that re-expression within "
        f"{INVARIANT_MAX_SPREAD_PCT:.0f}% while staying within "
        f"{NOMINAL_TOLERANCE_PCT:.0f}% of {reference['nominal']:.4f} at nominal scale."
    )
    return {
        "mode": "used",
        "trigger": "cold_start",
        "question": (
            f"Round {round_id}: what does the frozen reference already show about this "
            "instance family, and what must the first candidate satisfy?"
        ),
        "finding_summary": summary[:2048],
        "finding_status": "empirical_observation",
        "decision": "modify",
        "decision_summary": (
            "Write a rule that is explicit about where its secondary term acts: an "
            "absolute length added to a relative comparison will inherit the "
            f"{reference['spread_pct']:+.1f}% re-expression gap. Measure the candidate "
            f"on both scales, and keep the nominal objective within "
            f"{NOMINAL_TOLERANCE_PCT:.0f}% of the reference before claiming an improvement."
        )[:2048],
        "evidence_refs": ["experiments/cvrp_midterm/_reference.json"],
    }


def _sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def measure_round(round_dir: Path, instances: list[dict] | None = None,
                  reference: float | None = None) -> dict:
    """Score every distinct valid candidate of one round on the shared suite."""
    instances = instances or _instances()
    reference = reference if reference is not None else reference_nominal(instances)
    facts_path = round_dir / "evaluation_facts.json"
    if not facts_path.is_file():
        raise SystemExit(f"no evaluation facts: {facts_path}")
    facts = json.loads(facts_path.read_text(encoding="utf-8"))

    seen: dict[str, dict] = {}
    skipped: list[str] = []
    for candidate in facts.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        code = candidate.get("code")
        if not isinstance(code, str) or not code.strip():
            skipped.append(str(candidate.get("candidate_id")))
            continue
        sha = _sha(code)
        if sha in seen:
            seen[sha]["appearances"] += 1
            continue
        measured = _score_source(code, instances, (NOMINAL_SCALE, SCALED_SCALE))
        record = {
            "sha": sha,
            "candidate_id": candidate.get("candidate_id"),
            "reported_objective": candidate.get("objective"),
            "appearances": 1,
            "feasible": measured["feasible"],
        }
        if measured["feasible"]:
            nominal = measured["objectives"][f"{NOMINAL_SCALE:g}"]
            scaled_value = measured["objectives"][f"{SCALED_SCALE:g}"]
            record.update({
                "nominal": nominal,
                "scaled": scaled_value,
                "spread_pct": (scaled_value - nominal) / nominal * 100.0,
                "delta_vs_reference_pct": (nominal - reference) / reference * 100.0,
            })
        seen[sha] = record

    candidates = list(seen.values())
    feasible = [c for c in candidates if c["feasible"]]
    best = min(feasible, key=lambda c: c["nominal"]) if feasible else None
    return {
        "round_dir": str(round_dir),
        "round_id": int(facts.get("round_id") or -1),
        "reference": reference,
        "baseline_code_sha256": facts.get("baseline_code_sha256"),
        "candidate_count": len(candidates),
        "skipped_candidates": skipped,
        "candidates": candidates,
        "best": best,
        "distinct_shas": [c["sha"] for c in candidates],
    }


# ------------------------------------------------------------ state machine


def empty_state() -> dict:
    return {
        "version": 1,
        "rounds": [],
        "hypotheses": {
            key: {"status": "open", "transitions": []} for key in HYPOTHESES
        },
    }


def _transition(state: dict, key: str, status: str, round_id: int, evidence: str) -> None:
    entry = state["hypotheses"][key]
    if entry["status"] == status and entry["transitions"]:
        entry["transitions"][-1]["evidence"] = evidence
        entry["transitions"][-1]["round"] = round_id
        return
    entry["status"] = status
    entry["transitions"].append(
        {"round": round_id, "status": status, "evidence": evidence}
    )


def update_state(state: dict, measure: dict, *, prior_shas: set[str]) -> dict:
    """Fold one round's measurement into the hypothesis ledger."""
    round_id = measure["round_id"]
    reference = measure["reference"]
    feasible = [c for c in measure["candidates"] if c["feasible"]]

    invariant = [c for c in feasible if abs(_spread(c)) <= INVARIANT_MAX_SPREAD_PCT]
    invariant_ok = [
        c for c in invariant
        if c["nominal"] <= reference * (1.0 + NOMINAL_TOLERANCE_PCT / 100.0)
    ]
    if invariant_ok:
        best_ok = min(invariant_ok, key=lambda c: c["nominal"])
        _transition(
            state, "H-SCALE-FREE", "supported", round_id,
            f"{len(invariant_ok)}/{len(feasible)} candidates kept spread <= "
            f"{INVARIANT_MAX_SPREAD_PCT:.0f}% and stayed within "
            f"{NOMINAL_TOLERANCE_PCT:.0f}% of {reference:.4f} "
            f"(best {best_ok['nominal']:.4f}, {_delta(best_ok, reference):+.2f}%)",
        )
    elif invariant:
        cheapest = min(invariant, key=lambda c: c["nominal"])
        _transition(
            state, "H-SCALE-FREE", "refuted", round_id,
            f"all {len(invariant)} invariant candidates paid at nominal scale "
            f"(cheapest {cheapest['nominal']:.4f}, "
            f"{_delta(cheapest, reference):+.2f}% vs {reference:.4f})",
        )
    else:
        _transition(
            state, "H-SCALE-FREE", "open", round_id,
            f"no candidate reached a spread <= {INVARIANT_MAX_SPREAD_PCT:.0f}% "
            f"({len(feasible)} feasible candidates measured)",
        )

    previous = state["rounds"][-1] if state["rounds"] else None
    # The search engine always re-evaluates the seed and the current incumbent,
    # so carrying those two forward is elitism, not a re-proposal. Only code the
    # generator itself proposed in an earlier round counts as a repeat.
    carried = {measure.get("baseline_code_sha256") or ""}
    carried.add((previous or {}).get("best_sha") or "")
    carried.discard("")
    repeats = [
        c for c in feasible if c["sha"] in prior_shas and c["sha"] not in carried
    ]
    refuted_shape = [c for c in feasible if _spread(c) >= REFUTED_SPREAD_PCT]
    if repeats or refuted_shape:
        _transition(
            state, "H-NO-REPEAT", "refuted", round_id,
            f"{len(repeats)} re-proposed sha(s) from earlier rounds "
            f"(carried-forward seed/incumbent excluded), "
            f"{len(refuted_shape)} candidate(s) reproduced the swap with spread >= "
            f"{REFUTED_SPREAD_PCT:.0f}%",
        )
    elif feasible:
        _transition(
            state, "H-NO-REPEAT", "supported", round_id,
            f"{len(feasible)} distinct candidate(s), none repeated and none with "
            f"spread >= {REFUTED_SPREAD_PCT:.0f}%",
        )

    if feasible:
        best = min(feasible, key=lambda c: c["nominal"])
        if best["nominal"] <= reference:
            _transition(
                state, "H-BEAT-REF", "supported", round_id,
                f"best {best['nominal']:.4f} <= reference {reference:.4f}",
            )
        else:
            _transition(
                state, "H-BEAT-REF", "open", round_id,
                f"best {best['nominal']:.4f} is {_delta(best, reference):+.2f}% vs "
                f"reference {reference:.4f}",
            )

    row_shas = set(measure["distinct_shas"])
    best_value = (measure["best"] or {}).get("nominal")
    stagnant_rounds = 0
    if previous and best_value is not None and previous.get("best_nominal") is not None:
        if abs(best_value - previous["best_nominal"]) <= 1e-9 * max(1.0, abs(best_value)):
            stagnant_rounds = int(previous.get("stagnant_rounds") or 0) + 1
    state["rounds"].append({
        "round_id": round_id,
        "candidate_count": measure["candidate_count"],
        "feasible_count": len(feasible),
        "best_nominal": best_value,
        "best_sha": (measure["best"] or {}).get("sha"),
        "best_spread_pct": (measure["best"] or {}).get("spread_pct"),
        "best_delta_vs_reference_pct": (measure["best"] or {}).get("delta_vs_reference_pct"),
        "distinct_shas": measure["distinct_shas"],
        "new_shas": sorted(row_shas - prior_shas - carried),
        "repeated_shas": sorted((row_shas & prior_shas) - carried),
        "carried_shas": sorted(row_shas & carried),
        "stagnant_rounds": stagnant_rounds,
        "previous_best": (previous or {}).get("best_nominal"),
    })
    return state


def status_of(state: dict, key: str) -> str:
    return state["hypotheses"][key]["status"]


# ---------------------------------------------------------------- rendering


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def _row_for(state: dict, round_id: int) -> dict:
    for row in reversed(state["rounds"]):
        if row["round_id"] == round_id:
            return row
    return {}


def _progress_sentence(row: dict) -> str:
    """Round-specific progress note; this is what makes each round's text differ."""
    new = len(row.get("new_shas") or [])
    repeated = len(row.get("repeated_shas") or [])
    stagnant = int(row.get("stagnant_rounds") or 0)
    previous = row.get("previous_best")
    if stagnant == 0 and previous is not None:
        return (
            f"New best (previous round {previous:.4f}); {new} new code hash(es), "
            f"{repeated} reused."
        )
    if stagnant == 0:
        return f"First measured round; {new} distinct code hash(es)."
    return (
        f"Best unchanged for the {stagnant + 1} consecutive round(s); {new} new code "
        f"hash(es), {repeated} reused from earlier rounds or the seed."
    )


def render_activity(state: dict, measure: dict, *, round_id: int) -> dict:
    """Render the round's activity from measured facts (never from prose)."""
    reference = measure["reference"]
    feasible = [c for c in measure["candidates"] if c["feasible"]]
    best = min(feasible, key=lambda c: c["nominal"]) if feasible else None
    invariant = [c for c in feasible if abs(_spread(c)) <= INVARIANT_MAX_SPREAD_PCT]
    refuted_shape = [c for c in feasible if _spread(c) >= REFUTED_SPREAD_PCT]
    row = _row_for(state, round_id - 1)
    stagnant = int(row.get("stagnant_rounds") or 0)

    if best is None:
        summary = (
            f"Round {round_id - 1}: none of the {measure['candidate_count']} candidates "
            "was feasible on the shared suite, so there is no measurement to steer by."
        )
        decision = "modify"
        decision_summary = (
            "Submit only candidates that keep the capacity filter and serve every "
            "customer; an infeasible rule cannot be scored."
        )
        trigger = "badcase"
    else:
        summary = (
            f"Round {round_id - 1}: {len(feasible)} of {measure['candidate_count']} "
            f"distinct candidates feasible. Best nominal {best['nominal']:.4f} "
            f"({_pct(_delta(best, reference))} vs frozen reference {reference:.4f}); "
            f"re-expressing the same instances at 1e-3 moves it by "
            f"{_pct(_spread(best))}. {len(invariant)} candidate(s) held the spread under "
            f"{INVARIANT_MAX_SPREAD_PCT:.0f}%, {len(refuted_shape)} reproduced the refuted "
            f"pure-width swap (spread >= {REFUTED_SPREAD_PCT:.0f}%). "
            + _progress_sentence(row)
        )
        if best["nominal"] <= reference:
            decision = "retain"
            decision_summary = (
                f"The best candidate already matches or beats the reference at nominal "
                f"scale (spread {_pct(_spread(best))}). Keep its mechanism, and make the "
                "next round remove the remaining scale sensitivity without giving back "
                "the nominal gain."
            )
        elif stagnant >= 1:
            decision = "modify"
            decision_summary = (
                f"The objective has not improved for {stagnant + 1} consecutive round(s) "
                f"and still sits {_pct(_delta(best, reference))} above {reference:.4f}. "
                "Another width tweak would reproduce this plateau: change the mechanism "
                "that decides *where* the secondary term is allowed to act, then report "
                "the nominal objective and the 1e-3 spread for the new candidate."
            )
        elif invariant and all(c["nominal"] > reference * 1.01 for c in invariant):
            decision = "modify"
            decision_summary = (
                f"Invariance alone keeps losing at nominal scale (cheapest invariant "
                f"{min(invariant, key=lambda c: c['nominal'])['nominal']:.4f} vs "
                f"{reference:.4f}). Change the mechanism that chooses the tie-break value, "
                "not only the width: keep the nominal score within "
                f"{NOMINAL_TOLERANCE_PCT:.0f}% of the reference and let the second stage "
                "act only where primary scores fall inside a relative band."
            )
        else:
            decision = "modify"
            decision_summary = (
                f"The best rule still costs {_pct(_delta(best, reference))} at nominal "
                f"scale with spread {_pct(_spread(best))}. The next candidate must be "
                "measured on both scales before submission: nominal within "
                f"{NOMINAL_TOLERANCE_PCT:.0f}% of {reference:.4f} and 1e-3 spread under "
                f"{INVARIANT_MAX_SPREAD_PCT:.0f}%."
            )
        trigger = "stagnation" if stagnant >= 1 else ("cold_start" if round_id <= 2 else "badcase")

    status_bits = [f"{key}={state['hypotheses'][key]['status']}" for key in HYPOTHESES]
    activity = {
        "mode": "used",
        "trigger": trigger,
        "question": (
            f"Round {round_id}: which measured candidate behaviour should the next rule "
            "keep, and which refuted shape must it avoid?"
        ),
        "finding_summary": summary[:2048],
        "finding_status": "empirical_observation",
        "decision": decision,
        "decision_summary": decision_summary[:2048],
        "evidence_refs": [
            "experiments/cvrp_midterm/_reference.json",
            f"hypotheses_state.json#round-{round_id - 1}",
        ],
    }
    if round_id > 1:
        activity["evidence_refs"].append(
            f"rounds/round_{round_id - 1:04d}/evaluation_facts.json"
        )
    return {"activity": activity, "status_bits": status_bits}


def evaluation_hypotheses(state: dict, round_id: int) -> list[dict]:
    """The contract's hypothesis channel: claim + confidence + evidence refs."""
    weight = {"supported": "high", "refuted": "high", "open": "low"}
    row = _row_for(state, round_id)
    movement = ""
    stagnant = int(row.get("stagnant_rounds") or 0)
    if stagnant >= 1:
        movement = f" No new best for {stagnant + 1} consecutive rounds."
    items = []
    for key, template in HYPOTHESES.items():
        entry = state["hypotheses"][key]
        last = entry["transitions"][-1] if entry["transitions"] else None
        evidence = last["evidence"] if last else "no measurement yet"
        items.append({
            "claim": (
                f"{key} is {entry['status']} after round {round_id}: "
                + template.format(
                    inv=INVARIANT_MAX_SPREAD_PCT, tol=NOMINAL_TOLERANCE_PCT
                )
                + f" — {evidence}.{movement}"
            )[:1024],
            "confidence": weight[entry["status"]],
            "evidence_refs": [
                "hypotheses_state.json",
                f"rounds/round_{round_id:04d}/evaluation_facts.json",
            ],
        })
    return items


# -------------------------------------------------------------------- driver


def load_state(run_root: Path) -> dict:
    path = run_root / "hypotheses_state.json"
    if not path.is_file():
        return empty_state()
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(run_root: Path, state: dict) -> None:
    (run_root / "hypotheses_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def advance(run_root: Path, round_id: int) -> dict:
    """Measure ``round_id``, update the ledger, and return the next activity."""
    state = load_state(run_root)
    prior: set[str] = set()
    for row in state["rounds"]:
        prior.update(row["distinct_shas"])
    round_dir = run_root / "rounds" / f"round_{round_id:04d}"
    measure = measure_round(round_dir)
    if measure["baseline_code_sha256"]:
        prior.add(str(measure["baseline_code_sha256"]))
    state = update_state(state, measure, prior_shas=prior)
    save_state(run_root, state)
    rendered = render_activity(state, measure, round_id=round_id + 1)
    return {
        "measure": measure,
        "state": state,
        "activity": rendered["activity"],
        "status_bits": rendered["status_bits"],
        "hypotheses": evaluation_hypotheses(state, round_id),
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", help="run directory to replay (all four rounds)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.run:
        parser.error("--run or --selftest is required")

    run_root = Path(args.run)
    if not run_root.is_absolute():
        run_root = (HERE / run_root).resolve()
    for round_id in range(1, 5):
        round_dir = run_root / "rounds" / f"round_{round_id:04d}"
        if not (round_dir / "evaluation_facts.json").is_file():
            break
        result = advance(run_root, round_id)
        print(json.dumps({
            "round": round_id,
            "best_nominal": (result["measure"]["best"] or {}).get("nominal"),
            "status": result["status_bits"],
            "activity": result["activity"],
        }, ensure_ascii=False, indent=2))
    return 0


def _selftest() -> int:
    """Offline check of the state machine on synthetic measurements."""
    state = empty_state()
    invariant_but_costly = {
        "round_id": 1,
        "reference": 10.0,
        "candidate_count": 2,
        "candidates": [
            {"sha": "a", "feasible": True, "nominal": 10.5, "spread_pct": 0.2},
            {"sha": "b", "feasible": True, "nominal": 11.0, "spread_pct": 8.0},
        ],
        "best": None,
        "distinct_shas": ["a", "b"],
    }
    state = update_state(state, invariant_but_costly, prior_shas=set())
    assert status_of(state, "H-SCALE-FREE") == "refuted", status_of(state, "H-SCALE-FREE")
    assert status_of(state, "H-NO-REPEAT") == "refuted"

    free = {
        "round_id": 2,
        "reference": 10.0,
        "candidate_count": 1,
        "candidates": [
            {"sha": "c", "feasible": True, "nominal": 10.0, "spread_pct": 0.1},
        ],
        "best": None,
        "distinct_shas": ["c"],
    }
    state = update_state(state, free, prior_shas={"a", "b"})
    assert status_of(state, "H-SCALE-FREE") == "supported"
    assert status_of(state, "H-BEAT-REF") == "supported"
    assert status_of(state, "H-NO-REPEAT") == "supported"

    repeated = dict(free)
    repeated["round_id"] = 3
    repeated["candidates"] = [
        {"sha": "a", "feasible": True, "nominal": 10.0, "spread_pct": 0.1},
    ]
    state = update_state(state, repeated, prior_shas={"a", "b", "c"})
    assert status_of(state, "H-NO-REPEAT") == "refuted"

    rendered = render_activity(state, invariant_but_costly, round_id=5)
    assert rendered["activity"]["decision"] == "modify"
    assert "Round 4" in rendered["activity"]["finding_summary"]
    items = evaluation_hypotheses(state, 4)
    assert len(items) == len(HYPOTHESES)
    assert all(item["confidence"] in {"low", "medium", "high"} for item in items)
    print("selftest ok:", json.dumps(
        {key: state["hypotheses"][key]["status"] for key in HYPOTHESES}
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
