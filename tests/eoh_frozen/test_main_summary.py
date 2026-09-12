import pytest
from eoh_frozen.__main__ import _bridge_target, build_parser
from agent_skill_loop.__main__ import build_parser as compatibility_parser


def test_bridge_target_normalises_host_only_endpoint():
    assert _bridge_target("api.deepseek.com") == "https://api.deepseek.com/v1/chat/completions"
    assert _bridge_target("https://example.test/custom/chat/completions") == "https://example.test/custom/chat/completions"


def test_both_entrypoints_share_native_budget_arguments():
    argv = ["run", "--model", "fixture", "--output", "unused", "--pop-size", "2", "--max-sample-nums", "5", "--max-requests", "20"]
    first = vars(build_parser().parse_args(argv))
    second = vars(compatibility_parser().parse_args(argv))
    first.pop("func")
    second.pop("func")
    assert first == second
    with pytest.raises(SystemExit):
        compatibility_parser().parse_args(argv + ["--candidate-attempts", "3"])
