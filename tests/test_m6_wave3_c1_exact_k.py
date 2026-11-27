from __future__ import annotations

import json
import math
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from agent_skill_loop.interface_design import InterfaceValidator, build_interface_design, parse_hook_candidate
from agent_skill_loop.interface_design import fleet_exact_k as c1
from agent_skill_loop.interface_design import runtime
from agent_skill_loop.interface_design.fleet_exact_k_probes import _gate3_instances
from agent_skill_loop.interface_design.templates import get_template_spec


def _matrix(points):
    coordinates = np.asarray([(0, 0), *points], dtype=np.float64)
    return np.linalg.norm(coordinates[:, None] - coordinates[None, :], axis=2)


def _line_matrix(xs):
    return _matrix([(x, 0) for x in xs])


def _weights(demands):
    return np.asarray([0, *demands], dtype=np.float64)


def _route_cost(routes, dmat):
    return sum(dmat[a, b] for route in routes for a, b in zip([0, *route], [*route, 0]))


def _assert_partition(routes, demands, capacity, target):
    assert len(routes) == target
    assert all(routes)
    assert sorted(node for route in routes for node in route) == list(range(1, len(demands)))
    assert all(sum(demands[node] for node in route) <= capacity for route in routes)


def _baseline_hooks():
    template = get_template_spec(*c1.FLEET_EXACT_K_TEMPLATE_KEY)
    return runtime.compile_hook_bundle(template.hook_specs, template.baseline_implementations())


def test_parallel_merge_source_hashes_unchanged():
    expected = {
        "v1": "3bca783d3de8eaf5ec4fe559c71f92ccd98afc89d1e69adeb56a85a2d18e53ac",
        "v2": "7e6d9b3294d9703f38e9a5ad3b095c391bebf46e71518fb84697b148e3130ffa",
    }
    for version, source_hash in expected.items():
        assert get_template_spec("cvrp_parallel_merge_static", version).template_source_sha256 == source_hash


@pytest.mark.parametrize(("raw_demands", "capacity", "target", "packing"), [
    ([6, 6, 4, 4], 10, 2, "ffd"),
    ([30, 29, 29, 24, 24, 20, 15, 14, 14, 11, 8, 5, 4, 3, 3, 2], 30, 8, "bfd"),
])
def test_packing_witness(raw_demands, capacity, target, packing):
    demands = _weights(raw_demands)
    customers = list(range(1, len(demands)))
    ffd = c1._pack_first_fit(customers, demands, capacity, math.inf)
    bfd = c1._pack_best_fit(customers, demands, capacity, math.inf)
    _assert_partition(ffd, demands, capacity, target + (packing == "bfd"))
    _assert_partition(bfd, demands, capacity, target)
    routes, meta = c1.run_cvrp_fleet_aware_exact_k_v1(
        _line_matrix(customers), demands, capacity, _baseline_hooks(), target_k=target,
    )
    _assert_partition([route[1:-1] for route in routes], demands, capacity, target)
    assert meta["fleet_diagnostics"]["ffd_witness"] is True
    assert meta["fleet_diagnostics"]["witness_packing"] == packing


def test_witness_geometry_preserves_capacity_and_clustered_routes():
    demands = _weights([4, 6, 6, 4, 5, 5])
    cw = [[1, 2], [3], [4], [5, 6]]
    compact, remainder = c1._preserve_geometric_routes(
        cw, [[1, 3], [2, 4], [5, 6]], demands, 10, 3, math.inf,
    )
    assert compact == [[1, 2], [5, 6]]
    _assert_partition(compact + remainder, demands, 10, 3)

    dmat = _line_matrix([1, 2, 20, 21])
    mixed = [[2, 4], [3, 1]]
    clustered = c1._cluster_packing(mixed, dmat, demands, math.inf)
    assert clustered == [[2, 1], [3, 4]]
    assert _route_cost(clustered, dmat) < _route_cost(mixed, dmat)


def test_tier1_joins_capacity_feasible_negative_savings_pair():
    dmat = np.asarray([[0, 4, 3], [4, 0, 8], [3, 8, 0]], dtype=np.float64)
    demands = _weights([3, 4])
    incumbent = [[1], [2]]
    merged = c1._merge_routes(incumbent, dmat, demands, 7, 1, math.inf)
    _assert_partition(merged, demands, 7, 1)
    assert _route_cost(merged, dmat) == _route_cost(incumbent, dmat) + 1
    assert incumbent == [[1], [2]]


def _tier2_fixture():
    routes = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]
    demands = _weights([5, 3] * 4 + [4, 4])
    return routes, demands, _line_matrix(range(1, 11))


def test_tier2_donor_with_two_capacity_freeing_swaps():
    routes, demands, dmat = _tier2_fixture()
    repaired = c1._dissolve_donor(routes, 4, dmat, demands, 10, math.inf)
    assert repaired is not None
    _assert_partition(repaired, demands, 10, 4)
    assert sorted(sorted(demands[node] for node in route) for route in repaired) == [
        [3, 3, 4], [3, 3, 4], [5, 5], [5, 5],
    ]
    assert routes[-1] == [9, 10]


def test_tier2_interrupted_transaction_discards_partial_donor(monkeypatch):
    routes, demands, dmat = _tier2_fixture()
    incumbent = deepcopy(routes)
    clock = SimpleNamespace(now=0.0)
    clock.perf_counter = lambda: clock.now
    monkeypatch.setattr(c1, "time", clock)
    free_capacity = c1._free_capacity
    loads_at_swaps = []

    def expire_on_second_swap(workspace, loads, *args):
        loads_at_swaps.append(sorted(loads))
        if len(loads_at_swaps) == 2:
            clock.now = 1.0
        return free_capacity(workspace, loads, *args)

    monkeypatch.setattr(c1, "_free_capacity", expire_on_second_swap)
    assert c1._dissolve_donor(routes, 4, dmat, demands, 10, 1.0) is None
    assert loads_at_swaps == [[8, 8, 8, 8], [8, 8, 10, 10]]
    assert routes == incumbent


def test_tier3_repack_resolves_tight_2_for_1_exchange_deadlock():
    demands = _weights([5, 2, 2] * 10)
    routes = [list(range(offset, offset + 3)) for offset in range(1, 31, 3)]
    incumbent = deepcopy(routes)
    dmat = _line_matrix(range(1, 31))
    repaired = c1._repack_routes(routes, dmat, demands, 10, 9, math.inf)
    _assert_partition(repaired, demands, 10, 9)
    assert routes == incumbent


def test_tier4_chooses_global_cheapest_order_preserving_cuts():
    dmat = _line_matrix([5, 6, -5, -3, 8, 2])
    routes = [[1, 2, 3, 4], [5, 6]]
    split = c1._cheapest_split(routes, dmat, 4)
    assert split == [[1, 2], [3, 4], [5], [6]]
    assert _route_cost(split, dmat) - _route_cost(routes, dmat) == 4.0


@pytest.mark.parametrize(("points", "raw_demands", "capacity", "routes", "expected_group"), [
    ([(1, 0), (0, 1), (1, 1), (-4, -4)], [1, 1, 1, 3], 3, [[1, 2, 3], [4]], {1, 2, 3}),
    ([(10, 0), (-10, 0), (11, 0), (-11, 0), (0, 4)], [1, 1, 1, 1, 2], 2, [[1, 2], [3, 4], [5]], {1, 3}),
    ([(10, 0), (11, 0), (-10, 0), (-11, 0), (-11.1, 0)], [2, 2, 1, 2, 3], 5, [[1, 2, 3], [4], [5]], {1, 2}),
])
def test_exact_polish_improves_with_2opt_swap_and_nonemptying_relocate(
    points, raw_demands, capacity, routes, expected_group,
):
    demands, dmat = _weights(raw_demands), _matrix(points)
    incumbent = deepcopy(routes)
    polished = c1._polish_exact(routes, dmat, demands, capacity, math.inf)
    _assert_partition(polished, demands, capacity, len(routes))
    assert expected_group in [set(route) for route in polished]
    assert _route_cost(polished, dmat) < _route_cost(incumbent, dmat)
    assert routes == incumbent


def test_exact_polish_preserves_singleton_when_emptying_it_is_profitable():
    demands, dmat = _weights([1, 1, 1]), _line_matrix([10, 11, 10.1])
    routes = [[1, 2], [3]]
    assert _route_cost([[1, 3, 2]], dmat) < _route_cost(routes, dmat)
    polished = c1._polish_exact(routes, dmat, demands, 10, math.inf)
    _assert_partition(polished, demands, 10, 2)


def test_repair_toggle_preserves_identical_pre_repair_control():
    demands, dmat = _weights([6, 4, 5, 5]), _line_matrix([1, 2, 3, 4])
    hooks = _baseline_hooks()

    def static(_matrix, _demands, _capacity, i_idx, j_idx):
        return ((i_idx == 2) & (j_idx == 3)).astype(np.float64)

    hooks["score_merge_static"] = static
    controls = []
    for repair_enabled, target in [(False, 3), (True, 2)]:
        routes, meta = c1.run_cvrp_fleet_aware_exact_k_v1(
            dmat, demands, 10, hooks, target_k=2,
            template_options={"fleet_repair_enabled": repair_enabled}, capture_merge_sequence=True,
        )
        _assert_partition([route[1:-1] for route in routes], demands, 10, target)
        diag = meta["fleet_diagnostics"]
        assert diag["pre_repair_route_count"] == 3
        assert diag["pre_repair_exact_k"] is False
        assert diag["ffd_witness"] is repair_enabled
        controls.append((diag["pre_repair_cost"], meta["merge_sequence"]))
    assert controls[0] == controls[1]


@pytest.mark.parametrize("target", [None, 0, 1, 5, 1.5, True, "bad"])
def test_missing_or_infeasible_target_returns_valid_free_fleet(target):
    demand = _weights([4, 4, 4, 4])
    routes, meta = c1.run_cvrp_fleet_aware_exact_k_v1(
        _line_matrix([1, 2, 3, 4]), demand, 8, tuple(_baseline_hooks().values()), target_k=target,
    )
    _assert_partition([route[1:-1] for route in routes], demand, 8, 2)
    assert meta["fleet_diagnostics"]["exact_source"] is None
    assert meta["fleet_diagnostics"]["ffd_witness"] is False


@pytest.mark.parametrize("timed", [False, True])
def test_runtime_max_vehicles_matches_k_vehicles(timed):
    template_id, template_version = c1.FLEET_EXACT_K_TEMPLATE_KEY
    instance = _gate3_instances(build_interface_design(template_id, template_version))[1]
    instance.pop("k_vehicles")
    hooks = _baseline_hooks()
    routes = []
    for target in ({"k_vehicles": 2}, {"max_vehicles": 2}, {"k_vehicles": None, "max_vehicles": 2}):
        record = runtime.evaluate_hook_on_instance_inprocess(
            template_id=template_id, template_version=template_version, hook_fn=hooks,
            instance={**instance, **target}, vehicle_limit_policy="strict_max_vehicles",
            capture_timed_incumbents=timed,
        )
        assert record["valid"] is True
        assert record["route_count"] == 2
        assert record["fleet_diagnostics"]["target_k_status"] == "eligible"
        if timed:
            assert record["feasible_before_deadline_exact_k"] is True
        routes.append(record["routes"])
    assert routes[0] == routes[1] == routes[2]


@pytest.mark.parametrize("target", [0, False, True, 1.5, "bad"])
def test_runtime_invalid_vehicle_target_respects_policy(target):
    template_id, template_version = c1.FLEET_EXACT_K_TEMPLATE_KEY
    instance = _gate3_instances(build_interface_design(template_id, template_version))[0]
    instance.update(k_vehicles=target, max_vehicles="bad fallback")
    hooks = _baseline_hooks()
    strict = runtime.evaluate_hook_on_instance_inprocess(
        template_id=template_id, template_version=template_version, hook_fn=hooks,
        instance=instance, vehicle_limit_policy="strict_max_vehicles", capture_timed_incumbents=True,
    )
    assert strict["valid"] is False
    assert strict["status"] == "infeasible"
    assert strict["error_code"] == "invalid_vehicle_target"
    assert strict["error_detail"] == f"Invalid vehicle target for strict_max_vehicles: {target!r}"
    assert strict["feasible_before_deadline"] is False

    free = runtime.evaluate_hook_on_instance_inprocess(
        template_id=template_id, template_version=template_version, hook_fn=hooks,
        instance=instance, vehicle_limit_policy="free_fleet_min_k_lb", capture_timed_incumbents=True,
    )
    assert free["valid"] is True
    assert free["route_count"] == 1
    assert free["target_vehicles"] is None
    assert free["feasible_before_deadline"] is True


def test_interrupted_construction_returns_before_physical_deadline(monkeypatch):
    template = get_template_spec(*c1.FLEET_EXACT_K_TEMPLATE_KEY)
    fixture = _gate3_instances(build_interface_design(*c1.FLEET_EXACT_K_TEMPLATE_KEY))[1]
    clock = SimpleNamespace(now=0.0)
    clock.perf_counter = lambda: clock.now
    monkeypatch.setattr(c1, "time", clock)
    monkeypatch.setattr(runtime, "time", clock)
    hooks = _baseline_hooks()
    static = hooks[template.hook_name]

    def score(*args):
        clock.now = 0.493
        return static(*args)

    hooks[template.hook_name] = score
    record = runtime.evaluate_hook_on_instance_inprocess(
        template_id=template.template_id, template_version=template.template_version, hook_fn=hooks,
        instance=fixture, postprocess_mode="none", template_options={"fleet_repair_enabled": False},
        time_budget_ms=500.0, capture_merge_sequence=True, capture_timed_incumbents=True,
    )
    assert record["valid"] is True
    assert record["merge_sequence"] == []
    assert record["route_count"] == fixture["size"]
    assert record["budget_exhausted"] is False
    assert record["returned_before_deadline"] is True
    assert record["solve_ms"] == 493.0


@pytest.mark.parametrize("deadline", [500, 2000])
def test_default_subprocess_gates_accept_zero_adjustment_and_show_causality(deadline):
    design = build_interface_design(*c1.FLEET_EXACT_K_TEMPLATE_KEY, postprocess_mode="relocate_2opt")
    report = InterfaceValidator(solve_deadline_ms=deadline).validate(design)
    assert report.passed, [failure.as_dict() for failure in report.failures]
    assert [gate["gate_id"] for gate in report.gates if gate["passed"]] == [1, 2, 3, 4, 5]
    gate4 = report.diagnostics["gate4"]
    assert gate4["static"] == gate4["adjustment"] == {"prefer_A": [1, 2], "prefer_B": [2, 3]}
    assert gate4["fleet_feasibility"] == {
        "c1_missing_target": None, "c1_tight_target": True,
        "c1_under_fleet_witness": True, "c1_unpackable_target": False,
    }
    assert gate4["interrupted_repair_rolled_back"] is True
    assert report.diagnostics["gate5"]["scale_factor"] == pytest.approx(1e-3)
    assert len(report.diagnostics["gate5"]["stress_instance_ids"]) == 6


def test_gate4_rejects_submitted_constant_adjustment():
    design = build_interface_design(*c1.FLEET_EXACT_K_TEMPLATE_KEY)
    implementations = parse_hook_candidate(*c1.FLEET_EXACT_K_TEMPLATE_KEY, c1.FLEET_EXACT_K_MOCK_CANDIDATES[0])
    name = "score_fleet_adjustment"
    implementations[name] = c1.BASELINE_ADJUSTMENT_CODE.replace("return np.zeros_like", "return 1.0 + np.zeros_like")
    report = InterfaceValidator().validate(design, hook_implementations=implementations)
    assert not report.passed
    assert [(failure.gate_id, failure.symbol) for failure in report.failures] == [(4, name)]


def test_c1_mux_has_three_resumable_single_cell_panes(tmp_path):
    from tools.run_m6_wave3_c1_exact_k import run_c1_mux

    manifest = run_c1_mux(out_dir=tmp_path)
    live = tmp_path / "c1_live"
    assert json.loads((live / "mux_m6_c1.json").read_text(encoding="utf-8")) == manifest
    assert manifest["model"] == "DeepSeek-V4.1-Flash"
    assert manifest["request_cap"] == 36
    assert manifest["max_rounds"] == 12
    assert [manifest["template_id"], manifest["template_version"]] == list(c1.FLEET_EXACT_K_TEMPLATE_KEY)
    assert len(manifest["panes"]) == 3
    for pane, seed in zip(manifest["panes"], (20261124, 20261125, 20261126), strict=True):
        command = pane["command"]
        assert str(seed) in command
        assert "c1_cell" in command
        assert "--resume" in command
        receipt = manifest["common_starts"][str(seed)]
        common = json.loads((live / receipt["name"]).read_text(encoding="utf-8"))
        assert common["seed"] == seed
        assert common["dev_suite_hash"] == receipt["dev_suite_hash"]
        assert common["baseline_dev_eval"]["instance_count"] == 24
        assert common["baseline_dev_eval"]["exact_k_count"] > 0


def test_c1_mock_runs_research_agent_and_extracts_clean_champion(tmp_path):
    from tools.run_m6_wave3_c1_exact_k import run_c1_mock

    report = run_c1_mock(out_dir=tmp_path)
    assert report["passed"] is True
    assert report["no_private_leakage"] is True
    assert len(report["champion_bundle_sha256"]) == 64
    assert report["best_solver_manifest_ref"].endswith(".json")
    assert not list(tmp_path.rglob("*.md"))
