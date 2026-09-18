"""Reconstruct bounded source/behavior/effect comparisons from trusted evaluations.

This is descriptive evidence, never a search policy or a claim of semantic
equivalence.  Unknown parentage and incomplete observations stay unknown.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
from typing import Any, Mapping


SCHEMA_VERSION = "algorithm-optimization-execution-delta/v1"


def _sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _structure(code: str) -> dict[str, Any] | None:
    try:
        tree = ast.parse(code)
    except (SyntaxError, TypeError, ValueError):
        return None
    return {
        "functions": [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))][:16],
        "node_count": sum(1 for _ in ast.walk(tree)),
    }


def _behavior(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = (row.get("evaluation") or {}).get("metrics") or {}
    evidence = value.get("behavior_evidence") if isinstance(value, Mapping) else None
    return evidence if isinstance(evidence, Mapping) else None


def _compare(candidate: Mapping[str, Any], reference: Mapping[str, Any], role: str) -> dict[str, Any]:
    code = candidate.get("code") or ""
    parent_code = reference.get("code") or ""
    result = {
        "role": role,
        "reference_code_sha256": reference.get("code_sha256"),
        "reference_evaluation_id": reference.get("evaluation_id"),
        "source_relation": "same" if candidate.get("code_sha256") == reference.get("code_sha256") else "different",
        "behavior_relation": "not_comparable",
        "behavior_reason": "missing_or_incomplete_evidence",
        "instance_effect_delta": None,
    }
    diff = "".join(difflib.unified_diff(parent_code.splitlines(True), code.splitlines(True),
                                         fromfile=role, tofile="candidate"))
    result["source_delta"] = {"text": diff[:8000], "truncated": len(diff) > 8000,
                              "candidate_structure": _structure(code), "reference_structure": _structure(parent_code)}
    lhs, rhs = _behavior(candidate), _behavior(reference)
    if lhs and rhs:
        if lhs.get("status") == rhs.get("status") == "complete" and lhs.get("comparable") and rhs.get("comparable"):
            identity = ("behavior_contract_hash", "suite_hash")
            li, ri = lhs.get("instances") or [], rhs.get("instances") or []
            if all(lhs.get(key) == rhs.get(key) for key in identity) and [x.get("instance_id") for x in li] == [x.get("instance_id") for x in ri] and lhs.get("behavior_signature") and rhs.get("behavior_signature"):
                result["behavior_relation"] = "same" if lhs["behavior_signature"] == rhs["behavior_signature"] else "different"
                result["behavior_reason"] = None
            else:
                result["behavior_reason"] = "identity_or_instance_order_mismatch"
    a, b = candidate.get("evaluation") or {}, reference.get("evaluation") or {}
    av, bv = a.get("instance_objectives"), b.get("instance_objectives")
    if (a.get("valid") is True and b.get("valid") is True and a.get("suite_hash") == b.get("suite_hash")
            and candidate.get("evaluator_hash") == reference.get("evaluator_hash")
            and candidate.get("metric_spec_hash") == reference.get("metric_spec_hash")
            and isinstance(av, list) and isinstance(bv, list) and len(av) == len(bv) and len(av) > 0):
        result["instance_effect_delta"] = [float(x) - float(y) for x, y in zip(av, bv)]
    return result


def build_execution_delta(rows: list[Mapping[str, Any]], *, plan_ref: str, plan_sha256: str,
                          hypothesis: str | None, incumbent_code: str | None,
                          incumbent_ref: str | None, reference_skill_ref: str | None,
                          behavior_supported: bool = False,
                          previous_evaluated_hashes: set[str] | None = None) -> dict[str, Any]:
    observed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if isinstance(row.get("code"), str) and row.get("code_sha256") == _sha(row["code"]):
            observed.setdefault(row["code_sha256"], row)
    incumbent = observed.get(_sha(incumbent_code)) if incumbent_code else None
    seen: set[str] = set()
    previous = set(previous_evaluated_hashes or ())
    entries = []
    for row in rows:
        if row.get("origin") not in {"generated", "generated_repair"}:
            if isinstance(row.get("code_sha256"), str):
                seen.add(row["code_sha256"])
            continue
        code_hash = row.get("code_sha256")
        parents = row.get("generation_parents")
        status = row.get("lineage_status") if row.get("lineage_status") in {"verified", "no_parent", "partial", "unavailable"} else "unknown"
        if row.get("origin") == "generated_repair":
            # The original revision is not a newly selected EoH parent.
            status = "revision_of_original"
        comparisons = []
        if status == "verified" and isinstance(parents, list):
            for parent in parents:
                original = observed.get(parent.get("code_sha256")) if isinstance(parent, Mapping) else None
                if original:
                    comparisons.append(_compare(row, original, "actual_generation_parent"))
        if incumbent is not None:
            comparisons.append(_compare(row, incumbent, "incumbent_before"))
        if reference_skill_ref and reference_skill_ref != incumbent_ref:
            # Its declared reference is not a claim about the actual parents.
            comparisons.append({"role": "reference_skill", "ref": reference_skill_ref, "status": "not_loaded_for_comparison"})
        behavior = _behavior(row)
        entries.append({
            "candidate_id": row.get("candidate_id") or row.get("origin"),
            "revision": row.get("revision") or "original",
            "evaluation_id": row.get("evaluation_id"),
            "request_index": row.get("source_request_index"),
            "code_sha256": code_hash,
            "generation_parents": parents if isinstance(parents, list) else [],
            "lineage_status": status,
            "comparisons": comparisons,
            "source_novel_in_round": code_hash not in seen,
            "source_novel_in_session": code_hash not in seen and code_hash not in previous,
            "behavior_signature": behavior.get("behavior_signature") if behavior else None,
            "behavior_status": behavior.get("status") if behavior else "unavailable" if behavior_supported else "unsupported",
            "error_code": (row.get("evaluation") or {}).get("error_code"),
        })
        seen.add(code_hash)
    return {"schema_version": SCHEMA_VERSION, "plan_ref": plan_ref, "plan_sha256": plan_sha256,
            "declared_hypothesis": hypothesis, "agent_assessment_ref": None, "candidates": entries}
