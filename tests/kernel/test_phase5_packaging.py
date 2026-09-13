from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_skill_loop import session_runtime as db
from agent_skill_loop.__main__ import main
from eoh_frozen.__main__ import build_parser


SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "algorithm-optimization"


def test_algorithm_optimization_skill_package_is_complete_and_hashed():
    assert (SKILL_ROOT / "SKILL.md").is_file()
    assert (SKILL_ROOT / "agents" / "openai.yaml").is_file()
    assert (SKILL_ROOT / "references" / "protocol.md").is_file()
    assert (SKILL_ROOT / "references" / "plan-and-evaluate.md").is_file()
    assert (SKILL_ROOT / "references" / "examples" / "two-round-run.md").is_file()
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "name: algorithm-optimization" in text
    assert "session submit-plan" in text
    assert db._skill_content_hash() == db._skill_content_hash()


def test_skill_evaluation_alignment_docs_match_current_contract():
    text = (SKILL_ROOT / "references" / "plan-and-evaluate.md").read_text(encoding="utf-8")
    assert "aligned`, `partial`, `misaligned`, or `unknown" in text
    assert "`deviated` is accepted only for historical Session-client compatibility" in text
    assert "New Skill submissions MUST use `misaligned` instead" in text


def test_session_freezes_skill_content_identity(tmp_path, monkeypatch):
    root = tmp_path / "run"
    db.initialize_session(output=root, operation_id="init", eoh_model="fixture", size=6, count=1)
    config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
    assert config["optimization_skill"]["content_sha256"] == db._skill_content_hash()

    monkeypatch.setattr(db, "_skill_content_hash", lambda: "changed-skill")
    state = db.read_state(run=root)
    assert state["integrity"]["skill_identity"] == "mismatch"
    assert "submit_plan" not in state["allowed_actions"]


def test_legacy_workflow_is_a_non_effectful_migration_error(capsys, tmp_path):
    assert main(["workflow", "--output", str(tmp_path / "unused")]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "ok": False,
        "error": {
            "code": "WORKFLOW_DEPRECATED",
            "message": "Use session init and the algorithm-optimization Coding Agent Skill.",
        },
    }
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize(
    "model_flag,endpoint_flag,key_flag",
    [("--eoh-model", "--eoh-endpoint", "--eoh-api-key-env"),
     ("--model", "--endpoint", "--api-key-env")],
)
def test_eoh_run_accepts_canonical_flags_and_transition_aliases(model_flag, endpoint_flag, key_flag):
    args = build_parser().parse_args([
        "run", model_flag, "fixture", "--output", "out",
        endpoint_flag, "http://localhost", key_flag, "KEY",
    ])
    assert args.model == "fixture"
    assert args.endpoint == "http://localhost"
    assert args.api_key_env == "KEY"
