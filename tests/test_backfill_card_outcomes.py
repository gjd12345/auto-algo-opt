from __future__ import annotations

import json
from pathlib import Path

from eoh_rag.experiments.reports.backfill_card_outcomes import build_backfill_records


def _write_summary(root: Path, suite: str, payload: dict) -> Path:
    suite_dir = root / suite
    suite_dir.mkdir(parents=True)
    path = suite_dir / "summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_funnel_records_take_precedence_over_problem_rows(tmp_path: Path) -> None:
    _write_summary(
        tmp_path,
        "suite_a",
        {
            "problems": {
                "tsp_construct": [
                    {
                        "arm": "tocc_corrected",
                        "gen": 4,
                        "pop": 4,
                        "best": 6.2,
                        "valid": "4/4",
                        "cards": ["tsp_regret_insertion", "tsp_farthest_insertion"],
                    }
                ]
            },
            "success_funnel": {
                "per_run": [
                    {
                        "problem": "tsp_construct",
                        "arm": "tocc_corrected",
                        "gen": 4,
                        "best_code_record_id": "tsp_construct:tocc_corrected:g4:r1",
                        "selected_card_ids": ["tsp_regret_insertion", "tsp_farthest_insertion"],
                        "population_size": 4,
                        "valid_candidates": 4,
                        "best_objective": 6.2,
                        "pure_baseline": 6.5,
                        "generation_success": True,
                        "objective_success": True,
                        "failure_reason": None,
                    }
                ],
            },
        },
    )

    records = build_backfill_records(tmp_path)

    assert len(records) == 2
    assert {record.confidence for record in records} == {"summary_backfill_funnel"}
    assert {record.decision_hint for record in records} == {"positive"}


def test_problem_row_backfill_marks_population_collapse(tmp_path: Path) -> None:
    _write_summary(
        tmp_path,
        "suite_b",
        {
            "problems": {
                "cvrp_construct": [
                    {
                        "arm": "pure_eoh",
                        "gen": 0,
                        "pop": 4,
                        "best": 13.5,
                        "valid": "4/4",
                        "cards": [],
                    },
                    {
                        "arm": "default_rag",
                        "gen": 0,
                        "pop": 4,
                        "best": 13.28,
                        "valid": "1/1",
                        "cards": ["cvrp_far_first", "cvrp_nearest_capacity"],
                    },
                    {
                        "arm": "tocc_corrected",
                        "gen": 0,
                        "pop": 4,
                        "best": 12.9,
                        "valid": "4/4",
                        "cards": ["cvrp_far_first", "cvrp_regret_insertion"],
                    },
                ]
            },
            "success_funnel": {"per_run": []},
        },
    )

    records = build_backfill_records(tmp_path)
    by_card = {record.card_id: record for record in records}

    assert len(records) == 4
    assert {record.confidence for record in records} == {"summary_backfill_problem_row"}
    assert by_card["cvrp_nearest_capacity"].failure_reason == "valid_collapse"
    assert by_card["cvrp_nearest_capacity"].decision_hint == "negative"
    assert by_card["cvrp_far_first"].failure_reason is None
