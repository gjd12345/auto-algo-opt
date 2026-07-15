from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from eoh_rag.experiments.batch_runner import _build_cmd, _validate_manifest
from eoh_rag.search_control.tsp_controller import build_controller_suite


REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SRC = REPO_ROOT / "official_eoh" / "eoh" / "src"
if str(OFFICIAL_SRC) not in sys.path:
    sys.path.insert(0, str(OFFICIAL_SRC))

from eoh.eoh.evolution import (  # noqa: E402
    Evolution,
    _normalize_evaluation_result,
    parent_selection,
)
from eoh.eoh.eoh import EOH, confirmation_gate  # noqa: E402


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


def test_scale_aware_prompt_exposes_worst_scale_feedback() -> None:
    evolution = _evolution("scale_aware")
    parent = {
        **_population()[1],
        "other_inf": {
            "scale_gap_pct": {"10000": 0.2, "1000": 0.8, "5000": 0.4},
            "worst_scale": "1000",
        },
    }
    prompt = evolution._build_prompt("m1", parent)

    assert "1000 items=0.800000%" in prompt
    assert "Worst scale: 1000 items" in prompt
    assert "Do not trade a large regression on another scale" in prompt


def test_robust_aware_prompt_exposes_fold_variation() -> None:
    evolution = _evolution("robust_aware")
    parent = {
        **_population()[1],
        "other_inf": {
            "scale_gap_pct": {"1000": 0.8, "5000": 0.4, "10000": 0.2},
            "scale_std_pct": {"1000": 0.3, "5000": 0.1, "10000": 0.05},
            "worst_scale": "1000",
        },
    }
    prompt = evolution._build_prompt("m2", parent)

    assert "1000 items std=0.300000%" in prompt
    assert "within the reported fold variation" in prompt
    assert parent_selection([parent, *_population()], 1, "robust_aware")[0]["objective"] == 0.7


def test_confirmation_prompt_and_gate_require_two_batch_dominance() -> None:
    evolution = _evolution("confirmation_aware")
    parent = {
        **_population()[1],
        "other_inf": {
            "scale_gap_pct": {"1000": 0.8, "5000": 0.4, "10000": 0.2},
            "confirm_scale_gap_pct": {"1000": 0.9, "5000": 0.5, "10000": 0.3},
            "confirm_objective": 0.005,
            "worst_scale": "1000",
        },
    }
    prompt = evolution._build_prompt("m1", parent)
    accepted = {
        "objective": 0.6,
        "other_inf": {"confirm_objective": 0.0049},
    }
    rejected = {
        "objective": 0.6,
        "other_inf": {"confirm_objective": 0.0051},
    }

    assert "Independent confirmation gaps" in prompt
    assert "Avoid tuning to a search-only difference" in prompt
    assert confirmation_gate(accepted, parent)[0] is True
    assert confirmation_gate(rejected, parent)[0] is False


def test_confirmation_prompt_supports_generic_construct_feedback() -> None:
    evolution = _evolution("confirmation_aware")
    parent = {
        **_population()[1],
        "other_inf": {
            "confirm_objective": 0.75,
            "search_confirm_gap": 0.05,
        },
    }

    prompt = evolution._build_prompt("m1", parent)

    assert "Independent confirmation objective: 0.750000" in prompt
    assert "Search-confirm difference: 0.050000" in prompt
    assert "Scale feedback unavailable" not in prompt


def test_confirmation_gate_only_keeps_confirmation_values_out_of_prompt() -> None:
    parent = {
        **_population()[1],
        "other_inf": {
            "scale_gap_pct": {"1000": 0.8, "5000": 0.4, "10000": 0.2},
            "confirm_scale_gap_pct": {"1000": 0.9, "5000": 0.5, "10000": 0.3},
            "confirm_objective": 0.005,
        },
    }
    observe_prompt = _evolution("confirmation_observe_only")._build_prompt("m1", parent)
    gate_prompt = _evolution("confirmation_gate_only")._build_prompt("m1", parent)

    # 两个臂给模型的输入必须一致，确认值只供引擎接纳候选，不能暗中改变生成提示。
    assert observe_prompt == gate_prompt
    assert "Dev objective: 0.7 (lower is better)" in gate_prompt
    assert "Independent confirmation" not in gate_prompt
    assert "Preserve its strongest structure" in gate_prompt


def test_confirmation_gate_only_changes_acceptance_not_evaluation() -> None:
    parent = {
        **_population()[1],
        "other_inf": {"confirm_objective": 0.005},
    }

    class ImmediateExecutor:
        def submit(self, *_args, **_kwargs):
            return SimpleNamespace(
                result=lambda: {
                    "objective": 0.6,
                    "feedback": {"confirm_objective": 0.0051},
                }
            )

    def build_engine(policy: str) -> EOH:
        engine = EOH.__new__(EOH)
        engine.config = SimpleNamespace(feedback_policy=policy)
        engine.problem = SimpleNamespace(timeout=1)
        engine._eval_executor = ImmediateExecutor()
        engine.evolution = SimpleNamespace(
            generate_code=lambda _population, _operator: (
                parent,
                "def f(): return 1",
                "candidate",
            )
        )
        return engine

    observed = build_engine("confirmation_observe_only")._build_offspring([parent], "m1")
    gated = build_engine("confirmation_gate_only")._build_offspring([parent], "m1")

    assert observed["objective"] == gated["objective"] == 0.6
    assert observed["other_inf"] == {"confirm_objective": 0.0051}
    assert "selection_accepted" not in observed
    assert gated["selection_accepted"] is False
    assert gated["selection_reason"] == "dominance_failed"


def test_structured_evaluation_result_keeps_feedback_and_old_float_contract() -> None:
    old_objective, old_feedback = _normalize_evaluation_result(0.123456)
    objective, feedback = _normalize_evaluation_result(
        {
            "objective": 0.0123456,
            "feedback": {
                "scale_gap_pct": {"1000": 0.8},
                "worst_scale": "1000",
            },
        }
    )

    assert old_objective == 0.12346
    assert old_feedback is None
    assert objective == 0.01235
    assert feedback == {"scale_gap_pct": {"1000": 0.8}, "worst_scale": "1000"}


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


def test_bp_feedback_proxy_reuses_frozen_605_elites() -> None:
    manifest = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_objective_feedback_proxy_v1.json"
        ).read_text(encoding="utf-8")
    )
    seed_path = (
        REPO_ROOT / "official_eoh/examples/bp_online/seeds/bp_inherited_elites_v1.json"
    )
    seeds = json.loads(seed_path.read_text(encoding="utf-8"))
    snapshot_path = (
        REPO_ROOT
        / "evidence/final_batch_20260630/shared_pool_snapshot/best_codes_bp_online.jsonl"
    )
    snapshot_codes = {
        json.loads(line)["code"]
        for line in snapshot_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    assert _validate_manifest(manifest) == []
    assert manifest["broad_training"] is True
    assert manifest["n_train"] == 32
    assert len(manifest["held_out_set"]) == 3
    assert len(seeds) == 4
    assert all(seed["code"] in snapshot_codes for seed in seeds)
    assert hashlib.sha256(seed_path.read_bytes()).hexdigest().upper() == manifest[
        "feedback_hypothesis"
    ]["seed_asset_sha256"]
    policies = []
    for arm in manifest["arms"]:
        command = _build_cmd(manifest, "bp_online", arm, 2, 0, "out")
        policies.append(command[command.index("--evolution-feedback-policy") + 1])
    assert policies == ["legacy", "objective_aware"]


def test_bp_tied_discoveries_are_both_frozen_without_held_out_selection() -> None:
    assets = [
        json.loads(
            (
                REPO_ROOT
                / f"eoh_rag_workspace/experiments/assets/bp_online_agent_discovery_v1{suffix}.json"
            ).read_text(encoding="utf-8")
        )
        for suffix in ("a", "b")
    ]

    assert {asset["actor"] for asset in assets} == {"research_agent_eoh"}
    assert {asset["evaluation"]["agent_dev_objective"] for asset in assets} == {
        0.007359895252993983
    }
    assert all(asset["selection"]["held_out_used_to_break_tie"] is False for asset in assets)
    assert all(asset["visibility"]["codex_external_teacher_visible"] is False for asset in assets)
    for asset in assets:
        assert hashlib.sha256(asset["code"].encode()).hexdigest().upper() == asset[
            "best_code_sha256"
        ]


def test_bp_feedback_confirmation_scales_only_budget_and_training_suite() -> None:
    proxy = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_objective_feedback_proxy_v1.json"
        ).read_text(encoding="utf-8")
    )
    confirm = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/manifests/bp_objective_feedback_confirm_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert _validate_manifest(confirm) == []
    assert confirm["n_train"] == 128
    assert confirm["generations"] == [4]
    assert confirm["pop_size"] == 4
    assert confirm["seed_list"] == [10001, 10002, 10003]
    assert confirm["held_out_set"] == proxy["held_out_set"]
    assert confirm["operators"] == proxy["operators"]
    assert confirm["confirmation_protocol"]["proxy_discoveries_used_as_seeds"] is False
    assert confirm["confirmation_protocol"]["held_out_is_not_used_for_selection"] is True
    assert [arm["seed_codes"] for arm in confirm["arms"]] == [
        arm["seed_codes"] for arm in proxy["arms"]
    ]

    policies = []
    for arm in confirm["arms"]:
        command = _build_cmd(confirm, "bp_online", arm, 4, 0, "out")
        policies.append(command[command.index("--evolution-feedback-policy") + 1])
    assert policies == ["legacy", "objective_aware"]


def test_bp_agent_discovery_v2_keeps_dev_and_held_out_claims_separate() -> None:
    asset = json.loads(
        (
            REPO_ROOT
            / "eoh_rag_workspace/experiments/assets/bp_online_agent_discovery_v2.json"
        ).read_text(encoding="utf-8")
    )

    assert asset["actor"] == "research_agent_eoh"
    assert asset["origin"] == "automatic_evolution"
    assert asset["visibility"]["codex_external_teacher_visible"] is False
    assert asset["visibility"]["proxy_discoveries_visible"] is False
    assert asset["selection"]["held_out_used_for_selection"] is False
    assert asset["paired_confirmation"][
        "objective_aware_beats_legacy_generated_best_pairs"
    ] == 3
    assert asset["evaluation"]["agent_dev_objective"] < asset["evaluation"][
        "seeded_best_dev_objective"
    ]
    assert asset["evaluation"][
        "relative_mean_held_out_gap_reduction_vs_seed_pct"
    ] < 0
    assert hashlib.sha256(asset["code"].encode()).hexdigest().upper() == asset[
        "best_code_sha256"
    ]
