"""Offline checks for the Experiment 2 timing and holdout boundary."""

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from agent_skill_loop.cvrp_workbench import baselines_2026 as adapters
from tools import run_external_baselines_2026 as runner
from tools import s2_multiscale_calibration as calibration


@pytest.mark.parametrize(
    "record_exact_incumbent, finished_at, feasible, returned",
    [(True, 0.130, True, False), (False, 0.130, False, False), (True, 0.060, True, True)],
)
def test_pyvrp_dual_deadlines(monkeypatch, record_exact_incumbent, finished_at, feasible, returned):
    instance = {
        "instance_id": "tiny",
        "depot": [0.0, 0.0],
        "customer_coordinates": [[1.0, 0.0], [0.0, 1.0]],
        "demands": [1, 1],
        "capacity": 2,
        "k_vehicles": 2,
    }
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(adapters, "time", SimpleNamespace(perf_counter=lambda: clock.now))
    pyvrp, stop_module = ModuleType("pyvrp"), ModuleType("pyvrp.stop")
    pyvrp.IteratedLocalSearchCallbacks = object
    pyvrp.IteratedLocalSearchParams = pyvrp.SolveParams = SimpleNamespace
    for name in ("Client", "Depot", "Location", "ProblemData", "VehicleType"):
        setattr(pyvrp, name, lambda *args, **kwargs: None)
    stop_module.MaxRuntime = lambda _: lambda __: False

    def solution(groups):
        routes = [[SimpleNamespace(idx=i, is_client=lambda: True) for i in group] for group in groups]
        return SimpleNamespace(routes=lambda: routes, is_feasible=lambda: True)

    exact = solution([[0], [1]])
    too_few = solution([[0, 1]])

    def solve(data, stop, *, params, **kwargs):
        callbacks = params.ils.callbacks
        callbacks.on_start(SimpleNamespace(initial_solution=too_few))
        clock.now = 0.040
        if record_exact_incumbent:
            callbacks.on_best(exact)
        clock.now = 0.050
        callbacks.on_best(too_few)
        clock.now = finished_at
        callbacks.on_best(exact if clock.now > 0.1 else too_few)
        return SimpleNamespace(best=too_few, num_iterations=1)

    pyvrp.solve = solve
    monkeypatch.setitem(sys.modules, "pyvrp", pyvrp)
    monkeypatch.setitem(sys.modules, "pyvrp.stop", stop_module)

    result = adapters.solve_pyvrp(instance, budget_ms=100, vehicle_limit_policy="strict_max_vehicles")
    assert result["feasible_before_deadline"] is feasible
    assert result["returned_before_deadline"] is returned
    assert result["incumbent_ms"] == (40.0 if feasible else None)
    assert result["deadline_overrun_ms"] == pytest.approx(max(finished_at * 1000 - 100, 0))
    assert result["total_e2e_ms"] == pytest.approx(sum(result[field] for field in (
        "preprocess_ms", "solve_ms", "verify_ms",
    )))


def test_p95_retains_censored_timeouts_with_missing_duration():
    rows = [{"solve_ms": 2.0, "returned_before_deadline": True}] * 18
    rows += [{"status": "timeout", "solve_ms": None, "budget_ms": 100.0}] * 2
    summary = adapters.summarize_solve_timing(rows)
    assert summary["solve_ms_p50"] == 2.0
    assert summary["solve_ms_p50_is_lower_bound"] is False
    assert summary["solve_ms_p95"] == 100.0
    assert summary["solve_ms_p95_is_lower_bound"] is True
    assert summary["solve_ms_censored_count"] == 2
    assert summary["solve_ms_observation_count"] == 20


def test_track3_legacy_recompute_recovers_wall_limited_pyvrp():
    row = {
        "algorithm_id": "PyVRP", "instance_id": "tiny", "feasible": True,
        "preprocess_ms": 2, "solve_ms": 102, "verify_ms": 3,
        "time_limit_reached": True, "budget_exhausted": False,
    }

    def lane():
        return {"rows": [dict(row)], "overall": {"PyVRP": {}}, "common_completed": {"PyVRP": {}},
                "common_completed_instance_ids": ["tiny"]}

    report = {"schema_version": "cvrp-external-baselines-2026/v1", "budget_ms": 100,
              "suites": {"fixture": {name: lane() for name in runner.FLEET_POLICIES}}}
    section = runner.recompute_dual_timing(report)["suites"]["fixture"]["exact-k"]
    updated = section["rows"][0]
    assert updated["feasible_before_deadline"] is True
    assert updated["returned_before_deadline"] is False
    assert updated["deadline_overrun_ms"] == 2.0
    assert updated["total_e2e_ms"] == 107.0
    assert section["common_completed"]["PyVRP"]["solve_ms_p95_is_lower_bound"] is True


@pytest.mark.parametrize("size", [100, 200, 400, 500])
def test_synthetic_stress_probes_are_deterministic(size):
    probe = calibration.generate_stress_probe(size)
    assert probe == calibration.generate_stress_probe(size)
    assert len(probe["customer_coordinates"]) == len(probe["demands"]) == size
    assert probe != calibration.generate_stress_probe(size, replicate=1)


@pytest.mark.parametrize("lock_exists", [False, True])
def test_validate_setx_requires_verified_lock_before_opening_holdout(tmp_path, monkeypatch, lock_exists):
    lock = tmp_path / "multiscale_threshold_lock.json"
    if lock_exists:
        lock.write_text(json.dumps({"set_x_untouched": True, "lock_sha256": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(calibration, "_load_setx", lambda: pytest.fail("Set X opened before lock verification"))
    with pytest.raises(SystemExit) as failure:
        calibration.main(["validate-setx", "--lock-file", str(lock)])
    assert failure.value.code == 2


def test_threshold_lock_roundtrip_refuses_overwrite_and_rejects_edit(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    artifacts = runs / "example" / "agent_artifacts"
    artifacts.mkdir(parents=True)
    spec = runner.get_template_spec("cvrp_parallel_merge_static", "v1")
    code = spec.default_baseline_hook_code
    manifest = runner.FrozenInterfaceSolver(
        solver_id="fixture", display_name="Fixture", problem_family=spec.problem_family,
        paradigm=spec.paradigm, template_id=spec.template_id, template_version=spec.template_version,
        template_source_sha256=spec.template_source_sha256, postprocess_mode="none", template_options={},
        hook_name=spec.hook_name, hook_code=code, hook_code_sha256=runner.sha256_text(code),
        design_sha256="fixture", origin_run="example", kb_release_id="fixture",
    )
    (artifacts / "round_0001_frozen_solver.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    (artifacts / "setx_results.json").write_text("fail if read", encoding="utf-8")
    monkeypatch.setattr(calibration, "RUNS", runs)
    monkeypatch.setattr(calibration, "_load_setx", lambda: pytest.fail("Set X opened during calibration"))

    def evaluate(_, instance, **kwargs):
        return adapters.dual_timing_fields(
            {"solve_ms": instance["size"] / 10}, budget_ms=kwargs["budget_ms"], feasible=True,
        )

    monkeypatch.setattr(calibration, "_evaluate", evaluate)
    lock_path = tmp_path / "multiscale_threshold_lock.json"
    lock = calibration.calibrate_lock(lock_path, replicates=1)
    assert lock["set_x_untouched"] is True
    assert calibration.read_threshold_lock(lock_path) == lock
    original = lock_path.read_bytes()
    with pytest.raises(FileExistsError):
        calibration.calibrate_lock(lock_path, replicates=1)
    assert lock_path.read_bytes() == original
    lock["policy"]["max_ratio_200_100"] += 1.0
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="lock_sha256_mismatch"):
        calibration.validate_setx(lock_path)
