from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from eoh_rag.experiments import eoh_single_runner
from eoh_rag.experiments.batch_runner import _resolve_held_out_set


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_held_out_set_repo_relative_path_returns_absolute_file(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    held_out_file = repo_root / "data" / "held-out.pkl"
    held_out_file.parent.mkdir(parents=True)
    held_out_file.write_bytes(b"fixture")

    resolved_paths = _resolve_held_out_set(["data/held-out.pkl"], repo_root=repo_root)

    assert resolved_paths == [str(held_out_file.resolve())]


def test_resolve_held_out_set_expands_environment_variable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    held_out_file = tmp_path / "env-data" / "held-out.pkl"
    held_out_file.parent.mkdir()
    held_out_file.write_bytes(b"fixture")
    monkeypatch.setenv("EOH_HELD_OUT_ROOT", str(held_out_file.parent))

    resolved_paths = _resolve_held_out_set(["$EOH_HELD_OUT_ROOT/held-out.pkl"])

    assert resolved_paths == [str(held_out_file.resolve())]


def test_resolve_held_out_set_expands_user_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home = tmp_path / "home"
    held_out_file = fake_home / "held-out.pkl"
    fake_home.mkdir()
    held_out_file.write_bytes(b"fixture")
    # Windows 使用 USERPROFILE，POSIX 使用 HOME；同时设置以保持测试跨平台。
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("HOME", str(fake_home))

    resolved_paths = _resolve_held_out_set(["~/held-out.pkl"])

    assert resolved_paths == [str(held_out_file.resolve())]


def test_resolve_held_out_set_none_and_empty_list_return_empty() -> None:
    assert _resolve_held_out_set(None) == []
    assert _resolve_held_out_set([]) == []


@pytest.mark.parametrize("invalid_value", ["held-out.pkl", [""], [None]])
def test_resolve_held_out_set_invalid_shape_raises_clear_error(invalid_value: object) -> None:
    with pytest.raises(ValueError, match="held_out_set"):
        _resolve_held_out_set(invalid_value)


def test_resolve_held_out_set_missing_file_reports_raw_and_resolved_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    raw_path = "missing/held-out.pkl"
    expected_path = (repo_root / raw_path).resolve()

    with pytest.raises(FileNotFoundError) as exc_info:
        _resolve_held_out_set([raw_path], repo_root=repo_root)

    error_message = str(exc_info.value)
    assert raw_path in error_message
    assert str(expected_path) in error_message


def test_batch_runner_rejects_missing_held_out_file_before_creating_output(tmp_path: Path) -> None:
    manifest = {
        "suite": "missing_held_out",
        "problems": ["tsp_construct"],
        "arms": [{"name": "pure", "runner_arm": "pure_eoh"}],
        "broad_training": True,
        "held_out_set": ["missing/held-out.pkl"],
    }
    manifest_path = tmp_path / "manifest.json"
    output_dir = tmp_path / "output"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "eoh_rag.experiments.batch_runner",
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    combined_output = process.stdout + process.stderr
    assert process.returncode != 0
    assert "Manifest held_out_set validation FAILED" in combined_output
    assert "held_out_set[0] not found" in combined_output
    assert not output_dir.exists()


def test_single_runner_forwards_held_out_json_as_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    held_out_file = tmp_path / "held-out.pkl"
    held_out_file.write_bytes(b"fixture")
    held_out_json = json.dumps([str(held_out_file)])
    captured_command: list[str] = []

    api_key_env = "EOH_TEST_PATH_API_KEY"
    api_endpoint_env = "EOH_TEST_PATH_API_ENDPOINT"
    model_env = "EOH_TEST_PATH_MODEL"
    monkeypatch.setenv(api_key_env, "test-key")
    monkeypatch.setenv(api_endpoint_env, "https://api.example.test/v1")
    monkeypatch.setenv(model_env, "test-model")

    def fake_subprocess_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(eoh_single_runner.subprocess, "run", fake_subprocess_run)
    args = Namespace(
        official_root=str(REPO_ROOT / "official_eoh"),
        python=sys.executable,
        output_dir=str(tmp_path / "output"),
        problem="bp_online",
        arm="pure_eoh",
        context_file="",
        pop_size=2,
        generations=1,
        operators="i1",
        n_processes=1,
        eval_timeout_s=1,
        llm_timeout_s=1,
        run_timeout_s=1,
        use_official_seed=False,
        seed_codes="",
        adaptive_stop=False,
        stop_window=5,
        stop_min_gap=0.0,
        broad_training=True,
        n_train=1,
        held_out_set=held_out_json,
        api_key_env=api_key_env,
        api_endpoint_env=api_endpoint_env,
        model_env=model_env,
        llm_model="",
    )

    eoh_single_runner.run_official_eoh(args)

    held_out_argument = captured_command[captured_command.index("--held-out-set") + 1]
    assert json.loads(held_out_argument) == [str(held_out_file)]


@pytest.mark.parametrize(
    ("relative_module_path", "class_name"),
    [
        ("official_eoh/examples/tsp_construct/prob_broad.py", "TSPCONSTBroad"),
        ("official_eoh/examples/cvrp_construct/prob_broad.py", "CVRPCONSTBroad"),
    ],
)
def test_broad_evaluator_imports_from_arbitrary_working_directory(
    tmp_path: Path,
    relative_module_path: str,
    class_name: str,
) -> None:
    module_path = REPO_ROOT / relative_module_path
    import_script = (
        "import importlib.util, sys; "
        "module_path, class_name = sys.argv[1:3]; "
        "spec = importlib.util.spec_from_file_location('portable_prob_broad', module_path); "
        "module = importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "print(hasattr(module, class_name))"
    )

    process = subprocess.run(
        [sys.executable, "-c", import_script, str(module_path), class_name],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 0, process.stdout + process.stderr
    assert process.stdout.strip() == "True"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
