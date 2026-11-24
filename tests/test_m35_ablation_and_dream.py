"""Offline Phase 2B regressions for evidence, retrieval and the frozen fork."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.memory.auto_dream import ClaimEvidenceManifest, auto_dream, evidence_digest
from agent_skill_loop.memory.retrieval_m35 import CooldownLedger, admission_allowed, regime_false_trigger_rate, rerank_mmr
from knowledge_tools.core import validate_release
from research_agent.contracts import AgentConfig
from research_agent.loop import run_research_agent
from research_agent.tools.kb_tools import KnowledgeBaseTool


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _read_json(path):
    return json.loads(path.read_bytes())


def _scope():
    return {"problem": "cvrp_construct", "interface_id": "cvrp_parallel_merge_static",
            "fleet_policy": "unconstrained", "evaluator_version": "fixture"}


def _dream_fixture(root):
    scope = _scope()
    anchor = {"code_sha256": "a" * 64, "canonical_ast_sha256": "b" * 64}
    evidence = "evaluation:fixture"
    facts = {"problem": scope["problem"], "evaluator_version": scope["evaluator_version"],
             "interface_id": scope["interface_id"], "fleet_policy": scope["fleet_policy"],
             "evidence_refs": [evidence], "candidates": [{"evaluation_id": "fixture", **anchor}]}
    digest = evidence_digest(facts)
    store = root / "source_memory"
    reference = MemoryAPI(store).write(
        MemoryEntry("fixture", "Dev ranking outcome", "insight", scope["problem"], "select_next_node",
                    "**Why:** Ranking changed the verified dev outcome.\n**How to apply:** Repeat the dev comparison."),
        format_version=3, provenance={"evaluation_facts_sha256": digest, "evidence_ref": evidence},
    )["reference"]
    claim = {"claim_id": "fixture", "source_reference": reference, "applicability_scope": scope,
             "denominators": {"attempted": 3, "valid": 2}, "adverse_results": ["One of three cases failed."],
             "contradictions": ["A valid case also regressed."], "code_anchor": anchor,
             "evaluation_facts_sha256": digest, "evidence_ref": evidence}
    return store, {"split": "dev", "evaluation_facts": facts, "claims": [claim]}


def test_dream_is_bit_identical_after_blind_mutation(tmp_path):
    from tools import run_m35_memory_ablation as ablation

    store, doc = _dream_fixture(tmp_path)
    dev, blind = tmp_path / "dev_evidence.json", tmp_path / "blind_evidence.json"
    _write_json(dev, doc)
    _write_json(blind, {"split": "blind", "score": 1, "sealed_seed_token": "fixture"})

    def consolidate(root):
        dream = root / "runs" / "dream"
        result = auto_dream(dev_artifacts=[dev], source_stores=[store], output_store=dream / "memory", output_dir=dream)
        ref = result["cards"][0]["reference"]
        card = MemoryAPI(dream / "memory").read_version(ref)
        assert card["format_version"] == 3 and "One of three cases failed." in card["body"]
        assert result["offline_llm_usage"]["total_tokens"] == 0
        ablation._promote_dev_kb(root, result)
        return {path.relative_to(root): path.read_bytes() for path in root.rglob("*")
                if path.is_file() and path.suffix in {".md", ".json"}}

    before = consolidate(tmp_path / "first")
    _write_json(blind, {"split": "blind", "score": 9000, "sealed_seed_token": "changed"})
    assert consolidate(tmp_path / "second") == before
    with pytest.raises(ValueError, match="auto_dream_"):
        auto_dream(dev_artifacts=[dev, blind], source_stores=[store], output_store=tmp_path / "unsafe_memory",
                   output_dir=tmp_path / "unsafe_output")
    mixed = copy.deepcopy(doc)
    mixed["evaluation_facts"]["candidates"][0]["demands"] = [1, 2, 3]
    _write_json(dev, mixed)
    with pytest.raises(ValueError, match="auto_dream_"):
        auto_dream(dev_artifacts=[dev], source_stores=[store], output_store=tmp_path / "raw_memory",
                   output_dir=tmp_path / "raw_output")


def test_claim_manifest_requires_caveats_and_evaluator_and_counts_offline_tokens(tmp_path):
    store, doc = _dream_fixture(tmp_path)
    dev = tmp_path / "dev_evidence.json"
    _write_json(dev, doc)
    source = ClaimEvidenceManifest.from_dict(doc)
    dropped = source.as_dict()
    dropped["claims"][0]["contradictions"] = []
    with pytest.raises(ValueError, match="claim_evidence_changed"):
        ClaimEvidenceManifest.from_dict(dropped).validate_preserves(source)

    wrong = copy.deepcopy(doc)
    wrong["claims"][0]["applicability_scope"]["evaluator_version"] = "other"
    _write_json(dev, wrong)
    with pytest.raises(ValueError, match="evaluation_provenance_mismatch"):
        auto_dream(dev_artifacts=[dev], source_stores=[store], output_store=tmp_path / "wrong_memory",
                   output_dir=tmp_path / "wrong_output")

    def offline_driver(payload):
        return {"representative_claim_id": "fixture", "claim_evidence_manifest": payload["claim_evidence_manifest"],
                "usage": {"input_tokens": 21, "output_tokens": 3}}

    _write_json(dev, doc)
    result = auto_dream(dev_artifacts=[dev], source_stores=[store], output_store=tmp_path / "llm_memory",
                        output_dir=tmp_path / "llm_output", offline_llm_driver=offline_driver)
    assert result["offline_llm_usage"]["total_tokens"] == 24


def test_dream_rejects_a_pre_fix_solution_with_substituted_code(tmp_path):
    store, doc = _dream_fixture(tmp_path)
    claim = doc["claims"][0]
    scope = claim["applicability_scope"]
    evaluated = "def select_next_node():\n    return 1\n"
    anchor = {"code_sha256": hashlib.sha256(evaluated.encode()).hexdigest(),
              "canonical_ast_sha256": hashlib.sha256(ast.unparse(ast.parse(evaluated)).encode()).hexdigest()}
    doc["evaluation_facts"]["candidates"][0].update(anchor, valid=True)
    facts_sha = evidence_digest(doc["evaluation_facts"])
    written = MemoryAPI(store).write(
        MemoryEntry("legacy-substitution", "Verified construction ranking", "solution", scope["problem"], "select_next_node",
                    "## Execution\n```python\ndef select_next_node():\n    return 2\n```\n"
                    "**Reusable Experience:** Confirm the ranking on matching dev cases.\n"
                    "**Why:** Ranking changes the objective.\n**How to apply:** Compare against the same evaluator.",
                    code_anchor=anchor),
        format_version=3, provenance={"evaluation_facts_sha256": facts_sha, "evidence_ref": claim["evidence_ref"],
                                      "candidate_code_sha256": anchor["code_sha256"], "parent_version_id": "parent",
                                      "canonical_ast_sha256": anchor["canonical_ast_sha256"],
                                      "evaluator_hash": scope["evaluator_version"], "interface_id": scope["interface_id"]},
    )
    claim.update(source_reference=written["reference"], code_anchor=anchor, evaluation_facts_sha256=facts_sha)
    artifact = tmp_path / "dev_evidence.json"
    _write_json(artifact, doc)
    dream = tmp_path / "runs" / "dream"
    with pytest.raises(ValueError, match="auto_dream_unverified_solution"):
        auto_dream(dev_artifacts=[artifact], source_stores=[store], output_store=dream / "memory", output_dir=dream)
    assert not (dream / "l3_promotion_candidates.json").exists()


def test_kb_pins_release_and_rejects_internal_links(tmp_path, monkeypatch):
    store = tmp_path / "knowledge_store"
    release = store / "releases" / "fixture"
    index_hash = _write_json(release / "index.json", {"release_id": "fixture", "entries": []})
    digest = _write_json(release / "manifest.json", {"release_id": "fixture", "files": [{
        "path": "index.json", "sha256": index_hash,
    }]})
    (release / "manifest.sha256").write_text(digest + "\n", encoding="utf-8")
    (store / "current").write_text("releases/fixture", encoding="utf-8")
    kwargs = {"kb_store_path": store, "pinned_release_id": "fixture", "pinned_manifest_sha256": digest}
    tool = KnowledgeBaseTool(tmp_path / "run", **kwargs)
    assert tool.search(query="cvrp")["release_id"] == "fixture"
    assert _read_json(tool.log_path)["manifest_sha256"] == digest
    with pytest.raises(ValueError, match="pinned_manifest_sha256_mismatch"):
        KnowledgeBaseTool(tmp_path / "run", **{**kwargs, "pinned_manifest_sha256": "a" * 64})
    with pytest.raises(ValueError, match="pinned_release_id_mismatch"):
        KnowledgeBaseTool(tmp_path / "run", **{**kwargs, "pinned_release_id": "other"})

    link = release / "internal-link"
    try:
        link.symlink_to(release / "index.json")
    except OSError:
        # Exercise the trust check on Windows accounts without symlink privileges.
        is_symlink = Path.is_symlink
        link.touch()
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or is_symlink(path))
    with pytest.raises(ValueError, match="kb_release_link_forbidden"):
        tool.search(query="cvrp")

    disabled = KnowledgeBaseTool(tmp_path / "arm0", enabled=False, **kwargs)
    with pytest.raises(PermissionError, match="kb_disabled_in_arm"):
        disabled.search(query="anything")
    with pytest.raises(PermissionError, match="kb_disabled_in_arm"):
        disabled.read(entry_id="anything")
    assert not disabled.log_path.exists()


def test_mmr_cap_exact_scope_ttl_and_obp_guard(tmp_path):
    scope = _scope()
    cards = [{"reference": ref, "type": kind, "project": scope["problem"], "description": body}
             for ref, kind, body in (("a", "solution", "ranking ties"), ("b", "solution", "ranking ties"),
                                     ("c", "insight", "ranking"), ("d", "insight", "scale invariance"))]
    ledger_path = tmp_path / "cooldown.json"
    ledger = CooldownLedger(ledger_path, cooldown_rounds=2)
    pick = rerank_mmr("ranking ties", cards, context=scope, ledger=ledger)
    assert len(pick) == 3 and [card["reference"] for card in pick if card["type"] == "solution"] == ["a"]
    observed = {"evaluation_id": "eval-1", "completed": True, "valid": False, "attributed_references": ["a"]}
    assert not ledger.observe("a", scope, round_id=1, evaluation={**observed, "http_status": 429})
    assert not ledger.observe("a", scope, round_id=1, evaluation={**observed, "error_code": "worker_crash"})
    assert not ledger.observe("a", scope, round_id=1, evaluation={**observed, "attributed_references": ["b"]})
    assert ledger.observe("a", scope, round_id=1, evaluation=observed)
    ledger = CooldownLedger(ledger_path, cooldown_rounds=2)
    assert ledger.is_active("a", scope, 2) and ledger.is_active("a", scope, 3)
    assert not ledger.is_active("a", scope, 4)
    assert not ledger.is_active("a", {**scope, "fleet_policy": "exact_k"}, 2)
    assert "a" not in {card["reference"] for card in rerank_mmr("ranking", cards, context=scope, ledger=ledger, round_id=2)}
    assert ledger.observe("a", scope, round_id=2, evaluation={**observed, "evaluation_id": "eval-2", "valid": True,
                                                             "verified_improvement": True})
    assert not ledger.is_active("a", scope, 3)

    event = {"regime": "large", "held_out": True, "completed": True, "valid": True, "triggered": True}
    assert regime_false_trigger_rate([event, {**event, "regime": "small"}], "large")["status"] == "insufficient_evidence"
    assert regime_false_trigger_rate([event, event, {**event, "triggered": False}], "large")["rate"] == 2 / 3
    obp = {"problem": "obp"}
    assert not admission_allowed({"project": "bpp_offline", "prefix_trace_equal": True}, obp)
    assert not admission_allowed({"project": "obp", "prefix_trace_equal": False}, obp)
    assert admission_allowed({"project": "obp", "prefix_trace_equal": True}, obp)


def test_resume_configuration_pins_arm_memory(tmp_path):
    config = AgentConfig("fixture", str(tmp_path))
    _write_json(tmp_path / "agent_config.json", config.to_dict())
    with pytest.raises(ValueError, match="resume_config_mismatch:memory_enabled"):
        run_research_agent(replace(config, memory_enabled=True, memory_mode="m35_l12"), resume=True)


def test_mock_common_start_fork(tmp_path):
    from tools import run_m35_memory_ablation as ablation

    seed = ablation.SEEDS[0]
    args = ["--output-dir", str(tmp_path)]
    ablation.main([*args, "init-fork", "--mode", "mock", "--seed", str(seed)])
    fork_path = tmp_path / "runs" / str(seed) / "common_start_manifest.json"
    initial_manifest = fork_path.read_bytes()
    fork = _read_json(fork_path)
    promotion = fork["memory"]["l3_release"]
    release = Path(promotion["release_dir"])
    assert release.parent == tmp_path / "runs" / "dream" / "l3_release"
    assert (checked := validate_release(release))["ok"]
    assert checked["release_id"] == promotion["release_id"] != fork["kb"]["release_id"]
    assert checked["manifest_sha256"] == promotion["manifest_sha256"]
    tool = KnowledgeBaseTool(tmp_path / "inspect-release", kb_store_path=release,
                             pinned_release_id=promotion["release_id"], pinned_manifest_sha256=promotion["manifest_sha256"])
    [hit] = tool.search(query="CVRP scale-invariant merge ranking", problem_family="cvrp")["results"]
    entry = tool.read(entry_id=hit["id"])["entry"]
    assert entry["attributes"]["source_split"] == "dev" and "Verified Dev Evidence" in entry["body"]
    ablation.main([*args, "emit-mux"])
    mux = _read_json(tmp_path / "mux_m35.json")
    assert [pane["id"] for pane in mux["panes"]] == [
        f"{arm}_s{seed}" for arm in fork["arm_launch_order"]
    ]

    def run_arm(arm):
        return ablation.main([*args, "run-arm", "--seed", str(seed), "--arm", arm])

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run_arm, ablation.ARMS)) == [0] * 4
    for arm in ablation.ARMS:
        run = fork_path.parent / arm
        config = _read_json(run / "agent_config.json")
        summary = _read_json(run / "research_summary.json")
        if arm == ablation.ARM_0:
            assert not config["memory_enabled"] and not config["kb_enabled"]
            assert summary["feature_count"] == 0 and not (run / "agent_artifacts" / "kb_events.jsonl").exists()
            plans = run / "agent_artifacts" / "session_plans"
            assert _read_json(plans / "plan_r0001.json")["memory_basis"] == []
            assert _read_json(plans / "eval_r0001.json")["memory_action"] == {"kind": "disabled"}
        else:
            assert summary["feature_count"] > 0
            assert any(record["gateway_refs"] for record in summary["memory_consumption"])
            pin = promotion if arm == ablation.ARM_3 else fork["kb"]
            assert config["kb_store_path"] == pin["release_dir"]
            assert config["pinned_kb_release_id"] == pin["release_id"]
            assert config["pinned_kb_manifest_sha256"] == pin["manifest_sha256"]
            round_dir = run / "session_run" / "rounds" / "round_0001"
            plan_pin = _read_json(round_dir / "context_manifest.json")["interface_selection"]
            execution_pin = _read_json(round_dir / "eoh_run" / "summary.json")
            for receipt in (plan_pin, execution_pin):
                assert receipt["kb_release_id"] == pin["release_id"]
                assert receipt["kb_manifest_sha256"] == pin["manifest_sha256"]

    ablation.main([*args, "eval-select"])
    ablation.main([*args, "eval-external"])
    ablation.main([*args, "report"])
    report = _read_json(tmp_path / "runs" / ablation.REPORT)
    assert len(report["arm_wiring"]) == 4 and initial_manifest == fork_path.read_bytes()
    assert all(set(suite["per_seed"]) == {str(seed)} for suite in report["suites"].values())


def test_common_start_rounds_dev_metrics_to_challenger_precision(monkeypatch):
    from tools import run_m35_memory_ablation as ablation

    monkeypatch.setattr(ablation, "_build_initial_baseline_solver", lambda _: SimpleNamespace(to_dict=lambda: {}))
    monkeypatch.setattr(ablation, "_evaluate", lambda solver, item, suite: item)
    rows = [
        {"completed": True, "feasible": True, "budget_exhausted": False, "objective": 3.12345678},
        {"completed": True, "feasible": True, "budget_exhausted": False, "objective": 8.23456789},
        {"completed": False, "objective": None, "reference_objective": 99.3456789},
    ]
    metrics = ablation._common_start(ablation._agent_settings("mock"), {"instances": rows})["baseline_dev_eval"]
    assert metrics == {"instance_count": 3, "valid_count": 2, "all_feasible": False, "completion_rate": 0.666667,
                       "valid_only_mean_objective": 5.679012, "penalized_mean_objective": 70.016461}


def test_gateway_delivery_requires_durable_finish_receipt(tmp_path):
    from tools import run_m35_memory_ablation as ablation

    session = tmp_path / "session_run"
    local_ref = "rounds/round_0001/memory_consumption.json"
    path = session / local_ref
    context_ref = "rounds/round_0001/round_context_manifest.json"
    context = "verified context"
    context_hash = hashlib.sha256(context.encode()).hexdigest()
    manifest_hash = _write_json(session / context_ref, {"context_sha256": context_hash})
    path.with_name("round_context.txt").write_bytes(context.encode())
    input_ref = "gateway/input.json"
    input_hash = _write_json(session / input_ref, {"messages": [{"content": context}]})
    card = {"reference": "fixture", "body_sha256": "b" * 64, "injected_sha256": "c" * 64}
    evidence = {"schema_version": ablation.MEMORY_RECEIPT_SCHEMA, "memory_enabled": True, "round_id": 1,
                "run_id": "session-fixture", "compiled": [{**card, "status": "compiled_into_context"}],
                "context_manifest_ref": context_ref, "context_manifest_sha256": manifest_hash,
                "gateway_requests": [{"context_status": "gateway_attempt_exact_context", "transport_status": "delivered",
                                      "input_ref": input_ref, "input_sha256": input_hash,
                                      "memory": [{**card, "status": "gateway_attempt"}]}]}
    digest = _write_json(path, evidence)
    ledger = session / "session.sqlite3"
    summary = {"feature_count": 1, "memory_consumption": [{"round_id": 1, "artifact_ref": f"session_run/{local_ref}",
                                                           "injected_refs": ["fixture"], "gateway_refs": ["fixture"]}]}
    # A successful continue operation points at the next round in its envelope.
    receipt = {"round_id": 2, "result": {"memory_consumption_ref": local_ref, "memory_consumption_sha256": digest}}
    with sqlite3.connect(ledger) as con:
        con.execute("CREATE TABLE operations(run_id TEXT, round_id INTEGER, action TEXT, status TEXT, receipt_json TEXT)")
        con.execute("INSERT INTO operations VALUES ('session-fixture', 1, 'finish-round', 'SUCCEEDED', ?)",
                    (json.dumps(receipt),))
    assert ablation._verify_gateway(tmp_path, summary, enabled=True)["delivered_refs"] == ["fixture"]
    _write_json(path, {**evidence, "publication": {"status": "tampered"}})
    with pytest.raises(ValueError, match="m35_memory_consumption_digest_mismatch"):
        ablation._verify_gateway(tmp_path, summary, enabled=True)

    _write_json(path, evidence)
    del receipt["result"]["memory_consumption_sha256"]
    with sqlite3.connect(ledger) as con:
        con.execute("UPDATE operations SET receipt_json=?", (json.dumps(receipt),))
    wiring = ablation._verify_gateway(tmp_path, summary, enabled=True)
    assert wiring["gateway_refs"] == ["fixture"] and wiring["delivered_refs"] == []


def test_build_dev_seed_feeds_init_fork_and_loads_env(tmp_path, monkeypatch):
    from tools import run_m35_memory_ablation as ablation

    loaded = []
    monkeypatch.setattr(ablation, "load_local_env", lambda: loaded.append(True))
    args = ["--output-dir", str(tmp_path)]
    assert ablation.main([*args, "build-dev-seed", "--instance-limit", "2"]) == 0
    store = tmp_path / "dev_seed" / "source_memory"
    artifact = tmp_path / "dev_seed" / "dev_evidence.json"
    doc = _read_json(artifact)
    assert doc["split"] == "dev_train" and len(doc["claims"]) == 4
    seed = ablation.SEEDS[0]
    assert ablation.main([
        *args, "init-fork", "--mode", "mock", "--seed", str(seed),
        "--source-store", str(store), "--dev-artifact", str(artifact),
    ]) == 0
    assert len(loaded) == 2
    manifest = _read_json(tmp_path / "runs" / "dream" / "auto_dream_manifest.json")
    assert len(manifest["cards"]) == 4

    # P1/P2 audit regression: mismatched claim interface_id and compound blind path must fail cleanly.
    from agent_skill_loop.memory.auto_dream import _forbidden_path
    assert _forbidden_path(Path("cvrp_m5_control_blind_120_eval/dev.json"))
    tampered = copy.deepcopy(doc)
    tampered["claims"][0]["applicability_scope"]["interface_id"] = "cvrp_ruin_recreate"
    if tampered["claims"][0]["evidence_ref"] == "evaluation:dev_ordinal0_cvrp_ruin_recreate":
        tampered["claims"][1]["applicability_scope"]["interface_id"] = "cvrp_ruin_recreate"
    bad_artifact = tmp_path / "dev_seed" / "tampered_dev_evidence.json"
    _write_json(bad_artifact, tampered)
    with pytest.raises(ValueError, match="auto_dream_evaluation_provenance_mismatch"):
        auto_dream(
            dev_artifacts=[bad_artifact], source_stores=[store],
            output_store=tmp_path / "bad_dream_mem", output_dir=tmp_path / "bad_dream_out",
        )


def test_live_wall_seconds_and_session_cannot_continue(tmp_path):
    from research_agent.tools.session_tools import SessionRunnerTool
    from tools import run_m35_memory_ablation as ablation

    assert ablation._agent_settings("mock")["wall_seconds"] == 1200.0
    assert ablation._agent_settings("live")["wall_seconds"] == 14400.0

    session_dir = tmp_path / "session_run"
    session_dir.mkdir(parents=True)
    db_path = session_dir / "session.sqlite3"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE runs(run_id TEXT, eoh_round_max_requests INTEGER, round_wall_seconds REAL, engine_wall_seconds REAL)")
    con.execute("CREATE TABLE tasks(task_id TEXT, run_id TEXT, terminal_reason TEXT, engine_elapsed_seconds REAL)")
    con.execute("INSERT INTO runs VALUES ('r1', 10, 300.0, 1200.0)")
    con.execute("INSERT INTO tasks VALUES ('t1', 'r1', 'SUCCEEDED', 600.0)")
    con.commit()
    assert SessionRunnerTool._session_cannot_continue(session_dir) is False
    con.execute("INSERT INTO tasks VALUES ('t2', 'r1', 'DEADLINE_EXCEEDED', 600.5)")
    con.commit()
    assert SessionRunnerTool._session_cannot_continue(session_dir) is True
    con.close()
