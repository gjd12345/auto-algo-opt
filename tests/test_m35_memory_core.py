from __future__ import annotations

import ast
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent_skill_loop import session_actions as actions, session_runtime as db
from agent_skill_loop.client import ProviderFailure
from agent_skill_loop.contracts import SkillVersion
from agent_skill_loop.evidence.search_progress import build_search_progress, evaluate_stagnation
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.memory import api as memory_api
from agent_skill_loop.session_contracts import MemoryAction, PlanDocument, compile_round_context
from agent_skill_loop.skill_store import load_skill, save_skill
from research_agent import AgentConfig, run_research_agent
from research_agent.tools.session_tools import SessionRunnerTool


@pytest.mark.parametrize(("first", "last", "direction", "expected"), [
    (0.0, 0.0, "minimize", "stagnated"),
    (1.0, 1.0, "minimize", "stagnated"),
    (1.0, 1.0 - 5e-13, "minimize", "stagnated"),
    (0.0, 1e-12, "maximize", "stagnated"),
    (1.0, 2.0, "minimize", "stagnated"),
    (None, None, "minimize", "stagnated"),
    (1.0, 0.0, "minimize", "progress"),
    (0.0, 0.1, "maximize", "progress"),
])
def test_progress_requires_verified_gain_above_precision(first, last, direction, expected):
    history = [{"round_id": 1, "window": {"objective_direction": direction, "attempt_trace": {
        "complete": True, "events": [{"best_before": first, "best_after": last}],
    }}}]
    result = evaluate_stagnation(history, {"enabled": True, "window_evaluations": 1})
    assert result["status"] == expected
    if first is None:
        assert result["reason"] == "verified_objective_missing" and result["relative_gain_gate"] is False
    if first == 0.0:
        assert result["relative_gain_gate"] is None


@pytest.mark.parametrize("order", ["original_first", "repair_first", "prior_repair"])
def test_novelty_follows_durable_attempt_order(order):
    original = {"origin": "generated", "revision": "original", "code_sha256": "a" * 64,
                "evaluation_id": "original", "metrics": {"behavior_evidence": {
                    "status": "complete", "comparable": True, "behavior_signature": "same",
                    "behavior_contract_hash": "contract", "suite_hash": "suite",
                }}}
    repair = {**original, "origin": "generated_repair", "revision": "repair_1", "evaluation_id": "repair"}
    history = [{"candidates": [repair]}] if order == "prior_repair" else []
    calls = {"original_first": [original, repair], "repair_first": [repair, original], "prior_repair": [original]}[order]
    result = build_search_progress([*history, {"candidates": list(reversed(calls)), "solver_attempts": calls}], round_id=2)
    first = order == "original_first"
    assert result["source_duplicate_count"] == result["behavior_duplicate_count"] == int(not first)
    assert result["behavior_novel_count"] == int(first)
    assert result["cumulative"]["repair_source_duplicate_count"] == int(first)
    assert result["cumulative"]["repair_behavior_duplicate_count"] == int(first)


def _plan(refs=()):
    return {"round_id": 1, "direction": "Explore ranking", "preserve": "interface", "hypothesis": "fixture",
            "operations": [{"type": "preserve", "target": "interface", "mechanism": "keep entrypoint"}],
            "memory_basis": list(refs), "feedback_basis": None}


def test_packing_uses_utf8_bytes_and_preserves_whole_cards():
    plan = PlanDocument.from_dict(_plan(["card"]), expected_round_id=1, suite_hash="fixture")
    oversized = {"reference": "card", "body": "漢" * 7999}
    feedback = {"advice": "字" * 10}
    context = compile_round_context(plan, memory_summaries=[oversized], feedback_summary=feedback)
    payload = json.loads(context.split("\n", 1)[1])
    assert len(context) <= 12000 and len(context.encode("utf-8")) <= 24000
    assert payload["omitted_memory_refs"] == ["card"] and payload["memory"] == []
    short = {**oversized, "body": "漢" * 100}
    packed = compile_round_context(plan, memory_summaries=[short], feedback_summary=feedback)
    assert json.loads(packed.split("\n", 1)[1])["memory"] == [short]


def test_controller_token_preflight_blocks_generation_before_post(tmp_path, monkeypatch):
    from tools import memory_content_controller_call as controller

    calls = []
    count = controller.MAX_INPUT_TOKENS + 1

    def post(url, api_key, payload):
        calls.append((url, payload))
        if url.endswith("/input_tokens"):
            return {"object": "response.input_tokens", "input_tokens": count}
        return {"id": "fixture-response"}

    monkeypatch.setattr(controller, "_post", post)
    prompt = "Full prompt, including non-memory overhead 漢字"
    _, attempted, error = controller._dispatch(prompt, "fixture", tmp_path)
    assert not attempted and error == "controller_input_token_limit_exceeded"
    assert len(calls) == 1
    count -= 1
    result, attempted, error = controller._dispatch(prompt, "fixture", tmp_path)
    assert attempted and error is None and result["id"] == "fixture-response"
    count_payload, generation_payload = calls[-2][1], calls[-1][1]
    assert count_payload["input"] == prompt
    assert generation_payload == {**count_payload, "max_output_tokens": 6000, "store": False}


def _initialize(root, **options):
    result = db.initialize_session(output=root, operation_id="init", eoh_model="fixture", size=6, count=1, **options)
    return result["run_id"]


@pytest.mark.parametrize(("outcome", "final_phase"), [
    ({"session_status": "COMPLETED", "stop_reason": "request_limit"}, "completed"),
    ({"session_status": "STOPPED", "stop_reason": "operator_stop"}, "budget_stopped"),
    ({"session_status": "COMPLETED", "completion_reason": "DEADLINE_EXCEEDED"}, "budget_stopped"),
])
def test_reflect_resume_preserves_session_terminal_phase(tmp_path, monkeypatch, outcome, final_phase):
    from research_agent import loop

    config = AgentConfig(run_id="reflect-resume", output_dir=str(tmp_path), max_rounds=3,
                         archive_feedback_enabled=False, kb_enabled=False)
    calls = []

    def run_round(self, *, round_id, **kwargs):
        calls.append(("session", round_id))
        status = {"session_status": "RUNNING", "stop_reason": "request_limit"} if round_id == 1 else outcome
        return {**status, "evaluation_facts": {"terminal_reason": "REQUEST_BUDGET_EXHAUSTED"},
                "frozen_solver": {"solver_id": "fixture"}, "dev_eval": {
                    "valid_count": 1, "all_feasible": True, "completion_rate": 1.0, "penalized_mean_objective": 0.0,
                }}

    class Driver:
        def decide_step(self, *, phase, round_id, **kwargs):
            calls.append((phase, round_id))
            if phase == "reflect":
                return {"action": "finish_round"}
            return {"action": "submit_plan", "direction": "Check terminal state", "hypothesis": "Only one round runs"}

    append_result = loop.append_results_tsv_row

    def interrupt_after_reflection(path, row):
        append_result(path, row)
        if row["round_id"] == 2:
            raise RuntimeError("interrupted before round checkpoint")

    monkeypatch.setattr(SessionRunnerTool, "run_round", run_round)
    with monkeypatch.context() as patch:
        patch.setattr(loop, "append_results_tsv_row", interrupt_after_reflection)
        with pytest.raises(RuntimeError, match="interrupted before round checkpoint"):
            run_research_agent(config, driver=Driver())
    checkpoint = json.loads((tmp_path / "agent_checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["phase"] == "reflect"
    assert all(checkpoint["pending_reflect_payload"][key] == value for key, value in outcome.items())
    summary = run_research_agent(config, driver=Driver(), resume=True)
    assert summary["final_phase"] == final_phase
    assert summary["completed_rounds"] == [1, 2]
    assert all(summary["round_summaries"][-1][key] == value for key, value in outcome.items())
    assert calls == [(phase, round_id) for round_id in (1, 2) for phase in ("diagnose", "session", "reflect")]
    assert len((tmp_path / "results.tsv").read_text(encoding="utf-8").splitlines()) == 3


def test_solution_card_limit_is_one_even_if_three_total_cards_fit(tmp_path):
    from agent_skill_loop.memory.retrieval_m35 import rerank_mmr

    with pytest.raises(ValueError, match="memory_max_solution_cards_out_of_range"):
        AgentConfig(run_id="oversized", output_dir=str(tmp_path), memory_max_solution_cards=2)
    with pytest.raises(ValueError, match="memory_max_solution_cards_invalid"):
        rerank_mmr("ranking", [], context={}, max_solution_cards=2)


@pytest.mark.parametrize("response_received", [False, True])
def test_transport_delivery_is_distinct_from_pre_post_attempt(tmp_path, response_received):
    from agent_skill_loop.interface_design.model_routing import ModelRoutingPolicy
    from agent_skill_loop.interface_design.session_bridge import _build_session_bridge
    from agent_skill_loop.session_ledger import SessionRequestBudget

    root = tmp_path / "run"
    run_id = _initialize(root)
    con = db._connect(root / "session.sqlite3")
    try:
        con.execute("INSERT INTO tasks(task_id,run_id,round_id,state,created_at_utc) VALUES ('task',?,1,'RUNNING',?)",
                    (run_id, db._utc_now()))
    finally:
        con.close()

    class CrashBeforePost(BaseException):
        pass

    def hook(slot, payload, prompt):
        if response_received:
            return 200, b"invalid response body"
        raise CrashBeforePost

    request_log = root / "requests.jsonl"
    bridge = _build_session_bridge(endpoint="http://localhost/v1", api_key="fixture", model="fixture",
                                   request_timeout=5, budget=SessionRequestBudget(root, "task"), req_log=request_log,
                                   wall_seconds=10, problem="cvrp_construct", routing_policy=ModelRoutingPolicy(),
                                   ledger_path=None, run_id=run_id, strict_barriers=False, use_mock=True,
                                   mock_candidates=[], mock_failure_hook=hook, run_started_monotonic=time.monotonic())
    with pytest.raises(ProviderFailure if response_received else CrashBeforePost):
        bridge._forward_serial("fixture generation")
    con = db._connect(root / "session.sqlite3")
    try:
        row = con.execute("SELECT state, attempted_send_at_utc, delivered_at_utc, delivery_http_status FROM requests").fetchone()
    finally:
        con.close()
    assert row["state"] == ("unknown" if response_received else "sent")
    assert row["attempted_send_at_utc"]
    assert bool(row["delivered_at_utc"]) is response_received
    assert row["delivery_http_status"] == (200 if response_received else None)
    events = [json.loads(line)["state"] for line in request_log.read_text(encoding="utf-8").splitlines()]
    assert "attempted_send" in events and ("delivered" in events) is response_received


def _insight(name="ranking", *, project="cvrp_construct", scene="select_next_node"):
    return MemoryEntry(name, "A scoped ranking observation", "insight", project, scene,
                       "### Why\n**Why:** Preserve ties.\n**How to apply:** Compare fixed fixtures.")


def _antipattern(**scope_overrides):
    scope = {"problem": "cvrp_construct", "interface_id": "select_next_node", "fleet_policy": "unconstrained",
             "evaluator_version": "fixture", "n_range": [5, 10], "budget_ms_range": [1, 100000],
             "expires_at_utc": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
             "reentry_rule": "Require a new verified run.", **scope_overrides}
    return MemoryEntry("duplicate-ranking", "One observed ranking failure", "antipattern", "cvrp_construct",
                       "select_next_node", "## Root Cause\nRepeated ties.\n## Applicability Scope\nThis interface.\n"
                       "## Guardrail & False-Positive Boundary\nAllow independently verified outcomes.",
                       applicability_scope=scope, validity_status="active", evidence_tier="single_run",
                       code_anchor={"code_sha256": "a" * 64})


def _action(card, **fields):
    payload = card.as_dict()
    payload["kind"] = payload.pop("type")
    return {**payload, **fields}


def _evaluation(root, tmp_path, proposal, *, facts=None, **options):
    store = tmp_path / "memory"
    _initialize(root, memory_store=str(store), **options)
    ref = "rounds/round_0001/evaluation_facts.json"
    sha = actions.save(root, ref, facts or {"evidence_refs": [], "candidates": []})
    con = db._connect(root / "session.sqlite3")
    try:
        con.execute("UPDATE rounds SET state='WAITING_FOR_EVALUATION',evaluation_facts_ref=?,evaluation_facts_sha256=?", (ref, sha))
    finally:
        con.close()
    file = tmp_path / "evaluate.json"
    file.write_text(json.dumps({"plan_alignment": "unknown", "memory_action": proposal}), encoding="utf-8")
    return store, file, sha


def _fail_initial_publication(root, file, monkeypatch):
    def disk_unavailable(*args, **kwargs):
        raise OSError("disk unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(MemoryAPI, "write", disk_unavailable)
        failed = actions.submit_evaluation(run=root, operation_id="evaluate", expected_state_version=1, file=file)
    assert failed["result"]["memory"]["status"] == "failed"
    return failed


def test_revision_repairs_heading_and_rejects_unsupported_claim_change(tmp_path, monkeypatch):
    root = tmp_path / "run"
    card = _insight()
    store, file, facts_sha = _evaluation(root, tmp_path, _action(card))
    failed = _fail_initial_publication(root, file, monkeypatch)
    revision = tmp_path / "revision.json"
    revised_body = card.body.replace("### Why", "## Why")
    revision.write_text(json.dumps(_action(replace(card, body=revised_body.replace("Preserve ties", "Cut cost by 50%")))), encoding="utf-8")
    with pytest.raises(db.SessionError, match="MEMORY_REVISION_NEW_VERIFIED_EVIDENCE_REQUIRED"):
        actions.memory_revise(run=root, operation_id="unsupported", expected_state_version=failed["state_version"], file=revision)

    revision.write_text(json.dumps(_action(replace(card, body=revised_body))), encoding="utf-8")
    receipt = actions.memory_revise(run=root, operation_id="repair", expected_state_version=failed["state_version"], file=revision)
    binding = receipt["result"]
    assert binding["memory"]["status"] == "published"
    assert binding["evaluation_facts_sha256"] == facts_sha and binding["card_head"] is None
    assert binding["old_proposal_sha256"] == failed["result"]["proposal_sha256"]
    assert binding["new_proposal_sha256"] != binding["old_proposal_sha256"]
    published = MemoryAPI(store).read_version(binding["memory"]["reference"])
    assert published["body"] == revised_body and published["format_version"] == 3
    assert published["provenance"]["new_proposal_sha256"] == binding["new_proposal_sha256"]
    assert actions.memory_revise(run=root, operation_id="repair", expected_state_version=failed["state_version"], file=revision) == receipt


def test_revision_cannot_retarget_a_stale_card_head(tmp_path, monkeypatch):
    root = tmp_path / "run"
    card = _insight()
    store = tmp_path / "memory"
    api = MemoryAPI(store)
    initial = api.write(card)["reference"]
    proposal = _action(card, memory_based_on=initial)
    _, file, _ = _evaluation(root, tmp_path, proposal)
    failed = _fail_initial_publication(root, file, monkeypatch)
    latest = api.write(card, based_on=initial)["reference"]
    revision = tmp_path / "revision.json"
    revision.write_text(json.dumps(proposal), encoding="utf-8")
    with pytest.raises(db.SessionError, match="MEMORY_CARD_HEAD_CONFLICT"):
        actions.memory_revise(run=root, operation_id="stale", expected_state_version=failed["state_version"], file=revision)
    revision.write_text(json.dumps({**proposal, "memory_based_on": latest}), encoding="utf-8")
    with pytest.raises(db.SessionError, match="MEMORY_REVISION_IDENTITY_MISMATCH"):
        actions.memory_revise(run=root, operation_id="retarget", expected_state_version=failed["state_version"], file=revision)
    assert api.card_head(card) == latest


@pytest.mark.parametrize(("threshold", "submission", "error"), [
    (0.25, "equivalent", "solution_threshold_not_met"),
    (0.24, "equivalent", None),
    (0.24, "substituted", "solution_canonical_ast_hash_mismatch"),
    (0.24, "wrong_anchor", "solution_canonical_ast_hash_mismatch"),
])
def test_solution_threshold_is_strict_and_binds_verified_ast(tmp_path, threshold, submission, error):
    root = tmp_path / "run"
    src = "def select_next_node(current, candidates, remaining, demands, distances):\n    return 0\n"
    digest = db._sha256(src)
    ast_digest = db._sha256(ast.unparse(ast.parse(src)))
    source = "candidate"
    evidence = "evaluation:fixture"
    facts = {"baseline": {"objective": 4}, "best_generated_ref": source, "evidence_refs": [evidence],
             "candidates": [{"evaluation_id": "fixture", "code_sha256": digest, "objective": 3.0,
                             "valid": True, "origin": "generated", "canonical_ast_sha256": ast_digest}]}
    submitted_code = src.replace("return 0", "return 1" if submission == "substituted" else "return (0)  # same AST")
    card = replace(_insight(), type="solution", body=(
        f"## Execution\n```python\n{submitted_code}```\n**Reusable Experience:** Use the same interface.\n"
        "**Why:** Verified locally.\n**How to apply:** Confirm again."
    ), code_anchor={"code_sha256": digest, "canonical_ast_sha256": "b" * 64 if submission == "wrong_anchor" else ast_digest})
    store, file, _ = _evaluation(root, tmp_path, _action(card, source_skill_ref=source, evidence_ref=evidence),
                                 facts=facts, solution_threshold=threshold)
    config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
    save_skill(root / source, SkillVersion(version_id="fixture", problem="cvrp_construct", entrypoint="select_next_node",
                                          code=src, code_sha256=digest, parent_version_id="parent", suite_hash=config["suite_hash"],
                                          evaluator_hash=config["evaluator_hash"], valid=True, mean_objective=3.0,
                                          instance_objectives=(3.0,), source_attempt_id=None))
    result = actions.submit_evaluation(run=root, operation_id="evaluate", expected_state_version=1, file=file)["result"]["memory"]
    if error:
        assert result["status"] == "rejected"
        assert result["error_code"] == error
    else:
        assert result["status"] == "published"
        assert MemoryAPI(store).read_version(result["reference"])["provenance"]["canonical_ast_sha256"] == ast_digest


def test_session_exports_parent_lineage_for_solution_proposal(tmp_path):
    from agent_skill_loop.request_budget import PersistentRequestBudget
    from research_agent.loop import _build_initial_baseline_solver

    config = AgentConfig(run_id="lineage", output_dir=str(tmp_path), dev_instance_count=1, dev_instance_size=6,
                         eoh_n_pop=1, eoh_max_sample_nums=3, early_stop_no_jump_requests=1, kb_enabled=False)
    budget = PersistentRequestBudget(tmp_path / "agent_budget.sqlite3", config.total_request_cap, run_id=config.run_id)
    runner = SessionRunnerTool(run_dir=tmp_path, config=config, budget=budget)
    runner.ensure_initialized()
    root = runner.session_dir
    frozen_config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
    parent_code = _build_initial_baseline_solver(config).hook_code
    parent = SkillVersion(version_id="fixture-parent", problem="cvrp_construct", entrypoint="select_next_node",
                          code=parent_code, code_sha256=db._sha256(parent_code), parent_version_id=None,
                          suite_hash=frozen_config["suite_hash"], evaluator_hash=frozen_config["evaluator_hash"],
                          valid=True, mean_objective=1000.0, instance_objectives=(1000.0,), source_attempt_id=None)
    ref = "skills/fixture-parent"
    save_skill(root / ref, parent)
    con = db._connect(root / "session.sqlite3")
    try:
        con.execute("UPDATE rounds SET incumbent_before_ref=?,incumbent_before_objective=?", (ref, parent.mean_objective))
    finally:
        con.close()
    run = runner.run_round(round_id=1, template_id=config.initial_template_id, postprocess_mode="none",
                           direction="Test generated lineage", hypothesis="The exported hook keeps its parent",
                           is_final_round=True, eval_dev_suite=False)
    facts = run["evaluation_facts"]
    exported = load_skill(root / facts["best_generated_ref"])
    assert exported.parent_version_id == parent.version_id

    # Isolate card proposal from route quality. The actual evaluation identity and export are unchanged.
    facts = {**facts, "baseline": {"objective": 2 * exported.mean_objective}}
    runner.config = replace(config, memory_enabled=True, memory_mode="m35_l12")
    action = runner._memory_action(facts)
    assert action["kind"] == "solution"
    assert action["code_anchor"] == {"code_sha256": exported.code_sha256,
                                     "canonical_ast_sha256": db._sha256(ast.unparse(ast.parse(exported.code)))}


def test_sidecar_dual_reader_and_antipattern_contract(tmp_path):
    api = MemoryAPI(tmp_path)
    historical = _insight("legacy")
    path = tmp_path / historical.project / "insight_legacy.md"
    path.parent.mkdir()
    path.write_text(memory_api._render(historical), encoding="utf-8")
    assert api.read_version(f"{historical.project}/insight_legacy@v0001")["format_status"] == "legacy_compatible"
    v2 = api.write(_insight())
    assert api.read_version(v2["reference"])["format_version"] == 2
    card = _antipattern()
    parsed = MemoryAction.from_dict(_action(card), enabled=True)
    assert parsed.to_entry() == card
    with pytest.raises(ValueError, match="requires_enabled"):
        MemoryAction.from_dict(_action(card), enabled=False)
    with pytest.raises(ValueError, match="antipattern_.*section"):
        api.write(replace(card, body=card.body.replace("## Root Cause\n", "")))
    with pytest.raises(ValueError, match="format_version"):
        api.write(card, format_version=2)
    v3 = api.write(card)
    loaded = api.read_version(v3["reference"])
    assert loaded["format_version"] == 3 and loaded["applicability_scope"] == card.applicability_scope
    assert loaded["validity_status"] == "active" and loaded["code_anchor"] == card.code_anchor
    assert json.loads(Path(v3["path"]).with_suffix(".json").read_text())["schema"].endswith("/v3")
    context = {key: card.applicability_scope[key] for key in ("problem", "interface_id", "fleet_policy", "evaluator_version")}
    context.update(n=(5, 10), budget_ms=100)
    assert api.read_version(v3["reference"], require_active=True, applicability_context=context)["reference"] == v3["reference"]
    with pytest.raises(ValueError, match="inactive"):
        api.read_version(v3["reference"], require_active=True, applicability_context={**context, "n": (5, 11)})


@pytest.mark.parametrize("status", ["quarantined", "superseded", "stale_metric_regression"])
def test_inactive_head_does_not_resurrect_older_card(tmp_path, status):
    api = MemoryAPI(tmp_path)
    card = _insight()
    old = api.write(card)["reference"]
    latest = api.write(replace(card, validity_status=status), based_on=old)["reference"]
    assert api.read("", project=card.project)["memories"] == []
    assert api.read_version(latest)["validity_status"] == status
    with pytest.raises(ValueError, match="inactive"):
        api.read_version(latest, require_active=True)
    with pytest.raises(ValueError, match="superseded"):
        api.read_version(old, require_active=True)


def test_disabled_card_is_excluded_from_lookup_and_packing(tmp_path):
    api = MemoryAPI(tmp_path)
    card = _insight()
    written = api.write(card)
    sidecar = Path(written["path"]).with_suffix(".json")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    sidecar.write_text(json.dumps({**metadata, "enabled": False}), encoding="utf-8")
    reference = written["reference"]
    assert api.read("", project=card.project)["memories"] == []
    with pytest.raises(ValueError, match="inactive"):
        api.read_version(reference, require_active=True)
    plan = PlanDocument.from_dict(_plan([reference]), expected_round_id=1, suite_hash="fixture")
    context = compile_round_context(plan, memory_summaries=[api.read_version(reference)])
    assert json.loads(context.split("\n", 1)[1])["memory"] == []


@pytest.mark.parametrize(("project", "foreign_text"), [
    ("bp_online", "CVRP vehicle routing"), ("obp", "First Fit Decreasing"),
    ("cvrp_construct", "OBP prefix invariance"), ("tsp_construct", "OPTICS reachability plot"),
    ("bpp_offline", "Online bin packing"), ("optics", "Hamiltonian tour"),
])
def test_problem_vocab_guards_publication(project, foreign_text, tmp_path):
    card = _insight(project=project)
    api = MemoryAPI(tmp_path)
    with pytest.raises(ValueError, match="memory_problem_vocab_mismatch"):
        api.write(replace(card, body=f"{card.body}\n{foreign_text}"))
    assert api.write(card)["written"]


def test_shared_legacy_card_cannot_leak_foreign_vocab_through_pagination(tmp_path):
    api = MemoryAPI(tmp_path)
    card = _insight(project="_shared")
    ref = api.write(replace(card, body=f"{card.body}\nCVRP depot return."))["reference"]
    assert api.read_version(ref, max_chars=10)["truncated"]
    assert api.read("", project="obp", applicability_context={"problem": "obp"})["memories"] == []
    with pytest.raises(ValueError, match="memory_problem_vocab_mismatch"):
        api.read_version(ref, max_chars=10, require_active=True, applicability_context={"problem": "obp"})


def test_session_adopts_three_eligible_cards_and_rechecks_head(tmp_path):
    root, store = tmp_path / "run", tmp_path / "memory"
    _initialize(root, memory_store=str(store))
    api = MemoryAPI(store)
    config = json.loads((root / "config_frozen.json").read_text(encoding="utf-8"))
    antipattern = _antipattern(evaluator_version=config["evaluator_hash"], budget_ms_range=[0, 1000000])
    insight = _insight()
    solution = replace(insight, type="solution", body="## Execution\n**Reusable Experience:** Keep the interface.\n"
                       "**Why:** Verified locally.\n**How to apply:** Confirm again.")
    refs = [api.write(card)["reference"] for card in (insight, antipattern, solution)]
    assert all(actions.memory_read(run=root, reference=ref)["result"]["complete_memory_consumption"] for ref in refs)
    plan_text = tmp_path / "plan.json"
    plan_text.write_text(json.dumps(_plan(refs)), encoding="utf-8")
    with pytest.raises(ValueError, match="memory_basis_limit"):
        PlanDocument.from_dict(_plan([*refs, "fourth"]), expected_round_id=1, suite_hash="fixture")
    planned = actions.submit_plan(run=root, operation_id="three", expected_state_version=1, file=plan_text)
    assert planned["state"] == "READY_TO_EXECUTE"
    context = (root / "rounds/round_0001/round_context.txt").read_text(encoding="utf-8")
    assert [entry["reference"] for entry in json.loads(context.split("\n", 1)[1])["memory"]] == refs

    other = tmp_path / "other"
    _initialize(other, memory_store=str(store))
    assert all(actions.memory_read(run=other, reference=ref)["result"]["complete_memory_consumption"] for ref in refs)
    api.write(replace(insight, validity_status="quarantined"), based_on=refs[0])
    with pytest.raises(db.SessionError, match="superseded"):
        actions.submit_plan(run=other, operation_id="stale", expected_state_version=1, file=plan_text)
    with pytest.raises(db.SessionError, match="superseded"):
        actions.execute(run=root, operation_id="execute", expected_state_version=planned["state_version"])


def test_online_session_plan_requires_verified_prefix_evidence(tmp_path):
    from agent_skill_loop.problems import get_problem

    root, store = tmp_path / "obp", tmp_path / "memory"
    problem = "obp_online"
    _initialize(root, problem=problem, memory_store=str(store))
    api = MemoryAPI(store)
    card = _insight("packing-ties", project=problem, scene=get_problem(problem).entrypoint)
    unproven = api.write(card)["reference"]
    verified = api.write(replace(card, name="verified-packing-ties"),
                         provenance={"prefix_trace_equal": "true", "future_lookahead": "false"})["reference"]
    file = tmp_path / "plan.json"
    for ref in (unproven, verified):
        assert actions.memory_read(run=root, reference=ref)["result"]["complete_memory_consumption"]
        file.write_text(json.dumps(_plan([ref])), encoding="utf-8")
        if ref == unproven:
            with pytest.raises(db.SessionError, match="MEMORY_REFERENCE_INVALID|admission"):
                actions.submit_plan(run=root, operation_id="unproven", expected_state_version=1, file=file)
        else:
            assert actions.submit_plan(run=root, operation_id="verified", expected_state_version=1, file=file)["state"] == "READY_TO_EXECUTE"


def test_public_memory_lookup_allows_a_valid_template_but_plan_requires_exact_scope(tmp_path):
    root, store = tmp_path / "run", tmp_path / "memory"
    _initialize(root, memory_store=str(store))
    template = "cvrp_sequential_construct"
    scope = {"interface_id": template, "budget_ms_range": [500, 500]}
    reference = MemoryAPI(store).write(replace(_insight(), applicability_scope=scope))["reference"]
    assert actions.memory_search(run=root)["result"]["memories"] == []
    assert [card["reference"] for card in actions.memory_search(run=root, template_id=template)["result"]["memories"]] == [reference]
    assert actions.memory_read(run=root, reference=reference, template_id=template)["result"]["complete_memory_consumption"]
    with pytest.raises(db.SessionError) as wrong_family:
        actions.memory_read(run=root, reference=reference, template_id="tsp_constructive_step")
    assert wrong_family.value.code == "INVALID_ARGUMENT"

    file = tmp_path / "plan.json"
    plan = _plan([reference])
    file.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(db.SessionError, match="memory_reference_inactive") as unscoped:
        actions.submit_plan(run=root, operation_id="unscoped", expected_state_version=1, file=file)
    assert unscoped.value.code == "MEMORY_REFERENCE_INVALID"
    selection = {"template_id": template, "template_version": "v1", "postprocess_mode": "none"}
    plan["interface_selection"] = {**selection, "template_options": {"time_budget_ms": 600}}
    file.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(db.SessionError, match="memory_reference_inactive") as different_budget:
        actions.submit_plan(run=root, operation_id="different-budget", expected_state_version=1, file=file)
    assert different_budget.value.code == "MEMORY_REFERENCE_INVALID"
    plan["interface_selection"] = selection
    file.write_text(json.dumps(plan), encoding="utf-8")
    assert actions.submit_plan(run=root, operation_id="scoped", expected_state_version=1, file=file)["state"] == "READY_TO_EXECUTE"


def test_startup_recovers_sidecar_orphan_and_replays_operation(tmp_path, monkeypatch):
    class SimulatedExit(BaseException):
        pass

    def die_between_renames(path, content):
        if path.name == "antipattern_duplicate-ranking__v0001.md":
            raise SimulatedExit
        original(path, content)

    card = _antipattern()
    api = MemoryAPI(tmp_path)
    original = memory_api._atomic_text
    with monkeypatch.context() as patch:
        patch.setattr(memory_api, "_atomic_text", die_between_renames)
        with pytest.raises(SimulatedExit):
            api.write(card, operation_key="run:crash")
    folder = tmp_path / card.project
    assert len(list(folder.glob("*.json"))) == len(list(folder.glob("*.publish"))) == 1
    assert not list(folder.glob("*.md"))
    recovered = MemoryAPI(tmp_path)
    assert not list(folder.glob("*.publish"))
    replay = recovered.write(card, operation_key="run:crash")
    assert replay["replayed"] and replay["version"] == 1
    assert recovered.read_version(replay["reference"])["body"] == card.body


def test_session_replays_a_durable_stage_after_transient_disk_failure(tmp_path, monkeypatch):
    root = tmp_path / "run"
    store, file, _ = _evaluation(root, tmp_path, _action(_insight()))
    original = memory_api._atomic_text

    def fail_on_markdown(path, content):
        if path.name == "insight_ranking__v0001.md":
            raise OSError("transient failure after staging")
        original(path, content)

    with monkeypatch.context() as patch:
        patch.setattr(memory_api, "_atomic_text", fail_on_markdown)
        pending = actions.submit_evaluation(run=root, operation_id="evaluate", expected_state_version=1, file=file)
        assert pending["result"]["memory"]["status"] == "accepted"
        with pytest.raises(db.SessionError, match="Replay submit-evaluation"):
            actions.finish_round(run=root, operation_id="finish", expected_state_version=pending["state_version"], decision="complete")
    recovered = actions.submit_evaluation(run=root, operation_id="evaluate", expected_state_version=1, file=file)
    assert recovered["result"]["memory"]["status"] == "published"
    assert len(list(store.glob("*/*.md"))) == 1
