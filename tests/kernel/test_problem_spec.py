from __future__ import annotations

import pytest

from agent_skill_loop.problems.base import PROBLEM_REGISTRY, get_problem
from agent_skill_loop.problems.cvrp import (
    BASELINE_CODE,
    ENTRYPOINT,
    PROBLEM_NAME,
    SPLIT_OFFSETS,
    TASK_DESCRIPTION,
    TEMPLATE_PROGRAM,
    build_suite,
    suite_hash,
)


def test_cvrp_spec_exposes_identity_and_prompt_literals():
    spec = get_problem("cvrp_construct")
    assert spec.problem_id == PROBLEM_NAME == "cvrp_construct"
    assert spec.entrypoint == ENTRYPOINT == "select_next_node"
    assert spec.interface_version == "v1"
    assert spec.task_description == TASK_DESCRIPTION
    assert spec.template_program == TEMPLATE_PROGRAM
    assert spec.baseline_code == BASELINE_CODE
    assert spec.objective_direction == "minimize"
    assert spec.split_offsets == SPLIT_OFFSETS


def test_cvrp_spec_suite_lifecycle_matches_literals():
    spec = get_problem("cvrp_construct")
    suite = spec.build_suite(20260908, split="dev_train", count=3, size=20)
    assert suite["problem"] == "cvrp_construct"
    assert suite["content_hash"] == suite_hash("cvrp_construct", "dev_train", suite["instances"])
    instances, expected = spec.validate_suite(suite)
    assert len(instances) == 3
    assert expected == suite["content_hash"]


def test_cvrp_spec_carries_execution_whitelist():
    spec = get_problem("cvrp_construct")
    assert "numpy" in spec.allowed_import_roots
    assert "math" in spec.allowed_import_roots
    assert "np" in spec.np_math_roots
    assert "argmin" in spec.numpy_attributes
    assert "sqrt" in spec.math_attributes
    assert "open" in spec.forbidden_names
    assert "abs" in spec.safe_builtins
    assert callable(spec.evaluate_instances)
    assert callable(spec.build_suite)
    assert callable(spec.suite_hash)
    assert callable(spec.validate_suite)


def test_registry_resolves_cvrp_construct():
    assert PROBLEM_REGISTRY["cvrp_construct"].problem_id == "cvrp_construct"
    assert get_problem("cvrp_construct").entrypoint == "select_next_node"


def test_unknown_problem_raises():
    with pytest.raises(ValueError, match="unsupported_problem"):
        get_problem("tsp")
    with pytest.raises(ValueError, match="unsupported_problem"):
        get_problem(None)