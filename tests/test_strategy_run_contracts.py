from pathlib import Path

import pytest

from eoh_rag.experiments.provider import classify_provider_error, get_provider_config, temperature_for
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
    assert classify_provider_error(429, "") == "provider_rate_limited"
    assert classify_provider_error(402, "insufficient balance") == "provider_quota_exhausted"
    assert temperature_for("fixed", 4, 8, None) is None
    assert temperature_for("linear", 7, 8, 1.0) == 0.0
    assert temperature_for("step-down", 7, 8, 1.0) == 0.5
