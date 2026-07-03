"""
模块：extract_rerank_traces（LLM 重排训练数据抽取）
功能：从已完成的实验运行结果中，抽取 LLM 挑选策略卡（rerank）时的“输入提示 + 实际选择”样本对，
      整理成 RankLLM 兼容的对话式 JSON，供小模型做监督微调（SFT）训练。
职责：
  - 读取每个运行目录下的 official_eoh_run_summary.json 汇总文件；
  - 复原当时 LLM 看到的重排提示（问题、种群特征、候选卡及其历史表现）；
  - 把提示与 LLM 的真实选择（selected）和理由（reasoning）配成一条训练样本；
  - 可选按“是否优于该问题的 pure_eoh 基线”过滤，只保留高质量的教师样本；
  - 汇总统计并写出 JSONL。
接口：
  - build_example(summary_path, baseline_medians) -> dict | None：从单个汇总文件构造一条样本
  - collect_examples(runs_dir, baseline_medians) -> list[dict]：遍历目录收集全部样本
  - filter_examples(examples, min_improvement_pct, keep_unjudged) -> list[dict]：按提升幅度过滤
  - main() -> None：命令行入口，串起收集、过滤、写文件、打印统计
输入：
  - --runs-dir：包含各次实验运行子目录的根目录（其中散落着 official_eoh_run_summary.json）
  - --baseline-medians：JSON 字符串，把“问题名 -> pure_eoh 基线中位数”映射起来
  - --min-improvement-pct / --keep-unjudged：过滤阈值及是否保留无法评判提升的样本
输出：
  - 一份 JSONL 文件，每行是一条 {conversations, metadata} 训练样本；
  - 标准输出打印一段 JSON 统计（写出路径、样本总数、按问题分布、去重后的选择组合数等）。
示例：
    python -m eoh_rag.experiments.training.extract_rerank_traces \\
        --runs-dir eoh_rag_workspace/reports/auto_experiment_reports \\
        --output eoh_rag_workspace/training/rerank_sft_data.jsonl \\
        --baseline-medians '{"tsp_construct": 6.44, "cvrp_construct": 13.52}'
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

# 复用与线上推理完全一致的提示模板与格式化函数，保证训练/推理时的输入分布对齐。
from eoh_rag.rag.llm_reranker import (
    _RERANK_PROMPT_V1,
    _format_candidates_section,
    _format_population_section,
)
from eoh_rag.rag.schemas import CorpusItem

logger = logging.getLogger(__name__)

# 训练样本里固定的 system 角色内容：告诉模型它是“策略卡选择器”，
# 明确输入（进化任务、种群策略、候选卡及历史表现）和输出（严格 JSON，含 selected 与 reasoning）。
SYSTEM_MESSAGE = (
    "你是策略卡选择器，负责从候选卡片池中为算法进化挑选最有价值的卡片。"
    "输入是当前进化任务、种群已有策略、候选卡及其历史表现。"
    "输出严格 JSON，包含 selected 和 reasoning 字段。"
)


def _rebuild_candidate_items(
    candidate_ids: list[str],
    selected_items: list[dict[str, Any]],
    all_scores: list[dict[str, Any]],
) -> list[CorpusItem]:
    """为候选卡片池重建最小可用的 CorpusItem 对象列表。

    汇总记录里只对“最终被注入的卡片”保存了标题/摘要等详细信息，
    对其余候选卡则退化为“仅有 id”的占位对象——这与 LLM 在推理时看到的
    详细程度是一致的，不会造成训练/推理输入分布偏差。

    参数：
      - candidate_ids：候选卡片 id 列表，决定返回列表的顺序与集合。
      - selected_items / all_scores：两份可能带有卡片元信息的记录，按 id 合并成查表字典。
    返回：与 candidate_ids 一一对应的 CorpusItem 列表。
    """
    # 先把两份来源里的条目按 id 合并成查表字典；同一 id 以先出现的为准（不覆盖）。
    by_id = {}
    for source in (selected_items, all_scores):
        for entry in source:
            cid = entry.get("id")
            if not cid or cid in by_id:
                continue
            by_id[cid] = entry

    items = []
    for cid in candidate_ids:
        # 查不到元信息时用兜底默认值：标题退化为 id，摘要退化为一句占位说明。
        meta = by_id.get(cid, {})
        items.append(
            CorpusItem(
                id=cid,
                kind=meta.get("kind", "algorithm_card"),
                title=meta.get("title", cid),
                tags=meta.get("tags", []) or [],
                source_path="",
                summary=meta.get("summary", "") or f"strategy card {cid}",
                constraints=[],
                content="",
            )
        )
    return items


def _load_outcome_summaries(outcome_file: str) -> dict[str, Any]:
    """尽力从 card_outcomes.jsonl 文件加载各卡片的历史表现汇总。

    参数 outcome_file 为文件路径字符串；文件缺失或解析失败时返回空字典，
    不抛异常，确保上游流程不因缺少历史数据而中断。
    返回：{卡片 id -> 汇总信息字典} 的映射。
    """
    path = Path(outcome_file)
    if not outcome_file or not path.exists():
        return {}
    try:
        from eoh_rag.rag.card_outcomes import load_outcomes, summarize_all_cards

        outcomes = load_outcomes(path)
        summaries = summarize_all_cards(outcomes)
        from dataclasses import asdict

        # 把 dataclass 汇总对象转成普通字典，便于后续格式化进提示文本。
        return {cid: asdict(summary) for cid, summary in summaries.items()}
    except (ImportError, OSError, ValueError, TypeError) as exc:
        logger.warning("failed to load outcome summaries from %s: %s", outcome_file, exc)
        return {}


def build_example(
    summary_path: Path,
    baseline_medians: dict[str, float],
) -> dict[str, Any] | None:
    """从单个运行汇总 JSON 构造一条训练样本；不满足条件时返回 None 表示跳过。

    参数：
      - summary_path：某次运行的 official_eoh_run_summary.json 路径。
      - baseline_medians：{问题名 -> pure_eoh 基线中位数}，用于计算相对提升幅度。
    返回：形如 {"conversations": [...], "metadata": {...}} 的样本字典，或 None。

    只有当这次运行确实走了 LLM 重排（rag_rerank_mode == "llm"）、没有触发回退、
    且有实际选择结果时才会产出样本。
    """
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("failed to load summary %s: %s", summary_path, exc)
        return None

    rag = data.get("rag_trace") or {}
    # 只保留真正用 LLM 做重排的运行；非 llm 模式、发生回退、或无选择结果的一律跳过。
    if rag.get("rag_rerank_mode") != "llm":
        return None
    if rag.get("rag_llm_rerank_fallback_reason"):
        return None
    selected = rag.get("rag_llm_rerank_selected") or []
    if not selected:
        return None
    reasoning = rag.get("rag_llm_rerank_reasoning") or ""

    candidate_ids = rag.get("rag_candidate_card_ids") or []
    if not candidate_ids:
        return None

    candidates = _rebuild_candidate_items(
        candidate_ids,
        rag.get("rag_selected_items", []),
        rag.get("rag_all_scores", []),
    )
    population_features = set(rag.get("rag_population_features") or [])
    outcome_summaries = _load_outcome_summaries(rag.get("rag_outcome_file", ""))

    # 依次从汇总字段、run_summary、运行目录名推断问题类型，都取不到则记为 "unknown"。
    problem = (
        data.get("problem")
        or data.get("run_summary", {}).get("problem")
        or _problem_from_path(summary_path)
        or "unknown"
    )

    # 用与线上一致的模板复原“用户提问”：拼入问题、检索 query、种群特征、候选卡及历史表现。
    user_prompt = _RERANK_PROMPT_V1.format(
        problem=problem,
        query=rag.get("rag_query") or "",
        population_section=_format_population_section(population_features or None),
        candidates_section=_format_candidates_section(
            candidates, outcome_summaries or None
        ),
        top_k=len(selected),
    )

    # assistant 回复即 LLM 当时的真实输出：选中的卡片列表与理由。
    assistant_payload = {"selected": selected, "reasoning": reasoning}

    rs = data.get("run_summary") or {}
    best = rs.get("best_objective")
    baseline = baseline_medians.get(problem)
    improvement_pct = None
    # 相对提升百分比：基线优于结果为正；目标是最小化，故用 (基线 - 结果) / |基线|。
    if best is not None and baseline:
        improvement_pct = (baseline - best) / abs(baseline) * 100

    # conversations 是 RankLLM 兼容的三段式对话；metadata 保留溯源与筛选所需的辅助信息（不参与训练输入）。
    return {
        "conversations": [
            {"role": "system", "value": SYSTEM_MESSAGE},
            {"role": "user", "value": user_prompt},
            {"role": "assistant", "value": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "metadata": {
            "run_tag": summary_path.parent.name,
            "problem": problem,
            "best_objective": best,
            "baseline_median": baseline,
            "improvement_pct": improvement_pct,
            "selected": selected,
            "valid_candidates": rs.get("valid_candidates"),
            "population_feature_count": rag.get("rag_population_feature_count", 0),
            "outcome_summary_count": rag.get("rag_outcome_summary_count", 0),
        },
    }


def _problem_from_path(summary_path: Path) -> str | None:
    """从运行目录名推断问题类型（如 tsp_construct / cvrp_construct / bp_online）。

    匹配不到已知关键字时返回 None，交由上层用其他来源或默认值兜底。
    """
    name = summary_path.parent.name.lower()
    if "tsp_construct" in name:
        return "tsp_construct"
    if "cvrp_construct" in name:
        return "cvrp_construct"
    if "bp_online" in name or "bin_packing" in name:
        return "bp_online"
    return None


def collect_examples(
    runs_dir: Path,
    baseline_medians: dict[str, float],
) -> list[dict[str, Any]]:
    """递归遍历 runs_dir 下所有 official_eoh_run_summary.json，收集全部可用训练样本。

    参数 baseline_medians 透传给 build_example 用于计算提升幅度；
    返回按路径排序、逐个构造成功（非 None）的样本列表。
    """
    examples = []
    # rglob 递归查找汇总文件；排序保证多次运行产出的样本顺序稳定可复现。
    for summary_path in sorted(runs_dir.rglob("official_eoh_run_summary.json")):
        ex = build_example(summary_path, baseline_medians)
        if ex is not None:
            examples.append(ex)
    return examples


def filter_examples(
    examples: list[dict[str, Any]],
    min_improvement_pct: float | None,
    keep_unjudged: bool,
) -> list[dict[str, Any]]:
    """按“相对基线的提升幅度”筛选出高质量的教师样本。

    参数：
      - min_improvement_pct：最低提升阈值；为 None 时不过滤，原样返回。
      - keep_unjudged：当某样本无法计算提升幅度（improvement_pct 为 None）时，是否仍然保留。
    返回：过滤后的样本列表。
    """
    if min_improvement_pct is None:
        return examples
    kept = []
    for ex in examples:
        imp = ex["metadata"]["improvement_pct"]
        # 无法评判提升幅度的样本，仅在显式要求保留时才纳入。
        if imp is None:
            if keep_unjudged:
                kept.append(ex)
            continue
        # 达到阈值的样本视为高质量教师对，予以保留。
        if imp >= min_improvement_pct:
            kept.append(ex)
    return kept


def main() -> None:
    """命令行入口：解析参数，收集并（可选）过滤样本，写出 JSONL，并打印统计信息。"""
    parser = argparse.ArgumentParser(description="Extract LLM rerank training data")
    parser.add_argument(
        "--runs-dir",
        default="eoh_rag_workspace/reports/auto_experiment_reports",
        help="Root directory containing experiment run subdirectories",
    )
    parser.add_argument(
        "--output",
        default="eoh_rag_workspace/training/rerank_sft_data.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--baseline-medians",
        default='{"tsp_construct": 6.44, "cvrp_construct": 13.52}',
        help="JSON object mapping problem -> pure_eoh baseline median",
    )
    parser.add_argument(
        "--min-improvement-pct",
        type=float,
        default=None,
        help="Only keep runs that improved by at least this much vs baseline",
    )
    parser.add_argument(
        "--keep-unjudged",
        action="store_true",
        help="Keep runs where improvement_pct could not be computed",
    )
    args = parser.parse_args()

    # 把 --baseline-medians 的 JSON 字符串解析成 {问题名 -> 基线中位数} 字典。
    baseline_medians = json.loads(args.baseline_medians)

    examples = collect_examples(Path(args.runs_dir), baseline_medians)
    # 仅当给定阈值时才做质量过滤。
    if args.min_improvement_pct is not None:
        examples = filter_examples(examples, args.min_improvement_pct, args.keep_unjudged)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 逐行写出 JSONL：每行一条样本，ensure_ascii=False 以保留中文原文。
    with out_path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # 统计：按问题分布计数，并统计去重后的“选择组合”数量（组合按选中卡片 id 排序后拼接为 key）。
    by_problem: dict[str, int] = defaultdict(int)
    by_selection: dict[str, int] = defaultdict(int)
    for ex in examples:
        by_problem[ex["metadata"]["problem"]] += 1
        sel_key = ",".join(sorted(ex["metadata"]["selected"]))
        by_selection[sel_key] += 1

    print(json.dumps(
        {
            "wrote": str(out_path),
            "total_examples": len(examples),
            "by_problem": dict(by_problem),
            "unique_selections": len(by_selection),
            "min_improvement_pct": args.min_improvement_pct,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
