from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_skill_loop.benchmark import (
    ExperimentManifest,
    FrozenSelection,
    MetricSpec,
    PopulationSnapshot,
    SeedSelection,
    benchmark_profile,
    build_archive,
    build_pilot_manifests,
    calibrate_differential,
    calibrate_upstream,
    evaluate_candidate_set,
    evaluate_selection,
    evaluation_identity,
    freeze_selection,
    load_profile_suite,
    sha256_text,
)
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.session_runtime import initialize_session, read_state


def _member(code: str, algorithm: str, objective: float, index: int) -> dict:
    return {
        "generation": 3,
        "member_index": index,
        "algorithm": algorithm,
        "algorithm_text_sha256": sha256_text(algorithm),
        "code": code,
        "code_sha256": sha256_text(code),
        "objective": objective,
        "evaluation_id": f"evaluation-{index}",
        "revision": "original",
        "origin": "official_eoh",
    }


def test_population_snapshot_is_faithful_and_seed_selection_is_derived():
    metric_hash = "a" * 64
    code_a = "def priority(item, bins):\n    return -bins\n"
    code_b = "def priority(item, bins):\n    return bins\n"
    snapshot = PopulationSnapshot.from_members(
        [
            _member(code_a, "first description", 4.0, 0),
            _member(code_a, "duplicate description", 1.0, 1),
            _member(code_b, "second description", 2.0, 2),
        ],
        generation=3,
        metric_spec_hash=metric_hash,
    )
    assert [item["algorithm"] for item in snapshot.members] == [
        "first description", "duplicate description", "second description"
    ]
    assert [item["member_index"] for item in snapshot.members] == [0, 1, 2]

    selected = SeedSelection.from_snapshot(snapshot, 2)
    assert [item["code_sha256"] for item in selected.selected_members] == [
        sha256_text(code_b), sha256_text(code_a)
    ]
    assert selected.selected_members[1]["algorithm"] == "first description"
    assert not selected.terminated
    insufficient = SeedSelection.from_snapshot(snapshot, 3)
    assert insufficient.terminated
    assert insufficient.termination_reason == "insufficient_valid_seeds"

    with pytest.raises(ValueError, match="population_code_hash_mismatch"):
        PopulationSnapshot.from_members(
            [{**_member(code_a, "bad", 1.0, 0), "code_sha256": "b" * 64}],
            generation=1,
            metric_spec_hash=metric_hash,
        )


def test_evaluation_identity_and_metric_hash_are_part_of_reuse_identity():
    fields = {
        "candidate_code_sha256": "a" * 64,
        "problem_spec_hash": "b" * 64,
        "data_manifest_hash": "c" * 64,
        "evaluator_hash": "d" * 64,
        "metric_spec_hash": "e" * 64,
    }
    first = evaluation_identity(**fields)
    second = evaluation_identity(**{**fields, "metric_spec_hash": "f" * 64})
    assert first != second

    metric = MetricSpec(
        metric_id="relative_gap",
        version="v1",
        reference_manifest_hash="1" * 64,
    )
    assert metric.score(11.0, 10.0) > metric.score(10.0, 10.0)
    assert metric.aggregate([0.0, 0.2]) == pytest.approx(0.1)


def test_archive_and_frozen_selection_do_not_mix_metric_identities():
    code = "def priority(item, bins):\n    return -bins\n"
    row = {
        "code": code,
        "code_sha256": sha256_text(code),
        "problem_spec_hash": "a" * 64,
        "data_manifest_hash": "b" * 64,
        "evaluator_hash": "c" * 64,
        "metric_spec_hash": "d" * 64,
        "origin": "generated",
        "candidate_id": "candidate-1",
        "evaluation_id": "eval-1",
        "evaluation": {"valid": True, "objective": 2.0},
    }
    archive = build_archive(
        [row, {**row, "evaluation_id": "eval-2", "evaluation": {"valid": True, "objective": 1.0}},
         {**row, "metric_spec_hash": "e" * 64, "evaluation": {"valid": True, "objective": 0.1}}],
        problem_spec_hash="a" * 64,
        data_manifest_hash="b" * 64,
        evaluator_hash="c" * 64,
        metric_spec_hash="d" * 64,
    )
    assert len(archive) == 1
    assert archive[0].objective == 1.0
    snapshot = PopulationSnapshot.from_members(
        [_member(code, "generated", 1.0, 0)],
        generation=1,
        metric_spec_hash="d" * 64,
    )
    for kind in ("incumbent_top1", "archive_topk"):
        selection = freeze_selection(kind, archive, metric_spec_hash="d" * 64, k=1 if kind == "archive_topk" else None)
        assert selection.selection_kind == kind
        assert selection.training_metric_spec_hash == "d" * 64
    selection = freeze_selection(
        "final_population_set",
        archive,
        metric_spec_hash="d" * 64,
        population_snapshot=snapshot,
    )
    assert selection.selection_kind == "final_population_set"
    assert selection.members[0]["code_sha256"] == sha256_text(code)


def test_frozen_selection_round_trips_with_report_identity():
    selection = FrozenSelection(
        selection_kind="incumbent_top1",
        members=({"code_sha256": "a" * 64, "objective": 0.1},),
        training_metric_spec_hash="b" * 64,
        source_ref="rounds/round_0001/evaluation_facts.json",
    )
    payload = {**selection.as_dict(), "content_hash": selection.content_hash}
    restored = FrozenSelection.from_dict(payload)
    assert restored.content_hash == selection.content_hash
    from agent_skill_loop.benchmark import build_report
    manifest = ExperimentManifest(
        benchmark_spec_hash="c" * 64,
        metric_spec_hash="b" * 64,
        eoh_commit="eoh",
        runtime_hash="d" * 64,
        skill_hash="e" * 64,
        model="fixture",
        endpoint_identity="offline",
        inheritance_mode="incumbent_only",
        feedback_mode="off",
        agent_guidance=False,
        repair_mode="off",
        memory_enabled=False,
        evaluation_budget=10,
        population_size=2,
        rounds=1,
        round_budget=10,
        search_seed=1,
    )
    report = build_report(
        manifest=manifest,
        selection=restored,
        metrics={
            "best_training_fitness": 0.1,
            "experiment_manifest_sha256": manifest.content_hash,
            "selection_sha256": restored.content_hash,
            "metric_spec_hash": "b" * 64,
        },
        budget={
            "total_evaluation_attempts": 10,
            "novel_candidate_evaluations": 0,
            "seed_reevaluation_attempts": 0,
            "baseline_attempts": 0,
            "repair_attempts": 0,
            "experiment_manifest_sha256": manifest.content_hash,
            "selection_sha256": restored.content_hash,
        },
    )
    assert report["selection_kind"] == "incumbent_top1"
    assert report["test_isolation"]["test_updates_training"] is None
    assert report["test_isolation"]["status"] == "training_only"


def test_obp_gold_is_independent_and_zero_provider():
    suite = load_profile_suite("eohs_v1", "obp_mini", split="dev_train")
    _benchmark, _metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    gold = calibrate_upstream(suite)
    checked = calibrate_differential(suite, json.loads(json.dumps(gold)))
    assert checked["passed"]
    assert get_problem("obp_online").content_hash == suite["problem_spec_hash"]
    assert gold["heuristics"]["best_fit"]


def test_obp_evolution_mini_is_frozen_and_non_degenerate():
    suite = load_profile_suite("eohs_v1", "obp_evolution_mini", split="dev_train")
    _benchmark, metric, _item = benchmark_profile("eohs_v1", "obp_evolution_mini")
    assert metric.reference_kind == "known_optimum"
    gold = calibrate_upstream(suite)
    checked = calibrate_differential(
        suite,
        json.loads(Path("benchmarks/eohs_v1/expected/obp_evolution_mini_upstream_gold.json").read_text(encoding="utf-8")),
    )
    assert checked["passed"]
    first = gold["heuristics"]["first_fit"]
    best = gold["heuristics"]["best_fit"]
    assert any(left["bins_used"] != right["bins_used"] for left, right in zip(first, best))


def test_production_calibration_exposes_heuristic_set_and_rejects_unregistered_suite(tmp_path):
    suite = load_profile_suite("eohs_v1", "obp_mini", split="dev_train")
    from agent_skill_loop.benchmark.harness import calibrate_production, load_suite

    production = calibrate_production(suite)
    assert production["heuristic_set"]["member_ids"] == ["first_fit", "best_fit"]
    assert len(production["heuristic_set"]["per_instance"]) == len(suite["instances"])
    assert production["heuristic_set"]["aggregate_fitness"] is not None

    raw_path = tmp_path / "train.json"
    raw_path.write_bytes(Path("benchmarks/eohs_v1/manifests/obp_mini_train.json").read_bytes())
    assert load_suite(raw_path)["data_manifest_hash"]
    with pytest.raises(ValueError, match="data_manifest_hash_not_registered"):
        raw_path.write_text(raw_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        load_suite(raw_path)


def test_registered_suite_container_rejects_relabelled_instance_content(tmp_path):
    from agent_skill_loop.benchmark.harness import load_suite

    source = Path("benchmarks/eohs_v1/manifests/obp_mini_train.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    _benchmark, _metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    payload["data_manifest_hash"] = _benchmark.train_manifest_hash
    payload["instances"][0]["reference_objective"] = 999
    path = tmp_path / "forged-suite.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="data_manifest_content_mismatch"):
        load_suite(path)


def test_candidate_set_keeps_member_matrix_and_uses_per_instance_minimum():
    suite = load_profile_suite("eohs_v1", "obp_mini", split="dev_train")
    _benchmark, metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    result = evaluate_candidate_set(
        {
            "first_fit": "def priority(item, bins):\n    return -np.arange(len(bins), dtype=float)\n",
            "best_fit": "def priority(item, bins):\n    return -bins\n",
        },
        suite,
        metric_spec=metric,
    )
    assert result["complete_instance_coverage"] is True
    assert len(result["member_results"]) == 2
    assert len(result["per_instance"]) == len(suite["instances"])
    assert result["aggregate_fitness"] == pytest.approx(
        sum(item["best_gap"] for item in result["per_instance"]) / len(result["per_instance"])
    )


def test_candidate_set_retains_partial_member_successes_per_instance():
    suite = load_profile_suite("eohs_v1", "obp_mini", split="dev_train")
    _benchmark, metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    candidate_a = """def priority(item, bins):
    if item == 70:
        return 1 / (item - 70)
    return -bins
"""
    candidate_b = """def priority(item, bins):
    if item == 51:
        return 1 / (item - 51)
    return -bins
"""
    result = evaluate_candidate_set({"a": candidate_a, "b": candidate_b}, suite, metric_spec=metric)
    assert result["complete_instance_coverage"] is True
    assert result["aggregate_fitness"] == pytest.approx(0.0)
    assert result["per_instance"][0]["member_gaps"] == [0.0, None]
    assert result["per_instance"][1]["member_gaps"] == [None, 0.0]
    assert all(item["valid"] is False for item in result["member_results"])
    assert result["instance_evaluation_attempts"] == 8


def test_locked_selection_uses_the_same_partial_instance_matrix(monkeypatch):
    """Selection evaluation must not erase a member's partial successes."""
    from agent_skill_loop.benchmark import harness

    suite = load_profile_suite("eohs_v1", "obp_mini", split="heldout")
    _benchmark, metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    code_a = "def priority(item, bins):\n    return -bins\n"
    code_b = "def priority(item, bins):\n    return bins\n"
    selection = FrozenSelection(
        selection_kind="archive_topk",
        members=(
            {"candidate_id": "a", "code": code_a, "code_sha256": sha256_text(code_a)},
            {"candidate_id": "b", "code": code_b, "code_sha256": sha256_text(code_b)},
        ),
        training_metric_spec_hash=metric.content_hash,
    )

    def fake_evaluate(code, _suite, **_kwargs):
        rows = []
        for index, _instance in enumerate(suite["instances"]):
            valid = (code == code_a and index % 2 == 0) or (code == code_b and index % 2 == 1)
            rows.append({
                "instance_index": index,
                "attempted": True,
                "valid": valid,
                "objective": 0.0 if valid else None,
                "error_code": None if valid else "candidate_exception",
                "error_detail": None if valid else "fixture failure",
                "metrics": {},
            })
        return {
            "valid": False,
            "objective": None,
            "metrics": {"partial_instance_results": rows},
            "evaluation_identity": "fixture",
        }

    monkeypatch.setattr(harness, "evaluate_candidate", fake_evaluate)
    result = evaluate_selection(selection, suite, metric_spec=metric)
    assert result["complete_instance_coverage"] is True
    assert result["aggregate_fitness"] == pytest.approx(0.0)
    assert result["test_instance_evaluation_attempts"] == 2 * len(suite["instances"])
    assert result["per_instance"][0]["member_gaps"][0] == 0.0
    assert result["per_instance"][0]["member_gaps"][1] is None
    assert result["per_instance"][1]["member_gaps"][0] is None
    assert result["per_instance"][1]["member_gaps"][1] == 0.0


def test_archive_preserves_discovery_and_later_score_references():
    code = "def priority(item, bins):\n    return -bins\n"
    identity = {
        "problem_spec_hash": "a" * 64,
        "data_manifest_hash": "b" * 64,
        "evaluator_hash": "c" * 64,
        "metric_spec_hash": "d" * 64,
        "origin": "generated",
        "candidate_id": "candidate-1",
        "code": code,
        "code_sha256": sha256_text(code),
    }
    archive = build_archive(
        [
            {**identity, "evaluation_id": "eval-first", "discovery_ref": "rounds/1#candidate/0",
             "score_evaluation_ref": "evaluation:eval-first", "evaluation": {"valid": True, "objective": 2.0}},
            {**identity, "evaluation_id": "eval-later", "discovery_ref": "rounds/2#candidate/0",
             "score_evaluation_ref": "evaluation:eval-later", "evaluation": {"valid": True, "objective": 1.0}},
        ],
        problem_spec_hash="a" * 64,
        data_manifest_hash="b" * 64,
        evaluator_hash="c" * 64,
        metric_spec_hash="d" * 64,
    )
    assert archive[0].discovery_ref == "rounds/1#candidate/0"
    assert archive[0].score_evaluation_ref == "evaluation:eval-later"
    assert "source_ref" not in archive[0].as_dict()


def test_experiment_manifest_hash_is_stable_and_changes_with_guidance():
    kwargs = {
        "benchmark_spec_hash": "a" * 64,
        "metric_spec_hash": "b" * 64,
        "eoh_commit": "eoh-commit",
        "runtime_hash": "c" * 64,
        "skill_hash": "d" * 64,
        "model": "fixture",
        "endpoint_identity": "offline",
        "inheritance_mode": "population_seeds",
        "feedback_mode": "runtime_facts",
        "agent_guidance": True,
        "repair_mode": "off",
        "memory_enabled": False,
        "evaluation_budget": 100,
        "population_size": 4,
        "rounds": 4,
        "round_budget": 25,
        "search_seed": 1234,
    }
    manifest = ExperimentManifest(**kwargs)
    assert manifest.content_hash == ExperimentManifest(**kwargs).content_hash
    assert manifest.content_hash != ExperimentManifest(**{**kwargs, "agent_guidance": False}).content_hash


def test_controlled_pilot_keeps_c_and_d_identical_except_guidance():
    base = {
        "benchmark_spec_hash": "a" * 64,
        "metric_spec_hash": "b" * 64,
        "eoh_commit": "eoh-commit",
        "runtime_hash": "c" * 64,
        "skill_hash": "d" * 64,
        "model": "fixture",
        "endpoint_identity": "offline",
        "inheritance_mode": "population_seeds",
        "feedback_mode": "runtime_facts",
        "agent_guidance": True,
        "repair_mode": "off",
        "memory_enabled": False,
        "evaluation_budget": 100,
        "population_size": 4,
        "rounds": 4,
        "round_budget": 25,
        "search_seed": 1234,
    }
    pilot = build_pilot_manifests(base)
    assert set(pilot["groups"]) == {"A", "B", "C", "D"}
    c = pilot["groups"]["C"]["manifest"]
    d = pilot["groups"]["D"]["manifest"]
    assert c["agent_guidance"] is False
    assert d["agent_guidance"] is True
    differing_identity = {"agent_guidance", "experiment_manifest_sha256"}
    assert {key: value for key, value in c.items() if key not in differing_identity} == {
        key: value for key, value in d.items() if key not in differing_identity
    }
    assert pilot["groups"]["A"]["manifest"]["rounds"] == 1
    assert pilot["groups"]["A"]["manifest"]["round_budget"] == 100
    assert all(
        group["manifest"]["evaluation_budget"] == 100
        for group in pilot["groups"].values()
    )
    for group in pilot["groups"].values():
        policy = group["manifest"]["extra"]["search_policy_defaults"]
        assert policy["max_sample_nums"] == 100


def test_benchmark_session_freezes_problem_metric_and_population_identity(tmp_path):
    root = tmp_path / "benchmark-session"
    receipt = initialize_session(
        output=root,
        operation_id="init-benchmark",
        eoh_model="fixture",
        benchmark_id="eohs_v1",
        benchmark_profile_name="obp_mini",
        inheritance_mode="population_seeds",
        max_solver_calls=100,
    )
    state = read_state(run=root)
    assert receipt["run_state"] == "RUNNING"
    benchmark = state["result"]["benchmark"]
    assert benchmark["id"] == "eohs_v1"
    assert benchmark["profile"] == "obp_mini"
    assert len(benchmark["problem_spec_hash"]) == 64
    assert len(benchmark["metric_spec_hash"]) == 64
    assert benchmark["inheritance_mode"] == "population_seeds"
    assert state["result"]["budgets"]["total_evaluation_attempts"] == 0


def test_pilot_manifest_search_policy_is_loaded_without_cli_overrides(tmp_path):
    source = tmp_path / "source"
    initialize_session(output=source, operation_id="init", eoh_model="fixture",
                       benchmark_id="eohs_v1", max_rounds=2, round_budget=20, max_solver_calls=40)
    config = json.loads((source / "config_frozen.json").read_text(encoding="utf-8"))
    manifest = build_pilot_manifests(config["experiment_manifest"]["document"])["groups"]["C"]["manifest"]
    target = tmp_path / "pilot"
    initialize_session(output=target, operation_id="init", eoh_model="fixture",
                       benchmark_id="eohs_v1", experiment_manifest=manifest)
    frozen = json.loads((target / "config_frozen.json").read_text(encoding="utf-8"))
    assert frozen["eoh"]["search_policy_defaults"] == manifest["extra"]["search_policy_defaults"]
    assert frozen["eoh"]["search_policy_limits"] == manifest["extra"]["search_policy_limits"]


def test_archive_command_projects_hash_verified_session_facts(tmp_path):
    from agent_skill_loop.benchmark.archive import build_archive_from_session
    from agent_skill_loop.session_runtime import _connect, _sha256

    root = tmp_path / "archive-session"
    initialize_session(
        output=root,
        operation_id="init-archive",
        eoh_model="fixture",
        benchmark_id="eohs_v1",
        benchmark_profile_name="obp_mini",
        max_solver_calls=100,
    )
    state = read_state(run=root)
    benchmark = state["result"]["benchmark"]
    code = "def priority(item, bins):\n    return -bins\n"
    suite = json.loads((root / "dev_suite.json").read_text(encoding="utf-8"))
    candidate = {
        "candidate_id": "candidate_1",
        "revision": "original",
        "origin": "generated",
        "code": code,
        "code_sha256": sha256_text(code),
        "evaluation_id": "evaluation-archive",
        "valid": True,
        "objective": 0.0,
    }
    # The evaluator identity is a run-frozen field, not a runtime label from
    # the report.  Read it directly from SQLite for the synthetic evidence.
    con = _connect(root / "session.sqlite3")
    try:
        run = con.execute("SELECT * FROM runs LIMIT 1").fetchone()
        facts = {
            "round_id": 1,
            "problem": run["problem"],
            "suite_hash": run["suite_hash"],
            "evaluator_hash": run["evaluator_hash"],
            "benchmark": {
                "benchmark_id": run["benchmark_id"],
                "profile": run["benchmark_profile"],
                "problem_spec_hash": run["problem_spec_hash"],
                "benchmark_spec_hash": run["benchmark_spec_hash"],
                "data_manifest_hash": run["data_manifest_hash"],
                "reference_manifest_hash": run["reference_manifest_hash"],
                "metric_spec_hash": run["metric_spec_hash"],
            },
            "candidates": [candidate],
        }
        facts_text = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        facts_ref = root / "rounds/round_0001/evaluation_facts.json"
        facts_ref.parent.mkdir(parents=True, exist_ok=True)
        facts_ref.write_text(facts_text, encoding="utf-8")
        con.execute(
            "UPDATE rounds SET evaluation_facts_ref=?,evaluation_facts_sha256=? WHERE round_id=1",
            ("rounds/round_0001/evaluation_facts.json", _sha256(facts_text)),
        )
    finally:
        con.close()
    archive = build_archive_from_session(root)
    assert archive["entry_count"] == 1
    entry = archive["entries"][0]
    assert entry["discovery_ref"] == "rounds/round_0001/evaluation_facts.json#candidates/0"
    assert entry["score_evaluation_ref"] == "evaluation:evaluation-archive"
    assert archive["source_facts"][0]["candidate_count"] == 1


def test_registered_benchmark_json_assets_keep_registry_byte_hashes():
    registry = json.loads(Path("benchmarks/eohs_v1/registry.json").read_text(encoding="utf-8"))
    item = registry["benchmarks"][0]
    paths = item["manifest_paths"]
    expected = item["manifests"]
    for asset, path_key, hash_key in (
        ("dev_train", "dev_train", "train_hash"),
        ("heldout", "heldout", "test_hash"),
        ("reference", "reference", "reference_hash"),
    ):
        path = Path("benchmarks/eohs_v1") / paths[path_key]
        raw = path.read_bytes()
        assert b"\r\n" not in raw, asset
        assert hashlib.sha256(raw).hexdigest() == expected[hash_key], asset


def test_explicit_seed_session_freezes_and_exposes_seed_identity(tmp_path):
    code = "def priority(item, bins):\n    return -bins\n"
    root = tmp_path / "explicit-seeds"
    receipt = initialize_session(
        output=root,
        operation_id="init-explicit",
        eoh_model="fixture",
        benchmark_id="eohs_v1",
        benchmark_profile_name="obp_mini",
        inheritance_mode="explicit_seeds",
        explicit_seed_set=[
            {"algorithm": f"seed-{index}", "code": code + f"\n# {index}"}
            for index in range(4)
        ],
        max_solver_calls=100,
    )
    state = read_state(run=root)
    assert receipt["run_state"] == "RUNNING"
    assert state["result"]["benchmark"]["inheritance_mode"] == "explicit_seeds"
    seed_ref = root / "seeds/explicit_seeds.json"
    assert seed_ref.is_file()
    payload = json.loads(seed_ref.read_text(encoding="utf-8"))
    assert payload["metric_spec_hash"] == state["result"]["benchmark"]["metric_spec_hash"]
    assert state["integrity"]["runtime_identity"] == "ok"
    from agent_skill_loop.benchmark.harness import load_suite
    assert load_suite(root / "dev_suite.json")["data_manifest_hash"] == payload["data_manifest_hash"]


def test_population_seed_session_first_round_is_an_intentional_cold_start(tmp_path, monkeypatch):
    from agent_skill_loop import session_actions as actions

    root = tmp_path / "population-seeds"
    initialize_session(
        output=root,
        operation_id="init-population",
        eoh_model="fixture",
        benchmark_id="eohs_v1",
        benchmark_profile_name="obp_mini",
        inheritance_mode="population_seeds",
        max_rounds=2,
        round_budget=5,
        max_solver_calls=100,
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({
        "round_id": 1,
        "direction": "preserve the baseline interface",
        "operations": [{"type": "preserve", "target": "interface", "mechanism": "preserve"}],
        "preserve": "benchmark evaluator and interface",
        "feedback_basis": None,
        "memory_basis": [],
        "reference_skill_ref": None,
        "hypothesis": "unproven",
    }), encoding="utf-8")
    actions.submit_plan(run=root, operation_id="plan-population", expected_state_version=1, file=plan_path)
    monkeypatch.setattr(actions.subprocess, "Popen", lambda *args, **kwargs: None)
    receipt = actions.execute(run=root, operation_id="execute-population", expected_state_version=2)
    assert receipt["result"]["seed_selection"] is None
    assert receipt["result"]["inheritance"] == "population_seeds"


def test_report_rejects_matrix_that_disagrees_with_member_facts(tmp_path):
    from agent_skill_loop.benchmark.harness import load_profile_suite
    from agent_skill_loop.benchmark.report import build_report

    benchmark, metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    evaluator_hash = evaluator_source_hash()
    problem_hash = get_problem("obp_online").content_hash
    code = "def priority(item, bins):\n    return -bins\n"
    archive = build_archive([{
        "code": code,
        "code_sha256": sha256_text(code),
        "problem_spec_hash": problem_hash,
        "data_manifest_hash": benchmark.train_manifest_hash,
        "evaluator_hash": evaluator_hash,
        "metric_spec_hash": metric.content_hash,
        "origin": "generated",
        "candidate_id": "candidate-report",
        "evaluation_id": "evaluation-report",
        "evaluation": {"valid": True, "objective": 0.0},
    }], problem_spec_hash=problem_hash, data_manifest_hash=benchmark.train_manifest_hash,
        evaluator_hash=evaluator_hash, metric_spec_hash=metric.content_hash)
    selection = freeze_selection("incumbent_top1", archive, metric_spec_hash=metric.content_hash)
    test_suite = load_profile_suite("eohs_v1", "obp_mini", split="heldout")
    test_result = evaluate_selection(selection, test_suite, metric_spec=metric)
    manifest = ExperimentManifest(
        benchmark_spec_hash=benchmark.content_hash,
        metric_spec_hash=metric.content_hash,
        eoh_commit="eoh",
        runtime_hash="c" * 64,
        skill_hash="d" * 64,
        model="fixture",
        endpoint_identity="offline",
        inheritance_mode="incumbent_only",
        feedback_mode="off",
        agent_guidance=False,
        repair_mode="off",
        memory_enabled=False,
        evaluation_budget=10,
        population_size=1,
        rounds=1,
        round_budget=10,
        search_seed=1,
    )
    metrics = {
        "best_training_fitness": 0.0,
        "metric_spec_hash": metric.content_hash,
        "experiment_manifest_sha256": manifest.content_hash,
        "selection_sha256": selection.content_hash,
    }
    budget = {
        "total_evaluation_attempts": 1,
        "novel_candidate_evaluations": 1,
        "seed_reevaluation_attempts": 0,
        "baseline_attempts": 0,
        "repair_attempts": 0,
        "experiment_manifest_sha256": manifest.content_hash,
        "selection_sha256": selection.content_hash,
    }
    assert build_report(manifest=manifest, selection=selection, metrics=metrics, budget=budget, test_result=test_result)
    forged = json.loads(json.dumps(test_result))
    forged["per_instance"][0]["member_gaps"][0] = 123.0
    with pytest.raises(ValueError, match="test_member_matrix_mismatch"):
        build_report(manifest=manifest, selection=selection, metrics=metrics, budget=budget, test_result=forged)


def test_selection_requires_registered_heldout_suite():
    from agent_skill_loop.benchmark.harness import evaluate_selection

    benchmark, metric, _item = benchmark_profile("eohs_v1", "obp_mini")
    code = "def priority(item, bins):\n    return -bins\n"
    selection = FrozenSelection(
        selection_kind="incumbent_top1",
        members=({"code": code, "code_sha256": sha256_text(code)},),
        training_metric_spec_hash=metric.content_hash,
    )
    train_suite = load_profile_suite("eohs_v1", "obp_mini", split="dev_train")
    with pytest.raises(ValueError, match="test_requires_heldout_suite"):
        evaluate_selection(selection, train_suite, metric_spec=metric)
