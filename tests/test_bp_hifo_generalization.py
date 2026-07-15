from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from scripts.evaluate_bp_generalization import load_candidates
from scripts.evaluate_bp_hifo_generalization import _extract_instances, evaluate_pair


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    REPO_ROOT
    / "eoh_rag_workspace/experiments/manifests/bp_confirmation_gate_agent_hifo_v1.json"
)


def test_hifo_manifest_freezes_candidates_and_upstream_hashes() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    candidates = load_candidates(manifest)

    assert [item["item_count"] for item in manifest["datasets"]] == [1000, 5000, 10000]
    assert all(item["expected_instances"] == 5 for item in manifest["datasets"])
    assert manifest["comparison"]["hifo_used_during_evolution_or_selection"] is False
    assert manifest["comparison"]["scope_extension_only"] is True
    assert [item["candidate_id"] for item in candidates] == [
        "inherited_seed_best",
        "bp_online_agent_discovery_gate_confirmed_v1",
    ]


def test_extract_instances_matches_official_nested_contract() -> None:
    raw = {1000: {"a": {"items": [60, 40]}, "b": {"items": [70, 30]}}}

    instances = _extract_instances(raw)

    assert [item.tolist() for item in instances] == [[60, 40], [70, 30]]


def test_hifo_pair_evaluation_is_strictly_paired() -> None:
    code = "def score(item, bins):\n    return -bins"
    row = evaluate_pair(
        {
            "dataset_id": "tiny",
            "item_count": 2,
            "instance_index": 0,
            "items": np.array([60, 40]),
            "capacity": 100,
            "candidates": [
                {"candidate_id": "a", "code": code},
                {"candidate_id": "b", "code": code},
            ],
        }
    )

    assert row["results"]["a"] == row["results"]["b"]
    assert row["lower_bound"] == 1


def test_hifo_script_direct_entrypoint_is_portable() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/evaluate_bp_hifo_generalization.py", "--help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert "--manifest" in completed.stdout
