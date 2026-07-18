from __future__ import annotations

import importlib.util
import importlib
import json
import hashlib
from pathlib import Path
import sys

import numpy as np
import pytest

from eoh_rag.experiments.batch_runner import _validate_manifest
from eoh_rag.experiments.eoh_single_runner import _api_context, _runner_script
from eoh_rag.experiments.research_contracts import DecisionRecord, EvaluationResult


ROOT = Path(__file__).resolve().parents[1]
PROBLEM_PATH = (
    ROOT
    / "official_eoh/examples/cvrp_expert_router/cvrp_expert_router_problem.py"
)
MANIFEST_PATH = (
    ROOT / "eoh_rag_workspace/experiments/manifests/cvrp_expert_router_proxy_v1.json"
)


def _load_problem_module():
    spec = importlib.util.spec_from_file_location("_test_cvrp_expert_router_prob", PROBLEM_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def router_problem():
    module = _load_problem_module()
    return module.CVRPEXPERTROUTER(timeout=30, n_processes=1)


def test_minimum_research_contracts_are_serializable() -> None:
    evaluation = EvaluationResult(
        candidate_id="candidate",
        suite="development",
        objective=0.0,
        feasible=True,
        runtime_seconds=0.1,
        failure_type=None,
        instance_results_hash="instances",
    )
    decision = DecisionRecord(
        decision_id="decision",
        actor="research_agent",
        observed_scope="dev_only",
        action="select_expert_portfolio",
        reason="development only",
        input_hashes=("input",),
        output_hashes=("output",),
    )

    assert evaluation.to_eoh_payload()["objective"] == 0.0
    assert decision.to_dict()["actor"] == "research_agent"
    json.dumps({"evaluation": evaluation.to_dict(), "decision": decision.to_dict()})


def test_router_features_match_frozen_order_and_are_finite() -> None:
    module = _load_problem_module()
    instance = {
        "coords": np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 2.0]]),
        "demands": np.array([0, 2, 4]),
        "capacity": 5,
    }

    features = module.compute_instance_features(instance)
    contract = json.loads(
        (PROBLEM_PATH.parent / "router_contract_v1.json").read_text(encoding="utf-8")
    )

    assert list(features) == contract["feature_order"]
    assert all(np.isfinite(value) for value in features.values())
    assert features["n_customers"] == 2.0
    assert features["capacity_fill_ratio"] == 0.6


def test_n2_seed_is_valid_zero_reference_with_dev_only_records(router_problem) -> None:
    seed = json.loads(
        (PROBLEM_PATH.parent / "seeds/router_seeds_v1.json").read_text(encoding="utf-8")
    )[0]["code"]

    result = router_problem.evaluate(seed)

    assert result is not None
    assert abs(result["objective"]) < 1e-12
    feedback = result["feedback"]
    assert feedback["expert_selection_counts"] == {
        "n1": 0,
        "n2": 90,
        "density_structure": 0,
        "multi_environment_variance": 0,
    }
    assert feedback["decision_record"]["actor"] == "research_agent"
    assert feedback["decision_record"]["observed_scope"] == "dev_only"
    assert feedback["evaluation_result"]["suite"] == "development"

    router_problem.report_confirmation = True
    try:
        confirmation = router_problem.evaluate(seed)
    finally:
        router_problem.report_confirmation = False
    assert confirmation is not None
    assert abs(confirmation["objective"]) < 1e-12
    assert router_problem.confirmation_report["suite"] == "confirmation"
    assert router_problem.confirmation_report["mean_improvement_vs_n2_pct"] == 0.0


def test_router_rejects_unknown_id_input_mutation_and_imports(router_problem) -> None:
    assert router_problem.evaluate(
        "def select_expert(instance_features, expert_summaries):\n    return 'unknown'"
    ) is None
    assert router_problem.evaluate(
        "def select_expert(instance_features, expert_summaries):\n"
        "    instance_features.clear()\n"
        "    return 'n2'"
    ) is None
    assert router_problem.evaluate(
        "import os\n"
        "def select_expert(instance_features, expert_summaries):\n"
        "    return 'n2'"
    ) is None


def test_router_manifest_and_runner_contract_are_connected() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    contract_path = ROOT / manifest["router_contract"]
    seed_path = ROOT / manifest["arms"][0]["seed_codes"]

    assert _validate_manifest(manifest) == []
    assert manifest["selection_contract"]["actor"] == "research_agent"
    assert json.loads(contract_path.read_text(encoding="utf-8"))["scientific_actor"] == "research_agent"
    assert hashlib.sha256(contract_path.read_bytes()).hexdigest().upper() == manifest["router_contract_sha256"]
    assert hashlib.sha256(seed_path.read_bytes()).hexdigest().upper() == manifest["seed_codes_sha256"]
    assert "cvrp_expert_router" in _runner_script()
    assert "persist_best_confirmation_report" in _runner_script()
    assert "select_expert" in _api_context("cvrp_expert_router")

    manifest["router_contract_sha256"] = "0" * 64
    assert "router_contract SHA-256 mismatch" in _validate_manifest(manifest)


def test_router_problem_survives_real_spawn_evaluation() -> None:
    example_dir = str(PROBLEM_PATH.parent)
    if example_dir not in sys.path:
        sys.path.insert(0, example_dir)
    module = importlib.import_module("cvrp_expert_router_problem")
    problem = module.CVRPEXPERTROUTER(timeout=90, n_processes=1)
    seed = json.loads(
        (PROBLEM_PATH.parent / "seeds/router_seeds_v1.json").read_text(encoding="utf-8")
    )[0]["code"]
    from eoh.eoh.evolution import _eval_with_timeout

    result = _eval_with_timeout(problem, seed, timeout=90)

    assert result is not None
    assert abs(result["objective"]) < 1e-12
