from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from eoh_rag.experiments.batch_runner import _build_cmd
from scripts.analyze_m3_operator_screen import analyze
from scripts.analyze_m3_tsp_confirmation import analyze as analyze_tsp_confirmation


def test_arm_can_override_manifest_operators() -> None:
    manifest = {"operators": "e1,e2,m1,m2", "python_exe": "python"}
    arm = {"name": "with_m3", "runner_arm": "pure_eoh", "operators": "e1,e2,m1,m2,m3"}

    command = _build_cmd(manifest, "bp_online", arm, 4, 1, "run", seed=6101)

    assert command[command.index("--operators") + 1] == "e1,e2,m1,m2,m3"


def test_analysis_accepts_productive_m3_on_two_problems() -> None:
    rows = []
    for problem_index, problem in enumerate(("bp_online", "tsp_construct", "cvrp_construct")):
        for seed_index, seed in enumerate((6101, 6102, 6103)):
            baseline = 10.0 + problem_index + seed_index
            candidate = baseline - 1.0 if problem != "cvrp_construct" else baseline + 0.5
            rows.extend(
                [
                    {
                        "problem": problem,
                        "arm": "four_ops",
                        "seed": seed,
                        "objective": baseline,
                        "held_out": baseline,
                        "valid": True,
                        "m3_attempts": 0,
                        "m3_outputs": 0,
                        "m3_evaluated": 0,
                    },
                    {
                        "problem": problem,
                        "arm": "with_m3",
                        "seed": seed,
                        "objective": candidate,
                        "held_out": candidate,
                        "valid": True,
                        "m3_attempts": 4,
                        "m3_outputs": 3,
                        "m3_evaluated": 2,
                    },
                ]
            )

    result = analyze(rows)

    assert result["problems"]["bp_online"]["contract_ok"] is True
    assert result["problems"]["tsp_construct"]["objective_comparison"]["win"] == 3
    assert result["decision"]["status"] == "m3_candidate"


def test_tsp_confirmation_requires_training_and_core7_improvement() -> None:
    rows = []
    for index, seed in enumerate((7101, 7102, 7103, 7104, 7105)):
        baseline = 6800.0 + index
        rows.extend(
            [
                {
                    "problem": "tsp_construct",
                    "arm": "four_ops",
                    "seed": seed,
                    "objective": baseline,
                    "held_out": 20.0,
                    "valid": True,
                    "m3_attempts": 0,
                    "m3_outputs": 0,
                    "m3_evaluated": 0,
                },
                {
                    "problem": "tsp_construct",
                    "arm": "with_m3",
                    "seed": seed,
                    "objective": baseline - 100 if index < 4 else baseline + 20,
                    "held_out": 15.0 if index < 3 else 21.0,
                    "valid": True,
                    "m3_attempts": 8,
                    "m3_outputs": 8,
                    "m3_evaluated": 7,
                },
            ]
        )

    result = analyze_tsp_confirmation(rows)

    assert result["objective_comparison"]["win"] == 4
    assert result["core7_comparison"]["win"] == 3
    assert result["decision"]["status"] == "m3_tsp_confirmed"


def test_tsp_confirmation_direct_entry_can_import_dependencies() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_m3_tsp_confirmation.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
