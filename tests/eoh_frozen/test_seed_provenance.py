"""Spawn-boundary regressions for official EoH seed provenance."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("eoh")

from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.session_actions import _known_solver_attempts
from agent_skill_loop.skill_store import sha256_text
from eoh.eoh.evolution import _eval_with_timeout
from eoh_frozen.problem import FrozenProblem


def test_spawned_seed_and_generated_evaluations_keep_distinct_parent_identity(tmp_path):
    spec = get_problem("cvrp_construct")
    suite = spec.build_suite(20260908, split="dev_train", count=1, size=6)
    seed_code = spec.baseline_code
    generated_code = seed_code + "\n# generated revision\n"
    log = tmp_path / "results" / "evaluations.jsonl"
    problem = FrozenProblem(
        suite,
        spec=spec,
        timeout=20,
        seed_bindings={
            sha256_text(seed_code): {
                "origin": "population_seed",
                "candidate_id": "seed_1",
                "revision": "original",
                "seed_index": 0,
            }
        },
        evaluation_log=log,
    )

    assert _eval_with_timeout(problem, seed_code, 20) is not None
    problem.set_evaluation_context({
        "origin": "generated",
        "candidate_id": "candidate_1",
        "revision": "original",
        "evaluation_id": "generated-evaluation",
    })
    try:
        assert _eval_with_timeout(problem, generated_code, 20) is not None
    finally:
        problem.set_evaluation_context(None)

    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [row["origin"] for row in rows] == ["population_seed", "generated"]
    assert rows[0]["candidate_id"] == "seed_1"
    assert rows[1]["candidate_id"] == "candidate_1"
    assert rows[1]["evaluation_id"] == "generated-evaluation"


@pytest.mark.parametrize(
    ("inheritance_mode", "incumbent_before_ref", "seed_selection", "expected"),
    [
        ("incumbent_only", None, None, 1),
        ("incumbent_only", "skills/parent", None, 3),
        ("population_seeds", None, {"selected_members": [{}, {}]}, 3),
    ],
)
def test_known_solver_preflight_matches_actual_initialization_cost(
    inheritance_mode, incumbent_before_ref, seed_selection, expected
):
    assert _known_solver_attempts(
        inheritance_mode=inheritance_mode,
        incumbent_before_ref=incumbent_before_ref,
        seed_selection=seed_selection,
    ) == expected
