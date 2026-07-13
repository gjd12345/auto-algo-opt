from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from eoh_rag.experiments.reports.export_strategy_evidence import (
    RunEvidence,
    analyze_cross,
    analyze_q3,
    build_environment,
    collect_dataset_hashes,
    core_suite_score,
    load_formal_runs,
    write_cross_evidence,
    write_adversarial_candidates,
    write_q3_evidence,
)


def _run(
    problem: str,
    arm: str,
    seed: int,
    score: float,
    *,
    held_out_report: dict | None = None,
) -> RunEvidence:
    return RunEvidence(
        run_key=f"suite/{problem}/{arm}/{seed}",
        problem=problem,
        arm=arm,
        seed=seed,
        status="ok",
        attempts=1,
        runtime_s=10.0,
        best_objective=score,
        valid_candidates=6,
        population_size=6,
        best_code="def score(item, bins):\n    return bins\n",
        held_out_report=held_out_report or {"held_out/hifo_5k_C100.pkl": score},
    )


def test_q3_analysis_joins_by_seed_and_applies_directional_rule() -> None:
    runs: list[RunEvidence] = []
    for seed in range(2024, 2034):
        pure_score = 4.0
        answer_score = 3.0 if seed < 2031 else 5.0
        runs.extend(
            [
                _run("bp_online", "answer", seed, answer_score),
                _run("bp_online", "pure", seed, pure_score),
                _run("bp_online", "generic", seed, 3.5),
            ]
        )

    result = analyze_q3(list(reversed(runs)))

    assert [row["seed"] for row in result["pairs"]] == list(range(2024, 2034))
    assert result["decision"]["status"] == "directional_support"
    assert result["decision"]["answer_vs_pure"] == {"win": 7, "tie": 0, "loss": 3}
    assert result["decision"]["median_gain"] == 1.0


def test_core_suite_score_requires_every_fixed_instance_to_be_valid() -> None:
    complete_tsp = {
        f"instance-{index}": {"feasible": True, "relative_gap_pct": float(index)}
        for index in range(12)
    }
    incomplete_tsp = dict(complete_tsp)
    incomplete_tsp["instance-11"] = {
        "feasible": False,
        "error_type": "HeldOutTimeout",
    }

    assert core_suite_score("tsp_construct", complete_tsp) == 5.5
    assert core_suite_score("tsp_construct", incomplete_tsp) is None


def test_cross_analysis_is_inconclusive_when_any_problem_lacks_five_pairs() -> None:
    runs: list[RunEvidence] = []
    for problem in ("bp_online", "tsp_construct", "cvrp_construct"):
        for seed in range(3101, 3106):
            local = _run(problem, "local_only", seed, 10.0)
            mixed = _run(problem, "mixed_abstract", seed, 8.0)
            if problem == "tsp_construct" and seed == 3105:
                mixed = replace(mixed, held_out_report={"timeout": {"feasible": False}})
            elif problem == "tsp_construct":
                report = {
                    f"tsp-{index}": {"feasible": True, "relative_gap_pct": 8.0}
                    for index in range(12)
                }
                local = replace(local, held_out_report=report)
                mixed = replace(mixed, held_out_report=report)
            elif problem == "cvrp_construct":
                local_report = {
                    f"cvrp-{index}": {
                        "feasible": True,
                        "capacity_valid": True,
                        "coverage_valid": True,
                        "relative_gap_pct": 10.0,
                    }
                    for index in range(10)
                }
                mixed_report = {
                    f"cvrp-{index}": {
                        "feasible": True,
                        "capacity_valid": True,
                        "coverage_valid": True,
                        "relative_gap_pct": 8.0,
                    }
                    for index in range(10)
                }
                local = replace(local, held_out_report=local_report)
                mixed = replace(mixed, held_out_report=mixed_report)
            else:
                local = replace(
                    local,
                    held_out_report={
                        "hifo_1k_C100.pkl": 10.0,
                        "hifo_5k_C100.pkl": 10.0,
                        "hifo_10k_C100.pkl": 10.0,
                    },
                )
                mixed = replace(
                    mixed,
                    held_out_report={
                        "hifo_1k_C100.pkl": 8.0,
                        "hifo_5k_C100.pkl": 8.0,
                        "hifo_10k_C100.pkl": 8.0,
                    },
                )
            runs.extend([mixed, local])

    result = analyze_cross(list(reversed(runs)))

    assert result["decision"]["status"] == "inconclusive"
    assert result["decision"]["complete_pairs_by_problem"]["tsp_construct"] == 4
    assert result["global_test"]["p_value"] is None


def test_loader_accepts_wrapped_and_bare_summaries(tmp_path: Path) -> None:
    suite_dir = tmp_path / "formal" / "suite"
    rows = []
    for seed, wrapped in ((2024, True), (2025, False)):
        run_dir = suite_dir / "bp_online" / "pure" / str(seed)
        run_dir.mkdir(parents=True)
        run_summary = {
            "ok": True,
            "population_size": 6,
            "valid_candidates": 6,
            "best_objective": 1.0,
            "best_code": "def score(item, bins):\n    return bins\n",
            "held_out_report": {"hifo_5k_C100.pkl": 1.0},
        }
        payload = {"run_summary": run_summary} if wrapped else run_summary
        (run_dir / "official_eoh_run_summary.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        rows.append(
            {
                "run_key": f"suite/bp_online/pure/{seed}",
                "problem": "bp_online",
                "arm": "pure",
                "seed": seed,
                "status": "ok",
                "attempts": 1,
                "runtime_s": 10.0,
                "best_objective": 1.0,
                "valid_candidates": 6,
                "output_dir": str(run_dir),
            }
        )
    (suite_dir / "run_index.json").write_text(json.dumps(rows), encoding="utf-8")

    loaded = load_formal_runs(suite_dir, expected_count=2)

    assert [run.seed for run in loaded] == [2024, 2025]
    assert all(run.population_size == 6 for run in loaded)


def test_q3_writer_creates_required_evidence_without_local_paths(tmp_path: Path) -> None:
    runs: list[RunEvidence] = []
    for seed in range(2024, 2034):
        for arm, score in (("pure", 4.0), ("generic", 3.5), ("answer", 3.0)):
            runs.append(_run("bp_online", arm, seed, score))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"suite": "q3", "seed_list": list(range(2024, 2034))}), encoding="utf-8")
    output_dir = tmp_path / "evidence" / "q3_v2"
    environment = {
        "git_commit": "abc123",
        "python_version": "3.14",
        "provider_name": "opencode-go",
        "endpoint_host": "opencode.ai",
        "model": "deepseek-v4-flash",
        "max_concurrent_runs": 6,
        "dataset_hashes": {},
        "started_at": "2026-07-12T00:00:00+08:00",
        "completed_at": "2026-07-12T01:00:00+08:00",
    }

    write_q3_evidence(runs, manifest_path, output_dir, environment)

    required = {
        "manifest.lock.json",
        "environment.json",
        "run_index.compact.json",
        "paired_results.csv",
        "decision.json",
        "report.md",
        "q3_pairs.csv",
        "q3_summary.json",
        "q3_report.md",
    }
    assert required.issubset({path.name for path in output_dir.iterdir()})
    compact_text = (output_dir / "run_index.compact.json").read_text(encoding="utf-8")
    assert "output_dir" not in compact_text
    assert "C:\\Users" not in compact_text
    assert len(list((output_dir / "best_codes").glob("*.py"))) == 3


def test_cross_writer_records_incomplete_core_pairs_and_required_files(tmp_path: Path) -> None:
    runs: list[RunEvidence] = []
    for problem in ("bp_online", "tsp_construct", "cvrp_construct"):
        for seed in range(3101, 3106):
            for arm, score in (("local_only", 10.0), ("mixed_abstract", 8.0)):
                if problem == "bp_online":
                    report = {
                        "hifo_1k_C100.pkl": score,
                        "hifo_5k_C100.pkl": score,
                        "hifo_10k_C100.pkl": score,
                    }
                elif problem == "tsp_construct":
                    report = {
                        f"tsp-{index}": {
                            "feasible": index < 11,
                            "relative_gap_pct": score if index < 11 else None,
                            "error_type": None if index < 11 else "HeldOutTimeout",
                        }
                        for index in range(12)
                    }
                else:
                    report = {
                        f"cvrp-{index}": {
                            "feasible": True,
                            "capacity_valid": True,
                            "coverage_valid": True,
                            "relative_gap_pct": score,
                        }
                        for index in range(10)
                    }
                runs.append(_run(problem, arm, seed, score, held_out_report=report))

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"suite": "cross", "seed_list": list(range(3101, 3106))}), encoding="utf-8")
    output_dir = tmp_path / "evidence" / "cross_problem_transfer"
    environment = {
        "git_commit": {"launch": "abc123", "final_compatible": "def456"},
        "python_version": "3.14",
        "provider_name": "opencode-go",
        "endpoint_host": "opencode.ai",
        "model": "deepseek-v4-flash",
        "max_concurrent_runs": 6,
        "dataset_hashes": {},
        "started_at": "2026-07-12T00:00:00+08:00",
        "completed_at": "2026-07-12T01:00:00+08:00",
    }

    result = write_cross_evidence(runs, manifest_path, output_dir, environment)

    required = {
        "manifest.lock.json",
        "environment.json",
        "run_index.compact.json",
        "paired_results.csv",
        "decision.json",
        "report.md",
        "cross_pairs.csv",
        "cross_global_test.json",
        "cross_problem_holm.csv",
        "cross_report.md",
    }
    assert required.issubset({path.name for path in output_dir.iterdir()})
    assert result["decision"]["status"] == "inconclusive"
    assert result["decision"]["complete_pairs_by_problem"]["tsp_construct"] == 0
    assert len(list((output_dir / "best_codes").glob("*.py"))) == 4


def test_dataset_hashes_are_relative_and_adversarial_gap_is_explicit(tmp_path: Path) -> None:
    dataset = tmp_path / "data" / "held-out.pkl"
    dataset.parent.mkdir()
    dataset.write_bytes(b"fixed data")
    manifest = {
        "held_out_set": ["data/held-out.pkl"],
        "held_out_by_problem": {"bp_online": ["data/held-out.pkl"]},
    }

    hashes = collect_dataset_hashes(manifest, tmp_path)
    output_path = tmp_path / "reports" / "adversarial_candidates.json"
    payload = write_adversarial_candidates(tmp_path / "snapshot", output_path)

    assert set(hashes) == {"data/held-out.pkl"}
    assert len(hashes["data/held-out.pkl"]) == 64
    assert payload["status"] == "needs_human_review"
    assert payload["source_status"] == "missing_failures_files"
    assert output_path.is_file()


def test_environment_builder_keeps_only_audited_fields() -> None:
    environment = build_environment(
        git_commit={"launch": "abc123", "final_compatible": "def456"},
        dataset_hashes={"data/core.pkl": "a" * 64},
        started_at="2026-07-12T00:00:00+08:00",
        completed_at="2026-07-12T01:00:00+08:00",
    )

    assert set(environment) == {
        "git_commit",
        "python_version",
        "provider_name",
        "endpoint_host",
        "model",
        "max_concurrent_runs",
        "dataset_hashes",
        "started_at",
        "completed_at",
    }
    assert environment["provider_name"] == "opencode-go"
    assert environment["endpoint_host"] == "opencode.ai"
    assert environment["model"] == "deepseek-v4-flash"
