from __future__ import annotations

import json
import sys
import types

import pytest

pytest.importorskip("eoh")

from eoh_frozen.__main__ import _bridge_target, build_parser, cmd_run


def test_bridge_target_normalises_host_only_endpoint():
    assert _bridge_target("api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"
    assert _bridge_target("https://opencode.ai/zen/go/v1/chat/completions") == (
        "https://opencode.ai/zen/go/v1/chat/completions"
    )


def test_eoh_init_failure_writes_provider_failed_summary(tmp_path, monkeypatch):
    class BoomEoH:
        def __init__(self, **kwargs) -> None:
            raise RuntimeError("LLM API check failed")

    fake = types.ModuleType("eoh")
    fake.EoH = BoomEoH
    fake.LLMConfig = lambda **kwargs: object()
    monkeypatch.setitem(sys.modules, "eoh", fake)
    monkeypatch.setenv("TEST_EOH_KEY", "x")

    out = tmp_path / "run"
    args = build_parser().parse_args([
        "run",
        "--model", "test-model",
        "--output", str(out),
        "--endpoint", "https://opencode.ai/zen/go/v1/chat/completions",
        "--api-key-env", "TEST_EOH_KEY",
    ])
    code = cmd_run(args)
    assert code == 2
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["loop_completed"] is False
    assert summary["status"] == "provider_failed"
    assert summary["provider_error_code"] == "RuntimeError"
    assert summary["http_requests"] == 0
    assert summary["request_rejected"] == 0
    assert (out / "config_frozen.json").is_file()
