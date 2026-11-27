"""Acceptance coverage for the external CVRP baselines without live or full runs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from agent_skill_loop.benchmark import load_profile_suite
from agent_skill_loop.cvrp_workbench import baselines_2026 as adapters
from agent_skill_loop.cvrp_workbench.protocol import verify_cvrp_solution
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from tools import run_external_baselines_2026 as runner
from tools.multi_task_mux import _load_manifest


DEV_ID = "cvrp_dev_hetero_24"
SELECT_ID = "cvrp_select_multiscale_64"
EXTERNAL_ID = "cvrp_ext_eohs_256"
SEED = 20261124


def _instance(instance_id: str, *, k: int = 2, shift: float = 0.0) -> dict:
    return {
        "instance_id": instance_id,
        "depot": [0.0, 0.0],
        "customer_coordinates": [[0.34 + shift, 1.0], [0.4, 1.2], [3.12, 0.7], [3.42, 0.93]],
        "demands": [2, 2, 2, 2],
        "capacity": 4,
        "k_vehicles": k,
        "reference_objective": 10.0,
        "reference_kind": "solver_reference",
        "size": 4,
    }


def _suite(profile: str, split: str) -> dict:
    return {**load_profile_suite(BENCHMARK_ID, profile, split=split), "suite_id": profile}


@pytest.mark.parametrize("vehicle_policy,target", [("strict_max_vehicles", 2), ("free_fleet_min_k_lb", 1)])
def test_pyvrp_returns_independently_verified_float_cost(vehicle_policy: str, target: int) -> None:
    instance = _instance("tiny", k=target)
    result = adapters.solve_pyvrp(instance, budget_ms=500, seed=SEED, vehicle_limit_policy=vehicle_policy)

    verified = verify_cvrp_solution(instance, result["routes"], vehicle_limit_policy=vehicle_policy)
    assert verified["valid"] and result["completed"] and result["feasible"]
    assert verified["route_count"] == 2
    assert result["exact_vehicle_count"] is (target == 2)
    assert result["tour_length"] == verified["tour_length"] == result["objective"]
    assert not result["tour_length"].is_integer()
    assert result["solve_ms"] >= 0

    if target == 1:
        blocked = adapters.solve_pyvrp(instance, budget_ms=500, seed=SEED, vehicle_limit_policy="strict_max_vehicles")
        assert not blocked["completed"] and not blocked["feasible"]
        assert blocked["objective"] is None


def test_features_are_scale_invariant_and_exclude_reference_fields() -> None:
    original = _instance("original")
    changed = {
        **original,
        "instance_id": "renamed",
        "customer_coordinates": [[1000 * x + 17, 1000 * y - 5] for x, y in original["customer_coordinates"]],
        "depot": [17, -5],
        "demands": [7 * value for value in original["demands"]],
        "capacity": 7 * original["capacity"],
        "reference_objective": 100000,
        "reference_kind": "different",
        "bks_routes": [[0, 1, 2, 0], [0, 3, 4, 0]],
    }

    baseline = adapters.extract_cvrp_instance_features(original)
    rescaled = adapters.extract_cvrp_instance_features(changed)
    assert baseline.keys() == rescaled.keys()
    assert np.all(np.isfinite(list(baseline.values())))
    np.testing.assert_allclose(list(rescaled.values()), list(baseline.values()), rtol=1e-9, atol=1e-9)


def test_selectors_fit_authorized_splits_and_predict_on_external_instances() -> None:
    dev = _suite(DEV_ID, "dev_train")
    selection = _suite(SELECT_ID, "selection")
    external = _suite(EXTERNAL_ID, "heldout")
    costs = {
        row["instance_id"]: {
            "nn": 1.0,
            "cw_2opt": 0.9 if index % 2 else 1.3,
            "cw_parallel_merge": 1.5,
        }
        for index, row in enumerate([*dev["instances"], *selection["instances"]])
    }
    solver_names = ("nn", "cw_2opt", "cw_parallel_merge")
    selectors = adapters.fit_selectors([dev, selection], costs, solver_names=solver_names, hydra_k=2, seed=SEED)

    assert selectors.sbs == "nn"
    assert selectors.hydra_portfolio == ("nn", "cw_2opt")
    assert set(selectors.metadata["training_instance_ids"]) == costs.keys()
    assert {(row["suite_id"], row["split"]) for row in selectors.metadata["training_suites"]} == {
        (DEV_ID, "dev_train"), (SELECT_ID, "selection"),
    }
    out_of_sample = external["instances"][:2]
    for row in out_of_sample:
        assert row["instance_id"] not in costs
        picks = selectors.predict(row)
        assert picks.keys() == {"SATzilla", "AutoFolio", "Hydra", "SBS"}
        assert all(name in solver_names for name in picks.values())
        assert picks["Hydra"] in selectors.hydra_portfolio
        assert picks["SBS"] == "nn"

    mislabeled = {**dev, "instances": out_of_sample}
    for rejected in ([dev, external], [mislabeled, selection], [dev, {**selection, "split": "blind"}]):
        rejected_costs = {
            row["instance_id"]: dict.fromkeys(solver_names, 1.0)
            for suite in rejected
            for row in suite["instances"]
        }
        with pytest.raises(ValueError):
            adapters.fit_selectors(rejected, rejected_costs, solver_names=solver_names, seed=SEED)


def test_mock_evolution_resumes_and_delivers_dual_reporting(tmp_path: Path) -> None:
    dev = _suite(DEV_ID, "dev_train")
    dev["instances"] = dev["instances"][:2]
    methods = {"reevo": "ReEvo", "eohs": "EoH-S"}
    solvers = {}
    for method, label in methods.items():
        checkpoint = tmp_path / method / "checkpoint.json"
        options = {
            "seed": SEED,
            "request_cap": 8,
            "budget_ms": 500,
            "checkpoint_path": checkpoint,
            "driver": runner.MockDriver(),
            "portfolio_size": 2,
        }
        state = runner.evolve(method, dev, **options)
        assert checkpoint.is_file() and 0 < state["requests_used"] <= options["request_cap"]
        assert state["status"] == "completed" and state["accepted_candidate_count"] > 0
        winners = [FrozenInterfaceSolver.from_dict(manifest) for manifest in state["winners"]]
        assert winners
        assert len({frozen.hook_code_sha256 for frozen in winners}) == len(winners)
        assert all(frozen.template_id in {"cvrp_parallel_merge_static", "cvrp_ruin_recreate"} for frozen in winners)
        if method == "reevo":
            assert len(winners) == 1
        else:
            assert len(winners) == options["portfolio_size"]

        resumed = runner.evolve(method, dev, **options)
        assert resumed["requests_used"] == state["requests_used"]
        assert resumed["winners"] == state["winners"]
        assert resumed["history"] == state["history"]
        solvers[label] = runner.frozen_set_solver(winners, portfolio_size=len(winners))

    def reference_solver(instance, *, budget_ms, seed, distance_convention, vehicle_limit_policy):
        if instance["instance_id"] == "external_b":
            return {"valid": False, "completed": False, "status": "timeout", "objective": None, "solve_ms": budget_ms}
        routes = [[0, 1, 2, 0], [0, 3, 4, 0]]
        verified = verify_cvrp_solution(
            instance, routes, distance_convention=distance_convention, vehicle_limit_policy=vehicle_limit_policy,
        )
        return {**verified, "routes": routes, "completed": True, "status": "ok", "solve_ms": 1.0}

    def unavailable(instance, **kwargs):
        return {"valid": False, "status": "timeout", "solve_ms": kwargs["budget_ms"]}

    external = {
        "suite_id": EXTERNAL_ID,
        "split": "heldout",
        "distance_convention": "euc_2d_float",
        "instances": [_instance("external_a"), _instance("external_b", k=3, shift=0.1)],
    }
    report = runner.evaluate_external(
        [external], {"SBS": reference_solver, **solvers, "Unavailable": unavailable},
        seed=SEED, budget_ms=500, bootstrap_samples=50,
    )
    assert report["schema_version"]
    lanes = report["suites"][EXTERNAL_ID]
    for fleet in ("exact-k", "free_fleet"):
        lane = lanes[fleet]
        assert lane["overall"].keys() == lane["common_completed"].keys() == {"SBS", *solvers, "Unavailable"}
        assert lane["common_completed_count"] == 0
        rows = {(row["algorithm_id"], row["instance_id"]): row for row in lane["rows"]}
        failure = rows["SBS", "external_b"]
        assert failure["scored_objective"] == 2 * external["instances"][1]["reference_objective"]
        assert not failure["completed"]
        for label in solvers:
            assert rows[label, "external_a"]["completed"]
            assert rows[label, "external_a"]["exact_vehicle_count"]
            scored = rows[label, "external_b"]["scored_objective"]
            if fleet == "exact-k":
                assert scored == 20.0
            else:
                assert scored == rows[label, "external_b"]["tour_length"]
                assert scored < 20.0
        for denominator, expected_count in (("overall", 2), ("common_completed", 1)):
            comparison = lane["comparisons"][denominator]["ReEvo_vs_SBS"]
            assert comparison["n_instances"] == comparison["wilcoxon_signed_rank"]["n_pairs"] == expected_count
            assert len(comparison["rel_gain_ci95_pct"]) == 2
            assert 0 <= comparison["p_holm_wilcoxon"] <= 1
    report_stem = tmp_path / "report"
    runner.write_report(report, report_stem)
    assert json.loads(report_stem.with_suffix(".json").read_text(encoding="utf-8")) == report
    assert "exact-k / common_completed" in report_stem.with_suffix(".md").read_text(encoding="utf-8")


def test_mux_manifest_is_accepted_by_repository_mux(tmp_path: Path) -> None:
    manifest = runner.build_mux_manifest(output_dir=tmp_path, mode="mock")
    path = tmp_path / "mux.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    panes = _load_manifest(path)

    assert len(panes) == len({pane["id"] for pane in panes}) == 6
    assert all("--request-cap" in pane["command"] for pane in panes)
    for seed in ("20261124", "20261125", "20261126"):
        assert sum(seed in pane["command"] for pane in panes) == 2

    benchmark = runner.build_mux_manifest(output_dir=tmp_path, mode="mock", stage="benchmark")
    path.write_text(json.dumps(benchmark), encoding="utf-8")
    panes = _load_manifest(path)
    for budget in ("500", "2000"):
        assert sum(budget in pane["command"] for pane in panes) == 3
    assert all("--with-evolution" in pane["command"] for pane in panes)


def test_paratera_driver_budget_and_prose_json_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARATERA_ENDPOINT", "https://example.invalid/v1/chat/completions")
    monkeypatch.setenv("PARATERA_API_KEY", "fixture-key")
    payloads: list[dict] = []

    def fake_post(url: str, headers: dict, body: bytes, timeout_s: float) -> tuple[int, bytes]:
        payload = json.loads(body.decode("utf-8"))
        payloads.append(payload)
        return 200, json.dumps({"choices": [{"message": {"content": '{"ok": "yes"}'}}]}).encode("utf-8")

    monkeypatch.setattr(runner, "http_post_with_deadline", fake_post)
    driver = runner.ParateraDriver("DeepSeek-V4.1-Flash", 120.0)
    assert driver.complete(phase="propose", prompt="p", template_id="cvrp_ruin_recreate", seed=1, request=1) == '{"ok": "yes"}'
    assert driver.complete(phase="reflect_short", prompt="p", template_id="cvrp_ruin_recreate", seed=1, request=2) == '{"ok": "yes"}'
    assert [p["max_tokens"] for p in payloads] == [16384, 4096]
    assert runner._reply_field('Here is the hook:\n{"hook_code": "return x"}\nThanks.', "hook_code", 100) == "return x"


def test_score_penalizes_uncensored_deadline_overrun_and_separates_censored_callback() -> None:
    inst = _instance("overrun_case", k=2)
    ref = inst["reference_objective"]

    # 1. Uncensored overrun (e.g., EoH-S / ReEvo ran 502ms with completed not forced false)
    uncens = runner._score(
        inst,
        {"valid": True, "tour_length": 12.0, "exact_vehicle_count": True, "status": "ok", "solve_ms": 502.0},
        policy="free_fleet_min_k_lb",
        budget_ms=500.0,
    )
    assert uncens["uncensored_deadline_overrun"] is True
    assert uncens["completed"] is False
    assert uncens["scored_objective"] == 2.0 * ref
    assert uncens["completed_feasible_before_deadline"] is False
    assert uncens["completed_returned_before_deadline"] is False

    # 2. Censored callback overrun (e.g., PyVRP cooperative check after valid incumbent before deadline)
    cens = runner._score(
        inst,
        {
            "valid": True,
            "tour_length": 11.0,
            "exact_vehicle_count": True,
            "status": "ok",
            "completed": True,
            "solve_censored": True,
            "feasible_before_deadline": True,
            "solve_ms": 503.0,
        },
        policy="free_fleet_min_k_lb",
        budget_ms=500.0,
    )
    assert cens["uncensored_deadline_overrun"] is False
    assert cens["completed"] is True
    assert cens["scored_objective"] == 11.0
    assert cens["completed_feasible_before_deadline"] is True
    assert cens["completed_returned_before_deadline"] is False

    # 3. Clean under-budget completion
    clean = runner._score(
        inst,
        {"valid": True, "tour_length": 11.5, "exact_vehicle_count": True, "status": "ok", "solve_ms": 250.0},
        policy="free_fleet_min_k_lb",
        budget_ms=500.0,
    )
    assert clean["uncensored_deadline_overrun"] is False
    assert clean["completed"] is True
    assert clean["completed_feasible_before_deadline"] is True
    assert clean["completed_returned_before_deadline"] is True

    summary = runner._summary([uncens, cens, clean])
    assert summary["completed_count"] == 2
    assert summary["feasible_before_deadline_completed_count"] == 2
    assert summary["returned_before_deadline_completed_count"] == 1
    assert summary["uncensored_overrun_penalized_count"] == 1
    assert summary["censored_callback_overrun_count"] == 1
