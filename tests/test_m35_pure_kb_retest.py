from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from agent_skill_loop import session_actions, session_runtime
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.memory import api as memory_api
from research_agent import AgentConfig, run_research_agent
from research_agent.contracts import atomic_write_json, sha256_file
from research_agent.tools.kb_tools import verify_pinned_release
from tools import multi_task_mux
from tools import run_m35_pure_kb_retest as retest
from tools.m35_pure_kb_analysis import audit_cell, suite_report


def _json(path):
    return json.loads(path.read_bytes())


def _snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def _insight(name):
    return MemoryEntry(
        name, "CVRP ranking evidence", "insight", "cvrp_construct", "select_next_node",
        "**Why:** Preserve verified ranking ties.\n**How to apply:** Compare fixed fixtures.",
    )


def _memory_action(entry):
    fields = entry.as_dict()
    fields["kind"] = fields.pop("type")
    return fields


def _inject_stale_accepted_operation(root, file, proposal):
    """Simulate a persisted operation waiting for publication after process loss."""
    actions, db = session_actions, session_runtime
    action, operation = "submit-evaluation", "stale-evaluation"
    document = file.read_text(encoding="utf-8")
    base = "rounds/round_0001"
    proposal_ref, submitted_ref = f"{base}/memory_proposal.json", f"{base}/evaluation.submitted.json"
    proposal_sha = actions.save(root, proposal_ref, proposal)
    submitted_sha = actions.save(root, submitted_ref, document)
    with closing(db._connect(root / "session.sqlite3")) as con, db._transaction(con):
        run, round_row, input_hash, _ = actions.begin(
            con, action, operation, 1, {"document_sha256": db._sha256(document)},
        )
        con.execute(
            "INSERT INTO memory_writes(run_id,round_id,operation_id,kind,proposal_ref,status,created_at_utc) "
            "VALUES (?,1,?,?,?,'accepted',?)",
            (run["run_id"], operation, proposal["kind"], proposal_ref, db._utc_now()),
        )
        con.execute(
            "UPDATE rounds SET state='READY_TO_FINISH',submitted_evaluation_ref=?,submitted_evaluation_sha256=?, "
            "memory_proposal_ref=?,memory_commit_status='accepted'",
            (submitted_ref, submitted_sha, proposal_ref),
        )
        actions.receipt(con, run, round_row, action, operation, input_hash, {
            "evaluation_accepted": True, "evaluate_ref": submitted_ref, "proposal_ref": proposal_ref,
            "proposal_sha256": proposal_sha, "evaluation_facts_ref": round_row["evaluation_facts_ref"],
            "evaluation_facts_sha256": round_row["evaluation_facts_sha256"], "card_head": None,
            "memory": {"status": "accepted"},
        })
    return operation


def test_read_only_session_blocks_proposal_revision_and_crash_replay(tmp_path, monkeypatch):
    root, store = tmp_path / "session", tmp_path / "memory"
    api = MemoryAPI(store)
    seed_ref = api.write(_insight("seed-ranking"))["reference"]
    atomic_text = memory_api._atomic_text

    def fail_at_card_markdown(path, content):
        if path.name == "insight_unfinished-ranking__v0001.md":
            raise OSError("simulated process loss after publication staging")
        atomic_text(path, content)

    with monkeypatch.context() as patch:
        patch.setattr(memory_api, "_atomic_text", fail_at_card_markdown)
        with pytest.raises(memory_api.MemoryPublicationPending):
            api.write(_insight("unfinished-ranking"), operation_key="crashed:write")

    before = _snapshot(store)
    assert any(path.endswith(".publish") for path in before)
    settings = dict(output=root, operation_id="init", eoh_model="fixture", size=6, count=1,
                    memory_enabled=True, memory_online_writeback_enabled=False, memory_store=str(store))
    session_runtime.initialize_session(**settings)
    assert session_runtime.read_state(run=root)["memory"]["online_writeback_enabled"] is False
    assert _json(root / "config_frozen.json")["memory"]["online_writeback_enabled"] is False

    def unexpected_write(*args, **kwargs):
        pytest.fail("An online publication reached MemoryAPI.write")

    monkeypatch.setattr(MemoryAPI, "write", unexpected_write)
    search = session_actions.memory_search(run=root, query="ranking")["result"]
    assert [card["reference"] for card in search["memories"]] == [seed_ref]
    page = session_actions.memory_read(run=root, reference=seed_ref)["result"]
    assert page["complete_memory_consumption"] is True
    assert _snapshot(store) == before

    facts_ref = "rounds/round_0001/evaluation_facts.json"
    facts_sha = session_actions.save(root, facts_ref, {"evidence_refs": [], "candidates": []})
    with closing(session_runtime._connect(root / "session.sqlite3")) as con:
        con.execute("UPDATE rounds SET state='WAITING_FOR_EVALUATION',evaluation_facts_ref=?,evaluation_facts_sha256=?",
                    (facts_ref, facts_sha))
    proposal = _memory_action(_insight("online-ranking"))
    file = tmp_path / "evaluation.json"
    atomic_write_json(file, {"plan_alignment": "unknown", "memory_action": proposal})
    with pytest.raises(session_runtime.SessionError) as denied:
        session_actions.submit_evaluation(run=root, operation_id="new-evaluation", expected_state_version=1, file=file)
    assert denied.value.code == "MEMORY_ONLINE_WRITEBACK_DISABLED"
    assert session_runtime.read_state(run=root)["memory"]["writes"] == []

    operation = _inject_stale_accepted_operation(root, file, proposal)
    resumed = session_actions.submit_evaluation(run=root, operation_id=operation, expected_state_version=1, file=file)
    assert resumed["result"]["memory"] == {
        "status": "rejected", "error_code": "memory_online_writeback_disabled", "reference": None,
    }
    assert session_actions.submit_evaluation(run=root, operation_id=operation, expected_state_version=1, file=file) == resumed
    revision = tmp_path / "revision.json"
    atomic_write_json(revision, proposal)
    with pytest.raises(session_runtime.SessionError) as denied:
        session_actions.memory_revise(run=root, operation_id="revision", expected_state_version=resumed["state_version"],
                                     file=revision)
    assert denied.value.code == "MEMORY_ONLINE_WRITEBACK_DISABLED"
    assert _snapshot(store) == before


def test_research_resume_pins_writeback_and_rejects_non_boolean(tmp_path):
    config = AgentConfig("readonly", str(tmp_path), memory_enabled=True, memory_mode="m35_full",
                         memory_online_writeback_enabled=False, kb_enabled=False)
    with pytest.raises(ValueError, match="memory_online_writeback_enabled"):
        replace(config, memory_online_writeback_enabled=0)
    legacy = config.to_dict()
    del legacy["memory_online_writeback_enabled"]
    assert AgentConfig.from_dict(legacy).memory_online_writeback_enabled is True
    atomic_write_json(tmp_path / "agent_config.json", config.to_dict())
    with pytest.raises(ValueError, match="resume_config_mismatch:memory_online_writeback_enabled"):
        run_research_agent(replace(config, memory_online_writeback_enabled=True), resume=True)


def _record(instance_id, objective, *, exact=True, applicable=True, reference=10.0):
    return {
        "instance_id": instance_id, "size": 10, "objective": objective,
        "completed": objective is not None, "feasible": objective is not None, "budget_exhausted": False,
        "reference_objective": reference, "exact_k_applicable": applicable,
        "exact_k_feasible": exact if applicable else None,
    }


def test_selection_rank_preserves_zero_and_breaks_ties_deterministically():
    # A single completion cannot outrank two, even when the failure has a zero reference.
    incomplete = [_record("a", 0.0), _record("b", None, reference=0.0)]
    completed = [_record("a", 0.0), _record("b", 6.0, reference=0.0)]
    assert retest._select_key(completed, ordinal=9, digest="f") < retest._select_key(incomplete, ordinal=1, digest="a")
    assert retest._select_key(completed, ordinal=0, digest="f") < retest._select_key(completed, ordinal=1, digest="a")
    assert retest._select_key(completed, ordinal=0, digest="a") < retest._select_key(completed, ordinal=0, digest="f")


def test_paired_reporting_keeps_exact_fleet_and_completion_denominators_per_seed():
    left = [_record("a", 0.0), _record("b", 8.0, exact=False), _record("c", None, applicable=False)]
    right = [_record("a", 2.0), _record("b", 9.0), _record("c", 4.0, applicable=False)]
    seeds, arms = retest.SEEDS[:2], (retest.ARM_1, retest.ARM_0)
    suite = {
        "split": "heldout", "vehicle_limit_policy": "unconstrained", "instance_count": 3,
        "instance_set_sha256": "fixture", "records": {
            **{f"{seeds[0]}:{arm}": rows for arm, rows in zip(arms, (left, right), strict=True)},
            **{f"{seeds[1]}:{arm}": right for arm in arms},
        },
    }
    per_seed = suite_report(suite, seeds=seeds, arms=arms, contrasts=(arms,))["per_seed"]
    assert set(per_seed) == set(map(str, seeds))
    result = per_seed[str(seeds[0])]
    free, exact = result["free_fleet"], result["exact_k"]
    assert [free[denominator][0]["paired_count"] for denominator in ("overall", "common_completed")] == [3, 2]
    assert [exact[denominator][0]["paired_count"] for denominator in ("overall", "common_completed")] == [2, 1]
    assert free["overall"][0]["bootstrap"]["candidate_mean"] == pytest.approx((0.0 + 8.0 + 20.0) / 3, abs=1e-4)
    assert exact["overall"][0]["bootstrap"]["candidate_mean"] == 10.0
    assert exact["common_completed"][0]["bootstrap"]["candidate_mean"] == 0.0
    for stats in (free["overall"][0], free["common_completed"][0], exact["overall"][0], exact["common_completed"][0]):
        assert stats["bootstrap"]["replicates"] == 10_000
        assert len(stats["bootstrap"]["rel_gain_ci95_pct"]) == 2
        assert stats["wilcoxon_p_holm"] == pytest.approx(stats["wilcoxon"]["p_two_sided"], abs=5e-9)
    assert per_seed[str(seeds[1])]["free_fleet"]["overall"][0]["bootstrap"]["mean_diff_cand_minus_base"] == 0.0


def test_cvrplib_x_fleet_lower_bound_does_not_enter_exact_k_denominator(monkeypatch):
    monkeypatch.setattr(retest.v1, "_evaluate", lambda *args: _record("x", 5.0))
    x = retest._evaluate(None, {}, {"vehicle_limit_policy": "free_fleet_min_k_lb"})
    abp = retest._evaluate(None, {}, {"vehicle_limit_policy": "fixed_k_unconstrained_eval"})
    assert x["exact_k_applicable"] is False and x["exact_k_feasible"] is None
    assert abp["exact_k_applicable"] is True and abp["exact_k_feasible"] is True


def _base_with_collision(root, l3_entry, *, field):
    release_id = retest.RELEASE_ID
    base = root / field / release_id
    (base / "entries").mkdir(parents=True)
    entries, files = [], []
    for ordinal in range(354):
        entry_id = f"base-{ordinal:03d}"
        relative = f"entries/{entry_id}.md"
        if ordinal == 0 and field == "id":
            entry_id = l3_entry["id"]
        if ordinal == 0 and field == "path":
            relative = l3_entry["path"]
        path = base / relative
        path.write_bytes(b"# Base fixture\n")
        digest = sha256_file(path)
        entries.append({"id": entry_id, "path": relative, "content_sha256": digest})
        files.append({"path": relative, "sha256": digest, "size": path.stat().st_size})
    index = base / "index.json"
    index_sha = atomic_write_json(index, {"schema_version": "knowledge-v1", "release_id": release_id, "entries": entries})
    files.append({"path": "index.json", "sha256": index_sha, "size": index.stat().st_size})
    digest = atomic_write_json(base / "manifest.json", {
        "schema_version": "knowledge-v1", "release_id": release_id, "files": files, "self_hash_file": "manifest.sha256",
    })
    (base / "manifest.sha256").write_text(f"{digest}  manifest.json\n", encoding="utf-8")
    return {"release_dir": str(base), "release_id": release_id, "manifest_sha256": digest}


def _assert_merged_release(root, fork):
    base, merged = fork["kb"], fork["memory"]["merged_kb"]
    base_path, merged_path = Path(base["release_dir"]), Path(merged["release_dir"])
    assert merged_path.parent == root / "runs" / "dream" / "l3_merged_release"
    verified = verify_pinned_release(merged_path, release_id=merged["release_id"],
                                     manifest_sha256=merged["manifest_sha256"])
    assert verified["ok"]
    base_entries = {entry["id"]: entry for entry in _json(base_path / "index.json")["entries"]}
    merged_records = _json(merged_path / "index.json")["entries"]
    merged_entries = {entry["id"]: entry for entry in merged_records}
    assert len(base_entries) == 354 and len(merged_entries) == len(merged_records)
    assert {entry_id: merged_entries[entry_id] for entry_id in base_entries} == base_entries
    for entry in base_entries.values():
        for path_key, digest_key in (("path", "content_sha256"), ("metadata_path", "metadata_sha256")):
            if path_key in entry:
                assert sha256_file(merged_path / entry[path_key]) == entry[digest_key]

    dream = _json(root / "runs" / "dream" / "auto_dream_manifest.json")
    l3_entries = [merged_entries[key] for key in sorted(merged_entries.keys() - base_entries.keys())]
    assert {entry["attributes"]["memory_reference"] for entry in l3_entries} == {
        card["reference"] for card in dream["cards"]
    }
    assert len(l3_entries) == len(dream["cards"]) > 0
    assert all(entry["id"].startswith("evidence-m35-l3-") and entry["attributes"]["source_split"] == "dev"
               for entry in l3_entries)
    for field in ("id", "path"):
        collision = _base_with_collision(root / "test_bases", l3_entries[0], field=field)
        with pytest.raises(ValueError, match="collision"):
            retest._promote_merged_base_plus_dev_kb(root, dream, collision)


def test_mock_pipeline_uses_common_start_select_and_verified_arm_roles(tmp_path):
    seed = retest.SEEDS[0]
    args = ["--output-dir", str(tmp_path)]
    assert retest.main([*args, "build-dev-seed", "--instance-limit", "2"]) == 0
    assert retest.main([*args, "freeze-fork", "--mode", "mock", "--seed", str(seed)]) == 0
    runs = tmp_path / "runs"
    fork_path = runs / str(seed) / retest.FORK
    fork_bytes = fork_path.read_bytes()
    fork = _json(fork_path)
    _assert_merged_release(tmp_path, fork)

    assert retest.main([*args, "emit-mux"]) == 0
    panes = multi_task_mux._load_manifest(tmp_path / "mux_m35_pure_kb.json")
    assert {pane["id"] for pane in panes} == {f"{arm}_s{seed}" for arm in retest.ARMS}
    assert all("run-cell" in pane["command"] and "--resume" in pane["command"] for pane in panes)

    def run(arm, *extra):
        return retest.main([*args, "run-cell", "--seed", str(seed), "--arm", arm, *extra])

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, retest.ARMS)) == [0] * len(retest.ARMS)

    configs = {arm: retest._arm_configuration(tmp_path, fork, arm) for arm in retest.ARMS}
    empty = hashlib.sha256(b"{}").hexdigest()
    hashes = {arm: fork["arms"][arm]["initial_memory_sha256"] for arm in retest.ARMS}
    assert hashes[retest.ARM_0] is None and hashes[retest.ARM_1] == empty
    assert hashes[retest.ARM_2] == hashes[retest.ARM_3] == fork["memory"]["sha256"] != empty
    for arm, config in configs.items():
        pin = fork["kb"] if arm in {retest.ARM_0, retest.ARM_1} else fork["memory"]["merged_kb"]
        assert config.kb_enabled and config.pinned_kb_manifest_sha256 == pin["manifest_sha256"]
        assert config.memory_online_writeback_enabled == (arm in {retest.ARM_1, retest.ARM_3})
        assert config.memory_enabled == (arm != retest.ARM_0)

    read_only = configs[retest.ARM_2]
    store = Path(read_only.memory_store_path)
    before_resume = _snapshot(store)
    assert run(retest.ARM_2, "--resume") == 0
    assert _snapshot(store) == before_resume
    audits = {arm: audit_cell(config, initial_store_sha256=hashes[arm]) for arm, config in configs.items()}
    assert audits[retest.ARM_0]["kb_search_count"] > 0
    assert audits[retest.ARM_2]["memory_read_count"] > 0
    for arm in (retest.ARM_0, retest.ARM_2):
        assert audits[arm]["memory_write_row_count"] == audits[arm]["publication_count"] == 0
        assert audits[arm]["writeback_status"] == "disabled"
    assert audits[retest.ARM_2]["final_store_sha256"] == hashes[retest.ARM_2]
    for arm in (retest.ARM_1, retest.ARM_3):
        assert audits[arm]["solution_or_insight_count"] > 0
        for receipt in audits[arm]["writeback_receipts"]:
            assert len(receipt["canonical_ast_sha256"]) == 64
            if receipt["kind"] == "solution":
                assert receipt["parent_version_id"]

    with pytest.raises((ValueError, FileNotFoundError)):
        retest.main([*args, "eval-independent"])
    assert retest.main([*args, "select-and-freeze"]) == 0
    shortlist = _json(runs / retest.SHORTLIST)
    selection = _json(runs / retest.SELECT_EVAL)
    champions = _json(runs / retest.CHAMPIONS)
    assert selection["suite_id"] == "cvrp_select_multiscale_64"
    assert selection["shortlist_sha256"] == sha256_file(runs / retest.SHORTLIST)
    assert set(champions["cells"]) == set(selection["cells"]) == {f"{seed}:{arm}" for arm in retest.ARMS}
    for key, cell in champions["cells"].items():
        winner = cell["winner"]
        candidates = shortlist["cells"][key]["candidates"]
        records = selection["cells"][key]
        assert set(records) == {candidate["digest"] for candidate in candidates}
        ranked = min(candidates, key=lambda row: retest._select_key(
            records[row["digest"]], ordinal=row["ordinal"], digest=row["digest"],
        ))
        path = tmp_path / winner["ref"]
        assert sha256_file(path) == winner["sha256"]
        assert _json(path) == ranked["solver"] and winner["ordinal"] == ranked["ordinal"]
    assert retest.main([*args, "eval-independent"]) == 0
    independent = _json(runs / retest.INDEPENDENT_EVAL)
    assert independent["champions_sha256"] == sha256_file(runs / retest.CHAMPIONS)
    assert set(independent["suites"]) == {"cvrp_ext_cvrplib_abp_74", "cvrp_ext_cvrplib_x_100", "cvrp_final_accept_120"}
    assert retest.main([*args, "report"]) == 0
    report = _json(runs / retest.REPORT)
    assert all(set(suite["per_seed"]) == {str(seed)} for suite in report["suites"].values())
    assert fork_path.read_bytes() == fork_bytes

    path = tmp_path / champions["cells"][f"{seed}:{retest.ARM_0}"]["winner"]["ref"]
    frozen = path.read_bytes()
    path.write_bytes(frozen + b"\n")
    with pytest.raises(ValueError, match="m35v2_frozen_champion_mismatch"):
        retest.main([*args, "eval-independent"])
    path.write_bytes(frozen)

    card = next(store.glob("*/*.md"))
    card.write_bytes(card.read_bytes() + b"\nchanged after freeze\n")
    with pytest.raises(ValueError, match="m35v2_read_only_memory_digest_changed"):
        audit_cell(read_only, initial_store_sha256=hashes[retest.ARM_2])

    config = configs[retest.ARM_0]
    log = Path(config.output_dir) / "agent_artifacts" / "kb_events.jsonl"
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    events[0]["manifest_sha256"] = "0" * 64
    log.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="m35v2_kb_event_pin_mismatch"):
        audit_cell(config, initial_store_sha256=None)
