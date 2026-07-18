import json
from argparse import Namespace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from eoh_rag.experiments import batch_runner
from eoh_rag.experiments.provider import (
    classify_provider_error,
    get_provider_config,
    probe_provider,
    temperature_for,
)
from eoh_rag.experiments.run_spec import expand_run_specs, validate_run_manifest


def _manifest() -> dict:
    return {
        "suite": "q3_v2",
        "problems": ["bp_online", "tsp_construct"],
        "arms": [
            {"name": "pure", "runner_arm": "pure_eoh"},
            {"name": "tsp_only", "runner_arm": "literature_rag", "problems": ["tsp_construct"]},
        ],
        "generations": [8],
        "repeats": 2,
        "seed_list": [2024, 2025],
    }


def test_run_specs_expand_seed_problem_arm_and_scope(tmp_path: Path) -> None:
    specs = expand_run_specs(_manifest(), tmp_path)
    assert len(specs) == 6
    assert [spec.seed for spec in specs] == [2024, 2024, 2024, 2025, 2025, 2025]
    assert len({spec.run_key for spec in specs}) == len(specs)
    assert all("tsp_only" not in spec.run_key for spec in specs if spec.problem == "bp_online")


def test_multiple_generations_have_distinct_run_keys_and_directories(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest["generations"] = [4, 8]
    specs = expand_run_specs(manifest, tmp_path)

    assert len({spec.run_key for spec in specs}) == len(specs)
    assert len({spec.output_dir for spec in specs}) == len(specs)
    assert {spec.run_key.rsplit("/", 1)[-1] for spec in specs} == {"g4", "g8"}


def test_seed_list_must_match_repeats() -> None:
    manifest = _manifest()
    manifest["repeats"] = 3
    assert "repeats must equal len(seed_list)" in validate_run_manifest(manifest)
    with pytest.raises(ValueError):
        expand_run_specs(manifest, Path("out"))


def test_q3_isolation_rejects_outcome_and_prev_chain() -> None:
    manifest = _manifest()
    manifest.update({"outcome_policy": "disabled", "prev_run_chain": False})
    manifest["arms"][0]["rag"] = {"outcome_file": "secret.jsonl", "use_prev_run_dir_chain": True}
    errors = validate_run_manifest(manifest)
    assert any("outcome_file" in error for error in errors)
    assert any("prev-run chain" in error for error in errors)


def test_provider_audit_is_secret_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "do-not-log")
    audit = get_provider_config("opencode-go").audit_record()
    assert audit == {"provider_name": "opencode-go", "endpoint_host": "opencode.ai", "model": "deepseek-v4-flash", "key_present": True}
    assert "do-not-log" not in repr(audit)


def test_provider_error_and_temperature_contracts() -> None:
    assert classify_provider_error(401, "") == "provider_auth_invalid"
    assert classify_provider_error(None, "error=http_status=403 code=invalid_request_error") == "provider_auth_invalid"
    assert classify_provider_error(429, "") == "provider_rate_limited"
    assert classify_provider_error(402, "insufficient balance") == "provider_quota_exhausted"
    assert temperature_for("fixed", 4, 8, None) is None
    assert temperature_for("linear", 7, 8, 1.0) == 0.0
    assert temperature_for("step-down", 7, 8, 1.0) == 0.5


def test_provider_preflight_is_secret_free_and_classifies_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "must-not-appear"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    def reject_auth(request, timeout):
        assert request.headers["Authorization"] == f"Bearer {secret}"
        assert timeout == 9
        body = BytesIO(
            json.dumps(
                {
                    "error": {
                        "type": "authentication_error",
                        "message": "Authentication Fails",
                    }
                }
            ).encode("utf-8")
        )
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, body)

    monkeypatch.setattr("urllib.request.urlopen", reject_auth)
    result = probe_provider("deepseek", timeout=9, model="frozen-model")

    assert result["ok"] is False
    assert result["model"] == "frozen-model"
    assert result["http_status"] == 401
    assert result["error_class"] == "provider_auth_invalid"
    assert result["error_code"] == "authentication_error"
    assert secret not in repr(result)


def test_provider_preflight_reports_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENCODE_GO_API_KEY", raising=False)
    result = probe_provider("opencode-go")
    assert result["ok"] is False
    assert result["error_class"] == "provider_auth_missing"
    assert result["key_present"] is False


def test_reproducible_manifest_fails_fast_on_invalid_provider_auth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "suite": "auth_fail_fast",
        "problems": ["bp_online"],
        "arms": [{"name": "api", "runner_arm": "api_only"}],
        "generations": [1],
        "repeats": 1,
        "seed_list": [2024],
    }
    args = Namespace(
        output_dir=str(tmp_path),
        resume=False,
        max_concurrent_runs=1,
        provider="deepseek",
        temperature_schedule="fixed",
    )
    calls = 0

    def fake_run(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            returncode=1,
            stdout="API call failed (error=http_status=401 code=invalid_request_error).",
            stderr="RuntimeError: LLM API check failed.",
        )

    monkeypatch.setattr(batch_runner, "_build_cmd", lambda *_args, **_kwargs: ["fake-run"])
    monkeypatch.setattr(batch_runner.subprocess, "run", fake_run)

    assert batch_runner._run_reproducible_manifest(manifest, args) == 1
    index_path = tmp_path / "auth_fail_fast" / "run_index.json"
    rows = json.loads(index_path.read_text(encoding="utf-8"))
    assert calls == 1
    assert rows[0]["status"] == "provider_auth_invalid"
    assert rows[0]["attempts"] == 1
