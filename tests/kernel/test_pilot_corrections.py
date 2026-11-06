import copy
import json
import sys

import pytest

from agent_skill_loop.benchmark import FrozenSelection
from agent_skill_loop import session_runtime as db
from tools import assemble_controlled_pilot_report as report
from tools import prepare_agent_pilot as pilot


def selection():
    return FrozenSelection("incumbent_top1", ({"code": "pass", "code_sha256": "a" * 64,
                                              "objective": 0.0},), "b" * 64)


def test_heldout_observes_persisted_lock_and_cannot_silently_repeat(tmp_path, monkeypatch):
    chosen = selection()
    path = tmp_path / "top1.selection.json"
    report.freeze_to_disk(path, chosen)
    calls = []
    def evaluate(actual, suite):
        assert FrozenSelection.from_dict(json.loads(path.read_text())).content_hash == actual.content_hash
        assert path.with_suffix(".heldout-started.json").exists()
        calls.append(actual.content_hash)
        return {"aggregate_fitness": 0.0}
    monkeypatch.setattr(report, "evaluate_selection", evaluate)
    report.evaluate_locked(path, chosen.content_hash, {})
    with pytest.raises(FileExistsError):
        report.evaluate_locked(path, chosen.content_hash, {})
    with pytest.raises(FileExistsError):
        report.freeze_to_disk(path, chosen)
    assert len(calls) == 1


def test_tampered_selection_never_reaches_heldout(tmp_path, monkeypatch):
    chosen = selection()
    path = tmp_path / "top1.selection.json"
    report.freeze_to_disk(path, chosen)
    data = json.loads(path.read_text())
    data["members"][0]["objective"] = 100
    path.write_text(json.dumps(data))
    monkeypatch.setattr(report, "evaluate_selection", lambda *_: pytest.fail("heldout accessed"))
    with pytest.raises(ValueError, match="hash_mismatch"):
        report.evaluate_locked(path, chosen.content_hash, {})


def test_failed_heldout_keeps_attempt_marker(tmp_path, monkeypatch):
    chosen = selection()
    path = tmp_path / "top1.selection.json"
    report.freeze_to_disk(path, chosen)
    def crash(*_):
        raise RuntimeError("interrupted")
    monkeypatch.setattr(report, "evaluate_selection", crash)
    with pytest.raises(RuntimeError):
        report.evaluate_locked(path, chosen.content_hash, {})
    assert path.with_suffix(".heldout-started.json").exists()
    assert not path.with_suffix(".heldout-result.json").exists()


def test_environment_allowlist_excludes_secrets(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "not-for-evidence")
    monkeypatch.setenv("UNRELATED_SECRET", "not-for-evidence")
    value = pilot.execution_environment()
    assert "not-for-evidence" not in json.dumps(value)
    assert value["python_executable"] == sys.executable
    assert "numpy" in value["packages"]


def test_d1_freezes_controller_environment_without_generating_plan(tmp_path, monkeypatch):
    source = tmp_path / "source"
    db.initialize_session(output=source, operation_id="init", eoh_model="fixture",
                          benchmark_id="eohs_v1", benchmark_profile_name="obp_evolution_mini",
                          inheritance_mode="population_seeds", max_rounds=2, round_budget=10,
                          max_solver_calls=20, memory_enabled=False)
    template = json.loads((source / "config_frozen.json").read_text())["experiment_manifest"]["document"]
    monkeypatch.setattr(pilot, "execution_environment", lambda: {"installed_eoh_commit": db.EOH_COMMIT,
                                                               "python_version": "3.11.test"})
    monkeypatch.setattr(pilot, "source_identity", lambda: {"git_head": "test", "source_files_sha256": {}})
    controller = {"kind": "host_coding_agent", "host": "test host", "model": "test model",
                  "identity_source": "test fixture, not a real Agent"}
    result = pilot.prepare(template, controller, tmp_path / "D1")
    assert result["state"] == "WAITING_FOR_PLAN"
    config = json.loads((tmp_path / "D1/session/config_frozen.json").read_text())
    extra = config["experiment_manifest"]["document"]["extra"]
    assert extra["controller_identity"] == controller
    assert extra["execution_environment"]["python_version"] == "3.11.test"
    assert not list((tmp_path / "D1/session").rglob("plan.json"))
    invalid = copy.deepcopy(controller)
    invalid["kind"] = "fixed_script"
    with pytest.raises(ValueError, match="host_controller"):
        pilot.prepare(template, invalid, tmp_path / "rejected")
