"""M3.1 stratification and M3.1/M3.2 blind custody regression tests."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median

import pytest

from agent_skill_loop.cvrp_workbench import m31_suites as m31
from agent_skill_loop.cvrp_workbench.suites import load_m31_suite, load_milestone_suite_metadata
from agent_skill_loop.interface_design import blind_commitment as legacy_commitment
from agent_skill_loop.interface_design import blind_eval_m32 as blind
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.templates import get_template_spec


def test_m31_achieved_cells_and_disjoint_splits():
    all_splits = []
    for family in ("tsp", "obp", "bpp"):
        for split, repeats in (("dev", 2), ("select", 2), ("blind", 4)):
            suite_id = m31.m31_suite_id(family, split)
            if split == "blind":
                rows = m31.build_m31_suite(family, split, seed_token="private-test-token")
                design = load_milestone_suite_metadata(suite_id)
                assert design["commitment_status"] == "pending_external_seal"
                assert design["stratification_spec"]["by_cell"] == Counter(row["cell"] for row in rows)
            else:
                role = "selection_tuning" if split == "select" else "interactive_sandbox"
                rows = load_m31_suite(suite_id, role=role)["instances"]
            counts = Counter(row["cell"] for row in rows)
            assert len(counts) == 18 and set(counts.values()) == {repeats}
            assert len({row["size"] for row in rows}) == 3
            assert len({row["distribution"] for row in rows}) == 3
            for row in rows:
                assert row["protocol_id"] == m31.M31_PROTOCOL_IDS[family]
                if family == "tsp":
                    boundary = m31.convex_hull_boundary_count(row["coordinates"])
                    assert boundary / row["size"] == {"low": 0.1, "high": 0.3}[row["stratum"]]
                else:
                    assert max(row["items"]) <= row["capacity"]
                    assert row["capacity"] / median(row["items"]) == {"low": 4, "high": 8}[row["stratum"]]
            all_splits.append(rows)
    m31.assert_m31_splits_disjoint(*all_splits)
    assert m31.M31_PROTOCOL_IDS["obp"] != m31.M31_PROTOCOL_IDS["bpp"]
    with pytest.raises(ValueError, match="overlap"):
        m31.assert_m31_splits_disjoint(all_splits[0], all_splits[0])


def test_hull_counts_unique_collinear_boundary_points():
    points = [(0, 0), (0, 1), (0, 2), (2, 2), (2, 1), (2, 0), (1, 0), (1, 2), (1, 1), (0, 1)]
    assert m31.convex_hull_boundary_count(points) == 8
    assert m31.convex_hull_boundary_count([(0, 0), (1, 1), (2, 2), (0, 0)]) == 3


def test_legacy_m3_generator_source_matches_published_commitment():
    commitment = legacy_commitment.read_public_blind_commitment(legacy_commitment.M3_BLIND_COMMITMENT_PATH)
    assert legacy_commitment._generator_source_sha256() == commitment["generator_source_sha256"]


@pytest.mark.parametrize("role", ("selection", "selection_tuning"))
def test_selection_role_isolation(role):
    for suite_id in m31.M31_SELECTION_SUITE_IDS:
        with pytest.raises(ValueError, match="selection_suite_forbidden"):
            load_m31_suite(suite_id, role="feedback_archive")
        assert len(load_m31_suite(suite_id, role=role)["instances"]) == 36
    with pytest.raises(ValueError, match="selection_suite_forbidden"):
        blind.assert_milestone_suite_allowed_for_interactive_role("custom_suite", {"suite_role": role})
    for suite_id in blind.MILESTONE_BLIND_SUITE_IDS:
        with pytest.raises(ValueError, match="blind_suite_forbidden"):
            load_m31_suite(suite_id, role=role)


def _assert_public_output_is_safe(path: Path, seed: str) -> None:
    text = path.read_text(encoding="utf-8")
    for sensitive in ('"coordinates"', '"customer_coordinates"', '"demands"', '"items"', '"routes"',
                      '"sealed_seed_token"', '"error_detail"', seed):
        assert sensitive not in text


@pytest.mark.parametrize("family", ("tsp", "obp", "bpp"))
def test_m31_external_seal_verify_and_one_shot(tmp_path, family):
    repo_root, custody = tmp_path / "repo", tmp_path / "external"
    commitment_path = repo_root / "commitment.json"
    seed = "m31-fixture-private-seed"
    suite_id = m31.m31_suite_id(family, "blind")
    with pytest.raises(ValueError, match="outside_repository"):
        blind.seal_m31_blind_suite(
            family, commitment_path=commitment_path, custody_dir=repo_root / "custody",
            seed_token=seed, repo_root=repo_root,
        )
    sealed = blind.seal_m31_blind_suite(
        family, commitment_path=commitment_path, custody_dir=custody, seed_token=seed, repo_root=repo_root,
    )
    commitment = blind.read_public_milestone_blind_commitment(
        commitment_path, expected_sha256=sealed["commitment_sha256"], expected_suite_id=suite_id,
    )
    assert len(commitment["instances"]) == 72
    assert blind.verify_milestone_sealed_against_commitment(
        sealed_path=Path(sealed["sealed_path"]), commitment_path=commitment_path, repo_root=repo_root,
    )["verified_instances"] == 72
    _assert_public_output_is_safe(commitment_path, seed)

    def evaluate(instance):
        assert instance["protocol_id"] == m31.M31_PROTOCOL_IDS[family]
        assert list(custody.glob("*.attempt"))
        fallback = "tour_length" if family == "tsp" else "bins_used"
        return {"objective": None, fallback: instance["reference_objective"], "valid": True, "completed": True,
                "solve_ms": 0, "items": instance.get("items"), "coordinates": instance.get("coordinates")}

    kwargs = dict(commitment_path=commitment_path, expected_commitment_sha256=sealed["commitment_sha256"],
                  evaluator=evaluate, custody_dir=custody, repo_root=repo_root)
    report = blind.unseal_and_evaluate_m31(suite_id, output_dir=repo_root / "out1", **kwargs)
    assert len(report["records"]) == 72 and report["records"][0]["solve_ms"] == 0
    assert all(row["objective"] == row["reference_objective"] for row in report["records"])
    _assert_public_output_is_safe(Path(report["report_path"]), seed)
    with pytest.raises(FileExistsError, match="already_consumed"):
        blind.unseal_and_evaluate_m31(suite_id, output_dir=repo_root / "out2", **kwargs)


def _freeze_m32_fixture(tmp_path: Path) -> tuple[dict, str]:
    repo_root, custody = tmp_path / "repo", tmp_path / "external"
    commitment_path = repo_root / "commitment.json"
    protocol_path, lock_path = repo_root / "protocol.json", repo_root / "roster.json"
    seed = "m32-fixture-private-seed"
    sealed = blind.seal_m32_blind_120(
        commitment_path=commitment_path, custody_dir=custody, seed_token=seed, repo_root=repo_root,
    )
    assert blind.verify_milestone_sealed_against_commitment(
        sealed_path=Path(sealed["sealed_path"]), commitment_path=commitment_path, repo_root=repo_root,
    )["verified_instances"] == 120
    _assert_public_output_is_safe(commitment_path, seed)
    protocol = blind.freeze_pre_blind_protocol_m32(
        protocol_path, commitment_path=commitment_path, seeds=(17,),
        control_deadlines_ms={"model_routing": 500.0, "l3b_dual_hook": 450.0},
        cell_deadlines_ms={"17:control:l3b_dual_hook": 500.0},
    )
    plan = protocol["protocol"]
    assert plan["request_cap"] == 400 and plan["checkpoints"] == [36, 100, 200, 400]
    assert plan["one_shot_attempt"]["key"] == sealed["commitment_sha256"]
    assert plan["controls"] == ["model_routing", "l3b_dual_hook", "timeout_2000ms"]
    execution = plan["solver_rules"]["cell_execution"]
    assert execution["17:control:model_routing"] == {"solve_deadline_ms": 500.0, "outer_timeout_s": 5.0}
    assert execution["17:control:l3b_dual_hook"] == execution["17:control:model_routing"]
    assert execution["17:control:timeout_2000ms"] == {"solve_deadline_ms": 2000.0, "outer_timeout_s": 5.5}
    template = get_template_spec("cvrp_sequential_construct", "v1")
    code = template.default_baseline_hook_code
    solver = FrozenInterfaceSolver(
        "fixture", "Fixture", "cvrp", template.paradigm, template.template_id, template.template_version,
        template.template_source_sha256, "none", {}, template.hook_name, code, sha256_text(code),
        "fixture-design", "fixture-run", "fixture-release",
    )
    snapshot = repo_root / "snapshot.json"
    snapshot.write_text(json.dumps(solver.to_dict()), encoding="utf-8")
    snapshots = {
        cell: snapshot
        for cell in ("17:checkpoint:36", *(f"17:control:{name}" for name in plan["controls"]))
    }
    missing = {cell: "early_stop" for cell in plan["roster_cells"] if cell not in snapshots}
    kwargs = dict(protocol_path=protocol_path, expected_protocol_sha256=protocol["protocol_sha256"],
                  snapshot_paths=snapshots)
    with pytest.raises(ValueError, match="cover_every_cell"):
        blind.freeze_m32_roster_lock(lock_path, missing_cells={}, **kwargs)
    lock = blind.freeze_m32_roster_lock(lock_path, missing_cells=missing, **kwargs)
    kwargs.update(roster_lock_path=lock_path, expected_roster_lock_sha256=lock["roster_lock_sha256"],
                  commitment_path=commitment_path, custody_dir=custody, repo_root=repo_root)
    return kwargs, seed


def test_m32_pins_snapshot_bytes_and_opens_before_evaluation(tmp_path, monkeypatch):
    kwargs, seed = _freeze_m32_fixture(tmp_path)
    snapshot = kwargs["snapshot_paths"]["17:checkpoint:36"]
    data = snapshot.read_bytes()
    snapshot.write_bytes(data + b"\n")
    with pytest.raises(ValueError, match="locked_snapshot_roster_mismatch"):
        blind.unseal_and_evaluate_m32(output_dir=tmp_path / "out", **kwargs)
    assert not list(kwargs["custody_dir"].glob("*.attempt"))
    snapshot.write_bytes(data)

    real_read_payload = blind.read_verified_milestone_blind_payload
    openings = []

    def read_payload(*args, **options):
        openings.append(options["sealed_path"])
        assert len(list(kwargs["custody_dir"].glob("*.attempt"))) == 1
        return real_read_payload(*args, **options)

    deadlines = []

    def evaluate(_solver, instance, **rules):
        deadlines.append((rules["solve_deadline_ms"], rules["outer_timeout_s"]))
        return {"objective": None, "tour_length": 0, "valid": True, "completed": True, "solve_ms": 0,
                "routes": [[1]], "demands": instance["demands"], "exact_vehicle_count": True}

    monkeypatch.setattr(blind, "read_verified_milestone_blind_payload", read_payload)
    monkeypatch.setattr(blind, "evaluate_frozen_interface_solver", evaluate)
    report = blind.unseal_and_evaluate_m32(output_dir=tmp_path / "out", **kwargs)
    assert len(report["records"]) == 480 and report["missing_cells"]["17:checkpoint:400"] == "early_stop"
    assert len(openings) == 1 and deadlines == [(500.0, 5.0)] * 360 + [(2000.0, 5.5)] * 120
    first = report["records"][0]
    assert first["objective"] == 0 and first["solve_ms"] == 0 and first["exact_k_feasible"] is True
    _assert_public_output_is_safe(Path(report["report_path"]), seed)
    with pytest.raises(FileExistsError, match="already_consumed"):
        blind.unseal_and_evaluate_m32(output_dir=tmp_path / "new-output", **kwargs)
    assert len(openings) == 1


def test_m32_failure_after_unseal_consumes_attempt(tmp_path, monkeypatch):
    kwargs, _ = _freeze_m32_fixture(tmp_path)

    def fail(_solver, instance, **_rules):
        assert instance["customer_coordinates"]
        raise ValueError("private solver error")

    monkeypatch.setattr(blind, "evaluate_frozen_interface_solver", fail)
    with pytest.raises(RuntimeError, match="evaluation_failed_attempt_consumed") as error:
        blind.unseal_and_evaluate_m32(output_dir=tmp_path / "first", **kwargs)
    assert "private solver error" not in str(error.value)
    assert not (tmp_path / "first" / "m32_blind_evaluation.json").exists()
    with pytest.raises(FileExistsError, match="already_consumed"):
        blind.unseal_and_evaluate_m32(output_dir=tmp_path / "second", **kwargs)
