"""Tests for llm_rerank (Phase 4b): LLM-based card selection with fallback."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from eoh_rag.rag.llm_reranker import (
    LlmRerankTrace,
    _extract_json,
    _parse_rerank_response,
    llm_rerank,
)
from eoh_rag.rag.schemas import CorpusItem


def _make_card(card_id: str, title: str = "", summary: str = "") -> CorpusItem:
    return CorpusItem(
        id=card_id,
        kind="algorithm_card",
        title=title or card_id,
        tags=[],
        source_path="",
        summary=summary or f"summary of {card_id}",
        constraints=[],
        content=f"content of {card_id}",
    )


@pytest.fixture
def candidates() -> list[CorpusItem]:
    return [
        _make_card("tsp_regret_insertion"),
        _make_card("tsp_nearest_neighbor"),
        _make_card("tsp_farthest_insertion"),
        _make_card("tsp_two_opt_awareness"),
    ]


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_direct_json(self):
        text = '{"selected": ["a", "b"]}'
        assert _extract_json(text) == text

    def test_markdown_code_block(self):
        text = '```json\n{"selected": ["a"]}\n```'
        assert '{"selected": ["a"]}' in _extract_json(text)

    def test_with_surrounding_text(self):
        text = 'Here is my answer:\n{"selected": ["a", "b"]}\nDone.'
        out = _extract_json(text)
        assert '"selected"' in out
        assert "Done" not in out


class TestParseRerankResponse:
    def test_valid_response(self):
        text = '{"selected": ["tsp_regret_insertion", "tsp_farthest_insertion"], "reasoning": "ok"}'
        assert _parse_rerank_response(text) == ["tsp_regret_insertion", "tsp_farthest_insertion"]

    def test_missing_selected_key(self):
        assert _parse_rerank_response('{"chosen": ["a", "b"]}') == []

    def test_invalid_json(self):
        assert _parse_rerank_response("not json at all") == []

    def test_empty_selected(self):
        assert _parse_rerank_response('{"selected": []}') == []

    def test_drops_empty_strings(self):
        assert _parse_rerank_response('{"selected": ["a", "", "b"]}') == ["a", "b"]


# ---------------------------------------------------------------------------
# llm_rerank with mocked chat_completion
# ---------------------------------------------------------------------------

class TestLlmRerank:
    def test_success_returns_selected_items(self, candidates):
        mock_response = '{"selected": ["tsp_regret_insertion", "tsp_farthest_insertion"], "reasoning": "complementary"}'
        with patch("eoh_rag.rag.llm_reranker.chat_completion", return_value=mock_response):
            result, trace = llm_rerank("test query", candidates, top_k=2, problem="tsp")

        assert len(result) == 2
        assert [r.id for r in result] == ["tsp_regret_insertion", "tsp_farthest_insertion"]
        assert trace.selected_ids == ["tsp_regret_insertion", "tsp_farthest_insertion"]
        assert trace.fallback_reason == ""
        assert trace.reasoning == "complementary"
        assert trace.rerank_mode == "llm"
        assert trace.latency_ms >= 0

    def test_llm_call_failure_returns_empty_with_fallback_reason(self, candidates):
        with patch("eoh_rag.rag.llm_reranker.chat_completion", side_effect=TimeoutError("api timeout")):
            result, trace = llm_rerank("test query", candidates, top_k=2)

        assert result == []
        assert "llm_call_failed" in trace.fallback_reason
        assert "TimeoutError" in trace.fallback_reason

    def test_parse_failure_returns_empty_with_fallback_reason(self, candidates):
        with patch("eoh_rag.rag.llm_reranker.chat_completion", return_value="this is not json"):
            result, trace = llm_rerank("test query", candidates, top_k=2)

        assert result == []
        assert "parse_failed" in trace.fallback_reason

    def test_unknown_ids_returns_empty_with_fallback_reason(self, candidates):
        mock_response = '{"selected": ["nonexistent_card_a", "nonexistent_card_b"]}'
        with patch("eoh_rag.rag.llm_reranker.chat_completion", return_value=mock_response):
            result, trace = llm_rerank("test query", candidates, top_k=2)

        assert result == []
        assert "no_matching_ids" in trace.fallback_reason

    def test_partial_match_keeps_valid_ids(self, candidates):
        mock_response = '{"selected": ["tsp_regret_insertion", "nonexistent_card"]}'
        with patch("eoh_rag.rag.llm_reranker.chat_completion", return_value=mock_response):
            result, trace = llm_rerank("test query", candidates, top_k=2)

        assert len(result) == 1
        assert result[0].id == "tsp_regret_insertion"
        assert trace.fallback_reason == ""

    def test_top_k_truncation(self, candidates):
        mock_response = '{"selected": ["tsp_regret_insertion", "tsp_nearest_neighbor", "tsp_farthest_insertion"]}'
        with patch("eoh_rag.rag.llm_reranker.chat_completion", return_value=mock_response):
            result, trace = llm_rerank("test query", candidates, top_k=2)

        assert len(result) == 2
        assert trace.selected_ids == ["tsp_regret_insertion", "tsp_nearest_neighbor"]

    def test_population_features_passed_to_prompt(self, candidates):
        captured = {}

        def fake_chat(messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            return '{"selected": ["tsp_regret_insertion"]}'

        with patch("eoh_rag.rag.llm_reranker.chat_completion", side_effect=fake_chat):
            llm_rerank("test query", candidates, top_k=1,
                       population_features={"nearest", "regret"})

        prompt = captured["prompt"]
        assert "nearest" in prompt and "regret" in prompt

    def test_no_population_features_shows_first_round_hint(self, candidates):
        captured = {}

        def fake_chat(messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            return '{"selected": ["tsp_regret_insertion"]}'

        with patch("eoh_rag.rag.llm_reranker.chat_completion", side_effect=fake_chat):
            llm_rerank("test query", candidates, top_k=1, population_features=None)

        assert "首轮进化" in captured["prompt"] or "无种群信息" in captured["prompt"]

    def test_outcome_summaries_injected_per_card(self, candidates):
        captured = {}

        def fake_chat(messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            return '{"selected": ["tsp_regret_insertion"]}'

        outcome_summaries = {
            "tsp_regret_insertion": {"decision": "boost", "avg_delta_pct": -3.5, "total_injections": 9},
            "tsp_nearest_neighbor": {"decision": "suppress", "avg_delta_pct": 1.2, "total_injections": 4},
        }
        with patch("eoh_rag.rag.llm_reranker.chat_completion", side_effect=fake_chat):
            llm_rerank("test query", candidates, top_k=1, outcome_summaries=outcome_summaries)

        prompt = captured["prompt"]
        assert "boost" in prompt
        assert "suppress" in prompt
