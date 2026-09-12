from __future__ import annotations

import ast
import json

import pytest

pytest.importorskip("eoh")

from agent_skill_loop.problems.cvrp import BASELINE_CODE
from agent_skill_loop.skill_store import load_skill
from eoh_frozen.__main__ import build_parser, cmd_run
from eoh_frozen.smoke import fixture_provider


def _invalid_code(call_index: int) -> str:
    tree = ast.parse(BASELINE_CODE)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    function.body.insert(0, ast.parse(f"marker = {call_index}").body[0])
    code = ast.unparse(ast.fix_missing_locations(tree))
    return code.replace("np.argmin", "np.ix_")


def test_bounded_repair_re_evaluates_repaired_code_and_exports_b(tmp_path, monkeypatch):
    env_name = "EOH_REPAIR_FIXTURE_KEY"
    monkeypatch.setenv(env_name, "fixture")

    def responder(prompt: str, call_index: int):
        if prompt == "1+1=?":
            return 200, "2"
        if '"role":"execute_repair"' in prompt:
            return 200, json.dumps({
                "algorithm": "repaired nearest neighbor",
                "code": BASELINE_CODE,
                "repair_summary": "replace the forbidden attribute with the allowed argmin operation",
            })
        return 200, "{bad candidate}\n```python\n" + _invalid_code(call_index) + "\n```"

    out = tmp_path / "eoh"
    with fixture_provider("cvrp_construct", responder=responder) as (endpoint, _):
        args = build_parser().parse_args([
            "run", "--problem", "cvrp_construct", "--model", "fixture",
            "--output", str(out), "--endpoint", endpoint, "--api-key-env", env_name,
            "--pop-size", "2", "--n-pop", "1", "--max-sample-nums", "1",
            "--max-requests", "16", "--count", "1", "--size", "6",
            "--wall-seconds", "60", "--repair-mode", "bounded",
        ])
        args.execution_mode = "fixture"
        assert cmd_run(args) == 0

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["integration_mode"] == "bounded_repair"
    assert summary["repair"]["attempted"] >= 1
    assert summary["repair"]["succeeded"] >= 1
    assert summary["generated_valid_candidates"] >= 1
    assert (out / "skills" / "candidate_1" / "code.py").is_file()
    exported = load_skill(out / "exported_skill")
    assert exported.code == BASELINE_CODE
    repaired_asset = load_skill(out / "skills" / "candidate_1")
    assert repaired_asset.integration_mode == "bounded_repair"
    assert repaired_asset.repair_policy_version == "bounded_v2"
    assert repaired_asset.origin == "generated_repair"

    evaluations = [
        json.loads(line)
        for line in (out / "results" / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    original = [row for row in evaluations if row.get("origin") == "generated"]
    repaired = [row for row in evaluations if row.get("origin") == "generated_repair"]
    assert original and repaired
    assert all(row["code_sha256"] != repaired[0]["code_sha256"] for row in original)
    assert repaired[0]["evaluation"]["valid"] is True
    assert repaired[0]["revision"] == "repair_1"
    assert repaired[0]["original_code_sha256"] == original[0]["code_sha256"]

    repair_events = [
        json.loads(line)
        for line in (out / "results" / "repair_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(item["state"] == "request_started" for item in repair_events)
    assert any(item["state"] == "succeeded" for item in repair_events)
    requests = [
        json.loads(line)
        for line in (out / "results" / "requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(item.get("purpose") == "eoh_repair" for item in requests)


def test_repair_is_disabled_without_changing_official_path(tmp_path, monkeypatch):
    env_name = "EOH_REPAIR_OFF_FIXTURE_KEY"
    monkeypatch.setenv(env_name, "fixture")

    def responder(prompt: str, call_index: int):
        if prompt == "1+1=?":
            return 200, "2"
        return 200, "{candidate}\n```python\n" + BASELINE_CODE + "\n```"

    out = tmp_path / "eoh_off"
    with fixture_provider("cvrp_construct", responder=responder) as (endpoint, _):
        args = build_parser().parse_args([
            "run", "--problem", "cvrp_construct", "--model", "fixture",
            "--output", str(out), "--endpoint", endpoint, "--api-key-env", env_name,
            "--pop-size", "2", "--n-pop", "1", "--max-sample-nums", "0",
            "--max-requests", "8", "--count", "1", "--size", "6", "--wall-seconds", "60",
        ])
        args.execution_mode = "fixture"
        assert cmd_run(args) == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["repair_mode"] == "off"
    assert summary["repair"]["mode"] == "off"
    assert not (out / "results" / "repair_events.jsonl").exists()
