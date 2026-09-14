import copy
import json

import pytest

from agent_skill_loop.session_runtime import initialize_session, SessionError
from eoh_frozen.generation_contract import generation_parameters


def test_manifest_binds_actual_provider_and_resource_parameters(tmp_path):
    root = tmp_path / "source"
    initialize_session(output=root, operation_id="init", eoh_model="fixture",
                       benchmark_id="eohs_v1", max_solver_calls=20,
                       eoh_thinking="disabled", eoh_max_requests=24, eoh_round_max_requests=24)
    config = json.loads((root / "config_frozen.json").read_text())
    manifest = config["experiment_manifest"]["document"]
    contract = manifest["extra"]["generation_contract"]
    assert contract["generation_parameters"] == generation_parameters(config["eoh"]["endpoint"], "disabled")
    assert contract["max_output_tokens"] == 16384
    for key, replacement in (("temperature", 0.7), ("request_timeout_seconds", 1)):
        changed = copy.deepcopy(manifest)
        changed["extra"]["generation_contract"][key] = replacement
        with pytest.raises(SessionError, match="generation_contract_mismatch"):
            initialize_session(output=tmp_path / key, operation_id="init", eoh_model="fixture",
                               benchmark_id="eohs_v1", experiment_manifest=changed,
                               eoh_thinking="disabled", eoh_max_requests=24, eoh_round_max_requests=24)
    with pytest.raises(SessionError, match="resource_contract_mismatch"):
        initialize_session(output=tmp_path / "resource", operation_id="init", eoh_model="fixture",
                           benchmark_id="eohs_v1", experiment_manifest=manifest,
                           eoh_thinking="disabled", eoh_max_requests=25, eoh_round_max_requests=24)
