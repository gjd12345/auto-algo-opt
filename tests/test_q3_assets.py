from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eoh_rag.experiments.eoh_single_runner import _runner_script, summarize_run
from eoh_rag.experiments.reports import analyze_q3
from scripts import prepare_hifo_bp_data


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
Q3_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "eoh_rag_workspace"
    / "experiments"
    / "manifests"
    / "bp_ablation_cards_q3.json"
)
Q3_COMPONENT_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "eoh_rag_workspace"
    / "experiments"
    / "manifests"
    / "bp_card_component_q3.json"
)


def _write_run_summary(path: Path, dataset_name: str, score: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_summary": {
                    "held_out_report": {dataset_name: score},
                }
            }
        ),
        encoding="utf-8",
    )


def _dataset_spec(payload: bytes, destination_name: str = "sample.pkl") -> prepare_hifo_bp_data.DatasetSpec:
    return prepare_hifo_bp_data.DatasetSpec(
        size_label="sample",
        upstream_filename="upstream.pkl",
        destination_filename=destination_name,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_q3_manifest_preserves_recovered_protocol() -> None:
    manifest = json.loads(Q3_MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["suite"] == "bp_ablation_cards_q3"
    assert manifest["model"] == "deepseek-v4-flash"
    assert manifest["problems"] == ["bp_online"]
    assert manifest["broad_training"] is True
    assert manifest["n_train"] == 128
    assert manifest["held_out_set"] == [
        "eoh_rag_workspace/problems/bp_online/held_out/hifo_5k_C100.pkl"
    ]
    assert manifest["generations"] == [8]
    assert manifest["pop_size"] == 6
    assert manifest["repeats"] == 10
    assert manifest["max_runs"] == 30
    assert manifest["operators"] == "e1,e2,m1,m2"
    assert manifest["run_timeout_s"] == 7200
    assert manifest["n_processes"] == 1
    assert manifest["pool_policy"] == "disabled"
    assert manifest["outcome_policy"] == "disabled"
    assert manifest["prev_run_chain"] is False
    assert manifest["seed_list"] == list(range(2024, 2034))
    assert manifest["require_confirm_for_real_run"] is False
    assert manifest["official_root"] == "official_eoh"
    assert manifest["rag"] == {"top_k": 2, "max_chars": 2500, "rerank_mode": "llm"}
    assert all("outcome_file" not in (arm.get("rag") or {}) for arm in manifest["arms"])

    arms = {arm["name"]: arm for arm in manifest["arms"]}
    assert set(arms) == {"pure", "generic", "answer"}
    assert arms["pure"]["runner_arm"] == "pure_eoh"
    assert arms["generic"]["candidate_card_ids"] == [
        "obp_first_fit",
        "obp_best_fit",
        "obp_worst_fit",
    ]
    assert arms["answer"]["candidate_card_ids"] == [
        "obp_first_fit",
        "obp_best_fit",
        "obp_worst_fit",
        "obp_harmonic",
        "obp_funsearch_residual_poly",
        "obp_eoh_util_sqrt_exp",
    ]


def test_q3_component_manifest_only_adds_two_single_card_arms() -> None:
    manifest = json.loads(Q3_COMPONENT_MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["suite"] == "bp_card_component_q3"
    assert manifest["problems"] == ["bp_online"]
    assert manifest["held_out_set"] == [
        "eoh_rag_workspace/problems/bp_online/held_out/hifo_5k_C100.pkl"
    ]
    assert manifest["generations"] == [8]
    assert manifest["pop_size"] == 6
    assert manifest["seed_list"] == list(range(2024, 2034))
    assert manifest["repeats"] == 10
    assert manifest["max_runs"] == 20
    assert manifest["operators"] == "e1,e2,m1,m2"
    assert manifest["eval_timeout_s"] == 40
    assert manifest["pool_policy"] == "disabled"
    assert manifest["outcome_policy"] == "disabled"
    assert manifest["prev_run_chain"] is False

    arms = {arm["name"]: arm for arm in manifest["arms"]}
    assert set(arms) == {"harmonic_only", "residual_poly_only"}
    assert arms["harmonic_only"]["candidate_card_ids"] == ["obp_harmonic"]
    assert arms["residual_poly_only"]["candidate_card_ids"] == [
        "obp_funsearch_residual_poly"
    ]


def test_hifo_specs_pin_commit_names_and_confirmed_hashes() -> None:
    assert prepare_hifo_bp_data.UPSTREAM_COMMIT == "e64ce9edbfb4c8ebffd652b785b0c87261785586"
    assert [spec.destination_filename for spec in prepare_hifo_bp_data.DATASET_SPECS] == [
        "hifo_1k_C100.pkl",
        "hifo_5k_C100.pkl",
        "hifo_10k_C100.pkl",
    ]
    assert [spec.sha256 for spec in prepare_hifo_bp_data.DATASET_SPECS] == [
        "889fbc931ac7a5f94895e1e2dfa2cf4d762969bbfbfe0902f93867b74d363795",
        "172f86591a29ccba94ffc6b711b2f8283aff560c2c9718c9f3c23c93fda0d668",
        "cecc30e87b286fd6223ffb51624769242d306be6b383c843d6dadc57f3b81eb3",
    ]


def test_prepare_datasets_downloads_with_injected_opener(tmp_path: Path) -> None:
    payload = b"verified held-out data"
    spec = _dataset_spec(payload)

    def opener(request: object, timeout: float) -> io.BytesIO:
        assert str(getattr(request, "full_url", "")).endswith("/upstream.pkl")
        assert timeout == 7.5
        return io.BytesIO(payload)

    prepared = prepare_hifo_bp_data.prepare_datasets(
        tmp_path,
        timeout_seconds=7.5,
        opener=opener,
        dataset_specs=[spec],
    )

    assert prepared == [tmp_path / "sample.pkl"]
    assert prepared[0].read_bytes() == payload


def test_prepare_datasets_imports_destination_named_file(tmp_path: Path) -> None:
    payload = b"existing hifo checkout"
    spec = _dataset_spec(payload, destination_name="hifo_5k_C100.pkl")
    source_directory = tmp_path / "source"
    output_directory = tmp_path / "output"
    source_directory.mkdir()
    (source_directory / spec.destination_filename).write_bytes(payload)

    prepared = prepare_hifo_bp_data.prepare_datasets(
        output_directory,
        source_directory=source_directory,
        dataset_specs=[spec],
    )

    assert prepared[0].read_bytes() == payload


def test_hash_mismatch_does_not_replace_existing_file(tmp_path: Path) -> None:
    expected_payload = b"expected"
    destination = tmp_path / "sample.pkl"
    destination.write_bytes(b"keep this until replacement is verified")
    spec = _dataset_spec(expected_payload)

    with pytest.raises(prepare_hifo_bp_data.DatasetPreparationError, match="SHA-256 mismatch"):
        prepare_hifo_bp_data.prepare_datasets(
            tmp_path,
            opener=lambda request, timeout: io.BytesIO(b"corrupt download"),
            dataset_specs=[spec],
        )

    assert destination.read_bytes() == b"keep this until replacement is verified"
    assert not list(tmp_path.glob("*.part"))


def test_verify_only_reports_missing_dataset(tmp_path: Path) -> None:
    with pytest.raises(prepare_hifo_bp_data.DatasetPreparationError, match="is missing"):
        prepare_hifo_bp_data.prepare_datasets(
            tmp_path,
            verify_only=True,
            dataset_specs=[_dataset_spec(b"expected")],
        )


def test_generated_runner_persists_best_held_out_report() -> None:
    source = _runner_script()

    compile(source, "_run_official_eoh.py", "exec")
    assert "def persist_best_held_out_report" in source
    assert 'task.evaluate(best_candidate["code"])' in source
    assert "task.report_held_out = True" in source
    assert "task.report_held_out = False" in source
    assert "persist_best_held_out_report(task, Path(args.output_dir))" in source


def test_cross_broad_problems_expose_eoh_template_contract() -> None:
    root = REPOSITORY_ROOT / "official_eoh" / "examples"
    tsp_source = (root / "tsp_construct" / "prob_broad.py").read_text(encoding="utf-8")
    cvrp_source = (root / "cvrp_construct" / "prob_broad.py").read_text(encoding="utf-8")
    assert "class TSPCONSTBroad(TSPCONST)" in tsp_source
    assert "class CVRPCONSTBroad(CVRPCONST)" in cvrp_source


def test_tsp_broad_seed_survives_spawn_evaluation(tmp_path: Path) -> None:
    script = tmp_path / "spawn_smoke.py"
    script.write_text(
        f'''from pathlib import Path
import sys
root = Path(r"{REPOSITORY_ROOT / 'official_eoh'}")
sys.path.insert(0, str(root / "eoh" / "src"))
sys.path.insert(0, str(root / "examples" / "tsp_construct"))
from prob_broad import TSPCONSTBroad
from eoh.eoh.evolution import _eval_with_timeout

if __name__ == "__main__":
    problem = TSPCONSTBroad(n_train=4, held_out_set=[])
    value = _eval_with_timeout(problem, problem.template_program, 30)
    if value is None:
        raise SystemExit(2)
    print(value)
''',
        encoding="utf-8",
    )
    process = subprocess.run([sys.executable, str(script)], text=True, capture_output=True, timeout=60)
    assert process.returncode == 0, process.stdout + process.stderr


def test_tsp_broad_defers_held_out_until_final_report(tmp_path: Path) -> None:
    script = tmp_path / "held_out_gate_smoke.py"
    script.write_text(
        f'''from pathlib import Path
import sys
root = Path(r"{REPOSITORY_ROOT / 'official_eoh'}")
sys.path.insert(0, str(root / "eoh" / "src"))
sys.path.insert(0, str(root / "examples" / "tsp_construct"))
import prob_broad

calls = []
prob_broad.evaluate_held_out_with_timeout = (
    lambda program_str, entry, timeout_s: calls.append(entry) or {{"feasible": True}}
)
problem = prob_broad.TSPCONSTBroad(n_train=2, held_out_set=["held-out.tsp"])
assert problem.evaluate(problem.template_program) is not None
assert calls == []
problem.report_held_out = True
assert problem.evaluate(problem.template_program) is not None
assert calls == ["held-out.tsp"]
assert problem.held_out_report["held-out"]["feasible"] is True
''',
        encoding="utf-8",
    )
    process = subprocess.run([sys.executable, str(script)], text=True, capture_output=True, timeout=60)
    assert process.returncode == 0, process.stdout + process.stderr


def test_tsp_held_out_timeout_is_reported_without_blocking_run(tmp_path: Path) -> None:
    script = tmp_path / "held_out_timeout_smoke.py"
    held_out_path = (
        REPOSITORY_ROOT
        / "eoh_rag_workspace"
        / "held_out"
        / "core"
        / "tsp_construct"
        / "eil51.tsp"
    )
    script.write_text(
        f'''from pathlib import Path
import sys
import time
root = Path(r"{REPOSITORY_ROOT / 'official_eoh'}")
sys.path.insert(0, str(root / "eoh" / "src"))
sys.path.insert(0, str(root / "examples" / "tsp_construct"))
from prob_broad import evaluate_held_out_with_timeout

slow_code = """def select_next_node(current_node, destination_node, unvisited_nodes, distance_matrix):
    import time
    time.sleep(2)
    return unvisited_nodes[0]
"""

if __name__ == "__main__":
    started_at = time.perf_counter()
    result = evaluate_held_out_with_timeout(slow_code, r"{held_out_path}", 0.2)
    elapsed = time.perf_counter() - started_at
    assert result["error_type"] == "HeldOutTimeout"
    assert result["feasible"] is False
    assert elapsed < 5
''',
        encoding="utf-8",
    )
    process = subprocess.run([sys.executable, str(script)], text=True, capture_output=True, timeout=15)
    assert process.returncode == 0, process.stdout + process.stderr


def test_summarize_run_reads_held_out_report(tmp_path: Path) -> None:
    population_directory = tmp_path / "results" / "pops"
    population_directory.mkdir(parents=True)
    (population_directory / "population_generation_8.json").write_text(
        json.dumps([{"objective": 0.2, "algorithm": "best", "code": "def score(): pass"}]),
        encoding="utf-8",
    )
    report = {"held_out/hifo_5k_C100.pkl": 3.25}
    (tmp_path / "held_out_report.json").write_text(json.dumps(report), encoding="utf-8")

    summary = summarize_run(tmp_path)

    assert summary["ok"] is True
    assert summary["held_out_report"] == report
    assert summary["held_out_report_path"] == str(tmp_path / "held_out_report.json")


def test_summarize_run_tolerates_corrupt_held_out_report(tmp_path: Path) -> None:
    (tmp_path / "held_out_report.json").write_text("not-json", encoding="utf-8")

    summary = summarize_run(tmp_path)

    assert summary["ok"] is False
    assert summary["held_out_report"] == {}


def test_analyzer_discovers_batch_and_legacy_layouts(tmp_path: Path) -> None:
    _write_run_summary(
        tmp_path / "bp_ablation_cards_q3" / "run_bp_online_pure_g8_r1" / analyze_q3.SUMMARY_FILENAME,
        "held_out/hifo_5k_C100.pkl",
        2.5,
    )
    _write_run_summary(
        tmp_path / "pure" / "run_20260710" / analyze_q3.SUMMARY_FILENAME,
        "held_out/hifo_5k_C100.pkl",
        3.5,
    )
    _write_run_summary(
        tmp_path
        / "bp_ablation_cards_q3"
        / "bp_online"
        / "pure"
        / "2024"
        / analyze_q3.SUMMARY_FILENAME,
        "held_out/hifo_5k_C100.pkl",
        1.5,
    )

    assert analyze_q3.load_arm_scores(tmp_path, "pure") == [1.5, 2.5, 3.5]


def test_analyzer_fails_when_any_arm_has_no_scores(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_run_summary(
        tmp_path / "run_bp_online_pure_g8_r1" / analyze_q3.SUMMARY_FILENAME,
        "held_out/hifo_5k_C100.pkl",
        2.5,
    )

    exit_code = analyze_q3.main(["--report-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "generic, answer" in captured.err


def test_run_q3_parses_only_allowlisted_environment_keys() -> None:
    script = (REPOSITORY_ROOT / "run_q3.sh").read_text(encoding="utf-8")

    assert "load_api_environment" in script
    assert "DEEPSEEK_API_KEY|DEEPSEEK_API_ENDPOINT|DEEPSEEK_MODEL" not in script
    assert "case \"$key\" in" in script
    assert 'source "$AUTO_ALGO_OPT_ENV_FILE"' not in script
    assert '. "$AUTO_ALGO_OPT_ENV_FILE"' not in script
    assert "--shared-pool-dir" not in script
    assert "prepare_outcome_files" not in script
