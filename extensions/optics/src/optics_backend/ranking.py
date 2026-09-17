"""Pure S1 comparison and verification admission; no physics/model imports."""

import math

from .artifacts import canonical, digest

RANKING_POLICY = {"schema_id": "optics-s1-ranking/v1", "order": ["all_pass", "-vsum", "-vmax", "q"],
                  "violation": "max(0, -normalized_margin) for ranking_included rows",
                  "summation": "math.fsum in sorted constraint_id order",
                  "ties": "retain_parent", "direction": "lexicographic_max"}
RANKING_HASH = digest(canonical(RANKING_POLICY))


def rank_key(facts: dict):
    if (facts["mode"] != "online" or facts["submission_status"] != "valid"
            or facts["execution_status"] != "complete" or facts["physics_status"] != "OK"):
        return None
    constraints = facts["constraints"]
    if not constraints or set(constraints) != set(facts["constraint_ids"]):
        raise ValueError("INCOMPLETE_CONSTRAINT_VECTOR")
    violations = []
    for constraint_id in sorted(constraints):
        row = constraints[constraint_id]
        if type(row["passed"]) is not bool or type(row["ranking_included"]) is not bool:
            raise ValueError("INVALID_CONSTRAINT_TYPES")
        margin = row["normalized_margin"]
        if type(margin) not in (int, float) or not math.isfinite(margin):
            raise ValueError("INVALID_MARGIN")
        if row["ranking_included"]:
            violations.append(max(0.0, -margin))
    q = facts["quality_q"]
    if type(q) not in (int, float) or not math.isfinite(q):
        raise ValueError("INVALID_QUALITY")
    passed = all(row["passed"] for row in constraints.values())
    if facts["online_feasible"] is not passed:
        raise ValueError("FEASIBILITY_MISMATCH")
    total = math.fsum(violations)
    if not math.isfinite(total):
        raise ValueError("NONFINITE_VIOLATION_SUM")
    return (int(passed), -total, -max(violations, default=0.0), q)


def audit_eligible(facts: dict) -> bool:
    key = rank_key(facts)
    return key is not None and facts["online_feasible"] is True


def compare(previous: dict | None, candidate: dict) -> dict:
    if previous is not None:
        left = dict(previous["evaluation_identity"])
        right = dict(candidate["evaluation_identity"])
        left.pop("canonical_artifact_sha256")
        right.pop("canonical_artifact_sha256")
        if left != right:
            raise ValueError("COMPARISON_IDENTITY_MISMATCH")
    old = rank_key(previous) if previous is not None else None
    new = rank_key(candidate)
    accept = new is not None and (old is None or new > old)
    return {"ranking_contract_hash": RANKING_HASH,
            "previous_facts_sha256": digest(canonical(previous)) if previous else None,
            "candidate_facts_sha256": digest(canonical(candidate)),
            "previous_key": old, "candidate_key": new,
            "decision": "accept" if accept else "incomparable" if new is None else "retain",
            "accept_reason": "strictly_better_or_first" if accept else "incomparable" if new is None else "tie_or_worse"}
