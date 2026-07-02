"""LLM-based card reranking — uses LLM to select strategy cards from candidate pool."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from eoh_rag.llm.client import chat_completion
from eoh_rag.rag.schemas import CorpusItem


@dataclass
class LlmRerankTrace:
    """Trace for LLM rerank call."""

    rerank_mode: str = "llm"
    prompt_version: str = "v1"
    model: str = ""
    latency_ms: int = 0
    selected_ids: list[str] = field(default_factory=list)
    reasoning: str = ""
    fallback_reason: str = ""
    raw_response: str = ""


_RERANK_PROMPT_V1 = """\
你是策略卡选择器。从候选卡中选择最能帮助进化搜索的卡片。

## 任务
问题类型: {problem}
搜索目标: {query}

## 当前种群已有策略特征
{population_section}

## 候选卡片
{candidates_section}

## 选择规则
1. 选择 {top_k} 张最有价值的卡片
2. 优先选择能带来 **新搜索方向** 的卡片（与种群已有策略互补）
3. 如果有历史表现数据，优先选正面表现的卡片，避免负面表现的卡片
4. 避免与种群已有策略高度重复的卡片

输出严格 JSON 格式:
{{"selected": ["card_id_1", "card_id_2"], "reasoning": "简要说明选择理由"}}
"""


def _format_population_section(population_features: set[str] | None) -> str:
    if not population_features:
        return "（无种群信息，首轮进化）"
    features = sorted(population_features)
    return "已有: " + ", ".join(features[:20])


def _format_outcome_one_liner(card_id: str, outcome_summaries: dict[str, Any] | None) -> str:
    if not outcome_summaries or card_id not in outcome_summaries:
        return "无历史数据"
    s = outcome_summaries[card_id]
    if isinstance(s, dict):
        decision = s.get("decision", "neutral")
        avg_delta = s.get("avg_delta_pct")
        injections = s.get("total_injections", 0)
        delta_str = f"avg_delta={avg_delta:.1f}%" if avg_delta is not None else ""
        return f"{decision} ({injections}次注入 {delta_str})"
    return "neutral"


def _format_candidates_section(
    candidates: list[CorpusItem],
    outcome_summaries: dict[str, Any] | None,
) -> str:
    lines = []
    for i, item in enumerate(candidates, 1):
        outcome = _format_outcome_one_liner(item.id, outcome_summaries)
        lines.append(f"{i}. [{item.id}] {item.title} — {item.summary[:80]}... | 历史: {outcome}")
    return "\n".join(lines)


def llm_rerank(
    query: str,
    candidates: list[CorpusItem],
    top_k: int = 2,
    *,
    problem: str = "",
    population_features: set[str] | None = None,
    outcome_summaries: dict[str, Any] | None = None,
    temperature: float = 0.0,
) -> tuple[list[CorpusItem], LlmRerankTrace]:
    """Use LLM to select cards from candidate pool.

    Returns (selected_items, trace). On failure, returns empty list with
    fallback_reason in trace — caller should fall back to keyword/feature rerank.
    """
    trace = LlmRerankTrace()

    prompt = _RERANK_PROMPT_V1.format(
        problem=problem or "unknown",
        query=query,
        population_section=_format_population_section(population_features),
        candidates_section=_format_candidates_section(candidates, outcome_summaries),
        top_k=top_k,
    )

    start = time.time()
    try:
        response = chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            timeout_s=30,
            max_retries=2,
        )
    except Exception as e:
        trace.fallback_reason = f"llm_call_failed: {type(e).__name__}: {e}"
        trace.latency_ms = int((time.time() - start) * 1000)
        return [], trace

    trace.latency_ms = int((time.time() - start) * 1000)
    trace.raw_response = response[:500]

    # Parse JSON response
    selected_ids = _parse_rerank_response(response)
    if not selected_ids:
        trace.fallback_reason = "parse_failed: no valid card IDs extracted"
        return [], trace

    # Map IDs to items
    id_to_item = {item.id: item for item in candidates}
    result = [id_to_item[cid] for cid in selected_ids if cid in id_to_item]

    if not result:
        trace.fallback_reason = "no_matching_ids: LLM returned IDs not in candidate pool"
        return [], trace

    trace.selected_ids = [item.id for item in result[:top_k]]
    if hasattr(response, '__len__'):
        # Extract reasoning
        try:
            parsed = json.loads(_extract_json(response))
            trace.reasoning = parsed.get("reasoning", "")
        except (json.JSONDecodeError, TypeError):
            pass

    return result[:top_k], trace


def _extract_json(text: str) -> str:
    """Extract JSON object from LLM response (handles markdown code blocks)."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        return text

    # Try extracting from code block
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try finding first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]

    return text


def _parse_rerank_response(response: str) -> list[str]:
    """Parse LLM response to extract selected card IDs."""
    try:
        json_str = _extract_json(response)
        data = json.loads(json_str)
        if isinstance(data, dict) and "selected" in data:
            return [str(x) for x in data["selected"] if x]
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return []
