from __future__ import annotations

from eoh_rag.experiments.batch_runner import _arm_uses_shared_snapshot
from scripts.analyze_inherited_pool_control import analyze


def test_snapshot_inheritance_can_be_disabled_per_arm() -> None:
    assert _arm_uses_shared_snapshot("snapshot", {"inherit_shared_pool": True}) is True
    assert _arm_uses_shared_snapshot("snapshot", {"inherit_shared_pool": False}) is False
    assert _arm_uses_shared_snapshot("", {"inherit_shared_pool": True}) is False


def test_analysis_marks_problem_with_two_held_out_wins_as_candidate() -> None:
    rows = []
    for problem in ("tsp_construct", "cvrp_construct"):
        for index, seed in enumerate((8101, 8102, 8103)):
            rows.extend(
                [
                    {
                        "problem": problem,
                        "arm": "fresh_start",
                        "seed": seed,
                        "objective": 100.0,
                        "held_out": 20.0,
                        "runtime_s": 100.0,
                        "sample_count": 40,
                        "valid": True,
                    },
                    {
                        "problem": problem,
                        "arm": "inherited_top6",
                        "seed": seed,
                        "objective": 90.0 if index < 2 else 110.0,
                        "held_out": 15.0 if index < 2 else 21.0,
                        "runtime_s": 80.0,
                        "sample_count": 30,
                        "valid": True,
                    },
                ]
            )

    result = analyze(rows)

    assert result["problems"]["tsp_construct"]["held_out_comparison"]["win"] == 2
    assert result["decision"]["status"] == "inheritance_candidate"
    assert result["decision"]["candidate_problem_count"] == 2
