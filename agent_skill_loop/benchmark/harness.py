"""Offline benchmark harness and independent OBP calibration."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

from agent_skill_loop.evaluator import SubprocessEvaluator

from .catalog import benchmark_profile, load_profile_suite
from .contracts import MetricSpec, sha256_json, sha256_text


def load_suite(path: Path | None = None, *, benchmark_id: str = "eohs_v1", profile: str = "obp_mini", split: str = "dev_train") -> dict[str, Any]:
    if path is None:
        return load_profile_suite(benchmark_id, profile, split=split)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("instances"), list):
        raise ValueError("benchmark_suite_invalid")
    if "content_hash" not in payload:
        from agent_skill_loop.problems.obp import suite_hash
        payload["content_hash"] = suite_hash(str(payload.get("problem")), str(payload.get("split")), payload["instances"])
    return payload


def _upstream_pack(items: list[float], capacity: float, choose: Callable[[float, list[float]], int]) -> int:
    """Independent imperative implementation of the upstream OBP loop.

    This intentionally does not call the production candidate evaluator. It
    is the expected-value side of the differential calibration.
    """
    remaining: list[float] = []
    for item in items:
        feasible = [index for index, value in enumerate(remaining) if value + 1e-12 >= item]
        if not feasible:
            remaining.append(capacity - item)
            continue
        local_remaining = [remaining[index] for index in feasible]
        chosen_local = choose(item, local_remaining)
        if not isinstance(chosen_local, int) or not 0 <= chosen_local < len(feasible):
            raise ValueError("upstream_heuristic_return_invalid")
        remaining[feasible[chosen_local]] -= item
    return len(remaining)


def _first_fit(_item: float, _bins: list[float]) -> int:
    return 0


def _best_fit(_item: float, bins: list[float]) -> int:
    return min(range(len(bins)), key=lambda index: (bins[index], index))


def calibrate_upstream(suite: Mapping[str, Any]) -> dict[str, Any]:
    rows: dict[str, list[dict[str, Any]]] = {"first_fit": [], "best_fit": []}
    for instance in suite["instances"]:
        items = [float(item) for item in instance["items"]]
        capacity = float(instance["capacity"])
        reference = float(instance["reference_objective"])
        for name, chooser in (("first_fit", _first_fit), ("best_fit", _best_fit)):
            bins_used = _upstream_pack(items, capacity, chooser)
            rows[name].append({
                "instance_id": instance["instance_id"],
                "bins_used": bins_used,
                "reference": reference,
                "gap": (bins_used - reference) / reference,
            })
    return {
        "schema_version": "algorithm-optimization-obp-gold/v1",
        "benchmark_id": suite.get("benchmark_id"),
        "profile": suite.get("profile"),
        "problem": suite.get("problem"),
        "suite_hash": suite.get("content_hash"),
        "reference_kind": "upstream_compatibility_reference",
        "heuristics": rows,
    }


def calibrate_differential(suite: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, Any]:
    expected = calibrate_upstream(suite)
    mismatches: list[dict[str, Any]] = []
    if not isinstance(gold, Mapping):
        raise ValueError("obp_gold_invalid")
    for key in ("benchmark_id", "profile", "problem", "suite_hash", "reference_kind"):
        if gold.get(key) != expected.get(key):
            mismatches.append({"field": key, "expected": expected.get(key), "actual": gold.get(key)})
    given = gold.get("heuristics") if isinstance(gold, Mapping) else None
    if not isinstance(given, Mapping):
        raise ValueError("obp_gold_invalid")
    for name, expected_rows in expected["heuristics"].items():
        actual_rows = given.get(name, [])
        for index, expected_row in enumerate(expected_rows):
            actual = actual_rows[index] if index < len(actual_rows) else None
            if actual != expected_row:
                mismatches.append({"heuristic": name, "index": index, "expected": expected_row, "actual": actual})
    return {"passed": not mismatches, "mismatches": mismatches, "expected_sha256": sha256_json(expected), "gold_sha256": sha256_json(gold)}


def evaluate_candidate(code: str, suite: Mapping[str, Any], *, timeout: float = 20.0, metric_spec: MetricSpec | None = None) -> dict[str, Any]:
    result = SubprocessEvaluator(timeout=timeout).evaluate(code, suite)
    payload = result.as_dict()
    if result.valid and isinstance(result.metrics, dict):
        payload["raw_objectives"] = list(result.metrics.get("raw_objectives", []))
        payload["reference_objectives"] = list(result.metrics.get("reference_objectives", []))
        payload["bins_used"] = list(result.metrics.get("bins_used", []))
        payload["reference_kind"] = list(result.metrics.get("reference_kind", []))
    if metric_spec is not None:
        metric_hash = metric_spec.content_hash
        payload["metric_spec_hash"] = metric_hash
        payload["fitness"] = payload.get("objective")
    payload["candidate_code_sha256"] = sha256_text(code)
    payload["data_manifest_hash"] = sha256_json({"problem": suite.get("problem"), "split": suite.get("split"), "instances": suite.get("instances")})
    return payload


def budget_summary(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    """Return the v1.1 dual budget view from evaluation provenance rows."""
    total = len(rows)
    seen: set[str] = set()
    novel = 0
    seeds = baseline = repairs = 0
    for row in rows:
        code_hash = str(row.get("code_sha256") or "")
        origin = str(row.get("origin") or "")
        revision = str(row.get("revision") or "")
        if origin in {"explicit_parent", "population_seed", "seed"}:
            seeds += 1
        if origin == "baseline":
            baseline += 1
        if origin == "generated_repair" or revision == "repair_1":
            repairs += 1
        elif origin == "generated" and code_hash and code_hash not in seen:
            novel += 1
            seen.add(code_hash)
    return {
        "total_evaluation_attempts": total,
        "novel_candidate_evaluations": novel,
        "seed_reevaluation_attempts": seeds,
        "baseline_attempts": baseline,
        "repair_attempts": repairs,
    }
