"""Offline, hash-checked reporting for registered A/B/C diagnostics."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .contracts import sha256_json


SCHEMA_VERSION = "algorithm-optimization-research-loop-report/v1"
INDEX_SCHEMA_VERSION = "algorithm-optimization-research-loop-index/v1"
GROUP_TREATMENTS = {
    "A": "facts_to_plan",
    "B": "explicit_reflection",
    "C": "reflection_with_online_memory",
}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _verify_bundle(root: Path) -> None:
    hashes = _json(root / "SHA256SUMS.json")
    if not isinstance(hashes, Mapping):
        raise ValueError("research_bundle_hash_inventory_invalid")
    actual = {item.relative_to(root).as_posix() for item in root.rglob("*") if item.is_file()}
    if actual != set(hashes) | {"SHA256SUMS.json"}:
        raise ValueError("research_bundle_inventory_mismatch")
    for ref, expected in hashes.items():
        path = (root / str(ref)).resolve()
        if not path.is_relative_to(root) or _digest(path) != expected:
            raise ValueError("research_bundle_hash_mismatch:" + str(ref))


def _facts(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(root.glob("rounds/round_*/evaluation_facts.json")):
        payload = _json(path)
        if isinstance(payload, dict):
            payload["_evidence_ref"] = path.relative_to(root).as_posix()
            result.append(payload)
    return result


def _quality(calls: list[Mapping[str, Any]], *, completed: bool, budget: int) -> dict[str, Any]:
    if len(calls) > budget:
        raise ValueError("research_solver_budget_exceeded")
    best = None
    best_identity = None
    curve = []
    for index, call in enumerate(calls, 1):
        objective = _finite(call.get("objective"))
        valid = call.get("valid") in (True, 1) and call.get("state") == "complete"
        if valid and objective is not None and (best is None or objective < best):
            best = objective
            best_identity = {"evaluation_id": call.get("evaluation_id"),
                             "code_sha256": call.get("code_sha256")}
        curve.append({"solver_call": index, "best_so_far_objective": best})
    observed_calls = len(curve)
    if completed and best is not None:
        curve.extend({"solver_call": index, "best_so_far_objective": best}
                     for index in range(observed_calls + 1, budget + 1))
    values = [item["best_so_far_objective"] for item in curve]
    auc = sum(values) if values and all(value is not None for value in values) else None
    return {
        "observed_solver_calls": observed_calls,
        "budget_solver_calls": budget,
        "carry_forward_applied": completed and observed_calls < budget and best is not None,
        "best_so_far": curve,
        "best_so_far_curve_area": auc,
        "best_so_far_curve_mean": auc / budget if auc is not None and len(curve) == budget else None,
        "fixed_budget_endpoint_objective": best if completed else None,
        "endpoint_identity": best_identity if completed else None,
    }


def _per_instance_endpoint(facts: list[Mapping[str, Any]], identity: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not identity:
        return None
    matches = [candidate for fact in facts for candidate in fact.get("candidates", [])
               if isinstance(candidate, Mapping)
               and candidate.get("evaluation_id") == identity.get("evaluation_id")
               and candidate.get("code_sha256") == identity.get("code_sha256")]
    if len(matches) != 1:
        return None
    values = matches[0].get("instance_objectives")
    if not isinstance(values, list) or any(_finite(value) is None for value in values):
        return None
    return {**dict(identity), "instance_objectives": [float(value) for value in values]}


def _generated_metrics(facts: list[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = [candidate for fact in facts for candidate in fact.get("candidates", [])
                  if isinstance(candidate, Mapping)
                  and str(candidate.get("origin") or "").startswith("generated")]
    valid = sum(candidate.get("valid") is True for candidate in candidates)
    last_progress = facts[-1].get("search_progress", {}) if facts else {}
    cumulative = last_progress.get("cumulative", {}) if isinstance(last_progress, Mapping) else {}
    duplicates = cumulative.get("behavior_duplicate_count")
    comparable = cumulative.get("behavior_comparable_count")
    duplicate_rate = None
    if isinstance(duplicates, int) and isinstance(comparable, int) and comparable:
        duplicate_rate = duplicates / comparable
    return {
        "generated_candidate_count": len(candidates),
        "valid_generated_candidate_count": valid,
        "valid_candidate_rate": valid / len(candidates) if candidates else None,
        "behavior_duplicate_count": duplicates if isinstance(duplicates, int) else None,
        "behavior_comparable_count": comparable if isinstance(comparable, int) else None,
        "behavior_duplicate_rate": duplicate_rate,
    }


def _round_quality(calls: list[Mapping[str, Any]], facts: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    best = None
    result = []
    by_round: dict[int, list[Mapping[str, Any]]] = {}
    for call in calls:
        by_round.setdefault(int(call.get("round_id") or 0), []).append(call)
    for fact in facts:
        round_id = int(fact.get("round_id") or 0)
        for call in by_round.get(round_id, []):
            objective = _finite(call.get("objective"))
            if call.get("valid") in (True, 1) and call.get("state") == "complete" and objective is not None:
                best = objective if best is None else min(best, objective)
        result.append({"round_id": round_id, "best_so_far_objective": best,
                       "evidence_ref": fact.get("_evidence_ref")})
    return result


def _cost_curves(receipt: Mapping[str, Any], controller: Mapping[str, Any],
                 round_quality: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    requests = [item for item in receipt.get("requests", []) if isinstance(item, Mapping)]
    tasks = [item for item in receipt.get("tasks", []) if isinstance(item, Mapping)]
    events = [item for item in controller.get("events", []) if isinstance(item, Mapping)]
    result = []
    for quality in round_quality:
        round_id = int(quality["round_id"])
        req = [item for item in requests if int(item.get("round_id") or 0) <= round_id]
        outer = [item for item in events if int(item.get("round_id") or 0) <= round_id]
        eoh_complete = bool(req) and all(isinstance(item.get("input_tokens"), int)
                                         and isinstance(item.get("output_tokens"), int) for item in req)
        outer_complete = bool(outer) and all(item.get("availability") == "complete"
                                             and isinstance(item.get("input_tokens"), int)
                                             and isinstance(item.get("output_tokens"), int) for item in outer)
        eoh_tokens = sum(int(item["input_tokens"]) + int(item["output_tokens"]) for item in req) if eoh_complete else None
        outer_tokens = sum(int(item["input_tokens"]) + int(item["output_tokens"]) for item in outer) if outer_complete else None
        included_tasks = [item for item in tasks if int(item.get("round_id") or 0) <= round_id]
        engine_complete = bool(included_tasks) and all(_finite(item.get("engine_elapsed_seconds")) is not None
                                                       for item in included_tasks)
        controller_complete = bool(outer) and all(_finite(item.get("elapsed_seconds")) is not None
                                                       for item in outer)
        engine_wall = sum(float(item["engine_elapsed_seconds"]) for item in included_tasks) if engine_complete else None
        controller_elapsed = sum(float(item["elapsed_seconds"]) for item in outer) if controller_complete else None
        result.append({
            "round_id": round_id,
            "best_so_far_objective": quality.get("best_so_far_objective"),
            "eoh_model_tokens": eoh_tokens,
            "outer_controller_tokens": outer_tokens,
            "total_model_tokens": eoh_tokens + outer_tokens
            if eoh_tokens is not None and outer_tokens is not None else None,
            "engine_wall_seconds": round(engine_wall, 6) if engine_wall is not None else None,
            "controller_elapsed_seconds": round(controller_elapsed, 6) if controller_elapsed is not None else None,
            "quality_wall_time_seconds": round(engine_wall + controller_elapsed, 6)
            if engine_wall is not None and controller_elapsed is not None else None,
        })
    return result


def _memory_chain(root: Path) -> dict[str, Any]:
    records = []
    for path in sorted(root.glob("rounds/round_*/memory_consumption.json")):
        item = _json(path)
        if not isinstance(item, Mapping):
            continue
        records.append({
            "round_id": item.get("round_id"),
            "evidence_ref": path.relative_to(root).as_posix(),
            "published": [write.get("reference") for write in item.get("publication", {}).get("writes", [])
                          if isinstance(write, Mapping) and write.get("reference")],
            "searched_result_refs": [ref for search in item.get("searched", []) if isinstance(search, Mapping)
                                     for ref in search.get("results", [])],
            "read_refs": [read.get("reference") for read in item.get("read", [])
                          if isinstance(read, Mapping) and read.get("status") in {"ok", "complete"}],
            "selected_refs": list(item.get("selected") or []),
            "gateway_request_refs": [request.get("input_ref") for request in item.get("gateway_requests", [])
                                     if isinstance(request, Mapping)
                                     and request.get("context_status") == "gateway_attempt_exact_context"],
        })
    return {"rounds": records,
            "actual_reuse": any(item["read_refs"] and item["selected_refs"] and item["gateway_request_refs"]
                                for item in records if int(item.get("round_id") or 0) >= 2)}


def _reflection_chain(root: Path, group: str) -> list[str]:
    failures = []
    previous_ref = None
    previous_sha = None
    for round_id in range(1, 5):
        prefix = Path(f"rounds/round_{round_id:04d}")
        plan_path = root / prefix / "plan.json"
        evaluation_path = root / prefix / "evaluation.submitted.json"
        if not plan_path.is_file() or not evaluation_path.is_file():
            failures.append("plan_or_submitted_evaluation_missing")
            continue
        basis = _json(plan_path).get("reflection_basis")
        if group == "A" or round_id == 1:
            if basis is not None:
                failures.append("reflection_basis_forbidden")
        elif not isinstance(basis, Mapping) or basis.get("round_id") != round_id - 1 \
                or basis.get("evaluation_ref") != previous_ref \
                or basis.get("evaluation_sha256") != previous_sha:
            failures.append("reflection_basis_mismatch")
        previous_ref = (prefix / "evaluation.submitted.json").as_posix()
        previous_sha = _digest(evaluation_path)
    return sorted(set(failures))


def _cost_failures(cost: Mapping[str, Any]) -> list[str]:
    failures = []
    for key in ("eoh_provider", "outer_controller"):
        item = cost.get(key, {})
        if not isinstance(item, Mapping):
            failures.append("cost_summary_missing:" + key)
        elif item.get("status") != "complete" and (item.get("input_tokens") is not None
                                                     or item.get("output_tokens") is not None):
            failures.append("unknown_tokens_counted_as_numeric:" + key)
    if cost.get("total_model_token_status") != "complete" and cost.get("total_model_tokens") is not None:
        failures.append("incomplete_total_tokens_counted_as_numeric")
    return failures


def _load_run(item: Mapping[str, Any], base: Path) -> dict[str, Any]:
    group = str(item.get("group") or "")
    if group not in GROUP_TREATMENTS:
        raise ValueError("research_group_invalid")
    seed = item.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("research_seed_invalid")
    root = (base / str(item.get("bundle") or "")).resolve()
    if not root.is_dir():
        raise ValueError("research_bundle_missing")
    _verify_bundle(root)
    manifest_record = _json(root / "experiment_manifest.json")
    if (isinstance(manifest_record, Mapping)
            and isinstance(manifest_record.get("document"), Mapping)):
        manifest = dict(manifest_record["document"])
        if manifest_record.get("sha256") != sha256_json(manifest):
            raise ValueError("research_manifest_hash_mismatch")
    else:
        # Read compatibility for the original compact-bundle fixture shape.
        manifest = manifest_record
    if not isinstance(manifest, Mapping):
        raise ValueError("research_manifest_invalid")
    extra = manifest.get("extra", {}) if isinstance(manifest, Mapping) else {}
    domain_contracts = {
        "algorithm-optimization-research-loop-pilot/v1": ("obp_online", "obp_evolution_mini"),
        "algorithm-optimization-island605-bp-research-loop/v1": (
            "bp_online_island605", "historically_exposed_train_v1"),
    }
    domain = domain_contracts.get(extra.get("research_loop_schema"))
    if domain is None:
        raise ValueError("research_manifest_domain_invalid")
    expected = {
        "research_loop_schema": extra.get("research_loop_schema"),
        "problem_scope": domain[0],
        "benchmark_profile": domain[1],
        "primary_budget_resource": "solver_calls",
        "comparison_packet_policy": extra.get("comparison_packet_policy") if extra.get("comparison_packet_policy") in {"obp-research-contrasts/v1", "obp-research-contrasts/v2"} else None,
        "heldout_policy": "locked_no_access_diagnostic",
        "treatment": GROUP_TREATMENTS[group],
        "memory_source": "run_internal_empty_start" if group == "C" else "disabled",
    }
    if any(extra.get(key) != value for key, value in expected.items()):
        raise ValueError("research_manifest_contract_mismatch")
    if (manifest.get("evaluation_budget"), manifest.get("rounds"), manifest.get("round_budget")) != (100, 4, 25):
        raise ValueError("research_manifest_budget_mismatch")
    if bool(manifest.get("memory_enabled")) != (group == "C"):
        raise ValueError("research_manifest_memory_mismatch")
    receipt = _json(root / "budget_receipt.json")
    bundle = _json(root / "bundle.json")
    controller = _json(root / "controller_usage.json")
    cost = _json(root / "cost_summary.json")
    facts = _facts(root)
    calls = [call for call in receipt.get("solver_calls", []) if isinstance(call, Mapping)]
    completed = bundle.get("run_state") == "COMPLETED"
    quality = _quality(calls, completed=completed, budget=100)
    round_quality = _round_quality(calls, facts)
    failures = []
    if not completed:
        failures.append("run_not_completed")
    if any(call.get("state") in {"reserved", "started", "unknown"} for call in calls):
        failures.append("solver_ledger_incomplete")
    if len(facts) != 4:
        failures.append("round_evidence_incomplete")
    if any(not (root / f"rounds/round_{round_id:04d}/comparison_packet.json").is_file()
           for round_id in range(1, 5)):
        failures.append("comparison_packet_missing")
    failures.extend(_reflection_chain(root, group))
    failures.extend(_cost_failures(cost))
    return {
        "group": group, "seed": seed, "problem_scope": domain[0], "run_id": bundle.get("run_id"),
        "bundle": str(item.get("bundle")), "status": "failed" if failures else "complete",
        "failure_reasons": failures, "quality": quality,
        "endpoint_per_instance": _per_instance_endpoint(facts, quality.get("endpoint_identity")),
        "search_diagnostics": _generated_metrics(facts),
        "per_round_quality": round_quality,
        "secondary_cost_curves": _cost_curves(receipt, controller, round_quality),
        "cost_summary": cost,
        "memory_chain": _memory_chain(root) if group == "C" else None,
    }


def build_research_loop_report(index: Mapping[str, Any], *, base_dir: Path) -> dict[str, Any]:
    """Build a descriptive diagnostic report; never access or infer heldout results."""
    if index.get("schema_version") != INDEX_SCHEMA_VERSION or not isinstance(index.get("runs"), list):
        raise ValueError("research_loop_index_invalid")
    runs = [_load_run(item, base_dir) for item in index["runs"] if isinstance(item, Mapping)]
    scopes = {item["problem_scope"] for item in runs}
    if len(scopes) != 1:
        raise ValueError("research_loop_mixed_problem_scopes")
    identities = [(item["group"], item["seed"]) for item in runs]
    if len(identities) != len(set(identities)):
        raise ValueError("research_loop_duplicate_group_seed")
    seeds = sorted({item["seed"] for item in runs})
    paired = []
    for seed in seeds:
        groups = {item["group"]: item for item in runs if item["seed"] == seed}
        entry: dict[str, Any] = {"seed": seed, "complete_groups": sorted(groups)}
        if "A" in groups and "B" in groups:
            a, b = groups["A"]["quality"], groups["B"]["quality"]
            entry["b_minus_a"] = {
                "fixed_budget_endpoint": _delta(b["fixed_budget_endpoint_objective"], a["fixed_budget_endpoint_objective"]),
                "curve_area": _delta(b["best_so_far_curve_area"], a["best_so_far_curve_area"]),
            }
        if "B" in groups and "C" in groups:
            b_rounds = {item["round_id"]: item["best_so_far_objective"] for item in groups["B"]["per_round_quality"]}
            c_rounds = {item["round_id"]: item["best_so_far_objective"] for item in groups["C"]["per_round_quality"]}
            entry["c_minus_b_rounds_2_to_4"] = [
                {"round_id": round_id, "objective_delta": _delta(c_rounds.get(round_id), b_rounds.get(round_id))}
                for round_id in (2, 3, 4)
            ]
            entry["c_memory_actual_reuse"] = groups["C"]["memory_chain"]["actual_reuse"]
        paired.append(entry)
    complete_matrix = len(seeds) == 3 and all({item["group"] for item in runs if item["seed"] == seed}
                                               == set(GROUP_TREATMENTS) for seed in seeds)
    audit_complete = complete_matrix and all(item["status"] == "complete" for item in runs)
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": f"{next(iter(scopes))} dev_train diagnostic only; no heldout access",
        "primary_budget_resource": "solver_calls",
        "interpretation": "descriptive three-seed diagnostic; no significance or general-validity claim",
        "runs": runs,
        "paired_diagnostics": paired,
        "readiness": {
            "three_seed_paired_matrix": complete_matrix,
            "all_runs_auditable": audit_complete,
            "memory_reuse_observed_by_seed": {str(item["seed"]): item["memory_chain"]["actual_reuse"]
                                               for item in runs if item["group"] == "C"},
        },
    }


def _delta(left: Any, right: Any) -> float | None:
    a, b = _finite(left), _finite(right)
    return a - b if a is not None and b is not None else None
