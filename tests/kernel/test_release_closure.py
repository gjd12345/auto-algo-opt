import json
import sqlite3
from pathlib import Path
import re

import pytest

from agent_skill_loop import session_runtime as db, session_supervisor as supervisor
from agent_skill_loop.__main__ import main
from agent_skill_loop.session_contracts import PlanOperation, FeedbackBasis, strict_json_object


@pytest.mark.parametrize("purpose", ["plan", "evaluate", "memory", "arbitrary"])
def test_bridge_cannot_restore_legacy_roles(tmp_path, monkeypatch, purpose):
    from eoh_frozen.llm_bridge import OpenAIPathBridge
    from agent_skill_loop.request_budget import RequestBudget
    budget = RequestBudget(1)
    bridge = OpenAIPathBridge("http://localhost", "fixture", "fixture", budget=budget)
    monkeypatch.setattr("eoh_frozen.llm_bridge.http_post_with_deadline", lambda *a, **k: pytest.fail("provider called"))
    bridge.last_request_index = 41
    with pytest.raises(ValueError, match="gateway_purpose_denied"):
        bridge._forward("hello", purpose=purpose)
    assert budget.used == 0
    assert bridge.last_request_index is None


def test_documented_schema_matches_runtime():
    doc = (Path(__file__).resolve().parents[2] / "docs/sqlite-schema.md").read_text(encoding="utf-8")
    documented, actual = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    try:
        documented.executescript(re.findall(r"```sql\n(.*?)\n```", doc, re.S)[0])
        db._create_schema(actual)
        def schema(con):
            return [(kind, name, re.sub(r"\s+", " ", sql).replace(" IF NOT EXISTS", ""))
                    for kind, name, sql in con.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")]
        assert schema(documented) == schema(actual)
    finally:
        documented.close()
        actual.close()


def test_memory_replay_normalizes_body_without_duplicate_publication(tmp_path):
    from agent_skill_loop.memory.api import MemoryAPI, MemoryEntry
    api = MemoryAPI(tmp_path)
    entry = MemoryEntry("whitespace", "test", "insight", "cvrp_construct", "select_next_node",
                        "\n**Why:** observed failure\n**How to apply:** test only\n")
    first = api.write(entry, operation_key="same")
    replay = api.write(entry, operation_key="same")
    assert first["reference"] == replay["reference"]
    assert replay["replayed"]
    assert len(list(tmp_path.glob("*/*.md"))) == 1


def test_memory_project_symlink_cannot_escape_store(tmp_path):
    from agent_skill_loop.memory.api import MemoryAPI, MemoryEntry
    api = MemoryAPI(tmp_path / "store")
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (api.store / "cvrp_construct").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink privilege not available")
    entry = MemoryEntry("escape", "test", "insight", "cvrp_construct", "select_next_node",
                        "**Why:** fixture\n**How to apply:** fixture")
    with pytest.raises(ValueError, match="outside_store"):
        api.write(entry)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("value", [None, [], "", 1, True])
def test_nested_documents_reject_non_objects(value):
    with pytest.raises(ValueError, match="operation_must_be_object"):
        PlanOperation.from_dict(value)
    with pytest.raises(ValueError, match="feedback_basis_must_be_object"):
        FeedbackBasis.from_dict(value, expected_suite_hash="hash")


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":{"b":0,"b":1}}', '{"a":NaN}', '{"a":Infinity}'])
def test_ambiguous_json_is_rejected(text):
    with pytest.raises(ValueError):
        strict_json_object(text)


def test_non_owner_supervisor_cannot_finish_running_task(tmp_path, monkeypatch):
    root = tmp_path / "run"
    db.initialize_session(output=root, operation_id="init", eoh_model="fixture", size=6, count=1)
    with db._connect(root / "session.sqlite3") as con:
        run_id = con.execute("SELECT run_id FROM runs").fetchone()[0]
        con.execute("INSERT INTO tasks(task_id,run_id,round_id,state,created_at_utc) VALUES ('owned',?,1,'RUNNING',?)", (run_id, db._utc_now()))
    before = db.read_state(run=root)
    monkeypatch.setattr(supervisor.subprocess, "Popen", lambda *a, **k: pytest.fail("non-owner spawned work"))
    supervisor.run_task(root, "owned")
    after = db.read_state(run=root)
    assert before == after
    assert not list(root.glob("rounds/**/terminal.json"))


def test_session_cli_sqlite_failure_is_json(tmp_path, monkeypatch, capsys):
    from agent_skill_loop import session_actions
    def broken(**kwargs):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(session_actions, "memory_search", broken)
    assert main(["session", "memory", "search", "--run", str(tmp_path)]) == 10
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "SQLITE_ERROR"


def test_feedback_basis_is_copyable_from_state(tmp_path):
    root = tmp_path / "run"
    db.initialize_session(output=root, operation_id="init", eoh_model="fixture", size=6, count=1)
    assert db.read_state(run=root)["feedback_basis"] is None
    with db._connect(root / "session.sqlite3") as con:
        # Read-model probe: publication integrity remains submit-plan's job.
        con.execute("UPDATE rounds SET state='ROUND_COMPLETED'")
        con.execute("INSERT INTO rounds(run_id,round_id,state,updated_state_version,created_at_utc,feedback_ref) SELECT run_id,2,state,updated_state_version,created_at_utc,'rounds/round_0001/evaluation_facts.json' FROM rounds WHERE round_id=1")
        con.execute("UPDATE runs SET active_round_id=2")
    state = db.read_state(run=root)
    suite = json.loads((root / "dev_suite.json").read_text())
    assert state["feedback_basis"] == {
        "round_id": 1, "evaluation_ref": state["feedback_ref"], "suite_hash": suite["content_hash"]}


def test_missing_skill_resources_use_session_error_contract(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"
    db.initialize_session(output=root, operation_id="init", eoh_model="fixture", size=6, count=1)
    monkeypatch.setattr(db, "_skill_content_hash", lambda: (_ for _ in ()).throw(ValueError("optimization_skill_resources_missing")))
    assert main(["session", "state", "--run", str(root)]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "SKILL_RESOURCES_MISSING"
