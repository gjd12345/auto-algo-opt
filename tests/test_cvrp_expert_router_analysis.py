from __future__ import annotations

import json
from pathlib import Path

from eoh_rag.experiments.reports.analyze_cvrp_expert_router import analyze_proxy


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_proxy_analysis_applies_frozen_gate(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    run_root = tmp_path / "runs" / "suite"
    manifest = {
        "suite": "suite",
        "problems": ["cvrp_expert_router"],
        "arms": [{"name": "router", "runner_arm": "api_only"}],
        "generations": [4],
        "seed_list": [1, 2, 3],
        "proxy_gate": {
            "completed_runs_min": 3,
            "valid_generated_runs_min": 3,
            "paired_seed_count_min": 3,
            "confirmation_mean_improvement_vs_n2_pct_min": 0.3,
            "confirmation_environment_degradation_pct_max": 0.5,
            "runs_using_at_least_two_experts_min": 2,
            "selector_invalid_outputs_max": 0,
            "missing_coordinates_max": 0,
            "next_if_pass": "confirm",
            "next_if_fail": "reflect",
        },
    }
    _write_json(manifest_path, manifest)
    index = []
    for seed in (1, 2, 3):
        run_key = f"suite/cvrp_expert_router/router/{seed}"
        run_dir = run_root / str(seed)
        index.append(
            {
                "run_key": run_key,
                "seed": seed,
                "status": "ok",
                "output_dir": str(run_dir),
            }
        )
        _write_json(
            run_dir / "official_eoh_run_summary.json",
            {
                "run_summary": {
                    "ok": True,
                    "confirmation_report": {
                        "mean_improvement_vs_n2_pct": 0.4,
                        "environment_relative_cost_vs_n2": {
                            "uniform_50": -0.004,
                            "clustered_100": 0.001,
                            "rectangular_200": -0.002,
                        },
                        "expert_selection_counts": {"n1": 45, "n2": 45},
                        "selector_invalid_outputs": 0,
                        "evaluation_result": {"feasible": True},
                    },
                }
            },
        )
        _write_json(
            run_dir / "results/samples/samples_1.json",
            [{"objective": -0.001, "code": "def select_expert(): pass"}],
        )
    _write_json(run_root / "run_index.json", index)

    result = analyze_proxy(manifest_path, run_root)

    assert result["status"] == "passed"
    assert result["next_action"] == "confirm"
    assert all(result["checks"].values())
    assert result["metrics"]["completed_runs"] == 3
