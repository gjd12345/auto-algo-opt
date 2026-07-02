"""
模块：llm_reranker（基于大模型的策略卡重排序）
功能：调用大模型，从候选策略卡集合中挑选出最有助于进化搜索的少数几张卡片。
职责：组装重排序提示词、发起大模型请求、解析返回的 JSON，并把选中的卡片 ID 映射回原始卡片对象；同时记录一次调用的追踪信息（模型、耗时、选中项、失败原因等）。
接口：
  - LlmRerankTrace：数据类，保存一次重排序调用的追踪信息。
  - llm_rerank(query, candidates, top_k=2, *, problem, population_features, outcome_summaries, temperature)
    -> (选中的卡片列表, 追踪对象)：核心入口函数。
输入：query（搜索目标描述）、candidates（候选卡片列表）、problem（问题类型）、
  population_features（当前种群已有策略特征）、outcome_summaries（各卡片的历史表现摘要）。
输出：挑选出的 CorpusItem 列表（长度不超过 top_k）与一个 LlmRerankTrace 追踪对象。
  大模型调用或解析失败时返回空列表，并在追踪对象的 fallback_reason 中说明原因，
  由调用方回退到关键词/特征重排序。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from eoh_rag.llm.client import chat_completion
from eoh_rag.rag.schemas import CorpusItem


@dataclass
class LlmRerankTrace:
    """记录一次大模型重排序调用的追踪信息，便于日志、复盘与调试。

    字段说明：
    - rerank_mode：重排序方式标识（此处固定为大模型方式）。
    - prompt_version：所用提示词的版本号。
    - model：实际使用的模型名称。
    - latency_ms：本次调用耗时（毫秒）。
    - selected_ids：最终选中的卡片 ID 列表。
    - reasoning：大模型给出的选择理由。
    - fallback_reason：调用或解析失败时的原因说明；为空表示本次成功。
    - raw_response：大模型原始返回内容（截断后保存，用于排查问题）。
    """

    rerank_mode: str = "llm"
    prompt_version: str = "v1"
    model: str = ""
    latency_ms: int = 0
    selected_ids: list[str] = field(default_factory=list)
    reasoning: str = ""
    fallback_reason: str = ""
    raw_response: str = ""


# 重排序提示词模板（v1）：告知大模型如何从候选卡中挑选，并要求以严格 JSON 返回。
# 其中 {problem}/{query}/{population_section}/{candidates_section}/{top_k} 为待填充占位符；
# 结尾示例用了双花括号 {{...}} 转义，格式化后会还原成单花括号的 JSON 样例。
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
    """把当前种群已有的策略特征拼成一段文字，供提示词展示。

    无特征时返回“首轮进化”的占位说明；有特征时按字典序排序，最多展示前 20 项。
    """
    if not population_features:
        return "（无种群信息，首轮进化）"
    features = sorted(population_features)
    return "已有: " + ", ".join(features[:20])


def _format_outcome_one_liner(card_id: str, outcome_summaries: dict[str, Any] | None) -> str:
    """把单张卡片的历史表现摘要压缩成一行文字，附在候选列表里。

    摘要缺失时返回“无历史数据”；若摘要是字典，则读取决策倾向（decision）、
    平均增益百分比（avg_delta_pct）和注入次数（total_injections）拼成一行。
    """
    if not outcome_summaries or card_id not in outcome_summaries:
        return "无历史数据"
    s = outcome_summaries[card_id]
    if isinstance(s, dict):
        decision = s.get("decision", "neutral")
        avg_delta = s.get("avg_delta_pct")
        injections = s.get("total_injections", 0)
        # 仅在有平均增益数据时拼出 avg_delta 片段，否则留空
        delta_str = f"avg_delta={avg_delta:.1f}%" if avg_delta is not None else ""
        return f"{decision} ({injections}次注入 {delta_str})"
    return "neutral"


def _format_candidates_section(
    candidates: list[CorpusItem],
    outcome_summaries: dict[str, Any] | None,
) -> str:
    """把所有候选卡片格式化成带序号的多行清单，供提示词展示。

    每行包含：序号、卡片 ID、标题、摘要（截断到 80 字）与历史表现一行摘要。
    """
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
    """调用大模型，从候选卡片池中挑选最有价值的若干张卡片。

    关键参数：
    - query：本轮搜索目标的文字描述。
    - candidates：候选卡片列表（CorpusItem）。
    - top_k：最多选出多少张卡片，默认 2。
    - problem：问题类型（如在线装箱、TSP、CVRP、InsertShips 等），会写入提示词。
    - population_features：当前种群已有的策略特征集合，用于引导选出互补方向的卡片。
    - outcome_summaries：各卡片的历史表现摘要，帮助偏向正面、规避负面卡片。
    - temperature：采样温度，默认 0.0 以求结果稳定。

    返回：(选中的卡片列表, 追踪对象)。列表长度不超过 top_k。
    调用或解析失败时返回空列表，并在追踪对象的 fallback_reason 中记录原因，
    由调用方回退到关键词/特征重排序。
    """
    trace = LlmRerankTrace()

    # 用各分段内容填充提示词模板，组装出最终发给大模型的完整提问
    prompt = _RERANK_PROMPT_V1.format(
        problem=problem or "unknown",
        query=query,
        population_section=_format_population_section(population_features),
        candidates_section=_format_candidates_section(candidates, outcome_summaries),
        top_k=top_k,
    )

    start = time.time()
    try:
        # 发起大模型调用；限制超时与重试次数，避免长时间阻塞
        response = chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            timeout_s=30,
            max_retries=2,
        )
    except Exception as e:
        # 调用异常：记录失败原因与耗时后返回空结果，触发上层回退
        trace.fallback_reason = f"llm_call_failed: {type(e).__name__}: {e}"
        trace.latency_ms = int((time.time() - start) * 1000)
        return [], trace

    trace.latency_ms = int((time.time() - start) * 1000)
    trace.raw_response = response[:500]  # 只保留前 500 字用于排查

    # 解析 JSON 返回，提取选中的卡片 ID 列表
    selected_ids = _parse_rerank_response(response)
    if not selected_ids:
        trace.fallback_reason = "parse_failed: no valid card IDs extracted"
        return [], trace

    # 把 ID 映射回候选卡片对象；忽略不在候选池中的 ID
    id_to_item = {item.id: item for item in candidates}
    result = [id_to_item[cid] for cid in selected_ids if cid in id_to_item]

    if not result:
        # 大模型返回的 ID 全都不在候选池中，视为失败并回退
        trace.fallback_reason = "no_matching_ids: LLM returned IDs not in candidate pool"
        return [], trace

    trace.selected_ids = [item.id for item in result[:top_k]]
    if hasattr(response, '__len__'):
        # 再次解析以提取大模型给出的选择理由；解析失败则静默跳过
        try:
            parsed = json.loads(_extract_json(response))
            trace.reasoning = parsed.get("reasoning", "")
        except (json.JSONDecodeError, TypeError):
            pass

    return result[:top_k], trace


def _extract_json(text: str) -> str:
    """从大模型返回文本中提取出 JSON 对象字符串（可容忍 Markdown 代码块包裹）。

    依次尝试三种方式：直接判断是否以 { 开头；从 ```json 代码块中截取；
    退而求其次地取第一个 { 到最后一个 } 之间的内容。都不匹配则原样返回。
    """
    # 优先尝试直接解析：文本本身就是以 { 开头的 JSON
    text = text.strip()
    if text.startswith("{"):
        return text

    # 其次尝试从 Markdown 代码块（```json ... ```）中提取
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 最后兜底：截取第一个 { 到最后一个 } 之间的片段
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]

    return text


def _parse_rerank_response(response: str) -> list[str]:
    """解析大模型返回，提取被选中的卡片 ID 列表。

    先抽取 JSON 字符串并反序列化，若结果为字典且含 "selected" 字段，
    则把其中每个非空元素转为字符串返回；任何解析错误都返回空列表。
    """
    try:
        json_str = _extract_json(response)
        data = json.loads(json_str)
        if isinstance(data, dict) and "selected" in data:
            return [str(x) for x in data["selected"] if x]
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return []
