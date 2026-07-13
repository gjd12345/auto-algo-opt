from __future__ import annotations

import json

from scripts.analyze_q3_fused_confirmation import analyze as analyze_confirmation
from scripts.analyze_q3_mechanism_discovery import analyze
from scripts.freeze_q3_mechanism_contexts import build_contexts, freeze_contexts, validate_frozen_contexts


def test_mechanism_contexts_have_two_equal_slots() -> None:
    contexts = build_contexts()
    assert len(contexts) == 5
    assert len({len(value) for value in contexts.values()}) == 1
    assert all(value.count("[CARD SLOT ") == 2 for value in contexts.values())
    assert all(value.count("[END CARD SLOT ") == 2 for value in contexts.values())
    assert "harmonic" not in contexts["sham_sham"].lower()
    assert "residual" not in contexts["sham_sham"].lower()


def test_context_lock_matches_written_files(tmp_path) -> None:
    lock = freeze_contexts(tmp_path)
    assert lock["slot_count"] == 2
    assert len(lock["files"]) == 5
    for filename, metadata in lock["files"].items():
        assert len((tmp_path / filename).read_text(encoding="utf-8")) == metadata["chars"]

    persisted = json.loads((tmp_path / "context_lock.json").read_text(encoding="utf-8"))
    assert persisted == lock
    assert validate_frozen_contexts(tmp_path / "context_lock.json") == lock


def test_context_lock_rejects_modified_file(tmp_path) -> None:
    freeze_contexts(tmp_path)
    path = tmp_path / "sham_sham.txt"
    path.write_text(path.read_text(encoding="utf-8") + "changed", encoding="utf-8")

    try:
        validate_frozen_contexts(tmp_path / "context_lock.json")
    except ValueError as exc:
        assert "sham_sham.txt" in str(exc)
    else:
        raise AssertionError("modified context must fail the lock check")


def test_analysis_selects_semantic_confirmation() -> None:
    scores = {
        "pure_eoh": [4.2, 4.1, 4.0, 4.3, 4.2],
        "api_only": [4.1, 4.0, 4.0, 4.2, 4.1],
        "sham_sham": [4.0, 4.0, 3.9, 4.1, 4.0],
        "harmonic_sham": [3.9, 3.8, 3.9, 4.0, 3.8],
        "sham_residual": [3.8, 3.9, 3.8, 3.9, 3.9],
        "harmonic_residual": [3.2, 3.1, 3.3, 3.2, 3.1],
        "fused_sham": [3.2, 3.2, 3.3, 3.1, 3.2],
    }
    rows = [
        {"problem": "bp_online", "arm": arm, "seed": 4101 + index, "score": score, "valid": True}
        for arm, arm_scores in scores.items()
        for index, score in enumerate(arm_scores)
    ]
    result = analyze(rows)
    assert result["decision"]["status"] == "semantic_interaction_candidate"
    assert result["decision"]["fused_practically_equivalent"] is True


def test_fused_confirmation_requires_primary_wins_and_cross_scale_support() -> None:
    rows = []
    for index in range(10):
        seed = 5101 + index
        rows.extend(
            [
                {
                    "problem": "bp_online",
                    "arm": "sham_sham",
                    "seed": seed,
                    "status": "ok",
                    "attempts": 1,
                    "h1k": 4.8,
                    "h5k": 4.0,
                    "h10k": 4.1,
                    "valid": True,
                },
                {
                    "problem": "bp_online",
                    "arm": "fused_sham",
                    "seed": seed,
                    "status": "ok",
                    "attempts": 1,
                    "h1k": 4.7,
                    "h5k": 3.1 if index < 7 else 4.2,
                    "h10k": 3.0,
                    "valid": True,
                },
            ]
        )

    result = analyze_confirmation(rows)

    assert result["comparisons"]["h5k"]["win"] == 7
    assert result["decision"]["status"] == "confirmed_cross_scale"
    assert result["decision"]["next_branch"] == "dynamic_selection_pilot"
