"""
模块：card_outcomes（卡片效果记忆 / RAG 证据层）
功能：记录每一张 RAG 卡片在每一代（generation）注入进化流程后的真实效果，
      让下游的控制器与检索增强逻辑可以基于结构化证据决策，而非拍脑袋的启发式猜测。
职责：
      - 定义单条效果记录（CardOutcomeRecord）与聚合摘要（CardOutcomeSummary）的数据结构；
      - 从「注入审计 + 评测结果」构建效果记录，计算有效率、目标值提升、决策倾向；
      - 把记录去重后持久化到 JSONL 文件，并支持读回；
      - 按卡片维度聚合出可供检索/门控使用的摘要（boost / neutral / suppress）。
接口：
      - CardOutcomeRecord：单条记录（一张卡片在一代中的一次注入事件）
      - CardOutcomeSummary：单张卡片跨多次运行的聚合视图
      - compute_card_set_id(card_ids) -> str：为一组卡片计算与顺序无关的确定性哈希
      - compute_decision_hint(...) -> str：三级决策倾向 positive/neutral/negative
      - build_outcome_records(...) -> list[CardOutcomeRecord]：构建一代的效果记录
      - save_outcomes / load_outcomes：JSONL 持久化与读取
      - summarize_card / summarize_all_cards：卡片级别的效果聚合
输入：注入审计字典 injection_audit、评测结果字典 generation_result、目标 JSONL 路径
输出：结构化的效果记录（内存对象 + JSONL 文件）与聚合摘要
说明：本模块只负责「记录客观事实」这一层，本身不直接对卡片做封禁或加权；
      是否 block/boost 由上层控制器或门控读取摘要后自行判断。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CardOutcomeRecord:
    """单条效果记录：一张卡片在某一代进化中的一次「注入事件」。

    每张被检索到的卡片，在每一代注入进化流程时都会产生一行记录，
    既包含运行上下文（哪个 run、哪个问题、第几代），也包含这一代的评测结果
    （种群规模、有效解个数、目标值等）以及据此得到的成败判断与决策倾向。
    """

    schema_version: str = "card-outcome/v1"  # 记录格式版本，读回时用于兼容处理

    # 运行上下文：定位这条记录来自哪次运行、哪个问题、第几代
    run_id: str = ""
    trace_path: str = ""
    problem: str = ""
    arm: str = ""  # 实验分支/对照组标识
    generation: int = 0
    repeat: int | None = None  # 重复实验编号（用于提升置信度）

    # 卡片集合：解决「一代同时注入多张卡片时如何归因」的问题
    card_set_id: str = ""  # 本代所有策略卡片的集合哈希（与顺序无关）
    selected_card_ids: list[str] = field(default_factory=list)

    # 单张卡片自身的信息
    card_id: str = ""
    card_rank: int = 0  # 该卡片在本代注入中的排名（从 1 开始，0 表示被省略）
    card_source: str = ""  # "literature"（文献）| "history"（历史）
    injection_status: str = ""  # "full"（完整）| "truncated"（截断）| "omitted"（省略）
    injected_chars: int = 0  # 实际注入到 prompt 的字符数

    # 本代评测结果：同一卡片集合内的多张卡片共享这些字段
    population_size: int = 0  # 候选种群规模
    valid_candidates: int = 0  # 其中通过校验的有效候选数
    valid_rate: float = 0.0  # 有效率 = 有效候选 / 种群规模
    best_objective: float | None = None  # 本代最优目标值
    pure_baseline: float | None = None  # 无卡片注入时的纯基线目标值
    delta_pct: float | None = None  # 相对基线的目标值变化百分比（负值代表更优）

    # 判断结论
    generation_success: bool = False  # 生成是否成功（有效率是否达标）
    objective_success: bool = False  # 目标值是否优于基线
    failure_reason: str | None = None  # 失败原因："valid_collapse" | "timeout" | "regression" | None
    decision_hint: str = "neutral"  # 单次判断的决策倾向："positive" | "neutral" | "negative"
    confidence: str = "single_run"  # 置信度："single_run"（单次）| "repeat"（多次重复）

    timestamp: str = ""  # 记录生成的时间戳


def compute_card_set_id(card_ids: list[str]) -> str:
    """为一组卡片 ID 计算确定性哈希，与 ID 的排列顺序无关。

    先把 ID 排序再拼接，因此「相同集合、不同顺序」会得到同一个哈希，
    从而可以用它作为一代所注入卡片组合的唯一标识。返回长度为 12 的十六进制串。
    """
    key = "|".join(sorted(card_ids))  # 排序后拼接，保证顺序无关
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def compute_decision_hint(
    generation_success: bool,
    objective_success: bool,
    valid_rate: float,
    failure_reason: str | None,
) -> str:
    """根据本代表现给出三级决策倾向：positive / neutral / negative。

    判定规则（按优先级从上到下）：
    - 出现明确失败（有效率崩溃 / 超时 / 缺少种群）→ negative；
    - 有效率低于 0.3 → negative；
    - 生成成功且目标值也优于基线 → positive；
    - 其余情况 → neutral。
    """
    # 明确失败信号直接判负
    if failure_reason in ("valid_collapse", "timeout", "missing_population"):
        return "negative"
    # 有效率过低视为负面
    if valid_rate < 0.3:
        return "negative"
    # 生成与目标双双达标才算正面
    if generation_success and objective_success:
        return "positive"
    return "neutral"


def build_outcome_records(
    run_id: str,
    problem: str,
    generation: int,
    injection_audit: dict[str, Any],
    generation_result: dict[str, Any],
    *,
    arm: str = "",
    repeat: int | None = None,
    trace_path: str = "",
    timestamp: str = "",
) -> list[CardOutcomeRecord]:
    """从「一代的 RAG 注入轨迹 + 评测结果」构建效果记录列表。

    该代注入的每一张策略卡片都会生成一条记录（injection_status 为 full/truncated），
    被省略未注入的卡片也会各生成一条 omitted 记录，便于后续区分「注入了但没效果」
    与「压根没注入」。同一卡片集合内的所有记录共享本代的评测结果与决策倾向。

    参数说明
    ----------
    injection_audit : dict
        来自 format_prompt_context_with_audit 的审计字典，含 rag_injected_items、
        rag_omitted_items 等条目（每个条目至少有 id、section，可能有 status、chars）。
    generation_result : dict
        本代评测结果，必须包含：population_size、valid_candidates、best_objective、
        pure_baseline；可选地包含 generation_success、objective_success、failure_reason。

    返回
    ----------
    list[CardOutcomeRecord]：本代所有卡片（含被省略的）对应的效果记录。
    """
    injected_items = injection_audit.get("rag_injected_items", [])
    omitted_items = injection_audit.get("rag_omitted_items", [])

    # 只统计 strategy 区的卡片，并据此计算本代卡片集合哈希
    strategy_items = [e for e in injected_items if e.get("section") == "strategy"]
    strategy_card_ids = [e["id"] for e in strategy_items]
    card_set_id = compute_card_set_id(strategy_card_ids) if strategy_card_ids else ""

    # 从评测结果中取出核心指标并计算有效率
    population_size = generation_result.get("population_size", 0)
    valid_candidates = generation_result.get("valid_candidates", 0)
    valid_rate = valid_candidates / max(population_size, 1)  # 用 max 防止除以 0
    best_objective = generation_result.get("best_objective")
    pure_baseline = generation_result.get("pure_baseline")
    # 目标值相对基线的百分比变化；仅在基线可用且非零时才可计算（负值表示更优）
    delta_pct = None
    if best_objective is not None and pure_baseline is not None and pure_baseline != 0:
        delta_pct = round((best_objective - pure_baseline) / abs(pure_baseline) * 100, 2)

    # 成败判断：优先取评测结果显式给出的值，缺省时按有效率 / delta 的默认阈值推断
    generation_success = generation_result.get("generation_success", valid_rate >= 0.3)
    objective_success = generation_result.get("objective_success", delta_pct is not None and delta_pct < 0)
    failure_reason = generation_result.get("failure_reason")

    # 由本代整体表现得出统一的决策倾向，供本代所有卡片记录共享
    decision = compute_decision_hint(generation_success, objective_success, valid_rate, failure_reason)

    records = []
    # 为每张实际注入的策略卡片生成一条记录，rank 从 1 开始表示注入排名
    for rank, entry in enumerate(strategy_items, start=1):
        source = "history" if entry["id"].startswith("history_") else "literature"  # 依 id 前缀判断来源
        records.append(CardOutcomeRecord(
            run_id=run_id,
            trace_path=trace_path,
            problem=problem,
            arm=arm,
            generation=generation,
            repeat=repeat,
            card_set_id=card_set_id,
            selected_card_ids=strategy_card_ids,
            card_id=entry["id"],
            card_rank=rank,
            card_source=source,
            injection_status=entry.get("status", "full"),
            injected_chars=entry.get("chars", 0),
            population_size=population_size,
            valid_candidates=valid_candidates,
            valid_rate=round(valid_rate, 4),
            best_objective=best_objective,
            pure_baseline=pure_baseline,
            delta_pct=delta_pct,
            generation_success=generation_success,
            objective_success=objective_success,
            failure_reason=failure_reason,
            decision_hint=decision,
            confidence="single_run",
            timestamp=timestamp,
        ))

    # 为被省略（未真正注入 prompt）的卡片补一条记录：rank=0、status="omitted"
    for entry in omitted_items:
        source = "history" if entry["id"].startswith("history_") else "literature"
        records.append(CardOutcomeRecord(
            run_id=run_id,
            trace_path=trace_path,
            problem=problem,
            arm=arm,
            generation=generation,
            repeat=repeat,
            card_set_id=card_set_id,
            selected_card_ids=strategy_card_ids,
            card_id=entry["id"],
            card_rank=0,
            card_source=source,
            injection_status="omitted",
            injected_chars=0,
            population_size=population_size,
            valid_candidates=valid_candidates,
            valid_rate=round(valid_rate, 4),
            best_objective=best_objective,
            pure_baseline=pure_baseline,
            delta_pct=delta_pct,
            generation_success=generation_success,
            objective_success=objective_success,
            failure_reason=failure_reason,
            decision_hint=decision,
            confidence="single_run",
            timestamp=timestamp,
        ))

    return records


# ---------------------------------------------------------------------------
# Persistence (JSONL)
# ---------------------------------------------------------------------------

def _outcome_key(record: CardOutcomeRecord) -> tuple:
    """Dedup key: same run + card + generation + injection status = same event."""
    return (record.run_id, record.card_id, record.generation, record.injection_status)


def save_outcomes(records: list[CardOutcomeRecord], path: Path, *, append: bool = True) -> None:
    """Append outcome records to a JSONL file, skipping duplicates.

    Deduplication uses (run_id, card_id, generation, injection_status) so
    re-running the summarizer on the same data does not produce duplicate rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_keys: set[tuple] = set()
    if append and path.exists():
        for existing in load_outcomes(path):
            existing_keys.add(_outcome_key(existing))

    new_records = [r for r in records if _outcome_key(r) not in existing_keys]
    if not new_records:
        return

    with open(path, "a" if append else "w", encoding="utf-8") as f:
        for record in new_records:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_outcomes(path: Path) -> list[CardOutcomeRecord]:
    """Load all outcome records from a JSONL file."""
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            data.pop("schema_version", None)
            records.append(CardOutcomeRecord(**data))
    return records


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

@dataclass
class CardOutcomeSummary:
    """Aggregated view of a single card's performance across runs."""

    card_id: str
    total_injections: int = 0
    as_set_member_runs: int = 0
    avg_valid_rate: float = 0.0
    avg_delta_pct: float | None = None
    collapse_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    decision: str = "neutral"  # "boost" | "neutral" | "suppress"


def summarize_card(card_id: str, outcomes: list[CardOutcomeRecord]) -> CardOutcomeSummary:
    """Aggregate outcomes for a single card into a summary."""
    card_records = [r for r in outcomes if r.card_id == card_id and r.injection_status != "omitted"]
    if not card_records:
        return CardOutcomeSummary(card_id=card_id)

    set_ids = {r.card_set_id for r in card_records}
    valid_rates = [r.valid_rate for r in card_records]
    deltas = [r.delta_pct for r in card_records if r.delta_pct is not None]
    collapse_count = sum(1 for r in card_records if r.failure_reason == "valid_collapse")
    positive_count = sum(1 for r in card_records if r.decision_hint == "positive")
    negative_count = sum(1 for r in card_records if r.decision_hint == "negative")

    avg_valid = sum(valid_rates) / len(valid_rates) if valid_rates else 0.0
    avg_delta = sum(deltas) / len(deltas) if deltas else None

    if negative_count >= 3 or collapse_count >= 2:
        decision = "suppress"
    elif positive_count >= 3 and negative_count == 0:
        decision = "boost"
    else:
        decision = "neutral"

    return CardOutcomeSummary(
        card_id=card_id,
        total_injections=len(card_records),
        as_set_member_runs=len(set_ids),
        avg_valid_rate=round(avg_valid, 4),
        avg_delta_pct=round(avg_delta, 2) if avg_delta is not None else None,
        collapse_count=collapse_count,
        positive_count=positive_count,
        negative_count=negative_count,
        decision=decision,
    )


def summarize_all_cards(outcomes: list[CardOutcomeRecord]) -> dict[str, CardOutcomeSummary]:
    """Summarize all cards that have outcome records."""
    card_ids = {r.card_id for r in outcomes if r.injection_status != "omitted"}
    return {cid: summarize_card(cid, outcomes) for cid in sorted(card_ids)}
