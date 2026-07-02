"""Extract LLM rerank training data from completed experiment runs.

Reads `official_eoh_run_summary.json` files, rebuilds the rerank prompt that
the LLM saw, pairs it with the LLM's actual selection + reasoning, and emits
RankLLM-compatible `conversations` JSON for SFT training.

Filtering: optionally keep only runs where the resulting objective beat the
problem-specific pure_eoh baseline (high-quality teacher pairs).

Usage:
    python -m eoh_rag.experiments.training.extract_rerank_traces \\
        --runs-dir eoh_rag_workspace/reports/auto_experiment_reports \\
        --output eoh_rag_workspace/training/rerank_sft_data.jsonl \\
        --baseline-medians '{"tsp_construct": 6.44, "cvrp_construct": 13.52}'
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

# Reuse the exact prompt template so train/inference distributions match.
from eoh_rag.rag.llm_reranker import (
    _RERANK_PROMPT_V1,
    _format_candidates_section,
    _format_population_section,
)
from eoh_rag.rag.schemas import CorpusItem

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
    """Rebuild minimal CorpusItem objects for the candidate pool.

    The summary trace stores titles/summaries only for items that were
    eventually injected. For other candidates we fall back to id-only stubs;
    the LLM saw the same level of detail at inference time anyway.
    """
    by_id = {}
    for source in (selected_items, all_scores):
        for entry in source:
            cid = entry.get("id")
            if not cid or cid in by_id:
                continue
            by_id[cid] = entry

    items = []
    for cid in candidate_ids:
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
    """Best-effort load of outcome summaries from a card_outcomes.jsonl file."""
    path = Path(outcome_file)
    if not outcome_file or not path.exists():
        return {}
    try:
        from eoh_rag.rag.card_outcomes import load_outcomes, summarize_all_cards

        outcomes = load_outcomes(path)
        summaries = summarize_all_cards(outcomes)
        from dataclasses import asdict

        return {cid: asdict(summary) for cid, summary in summaries.items()}
    except Exception:
        return {}


def build_example(
    summary_path: Path,
    baseline_medians: dict[str, float],
) -> dict[str, Any] | None:
    """Build one training example from a run summary JSON; return None to skip."""
    try:
        data = json.loads(summary_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    rag = data.get("rag_trace") or {}
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

    # Detect problem from summary or from run dir name
    problem = (
        data.get("problem")
        or data.get("run_summary", {}).get("problem")
        or _problem_from_path(summary_path)
        or "unknown"
    )

    user_prompt = _RERANK_PROMPT_V1.format(
        problem=problem,
        query=rag.get("rag_query") or "",
        population_section=_format_population_section(population_features or None),
        candidates_section=_format_candidates_section(
            candidates, outcome_summaries or None
        ),
        top_k=len(selected),
    )

    assistant_payload = {"selected": selected, "reasoning": reasoning}

    rs = data.get("run_summary") or {}
    best = rs.get("best_objective")
    baseline = baseline_medians.get(problem)
    improvement_pct = None
    if best is not None and baseline:
        improvement_pct = (baseline - best) / abs(baseline) * 100

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
    """Recover problem id from the run directory name."""
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
    examples = []
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
    """Keep only high-quality teacher pairs."""
    if min_improvement_pct is None:
        return examples
    kept = []
    for ex in examples:
        imp = ex["metadata"]["improvement_pct"]
        if imp is None:
            if keep_unjudged:
                kept.append(ex)
            continue
        if imp >= min_improvement_pct:
            kept.append(ex)
    return kept


def main() -> None:
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

    baseline_medians = json.loads(args.baseline_medians)

    examples = collect_examples(Path(args.runs_dir), baseline_medians)
    if args.min_improvement_pct is not None:
        examples = filter_examples(examples, args.min_improvement_pct, args.keep_unjudged)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # Summary
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
