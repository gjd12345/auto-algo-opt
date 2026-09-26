from __future__ import annotations

import json
import math

import numpy as np
import pytest

from agent_skill_loop.evaluator import _validate_candidate_ast, evaluate_candidate_request, evaluator_source_hash
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.problems.six_mirror_newton import (
    BASELINE_CODE,
    DIMENSION,
    SEED_2_CODE,
    build_suite,
    run_diagonal_newton,
    suite_hash,
)
from agent_skill_loop.problems.six_mirror_physics import WHEEL_SHA256
from agent_skill_loop.session_runtime import (
    SessionError,
    _normalize_explicit_seed_set,
    _sha256,
    initialize_session,
)


def _load_baseline():
    namespace = {"np": np, "math": math}
    exec(BASELINE_CODE, namespace)
    return namespace["select_diagonal_newton_step"]


def _as_rows(points: np.ndarray) -> np.ndarray:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    return array


def _flat_oracle(points: np.ndarray) -> np.ndarray:
    # Zero curvature and a nonzero gradient. A constant oracle stops earlier
    # at gradient_tolerance, before the descent check.
    return np.sum(_as_rows(points), axis=1)


def _quadratic_oracle(points: np.ndarray) -> np.ndarray:
    array = _as_rows(points)
    return np.sum(array * array, axis=1)


def test_flat_oracle_reports_no_descent_and_keeps_objective():
    x0 = np.ones(DIMENSION, dtype=np.float64)
    objective, final_x, metrics = run_diagonal_newton(_load_baseline(), x0, _flat_oracle)
    initial = float(_flat_oracle(x0)[0])
    assert metrics["solver_status"] == "no_descent_direction"
    assert objective == initial
    assert metrics["final_rms_waves"] == initial
    assert metrics["initial_rms_waves"] == initial
    assert metrics["accepted_steps"] == 0
    assert np.array_equal(final_x, x0)


def test_bad_return_shape_is_invalid_return():
    x0 = np.ones(DIMENSION, dtype=np.float64)

    def bad_shape(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
        del phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value
        return np.zeros(3, dtype=np.float64)

    def boolean_choice(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
        del phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value
        return True

    def out_of_range(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
        del scale, hessian, current_value, slope, trial_alpha, trial_value
        if int(phase) == 0:
            return -np.asarray(gradient, dtype=np.float64)
        return np.asarray([99], dtype=np.int64)

    with pytest.raises(ValueError, match="invalid_return"):
        run_diagonal_newton(bad_shape, x0, _flat_oracle)
    with pytest.raises(ValueError, match="invalid_return"):
        run_diagonal_newton(boolean_choice, x0, _flat_oracle)
    with pytest.raises(ValueError, match="invalid_return"):
        run_diagonal_newton(out_of_range, x0, _quadratic_oracle)


def test_mutated_input_is_rejected():
    x0 = np.ones(DIMENSION, dtype=np.float64)

    def mutate(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
        del phase, scale, hessian, current_value, slope, trial_alpha, trial_value
        gradient[0] = 5.0
        return np.zeros_like(gradient, dtype=np.float64)

    with pytest.raises(ValueError, match="candidate_mutated_input"):
        run_diagonal_newton(mutate, x0, _flat_oracle)


def test_physical_step_is_scale_times_direction():
    baseline = _load_baseline()
    x0 = np.full(DIMENSION, 2.0)

    def length_one(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
        if int(phase) == 0:
            return baseline(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value)
        return np.asarray([0], dtype=np.int64)

    for entry in (baseline, length_one):
        objective, final_x, metrics = run_diagonal_newton(entry, x0, _quadratic_oracle)
        assert metrics["accepted_alphas"][0] == 1.0
        assert objective < metrics["initial_rms_waves"]
        assert float(np.max(np.abs(final_x))) < 1e-3


def test_in_range_index_must_pass_evaluator_armijo():
    x0 = np.ones(DIMENSION, dtype=np.float64)

    def insufficient(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
        del scale, hessian, current_value, slope, trial_alpha, trial_value
        if int(phase) == 0:
            return -np.asarray(gradient, dtype=np.float64)
        return np.asarray([0], dtype=np.int64)

    objective, final_x, metrics = run_diagonal_newton(insufficient, x0, _quadratic_oracle)
    assert metrics["solver_status"] == "line_search_failed"
    assert metrics["accepted_steps"] == 0
    assert objective == metrics["initial_rms_waves"]
    assert np.array_equal(final_x, x0)


def test_phase1_negative_one_does_not_move_parameters():
    x0 = np.ones(DIMENSION, dtype=np.float64)

    def hold(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):
        del scale, hessian, current_value, slope, trial_alpha, trial_value
        if int(phase) == 0:
            return -np.asarray(gradient, dtype=np.float64)
        return np.asarray([-1], dtype=np.int64)

    objective, final_x, metrics = run_diagonal_newton(hold, x0, _quadratic_oracle)
    assert metrics["solver_status"] == "line_search_failed"
    assert metrics["accepted_steps"] == 0
    assert metrics["accepted_alphas"] == []
    assert objective == metrics["initial_rms_waves"]
    assert np.array_equal(final_x, x0)


def test_sandbox_rejects_torch_and_open():
    spec = get_problem("six_mirror_newton")
    suite = build_suite(1)
    torch_code = "import torch\n" + BASELINE_CODE
    open_code = (
        "def select_diagonal_newton_step(phase, scale, gradient, hessian, current_value, slope, trial_alpha, trial_value):\n"
        "    open('prescription.mat')\n"
        "    return -1\n"
    )
    for code, error_code in ((torch_code, "forbidden_import"), (open_code, "forbidden_name")):
        result = evaluate_candidate_request({"problem": "six_mirror_newton", "suite": suite, "code": code})
        assert result["valid"] is False
        assert result["error_code"] == error_code
        assert result["objective"] is None
    _validate_candidate_ast(BASELINE_CODE, spec)


def test_suite_is_frozen_and_ignores_seed():
    spec = get_problem("six_mirror_newton")
    other = get_problem("tsp_2opt")
    assert spec.problem_id == "six_mirror_newton"
    assert spec.entrypoint == "select_diagonal_newton_step"
    assert spec.interface_version == "v1"
    assert spec.objective_direction == "minimize"
    assert spec.split_offsets == {"dev_train": 0x5EED0032}
    assert spec.baseline_code == BASELINE_CODE
    assert spec.allowed_import_roots == other.allowed_import_roots
    assert spec.forbidden_names == other.forbidden_names
    assert spec.numpy_attributes == other.numpy_attributes
    assert spec.math_attributes == other.math_attributes
    assert spec.safe_builtins == other.safe_builtins
    first = build_suite(1)
    assert build_suite(99) == first
    assert first["instances"][0]["prescription_version"] == "v2"
    assert first["instances"][0]["field_indices"] == [32]
    assert first["instances"][0]["sample_d"] == 9
    assert first["instances"][0]["max_iterations"] == 2
    assert first["instances"][0]["initial_scale"] == 1.0
    assert first["instances"][0]["physics_wheel_sha256"] == WHEEL_SHA256
    assert first["instances"][0]["physics_tree_sha256"] == ""
    assert "seed" not in first["instances"][0]
    reloaded = json.loads(json.dumps(first))
    assert spec.validate_suite(reloaded)[1] == first["content_hash"]
    with pytest.raises(ValueError, match="invalid_count"):
        build_suite(1, count=2)
    with pytest.raises(ValueError, match="invalid_count"):
        build_suite(1, count=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="invalid_size"):
        build_suite(1, size=20)
    with pytest.raises(ValueError, match="invalid_split"):
        build_suite(1, split="heldout")
    with pytest.raises(ValueError, match="invalid_seed"):
        build_suite(True)  # type: ignore[arg-type]

    def rejected(**updates: object) -> None:
        payload = json.loads(json.dumps(first))
        payload["instances"][0].update(updates)
        payload["content_hash"] = suite_hash(payload["problem"], payload["split"], payload["instances"])
        with pytest.raises(ValueError, match="invalid_suite"):
            spec.validate_suite(payload)

    rejected(prescription_version="v1")
    rejected(field_indices=[0])
    rejected(sample_d=64)
    rejected(max_iterations=1)
    rejected(initial_scale=1e-4)
    rejected(backend="torch")
    rejected(physics_wheel_sha256="0" * 64)
    rejected(physics_tree_sha256="f" * 64)


def _explicit_seed_identity() -> dict[str, str | None]:
    spec = get_problem("six_mirror_newton")
    suite = build_suite(1)
    return {
        "problem_spec_hash": spec.content_hash,
        "suite_hash": suite["content_hash"],
        "evaluator_hash": evaluator_source_hash(),
        "data_manifest_hash": None,
        "metric_spec_hash": None,
    }


def test_seed_2_hash_differs_and_normalizer_drops_objective():
    assert _sha256(SEED_2_CODE) != _sha256(BASELINE_CODE)
    assert SEED_2_CODE[SEED_2_CODE.index("    c1 = 0.1"):] == BASELINE_CODE[BASELINE_CODE.index("    c1 = 0.1"):]
    namespace = {"np": np, "math": math}
    exec(SEED_2_CODE, namespace)
    gradient = np.arange(DIMENSION, dtype=np.float64)
    direction = namespace["select_diagonal_newton_step"](
        0, np.ones(DIMENSION), gradient, np.ones(DIMENSION), 1.0, 0.0, np.zeros(0), np.zeros(0)
    )
    assert np.array_equal(direction, -gradient)
    _validate_candidate_ast(SEED_2_CODE, get_problem("six_mirror_newton"))
    identity = _explicit_seed_identity()
    normalized = _normalize_explicit_seed_set(
        {
            **identity,
            "objective": 0.010906458907220248,
            "members": [{
                "algorithm": "curvature-disabled gradient",
                "code": SEED_2_CODE,
                "objective": 0.010906458907220248,
                "evaluation_id": "caller-supplied",
            }],
        },
        problem_spec_hash=identity["problem_spec_hash"],
        suite_hash=identity["suite_hash"],
        evaluator_hash=identity["evaluator_hash"],
        data_manifest_hash=identity["data_manifest_hash"],
        metric_spec_hash=identity["metric_spec_hash"],
    )
    assert "objective" not in json.dumps(normalized)
    assert "evaluation_id" not in json.dumps(normalized)
    member = normalized["members"][0]
    assert set(member) == {"algorithm", "algorithm_text_sha256", "code", "code_sha256"}
    assert member["code"] == SEED_2_CODE
    assert member["code_sha256"] == _sha256(SEED_2_CODE)


def test_explicit_seed_population_of_two_passes_initialize_session_size_check(tmp_path):
    identity = _explicit_seed_identity()
    policy = {"pop_size": 2, "n_pop": 2, "max_sample_nums": 8}
    members = [
        {"algorithm": "diagonal Newton baseline", "code": BASELINE_CODE, "objective": 0.021483322678436757},
        {"algorithm": "curvature-disabled gradient", "code": SEED_2_CODE, "objective": 0.010906458907220248},
    ]
    with pytest.raises(SessionError, match="explicit seed set is smaller than target population"):
        initialize_session(
            output=tmp_path / "short",
            operation_id="init-short",
            problem="six_mirror_newton",
            eoh_model="fixture",
            count=1,
            size=62,
            memory_enabled=False,
            inheritance_mode="explicit_seeds",
            explicit_seed_set={"members": members[:1], **identity},
            search_policy_defaults=policy,
        )
    receipt = initialize_session(
        output=tmp_path / "two",
        operation_id="init-two",
        problem="six_mirror_newton",
        eoh_model="fixture",
        count=1,
        size=62,
        memory_enabled=False,
        inheritance_mode="explicit_seeds",
        explicit_seed_set={"members": members, **identity, "objective": 0.010906458907220248},
        search_policy_defaults=policy,
    )
    assert receipt["run_state"] == "RUNNING"
    assert receipt["result"]["provider_requests"] == 0
    assert receipt["result"]["solver_calls"] == 0
    payload = json.loads((tmp_path / "two" / "seeds" / "explicit_seeds.json").read_text(encoding="utf-8"))
    assert len(payload["members"]) == 2
    assert [item["code"] for item in payload["members"]] == [BASELINE_CODE, SEED_2_CODE]
    assert "objective" not in json.dumps(payload)
    config = json.loads((tmp_path / "two" / "config_frozen.json").read_text(encoding="utf-8"))
    assert config["eoh"]["search_policy_defaults"]["pop_size"] == 2
