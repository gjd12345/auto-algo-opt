from __future__ import annotations

import json

from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import SubprocessEvaluator, evaluator_source_hash
from agent_skill_loop.problems.cvrp import BASELINE_CODE, ENTRYPOINT, PROBLEM_NAME, build_suite
from agent_skill_loop.skill_store import load_skill, make_skill, publish_export_ref, save_skill


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


def test_save_skill_refuses_silent_overwrite(tmp_path):
    suite = build_suite(DEFAULT_SEED, count=3, size=8)
    first = SubprocessEvaluator(timeout=10.0).evaluate(BASELINE_CODE, suite)
    skill = make_skill(
        version_id="t1",
        code=BASELINE_CODE,
        suite_hash=suite["content_hash"],
        valid=True,
        mean_objective=first.objective,
        instance_objectives=first.instance_objectives,
        parent_version_id=None,
        source_attempt_id=1,
        problem=PROBLEM_NAME,
        entrypoint=ENTRYPOINT,
    )
    path = tmp_path / "skill"
    save_skill(path, skill)
    try:
        save_skill(path, skill)
        raise AssertionError("expected skill_directory_exists")
    except ValueError as exc:
        assert str(exc) == "skill_directory_exists"
    loaded = load_skill(path)
    assert loaded.version_id == "t1"
    original = (path / "code.py").read_text(encoding="utf-8")
    assert original == BASELINE_CODE


def _valid_skill(suite, version_id: str):
    first = SubprocessEvaluator(timeout=10.0).evaluate(BASELINE_CODE, suite)
    return make_skill(
        version_id=version_id,
        code=BASELINE_CODE,
        suite_hash=suite["content_hash"],
        valid=True,
        mean_objective=first.objective,
        instance_objectives=first.instance_objectives,
        parent_version_id=None,
        source_attempt_id=1,
        problem=PROBLEM_NAME,
        entrypoint=ENTRYPOINT,
    )


def test_export_ref_points_at_immutable_version(tmp_path):
    suite = build_suite(DEFAULT_SEED, count=2, size=6)
    run = tmp_path / "run"
    first_dir = run / "skills" / "generated_1"
    second_dir = run / "skills" / "generated_2"
    save_skill(first_dir, _valid_skill(suite, "generated_1"))
    save_skill(second_dir, _valid_skill(suite, "generated_2"))
    publish_export_ref(run, first_dir)
    assert load_skill(run / "exported_skill").version_id == "generated_1"
    publish_export_ref(run, second_dir)
    assert load_skill(run / "exported_skill").version_id == "generated_2"
    assert (first_dir / "skill.json").is_file()
    ref = json.loads((run / "exported_skill" / "ref.json").read_text(encoding="utf-8"))
    assert ref["skill_dir"] == "skills/generated_2"
    assert not (run / "exported_skill" / "code.py").exists()


def test_invalid_eoh_best_writes_diagnostic_not_export(tmp_path):
    from eoh_frozen.export import export_best_skill

    suite = build_suite(DEFAULT_SEED, count=2, size=6)
    out = tmp_path / "eoh_out"
    best_dir = out / "results" / "pops_best"
    best_dir.mkdir(parents=True)
    payload = {
        "algorithm": "broken",
        "code": "def select_next_node(*args):\n    return 'nope'\n",
        "objective": 1.0,
        "other_inf": None,
    }
    (best_dir / "population_generation_1.json").write_text(json.dumps(payload), encoding="utf-8")
    path = export_best_skill(out, suite, timeout=10.0)
    assert path is None
    rejected = json.loads((out / "results" / "export_rejected.json").read_text(encoding="utf-8"))
    assert rejected["reason"] == "reeval_invalid"
    assert rejected["error_code"] == "invalid_return"
    assert not (out / "exported_skill" / "ref.json").exists()
    assert not (out / "skills" / "eoh_best").exists()
