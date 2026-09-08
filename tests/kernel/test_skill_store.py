from __future__ import annotations

from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import SubprocessEvaluator, evaluator_source_hash
from agent_skill_loop.problems.cvrp import BASELINE_CODE, ENTRYPOINT, PROBLEM_NAME, build_suite
from agent_skill_loop.skill_store import load_skill, make_skill, save_skill


def test_save_load_re_evaluate_matches(tmp_path):
    suite = build_suite(DEFAULT_SEED, count=3, size=8)
    first = SubprocessEvaluator(timeout=10.0).evaluate(BASELINE_CODE, suite)
    assert first.valid
    skill = make_skill(
        version_id="t1",
        code=BASELINE_CODE,
        suite_hash=suite["content_hash"],
        valid=True,
        mean_objective=first.objective,
        instance_objectives=first.instance_objectives,
        parent_version_id=None,
        source_attempt_id=1,
        description="test",
        problem=PROBLEM_NAME,
        entrypoint=ENTRYPOINT,
    )
    assert skill.evaluator_hash == evaluator_source_hash()
    path = tmp_path / "skill"
    save_skill(path, skill)
    loaded = load_skill(path)
    assert loaded.code == BASELINE_CODE
    assert loaded.code_sha256 == skill.code_sha256
    second = SubprocessEvaluator(timeout=10.0).evaluate(loaded.code, suite)
    assert second.valid
    assert second.instance_objectives == first.instance_objectives
    assert second.objective == first.objective
