from __future__ import annotations

import json
import sqlite3

import pytest

from agent_skill_loop.__main__ import main
from agent_skill_loop.session_runtime import (
    SessionError,
    initialize_session,
    read_state,
    stop_session,
)
from agent_skill_loop.journal import verify_audit_journal


def _init(path):
    return initialize_session(
        output=path,
        operation_id="init-001",
        problem="cvrp_construct",
        eoh_model="deepseek-flash",
        eoh_endpoint="https://api.deepseek.com/v1/chat/completions",
        eoh_api_key_env="DEEPSEEK_API_KEY",
        eoh_max_requests=8,
        count=1,
        size=4,
    )


def test_init_freezes_identity_without_external_effects(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sentinel-secret-value")
    run = tmp_path / "session"
    result = _init(run)

    assert result["state"] == "WAITING_FOR_PLAN"
    assert result["state_version"] == 1
    assert result["result"]["provider_requests"] == 0
    assert result["result"]["solver_calls"] == 0

    connection = sqlite3.connect(run / "session.sqlite3")
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"schema_meta", "runs", "rounds", "operations"} <= tables
        assert connection.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 1
    finally:
        connection.close()

    config_text = (run / "config_frozen.json").read_text(encoding="utf-8")
    assert "sentinel-secret-value" not in config_text
    assert "DEEPSEEK_API_KEY" in config_text
    assert "sentinel-secret-value" not in (run / "session.sqlite3").read_bytes().decode("latin1")
    audit = verify_audit_journal(run / "journal" / "events.jsonl", expected_run_id=result["run_id"])
    assert audit["events"] == 2
    state = read_state(run=run)
    assert state["state_version"] == 1
    assert state["budgets"]["eoh_requests_used"] == 0
    assert state["result"]["budgets"]["eoh_requests_used"] == 0


def test_stop_is_idempotent_and_checks_state_version(tmp_path):
    run = tmp_path / "session"
    _init(run)

    stopped = stop_session(
        run=run,
        operation_id="stop-001",
        expected_state_version=1,
        reason="user_requested",
    )
    assert stopped["run_state"] == "STOPPED"
    assert stopped["state"] == "STOPPED"
    assert stopped["state_version"] == 2
    audit = verify_audit_journal(run / "journal" / "events.jsonl" , expected_run_id=stopped["run_id"])
    assert audit["events"] == 5

    replay = stop_session(
        run=run,
        operation_id="stop-001",
        expected_state_version=999,
        reason="user_requested",
    )
    assert replay == stopped
    assert read_state(run=run)["state_version"] == 2

    with pytest.raises(SessionError, match="different stop input") as conflict:
        stop_session(
            run=run,
            operation_id="stop-001",
            expected_state_version=2,
            reason="different_reason",
        )
    assert conflict.value.code == "OPERATION_ID_CONFLICT"


def test_stop_rejects_stale_state_version(tmp_path):
    run = tmp_path / "session"
    _init(run)
    connection = sqlite3.connect(run / "session.sqlite3")
    try:
        connection.execute("UPDATE runs SET state_version=2 WHERE state_version=1")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(SessionError) as error:
        stop_session(run=run, operation_id="stop-002", expected_state_version=1)
    assert error.value.code == "STATE_VERSION_CONFLICT"


def test_session_cli_emits_json_only(tmp_path, capsys):
    run = tmp_path / "session"
    exit_code = main([
        "session", "init", "--output", str(run), "--operation-id", "init-cli",
        "--eoh-model", "deepseek-flash", "--count", "1", "--size", "4",
    ])
    assert exit_code == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["action"] == "init"
    assert payload["state"] == "WAITING_FOR_PLAN"

    exit_code = main(["session", "state", "--run", str(run)])
    assert exit_code == 0
    state = json.loads(capsys.readouterr().out)
    assert state["state_version"] == 1
