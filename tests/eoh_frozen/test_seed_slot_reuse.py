"""A byte-identical seed slot must not spend a second solver call.

Upstream EoH samples seed parents with replacement, so an ``incumbent_only``
round can place the same parent code in several population slots.  Each slot
used to be evaluated again, which doubled the parent cost and made
``seed_reevaluation_attempts`` look larger than the real work.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("eoh")

from eoh_frozen.problem import FrozenProblem  # noqa: E402
from agent_skill_loop.problems import cvrp  # noqa: E402
from agent_skill_loop.problems.base import get_problem  # noqa: E402


def _task(tmp_path: Path, origin: str) -> FrozenProblem:
    return FrozenProblem(
        cvrp.build_suite(7, split="dev_train", count=1, size=8),
        spec=get_problem("cvrp_construct"),
        timeout=30,
        origin=origin,
        evaluation_log=tmp_path / "evaluations.jsonl",
    )


def test_duplicate_seed_slot_reuses_first_evaluation(tmp_path):
    task = _task(tmp_path, origin="explicit_parent")
    first = task.evaluate_result(cvrp.BASELINE_CODE)
    second = task.evaluate_result(cvrp.BASELINE_CODE)

    assert first.valid is True
    assert second.valid is True
    assert second.objective == first.objective

    records = [
        json.loads(line)
        for line in (tmp_path / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    starts = [record for record in records if record.get("evaluation") is not None and not record.get("reused")]
    reused = [record for record in records if record.get("reused") is True]
    assert len(starts) == 1, "the duplicate slot must not run a second evaluation"
    assert len(reused) == 1
    assert reused[0]["reuse_reason"] == "byte_identical_seed_slot"
    assert reused[0]["code_sha256"] == starts[0]["code_sha256"]


def test_generated_candidate_is_never_reused(tmp_path):
    """Generated code is evaluated per request, even when byte-identical."""
    task = _task(tmp_path, origin="engine")
    task.evaluate_result(cvrp.BASELINE_CODE)
    task.evaluate_result(cvrp.BASELINE_CODE)
    records = [
        json.loads(line)
        for line in (tmp_path / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert not [record for record in records if record.get("reused") is True]
