"""Tests for eoh_rag.rag.card_synthesis — best-code → card feedback loop."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from eoh_rag.rag.card_synthesis import (
    append_card_to_corpus,
    extract_strategy_features,
    get_code_family,
    synthesize_card,
)
from eoh_rag.rag.features import STRATEGY_FEATURES
from eoh_rag.rag.schemas import CorpusItem, load_corpus, save_corpus


# ── Feature extraction ──────────────────────────────────────────────────────

class TestExtractStrategyFeatures:
    def test_empty_code(self):
        assert extract_strategy_features(None) == set()
        assert extract_strategy_features("") == set()

    def test_regret_and_destination(self):
        code = """
        regret = second_best - best
        dist_to_dest = distance_matrix[unvisited_nodes, destination]
        """
        features = extract_strategy_features(code)
        assert "regret" in features
        assert "destination" in features

    def test_normalize_and_adaptive(self):
        code = """
        range_fwd = max_fwd - min_fwd
        fwd_score = (dist - min_fwd) / range_fwd
        alpha = 0.6
        beta = 0.3
        remaining_ratio = len(unvisited) / total
        """
        features = extract_strategy_features(code)
        assert "normalize" in features
        assert "adaptive_weights" in features
        assert "remaining_aware" in features

    def test_clustering_and_central(self):
        code = """
        # cluster detection via centroid
        centrality = np.sum(sub_dist, axis=1)
        mst = minimum_spanning_tree(graph)
        """
        features = extract_strategy_features(code)
        assert "cluster" in features
        assert "centrality" in features

    def test_far_first_and_penalty(self):
        code = """
        idx_farthest = np.argmax(dist_from_depot)
        penalty = np.exp(-dist_to_dest * remaining_ratio)
        """
        features = extract_strategy_features(code)
        assert "farthest" in features
        assert "penalty" in features

    def test_savings(self):
        code = """
        saving = current_to_depot + distance_matrix[node][depot] - distance_matrix[current_node][node]
        """
        features = extract_strategy_features(code)
        assert "savings" in features


class TestGetCodeFamily:
    def test_backward_compatible(self):
        code = "regret = second_best; nearest = argmin(dists); rest_capacity = capacity - used"
        family = get_code_family(code)
        assert "regret" in family
        assert "nearest" in family
        assert "capacity" in family

    def test_matches_canonical_strategy_extractor(self):
        from eoh_rag.rag.features import extract_strategy_features as canonical_extract

        code = "far_first = distant_nodes[0]; regret_score = second_best - best"
        assert get_code_family(code) == canonical_extract(code)

    def test_empty(self):
        assert get_code_family(None) == set()
        assert get_code_family("") == set()


# ── Card synthesis ───────────────────────────────────────────────────────────

class TestSynthesizeCard:
    def test_basic_synthesis(self):
        code = "regret = second_best - best; dest = distance_matrix[u, destination]"
        card = synthesize_card("tsp_construct", code)
        assert card.kind == "algorithm_card"
        assert card.id.startswith("history_tsp_construct_")
        assert "TSP" in card.title
        assert "construct" in card.tags
        assert "evolved" in card.tags
        assert "Skill:" in card.content
        assert "When:" in card.content
        assert "Do:" in card.content
        assert "Fallback:" in card.content
        assert "Safety:" in card.content

    def test_features_in_tags(self):
        code = "regret = second_best; normalize = (x - min) / range; alpha = 0.7"
        card = synthesize_card("tsp_construct", code)
        assert "regret" in card.tags
        assert "normalize" in card.tags

    def test_synthesis_limits_history_card_to_small_operator(self):
        code = """
        regret = second_best - best
        farthest = argmax(dist_from_depot)
        dest = distance_matrix[u, destination]
        alpha = remaining_ratio
        lookahead = future_cost
        normalize = (x - min) / range
        capacity_check = demand <= rest_capacity
        """
        card = synthesize_card("cvrp_construct", code)
        strategy_tags = [tag for tag in card.tags if tag not in {"cvrp", "construct", "evolved"}]
        assert len(strategy_tags) <= 3
        assert set(strategy_tags) <= STRATEGY_FEATURES
        assert "alpha" in card.content
        assert "α" not in card.content
        # Core section (before Feature tags) should stay bounded
        core_section = card.content.split("\n\nFeature tags:")[0]
        assert core_section.count(";") <= 6
        # New sections exist
        assert "Feature tags:" in card.content
        assert "Formula summary:" in card.content
        assert "Code pattern:" in card.content

    def test_explicit_legacy_features_are_normalized_or_excluded(self):
        card = synthesize_card(
            "tsp_construct",
            "regret = second_best",
            features={"clustering", "regret", "threshold"},
        )
        assert "cluster" in card.tags
        assert "regret" in card.tags
        assert "clustering" not in card.tags
        assert "threshold" not in card.tags

    def test_cvrp_synthesis(self):
        code = "farthest = argmax(dist_depot); capacity_check = demand <= rest"
        card = synthesize_card("cvrp_construct", code)
        assert "CVRP" in card.title
        assert "cvrp" in card.tags
        assert "Return one int" in card.content or "feasible" in card.content or "capacity" in card.content

    def test_no_features_raises(self):
        with pytest.raises(ValueError, match="No strategy features"):
            synthesize_card("tsp_construct", "x = 1")

    def test_run_info_in_source_path(self):
        code = "regret = second_best"
        card = synthesize_card("tsp_construct", code, run_info={"run_dir": "/some/path/run_123"})
        assert card.source_path == "/some/path/run_123"


# ── Corpus persistence ──────────────────────────────────────────────────────

class TestAppendCardToCorpus:
    def test_append_new_card(self, tmp_path):
        code = "regret = second_best - best"
        card = synthesize_card("tsp_construct", code)
        written = append_card_to_corpus(card, tmp_path)
        assert written is True

        # Verify it's in the file
        items = load_corpus(tmp_path / "algorithm_cards.jsonl")
        assert any(item.id == card.id for item in items)

    def test_dedup(self, tmp_path):
        code = "regret = second_best - best"
        card = synthesize_card("tsp_construct", code)
        assert append_card_to_corpus(card, tmp_path) is True
        assert append_card_to_corpus(card, tmp_path) is False  # duplicate

        items = load_corpus(tmp_path / "algorithm_cards.jsonl")
        assert sum(1 for item in items if item.id == card.id) == 1

    def test_preserves_existing(self, tmp_path):
        # Write a curated card first
        curated = CorpusItem(
            id="tsp_nearest_neighbor",
            kind="algorithm_card",
            title="TSP Nearest Neighbor Skill Card",
            tags=["tsp", "construct", "nearest"],
            source_path="curated",
            summary="TSP baseline: select nearest unvisited node.",
            constraints=["Return one int."],
            content="Skill: tsp_nearest_neighbor\nWhen: constructing.\nDo: argmin.\nFallback: none.\nSafety: valid.",
        )
        save_corpus([curated], tmp_path / "algorithm_cards.jsonl")

        # Append a history card
        code = "regret = second_best"
        card = synthesize_card("tsp_construct", code)
        append_card_to_corpus(card, tmp_path)

        # Both should exist
        items = load_corpus(tmp_path / "algorithm_cards.jsonl")
        ids = {item.id for item in items}
        assert "tsp_nearest_neighbor" in ids
        assert card.id in ids


# ── Build corpus preservation ───────────────────────────────────────────────

class TestHistoryCardPreservation:
    def test_rebuild_keeps_history_cards(self, tmp_path):
        """build_all_corpora should preserve history cards, not strip them."""
        from eoh_rag.rag.build_corpus import build_all_corpora, _is_history_card

        # Create a history card
        code = "regret = second_best"
        card = synthesize_card("tsp_construct", code)
        assert _is_history_card(card) is True

        # Create a curated card
        curated = CorpusItem(
            id="tsp_nearest_neighbor",
            kind="algorithm_card",
            title="TSP Nearest Neighbor Skill Card",
            tags=["tsp", "construct", "nearest"],
            source_path="curated",
            summary="TSP baseline.",
            constraints=[],
            content="Skill: tsp_nearest_neighbor\nWhen: constructing.\nDo: argmin.\nFallback: none.\nSafety: valid.",
        )
        assert _is_history_card(curated) is False

        external_literature = CorpusItem(
            id="tsp_external_reference",
            kind="algorithm_card",
            title="External TSP reference",
            tags=["tsp", "construct", "reference"],
            source_path="papers/tsp_external.md",
            summary="External reference card should not be treated as history.",
            constraints=[],
            content="Skill: external\nWhen: constructing.\nDo: use reference.\nFallback: nearest.\nSafety: valid.",
        )
        assert _is_history_card(external_literature) is False

        # Write both to corpus
        save_corpus([curated, card], tmp_path / "algorithm_cards.jsonl")

        # Verify _is_history_card correctly distinguishes
        items = load_corpus(tmp_path / "algorithm_cards.jsonl")
        history_items = [i for i in items if _is_history_card(i)]
        assert len(history_items) == 1
        assert history_items[0].id == card.id


class TestExtractScoringCore:
    """Tests for _extract_scoring_core code snippet extraction."""

    def test_extracts_scoring_lines_from_simple_function(self):
        from eoh_rag.rag.card_synthesis import _extract_scoring_core
        code = """
def select_next_node(current, unvisited, distance_matrix):
    scores = []
    for node in unvisited:
        dist = distance_matrix[current][node]
        score = 1.0 / (dist + 1e-8)
        scores.append((score, node))
    best = max(scores, key=lambda x: x[0])
    return best[1]
"""
        snippet = _extract_scoring_core(code)
        assert snippet is not None
        assert "score" in snippet
        assert len(snippet.splitlines()) <= 15

    def test_returns_none_for_empty_code(self):
        from eoh_rag.rag.card_synthesis import _extract_scoring_core
        assert _extract_scoring_core(None) is None
        assert _extract_scoring_core("") is None

    def test_filters_dangerous_lines(self):
        from eoh_rag.rag.card_synthesis import _extract_scoring_core
        code = """
def heuristic(nodes):
    import os
    print("debug")
    score = len(nodes) * 2
    return score
"""
        snippet = _extract_scoring_core(code)
        if snippet:
            assert "import os" not in snippet
            assert "print(" not in snippet

    def test_rejects_deeply_nested_code(self):
        from eoh_rag.rag.card_synthesis import _extract_scoring_core
        code = """
def deep():
    for i in range(10):
        for j in range(10):
            for k in range(10):
                for m in range(10):
                    score = i + j + k + m
    return score
"""
        snippet = _extract_scoring_core(code)
        assert snippet is None

    def test_rejects_infinite_loop(self):
        from eoh_rag.rag.card_synthesis import _extract_scoring_core
        code = """
def bad():
    while True:
        score = 1
    return score
"""
        snippet = _extract_scoring_core(code)
        assert snippet is None

    def test_snippet_respects_max_chars(self):
        from eoh_rag.rag.card_synthesis import _extract_scoring_core
        code = "def f():\n" + "\n".join(f"    score_{i} = {i} * distance" for i in range(50)) + "\n    return score_0"
        snippet = _extract_scoring_core(code)
        if snippet:
            assert len(snippet) <= 700

    def test_formula_summary_in_synthesized_card(self):
        code = """
def select(current, unvisited, dist):
    regret = second_best - best
    alpha = remaining_ratio
    score = regret * alpha
    return argmin(score)
"""
        card = synthesize_card("tsp_construct", code)
        assert "Formula summary:" in card.content
        assert "regret" in card.content
