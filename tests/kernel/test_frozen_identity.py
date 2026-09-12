from __future__ import annotations

from agent_skill_loop.contracts import DEFAULT_SEED
from agent_skill_loop.evaluator import evaluator_source_hash
from eoh_frozen.__main__ import prepare_output


def test_prepare_config_has_identity_fields(tmp_path):
    out = tmp_path / "prep"
    config = prepare_output(out, problem_id="cvrp_construct", seed=DEFAULT_SEED, count=3, size=20)
    assert config["problem"] == "cvrp_construct"
    assert config["entrypoint"] == "select_next_node"
    assert config["evaluator_hash"] == evaluator_source_hash()
