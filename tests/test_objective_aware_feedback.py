from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest
from eoh_rag.search_control.tsp_controller import build_controller_suite


REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SRC = REPO_ROOT / "official_eoh" / "eoh" / "src"
if str(OFFICIAL_SRC) not in sys.path:
    sys.path.insert(0, str(OFFICIAL_SRC))

from eoh.eoh.evolution import Evolution, parent_selection  # noqa: E402


def _population() -> list[dict]:
    return [
        {"algorithm": "weak", "code": "def f(): return 3", "objective": 0.9},
        {"algorithm": "best", "code": "def f(): return 1", "objective": 0.7},
        {"algorithm": "middle", "code": "def f(): return 2", "objective": 0.8},
    ]


def _evolution(policy: str) -> Evolution:
    evolution = Evolution.__new__(Evolution)
    evolution.feedback_policy = policy
    evolution.task = "Minimize the development objective."
    evolution.template = "def f():\n    pass"
    evolution._template_kind = "function"
    return evolution


def test_objective_aware_parent_selection_keeps_current_best() -> None:
    single = parent_selection(_population(), 1, "objective_aware")
    pair = parent_selection(_population(), 2, "objective_aware")

    assert single[0]["algorithm"] == "best"
    assert pair[0]["algorithm"] == "best"
    assert pair[1]["algorithm"] != "best"


def test_objective_aware_prompt_exposes_feedback_without_generic_reset() -> None:
    evolution = _evolution("objective_aware")
    parents = parent_selection(_population(), 2, "objective_aware")
    prompt = evolution._build_prompt("e1", parents)

    assert "dev objective=0.7 (lower is better)" in prompt
    assert "Preserve effective parts of the best parent" in prompt
    assert "totally different form" not in prompt


def test_legacy_prompt_contract_remains_unchanged() -> None:
    evolution = _evolution("legacy")
    prompt = evolution._build_prompt("m1", _population()[0])

    assert "Dev objective" not in prompt
    assert "different form" in prompt


def test_objective_feedback_manifest_pairs_policy_only() -> None:
    manifest_path = (
        REPO_ROOT
        / "eoh_rag_workspace/experiments/manifests/tsp_search_controller_objective_feedback_proxy_v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert _validate_manifest(manifest) == []
    assert manifest["controller_confirm_suite"] == "synthetic_confirm_v5"
    assert len(build_controller_suite("synthetic_confirm_v5")) == 12
    policies = []
    seed_paths = []
    for arm in manifest["arms"]:
        command = _build_cmd(manifest, "tsp_search_controller", arm, 4, 0, "out")
        policies.append(command[command.index("--evolution-feedback-policy") + 1])
        seed_paths.append(command[command.index("--seed-codes") + 1])

    assert policies == ["legacy", "objective_aware"]
    assert seed_paths[0] == seed_paths[1]


def test_agent_discovery_v3_is_attributed_to_feedback_evolution() -> None:
    asset_path = (
        REPO_ROOT
        / "eoh_rag_workspace/experiments/assets/tsp_search_controller_agent_discovery_v3.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))

    assert asset["actor"] == "research_agent_eoh"
    assert asset["origin"] == "automatic_evolution"
    assert asset["visibility"]["objective_feedback_visible"] is True
    assert asset["visibility"]["external_teacher_visible"] is False
    assert asset["selection"]["confirm_used_for_selection"] is False
    assert asset["evaluation"]["agent_dev_objective"] < asset["evaluation"][
        "parent_v2_dev_objective"
    ]
    assert hashlib.sha256(asset["code"].encode()).hexdigest().upper() == asset[
        "best_code_sha256"
    ]
