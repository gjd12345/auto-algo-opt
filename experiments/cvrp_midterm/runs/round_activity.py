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
MEASUREMENT_SPEC = "cvrp_construct_shared_nominal_1e-3_v2"
SEED_ORIGINS = frozenset({"baseline", "explicit_parent", "population_seed"})

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


def load_session_dev_instances(run_root: Path) -> list[dict]:
    """Load the 4-instance session search suite (explicitly distinct from shared 6-inst suite)."""
    dev_path = run_root / "dev_suite.json"
    suite = json.loads(dev_path.read_text(encoding="utf-8"))
    return list(suite["instances"])


def _canonical_instance_payload(instance: dict) -> dict:
    return {
        "depot": [float(x) for x in instance["depot"]],
        "customer_coordinates": [
            [float(x), float(y)] for x, y in instance["customer_coordinates"]
        ],
        "demands": [float(d) for d in instance["demands"]],
        "capacity": float(instance["capacity"]),
    }


def suite_content_hash(instances: list[dict]) -> str:
    payload = [_canonical_instance_payload(inst) for inst in instances]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _c_source_hash(reference_code: str | None = None) -> str:
    if reference_code is None:
        reference_code = (FROZEN_DIR / "C.py").read_text(encoding="utf-8")
    return hashlib.sha256(reference_code.encode("utf-8")).hexdigest()


def _score_source(code: str, instances: list[dict], scales: tuple[float, ...]) -> dict:
    """Replay one candidate at the requested scales; report normalised objectives."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(code, encoding="utf-8")
        try:
            fn = load_candidate(path)
        except Exception as exc:  # noqa: BLE001
            return {
                "feasible": False,
                "scale": None,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        rows: dict[str, float] = {}
        early_returns_by_scale: dict[str, int] = {}
        per_instance_nominal: list[float] = []
        for scale in scales:
            objectives = []
            early_returns = 0
            for instance in instances:
                shifted_instance = scaled(instance, scale)
                try:
                    result = simulate(
                        fn,
                        shifted_instance,
                        matrix=build_matrix(shifted_instance),
                    )
                except (ValueError, RuntimeError, IndexError, TypeError, ZeroDivisionError, FloatingPointError) as exc:
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
                        "reason": f"incomplete_route: served={len(served)} expected={expected}",
                        "served": len(served),
                        "expected": expected,
                    }
                norm_obj = float(result.objective) / scale
                objectives.append(norm_obj)
                early_returns += int(result.early_returns)
                if scale == NOMINAL_SCALE:
                    per_instance_nominal.append(norm_obj)
            rows[f"{scale:g}"] = float(np.mean(objectives))
            early_returns_by_scale[f"{scale:g}"] = early_returns
    return {
        "feasible": True,
        "objectives": rows,
        "per_instance_nominal": per_instance_nominal,
        "early_returns": early_returns_by_scale,
    }


def reference_nominal(
    instances: list[dict] | None = None,
    force: bool = False,
    *,
    cache_path: Path | None = REFERENCE_CACHE,
    reference_code: str | None = None,
    measurement_spec: str = MEASUREMENT_SPEC,
    suite_role: str | None = None,
    write_cache: bool | None = None,
) -> float:
    """Nominal objective of frozen C on the specified suite (identity-keyed cache)."""
    using_default_suite = instances is None
    active_instances = _instances() if instances is None else list(instances)
    if not active_instances:
        raise ValueError("instances must be non-empty")
    content_hash = suite_content_hash(active_instances)
    c_hash = _c_source_hash(reference_code)
    role = suite_role or ("shared_diagnostic_6" if using_default_suite else "custom_suite")

    if cache_path is not None and cache_path.is_file() and not force:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = {}
        # Legacy caches without identity fields are recognized and treated as stale
        # so callers with a different suite/reference/spec always recompute cleanly.
        if (
            isinstance(cached, dict)
            and cached.get("suite_content_hash") == content_hash
            and cached.get("c_source_sha256") == c_hash
            and cached.get("measurement_spec") == measurement_spec
            and isinstance(cached.get("c_nominal"), (int, float))
        ):
            return float(cached["c_nominal"])

    refreshed = measure_reference(active_instances, reference_code=reference_code)
    should_write = (
        write_cache
        if write_cache is not None
        else (cache_path is not None and (using_default_suite or cache_path != REFERENCE_CACHE))
    )
    if should_write and cache_path is not None:
        if using_default_suite:
            try:
                suite_str = SUITE.resolve().relative_to(REPO).as_posix()
            except ValueError:
                suite_str = str(SUITE)
        else:
            suite_str = role
        cache_path.write_text(
            json.dumps(
                {
                    "c_nominal": refreshed["nominal"],
                    "c_scaled": refreshed["scaled"],
                    "c_spread_pct": refreshed["spread_pct"],
                    "suite": suite_str,
                    "suite_role": role,
                    "instances": len(active_instances),
                    "suite_content_hash": content_hash,
                    "c_source_sha256": c_hash,
                    "measurement_spec": measurement_spec,
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


def measure_reference(
    instances: list[dict] | None = None,
    *,
    reference_code: str | None = None,
) -> dict:
    """Score frozen C at both scales: the measurement available before round 1."""
    active_instances = _instances() if instances is None else list(instances)
    code = (
        reference_code
        if reference_code is not None
        else (FROZEN_DIR / "C.py").read_text(encoding="utf-8")
    )
    measured = _score_source(code, active_instances, (NOMINAL_SCALE, SCALED_SCALE))
    if not measured["feasible"]:
        raise SystemExit(f"frozen C is infeasible on the target suite: {measured}")
    nominal = measured["objectives"][f"{NOMINAL_SCALE:g}"]
    scaled_value = measured["objectives"][f"{SCALED_SCALE:g}"]
    return {
        "nominal": nominal,
        "scaled": scaled_value,
        "spread_pct": (scaled_value - nominal) / nominal * 100.0,
        "suite_content_hash": suite_content_hash(active_instances),
        "c_source_sha256": _c_source_hash(code),
        "instances": len(active_instances),
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


def measure_round(
    round_dir: Path,
    instances: list[dict] | None = None,
    reference: float | None = None,
    *,
    suite_role: str | None = None,
    use_session_dev_suite: bool = False,
) -> dict:
    """Score every officially valid distinct candidate of one round on the target suite.

    Separately tracks:
    - ``official_valid`` (from ``evaluation_facts.json``),
    - ``probe_feasible`` (from ``_score_source`` at nominal + 1e-3 scales),
    - ``included = official_valid and probe_feasible``.

    Only ``included`` candidates participate in best-objective, spread, and
    feasibility statistics; officially rejected candidates are never executed in
    the probe and keep their official rejection error code/detail for auditing.
    """
    using_default_suite = instances is None and not use_session_dev_suite
    if use_session_dev_suite:
        active_instances = load_session_dev_instances(round_dir.parents[1])
        role = suite_role or "session_dev_4"
    elif instances is None:
        active_instances = _instances()
        role = suite_role or "shared_diagnostic_6"
    else:
        active_instances = list(instances)
        role = suite_role or "custom_suite"

    if reference is None:
        reference = reference_nominal(
            None if using_default_suite else active_instances,
            suite_role=role,
        )
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
        origin = str(candidate.get("origin") or "unknown")
        # Default True only for legacy/synthetic dicts that omit 'valid'
        cand_official_valid = bool(candidate.get("valid", True))
        if sha in seen:
            rec = seen[sha]
            rec["appearances"] += 1
            if origin not in rec["origins"]:
                rec["origins"].append(origin)
            if cand_official_valid and not rec["official_valid"]:
                rec["official_valid"] = True
                rec["official_error_code"] = None
                rec["official_error_detail"] = None
            continue
        seen[sha] = {
            "sha": sha,
            "code": code,
            "candidate_id": candidate.get("candidate_id"),
            "reported_objective": candidate.get("objective"),
            "appearances": 1,
            "origins": [origin],
            "official_valid": cand_official_valid,
            "official_error_code": None if cand_official_valid else candidate.get("error_code"),
            "official_error_detail": None if cand_official_valid else candidate.get("error_detail"),
        }

    candidates: list[dict] = []
    official_rejected: list[dict] = []
    probe_failed: list[dict] = []
    for rec in seen.values():
        code = rec.pop("code")
        rec["origins"] = sorted(rec["origins"])
        if not rec["official_valid"]:
            rec.update({
                "probe_feasible": None,
                "probe_reason": "skipped_official_invalid",
                "included": False,
                "feasible": False,
            })
            official_rejected.append({
                "sha": rec["sha"],
                "candidate_id": rec["candidate_id"],
                "origins": rec["origins"],
                "error_code": rec["official_error_code"],
                "error_detail": rec["official_error_detail"],
            })
            candidates.append(rec)
            continue

        measured = _score_source(code, active_instances, (NOMINAL_SCALE, SCALED_SCALE))
        probe_ok = bool(measured["feasible"])
        rec["probe_feasible"] = probe_ok
        rec["probe_reason"] = None if probe_ok else measured.get("reason")
        rec["included"] = probe_ok
        rec["feasible"] = probe_ok
        if probe_ok:
            nominal = measured["objectives"][f"{NOMINAL_SCALE:g}"]
            scaled_value = measured["objectives"][f"{SCALED_SCALE:g}"]
            rec.update({
                "nominal": nominal,
                "scaled": scaled_value,
                "spread_pct": (scaled_value - nominal) / nominal * 100.0,
                "delta_vs_reference_pct": (nominal - reference) / reference * 100.0,
                "early_returns": measured.get("early_returns"),
            })
        else:
            probe_failed.append({
                "sha": rec["sha"],
                "candidate_id": rec["candidate_id"],
                "origins": rec["origins"],
                "reason": rec["probe_reason"],
            })
        candidates.append(rec)

    included = [c for c in candidates if c["included"]]
    best = min(included, key=lambda c: c["nominal"]) if included else None
    return {
        "round_dir": str(round_dir),
        "round_id": int(facts.get("round_id") or -1),
        "suite_role": role,
        "suite_instance_count": len(active_instances),
        "suite_content_hash": suite_content_hash(active_instances),
        "measurement_spec": MEASUREMENT_SPEC,
        "reference": reference,
        "baseline_code_sha256": facts.get("baseline_code_sha256"),
        "candidate_count": len(candidates),
        "official_valid_count": sum(1 for c in candidates if c["official_valid"]),
        "official_rejected_count": len(official_rejected),
        "probe_failed_count": len(probe_failed),
        "included_count": len(included),
        "official_rejected": official_rejected,
        "probe_failed": probe_failed,
        "skipped_candidates": skipped,
        "candidates": candidates,
        "best": best,
        "distinct_shas": [c["sha"] for c in candidates],
        "included_shas": [c["sha"] for c in included],
    }


# ------------------------------------------------------------ state machine


def empty_state() -> dict:
    return {
        "version": 2,
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


def _is_eligible(candidate: dict) -> bool:
    if "included" in candidate:
        return bool(candidate["included"])
    if "official_valid" in candidate and not candidate["official_valid"]:
        return False
    return bool(candidate.get("feasible"))


def _is_generated(candidate: dict) -> bool:
    origins = candidate.get("origins")
    if isinstance(origins, list) and origins:
        return "generated" in origins
    # Fallback for synthetic unit-test payloads without origin metadata
    return True


def _is_seed_only(candidate: dict) -> bool:
    origins = candidate.get("origins")
    if isinstance(origins, list) and origins:
        return "generated" not in origins and bool(set(origins) & SEED_ORIGINS)
    return False


def update_state(state: dict, measure: dict, *, prior_shas: set[str]) -> dict:
    """Fold one round's measurement into the hypothesis ledger."""
    round_id = measure["round_id"]
    reference = measure["reference"]
    feasible = [c for c in measure["candidates"] if _is_eligible(c)]

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
            f"({len(feasible)} eligible candidates measured)",
        )

    previous = state["rounds"][-1] if state["rounds"] else None
    # Distinguish freshly generated candidates from inherited seeds/elites by
    # origin metadata AND prior hashes so inherited seeds are never counted as
    # new or repeated proposals.
    carried_ids = {measure.get("baseline_code_sha256") or ""}
    carried_ids.add((previous or {}).get("best_sha") or "")
    carried_ids.discard("")

    seed_only_shas = {c["sha"] for c in measure["candidates"] if _is_seed_only(c)}
    carried = carried_ids | seed_only_shas
    generated_shas = {c["sha"] for c in measure["candidates"] if _is_generated(c)}

    repeats = [
        c for c in feasible
        if _is_generated(c) and c["sha"] in prior_shas and c["sha"] not in carried_ids
    ]
    refuted_shape = [c for c in feasible if _spread(c) >= REFUTED_SPREAD_PCT]
    if repeats or refuted_shape:
        _transition(
            state, "H-NO-REPEAT", "refuted", round_id,
            f"{len(repeats)} re-proposed generated sha(s) from earlier rounds "
            f"(inherited seeds/incumbent excluded), "
            f"{len(refuted_shape)} candidate(s) reproduced spread >= "
            f"{REFUTED_SPREAD_PCT:.0f}%",
        )
    elif feasible:
        _transition(
            state, "H-NO-REPEAT", "supported", round_id,
            f"{len(feasible)} eligible candidate(s), none repeated and none with "
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
    best_obj = measure.get("best") or (min(feasible, key=lambda c: c["nominal"]) if feasible else None)
    best_value = (best_obj or {}).get("nominal")
    prev_best = (previous or {}).get("best_nominal")
    prev_incumbent = (previous or {}).get("incumbent_best_nominal")
    if prev_incumbent is None and prev_best is not None:
        prev_incumbent = prev_best

    if best_value is None:
        progress_status = "no_valid_candidate"
        stagnant_rounds = int((previous or {}).get("stagnant_rounds") or 0) + (1 if previous else 0)
        incumbent_best = prev_incumbent
    elif prev_best is None:
        progress_status = "first_round"
        stagnant_rounds = 0
        incumbent_best = best_value
    else:
        tol = 1e-9 * max(1.0, abs(best_value), abs(prev_best))
        if best_value < prev_best - tol:
            progress_status = "improved"
            stagnant_rounds = 0
        elif abs(best_value - prev_best) <= tol:
            progress_status = "stagnant"
            stagnant_rounds = int(previous.get("stagnant_rounds") or 0) + 1
        else:
            progress_status = "regressed"
            stagnant_rounds = int(previous.get("stagnant_rounds") or 0) + 1
        incumbent_best = min(best_value, prev_incumbent) if prev_incumbent is not None else best_value

    new_shas = sorted(generated_shas - prior_shas - carried_ids)
    repeated_shas = sorted((generated_shas & prior_shas) - carried_ids)
    carried_shas = sorted(row_shas & carried)
    state["rounds"].append({
        "round_id": round_id,
        "suite_role": measure.get("suite_role"),
        "suite_content_hash": measure.get("suite_content_hash"),
        "candidate_count": measure["candidate_count"],
        "official_valid_count": measure.get("official_valid_count", measure["candidate_count"]),
        "official_rejected_count": measure.get("official_rejected_count", 0),
        "probe_failed_count": measure.get("probe_failed_count", 0),
        "included_count": len(feasible),
        "feasible_count": len(feasible),
        "best_nominal": best_value,
        "best_sha": (best_obj or {}).get("sha"),
        "best_spread_pct": (best_obj or {}).get("spread_pct"),
        "best_delta_vs_reference_pct": (best_obj or {}).get("delta_vs_reference_pct"),
        "distinct_shas": measure["distinct_shas"],
        "new_shas": new_shas,
        "repeated_shas": repeated_shas,
        "carried_shas": carried_shas,
        "exact_code_repeat_count": len(repeated_shas),
        "mechanism_repeat_count": len(refuted_shape),
        "stagnant_rounds": stagnant_rounds,
        "progress_status": progress_status,
        "previous_best": prev_best,
        "incumbent_best_nominal": incumbent_best,
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
    """Round-specific progress note comparing adjacent round bests and historical incumbent."""
    new = len(row.get("new_shas") or [])
    repeated = len(row.get("repeated_shas") or [])
    stagnant = int(row.get("stagnant_rounds") or 0)
    current = row.get("best_nominal")
    previous = row.get("previous_best")
    incumbent = row.get("incumbent_best_nominal")
    inc_note = f"; historical incumbent {incumbent:.4f}" if incumbent is not None else ""

    if current is None:
        prev_note = f" (previous round best {previous:.4f}{inc_note})" if previous is not None else ""
        return (
            f"No valid candidate measured in this round{prev_note}; "
            f"{new} new generated code hash(es), {repeated} repeated."
        )
    if previous is None:
        return (
            f"First measured round (round best {current:.4f}); "
            f"{new} distinct generated code hash(es)."
        )
    tol = 1e-9 * max(1.0, abs(current), abs(previous))
    if current < previous - tol:
        return (
            f"Improved vs previous round best ({previous:.4f} -> {current:.4f}{inc_note}); "
            f"{new} new generated code hash(es), {repeated} repeated."
        )
    if abs(current - previous) <= tol:
        return (
            f"Stagnant vs previous round best ({current:.4f}) for {stagnant + 1} "
            f"consecutive round(s){inc_note}; {new} new generated code hash(es), "
            f"{repeated} repeated."
        )
    return (
        f"Regressed vs previous round best ({previous:.4f} -> {current:.4f}{inc_note}); "
        f"{new} new generated code hash(es), {repeated} repeated."
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


def discover_rounds(run_root: Path) -> dict:
    """Discover saved round directories under ``rounds/round_*`` sorted by round_id."""
    rounds_dir = run_root / "rounds"
    complete: list[int] = []
    incomplete: list[int] = []
    if rounds_dir.is_dir():
        found: list[tuple[int, Path]] = []
        for entry in rounds_dir.iterdir():
            if not entry.is_dir() or not entry.name.startswith("round_"):
                continue
            suffix = entry.name[len("round_"):]
            if suffix.isdigit():
                found.append((int(suffix), entry))
        found.sort(key=lambda pair: pair[0])
        for rid, path in found:
            if (path / "evaluation_facts.json").is_file():
                complete.append(rid)
            else:
                incomplete.append(rid)
    all_seen = sorted(set(complete) | set(incomplete))
    missing: list[int] = []
    if all_seen:
        expected = set(range(1, max(all_seen) + 1))
        missing = sorted(expected - set(all_seen))
    return {
        "complete_rounds": complete,
        "incomplete_rounds": incomplete,
        "missing_round_ids": missing,
    }


def replay_run(
    run_root: Path,
    *,
    out_dir: Path | None = None,
    instances: list[dict] | None = None,
    use_session_dev_suite: bool = False,
) -> dict:
    """Deterministically replay a finished or interrupted run from empty state.

    Never overwrites historical ``hypotheses_state.json`` inside ``run_root``.
    When ``out_dir`` is given, writes ``<out_dir>/<run_name>_replay.json``.
    """
    discovered = discover_rounds(run_root)
    state = empty_state()
    prior: set[str] = set()
    rounds_summary: list[dict] = []

    for round_id in discovered["complete_rounds"]:
        round_dir = run_root / "rounds" / f"round_{round_id:04d}"
        measure = measure_round(
            round_dir,
            instances=instances,
            use_session_dev_suite=use_session_dev_suite,
        )
        if measure["baseline_code_sha256"]:
            prior.add(str(measure["baseline_code_sha256"]))
        state = update_state(state, measure, prior_shas=set(prior))
        for cand in measure["candidates"]:
            if cand.get("included") and "generated" in (cand.get("origins") or []):
                prior.add(cand["sha"])
        rendered = render_activity(state, measure, round_id=round_id + 1)
        row_state = state["rounds"][-1]
        rounds_summary.append({
            "round_id": round_id,
            "suite_role": measure["suite_role"],
            "suite_content_hash": measure["suite_content_hash"],
            "candidate_count": measure["candidate_count"],
            "official_valid_count": measure["official_valid_count"],
            "official_rejected_count": measure["official_rejected_count"],
            "probe_failed_count": measure["probe_failed_count"],
            "included_count": measure["included_count"],
            "official_rejected": measure["official_rejected"],
            "probe_failed": measure["probe_failed"],
            "best_nominal": (measure["best"] or {}).get("nominal"),
            "best_spread_pct": (measure["best"] or {}).get("spread_pct"),
            "progress_status": row_state["progress_status"],
            "exact_code_repeat_count": row_state["exact_code_repeat_count"],
            "mechanism_repeat_count": row_state["mechanism_repeat_count"],
            "status_bits": rendered["status_bits"],
            "finding_summary": rendered["activity"]["finding_summary"],
            "decision_summary": rendered["activity"]["decision_summary"],
        })

    payload = {
        "run": run_root.name,
        "discovered": discovered,
        "rounds": rounds_summary,
        "state": state,
    }
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{run_root.name}_replay.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return payload


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", help="run directory to replay (auto-discovers all saved rounds)")
    parser.add_argument("--out-dir", type=Path, help="optional directory for deterministic replay JSON")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.run:
        parser.error("--run or --selftest is required")

    run_root = Path(args.run)
    if not run_root.is_absolute():
        run_root = (HERE / run_root).resolve()
    result = replay_run(run_root, out_dir=args.out_dir)
    print(json.dumps({
        "run": result["run"],
        "discovered": result["discovered"],
        "rounds": [
            {
                "round_id": r["round_id"],
                "best_nominal": r["best_nominal"],
                "progress_status": r["progress_status"],
                "official_rejected_count": r["official_rejected_count"],
                "probe_failed_count": r["probe_failed_count"],
                "included_count": r["included_count"],
                "status_bits": r["status_bits"],
            }
            for r in result["rounds"]
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def _selftest() -> int:
    """Offline check of the state machine and progress sentences on synthetic measurements."""
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
    assert state["rounds"][-1]["progress_status"] == "first_round"

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
    assert state["rounds"][-1]["progress_status"] == "improved"
    assert "Improved" in _progress_sentence(state["rounds"][-1])

    repeated = dict(free)
    repeated["round_id"] = 3
    repeated["candidates"] = [
        {"sha": "a", "feasible": True, "nominal": 10.0, "spread_pct": 0.1},
    ]
    state = update_state(state, repeated, prior_shas={"a", "b", "c"})
    assert status_of(state, "H-NO-REPEAT") == "refuted"
    assert state["rounds"][-1]["progress_status"] == "stagnant"
    assert "Stagnant" in _progress_sentence(state["rounds"][-1])

    regressed = dict(free)
    regressed["round_id"] = 4
    regressed["candidates"] = [
        {"sha": "d", "feasible": True, "nominal": 11.0, "spread_pct": 0.1},
    ]
    state = update_state(state, regressed, prior_shas={"a", "b", "c"})
    assert state["rounds"][-1]["progress_status"] == "regressed"
    sent_reg = _progress_sentence(state["rounds"][-1])
    assert "Regressed" in sent_reg and "New best" not in sent_reg

    missing = dict(free)
    missing["round_id"] = 5
    missing["candidate_count"] = 1
    missing["candidates"] = [{"sha": "e", "feasible": False}]
    state = update_state(state, missing, prior_shas={"a", "b", "c", "d"})
    assert state["rounds"][-1]["progress_status"] == "no_valid_candidate"
    assert "No valid candidate" in _progress_sentence(state["rounds"][-1])

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
