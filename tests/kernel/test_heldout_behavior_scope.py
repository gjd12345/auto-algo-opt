"""Held-out suites never carry training-side behavior evidence.

R01 in the 2026-10-04 independent review: ``_evaluate_problem`` dispatched on
``spec.evaluate_with_behavior`` without looking at the suite split, so a
held-out evaluation could return ``behavior_evidence`` and be copied into the
benchmark artifact as if it were a training fact.  These tests pin the gate.
"""
from agent_skill_loop.evaluator import evaluate_candidate_request
from agent_skill_loop.problems import obp

CODE = "def priority(item, bins):\n    return -bins\n"


def _result(split: str, *, collect_partial: bool) -> dict:
    suite = obp.build_suite(1, split=split, count=1, size=6)
    return evaluate_candidate_request({
        "problem": obp.PROBLEM_NAME,
        "suite": suite,
        "code": CODE,
        "collect_partial": collect_partial,
    })


def test_training_split_keeps_behavior_evidence():
    result = _result("dev_train", collect_partial=False)
    assert result["valid"] is True
    assert isinstance(result["metrics"].get("behavior_evidence"), dict)


def test_heldout_split_drops_behavior_evidence():
    result = _result("heldout", collect_partial=False)
    assert result["valid"] is True
    assert "behavior_evidence" not in result["metrics"]
    # The objective itself is still produced: only the training-side fact is gone.
    assert result["objective"] is not None


def test_heldout_partial_collection_drops_behavior_evidence():
    result = _result("heldout", collect_partial=True)
    assert result["valid"] is True
    assert "behavior_evidence" not in result["metrics"]
    for record in result["metrics"]["partial_instance_results"]:
        assert "behavior_evidence" not in (record.get("metrics") or {})
