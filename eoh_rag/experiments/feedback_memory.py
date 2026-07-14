"""把历史开发集结果压缩成科研 Agent 可检索的反馈记忆。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Sequence

from eoh_rag.rag.schemas import CorpusItem, save_corpus


def _short_text(value: object, limit: int = 360) -> str:
    """压平模型描述，避免把长响应或代码带入正式记忆资产。"""

    text = " ".join(str(value or "").split())
    return text[:limit]


def collect_dev_samples(report_dirs: Sequence[Path]) -> list[dict[str, Any]]:
    """只读取 EOH 的 samples 文件，不触碰 held-out 报告或最终 population。"""

    records: list[dict[str, Any]] = []
    for report_dir in report_dirs:
        root = report_dir.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"反馈来源目录不存在：{root}")
        sample_paths = sorted(root.glob("**/results/samples/samples_*.json"))
        if not sample_paths:
            raise FileNotFoundError(f"反馈来源中没有 samples 文件：{root}")
        for sample_path in sample_paths:
            payload = json.loads(sample_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"samples 文件必须是 JSON 数组：{sample_path}")
            run_dir = sample_path.parents[2]
            for item in payload:
                if not isinstance(item, dict):
                    raise ValueError(f"samples 条目必须是对象：{sample_path}")
                objective = item.get("objective")
                objective_value = None
                if isinstance(objective, (int, float)) and not isinstance(objective, bool):
                    candidate = float(objective)
                    if math.isfinite(candidate):
                        objective_value = candidate
                records.append(
                    {
                        "suite": root.name,
                        "run": run_dir.relative_to(root).as_posix(),
                        "sample_order": item.get("sample_order"),
                        "operator": _short_text(item.get("operator"), 32),
                        "has_code": bool(item.get("code")),
                        "objective": objective_value,
                        # 只保留自然语言算法摘要；原始代码和完整响应永不写入记忆。
                        "algorithm": _short_text(item.get("algorithm")),
                    }
                )
    return records


def build_feedback_cards(
    records: Sequence[dict[str, Any]],
    *,
    problem: str,
    baseline_objective: float,
    asset_version: str,
    minimum_improvement: float = 0.0001,
) -> list[CorpusItem]:
    """将样本汇总为四张事实卡；卡片只描述反馈，不给出新的手工搜索计划。"""

    if not records:
        raise ValueError("反馈记忆至少需要一条开发集样本")
    if not math.isfinite(baseline_objective):
        raise ValueError("baseline_objective 必须是有限数")

    total = len(records)
    code_records = [item for item in records if item["has_code"]]
    valid_records = [item for item in records if item["objective"] is not None]
    missing_code = total - len(code_records)
    invalid_after_code = len(code_records) - len(valid_records)
    valid_sorted = sorted(valid_records, key=lambda item: float(item["objective"]))
    better_count = sum(
        float(item["objective"]) < baseline_objective - minimum_improvement
        for item in valid_sorted
    )
    suites = sorted({str(item["suite"]) for item in records})
    source_path = ",".join(suites)
    card_prefix = f"history_{problem}_{asset_version}"

    best_objective = float(valid_sorted[0]["objective"]) if valid_sorted else None
    worst_objective = float(valid_sorted[-1]["objective"]) if valid_sorted else None
    best_text = f"{best_objective:.5f}" if best_objective is not None else "none"
    worst_text = f"{worst_objective:.5f}" if worst_objective is not None else "none"

    example_lines = []
    for rank, item in enumerate(valid_sorted[:3], start=1):
        description = item["algorithm"] or "No natural-language description"
        example_lines.append(
            f"Rank {rank}: dev objective={float(item['objective']):.5f}; description={description}"
        )
    if valid_sorted:
        weakest = valid_sorted[-1]
        example_lines.append(
            "Weak example: dev objective="
            f"{float(weakest['objective']):.5f}; description="
            f"{weakest['algorithm'] or 'No natural-language description'}"
        )

    return [
        CorpusItem(
            id=f"{card_prefix}_generation_reliability",
            kind="algorithm_card",
            title="Controller generation reliability feedback",
            tags=["tsp", "history", "controller", "generation"],
            source_path=source_path,
            summary=f"{missing_code} of {total} development samples returned no code.",
            constraints=[
                "Always return the required build_search_plan function.",
                "Return a non-empty list of three-field tuples and no explanatory wrapper.",
            ],
            content=(
                f"Observed development-only outcomes from {len(suites)} frozen cohorts: "
                f"total={total}, no_code={missing_code}, code_returned={len(code_records)}. "
                "This card contains no held-out result and no candidate code."
            ),
        ),
        CorpusItem(
            id=f"{card_prefix}_contract_validity",
            kind="algorithm_card",
            title="Controller contract validity feedback",
            tags=["tsp", "history", "controller", "validity"],
            source_path=source_path,
            summary=(
                f"{invalid_after_code} code-producing samples were invalid; "
                f"{len(valid_records)} of {total} samples were evaluable."
            ),
            constraints=[
                "Use only the documented primitive names, numeric thresholds, and integer step budgets.",
                "Treat total_budget as a weighted limit even when the evaluator can clip overflow.",
            ],
            content=(
                f"Development contract outcomes: valid={len(valid_records)}, "
                f"invalid_after_code={invalid_after_code}. The clip policy preserves a legal prefix, "
                "but a valid full plan gives clearer feedback to evolution."
            ),
        ),
        CorpusItem(
            id=f"{card_prefix}_quality_plateau",
            kind="algorithm_card",
            title="Controller quality plateau feedback",
            tags=["tsp", "history", "controller", "quality"],
            source_path=source_path,
            summary=(
                f"No generated candidate beat the frozen dev baseline; best={best_text}, "
                f"baseline={baseline_objective:.5f}."
            ),
            constraints=[
                "Do not claim progress from validity alone; the development objective must decrease.",
                "Avoid reproducing the unchanged seed plan; use problem_size to test a distinct schedule.",
            ],
            content=(
                f"Across {len(valid_records)} valid development candidates, better_than_baseline={better_count}, "
                f"best={best_text}, worst={worst_text}, baseline={baseline_objective:.5f}. "
                "Explore a genuinely different size-aware ordering, budget split, or stopping rule while "
                "keeping the same safe primitive whitelist."
            ),
        ),
        CorpusItem(
            id=f"{card_prefix}_ranked_outcomes",
            kind="algorithm_card",
            title="Ranked controller outcome memory",
            tags=["tsp", "history", "controller", "outcomes"],
            source_path=source_path,
            summary="Natural-language descriptions are paired with dev objectives for outcome-aware reuse.",
            constraints=[
                "Use these descriptions as evidence, not as instructions to copy a candidate.",
                "Prefer hypotheses that differ from both the best and weakest observed descriptions.",
            ],
            content="\n".join(example_lines) or "No valid development examples were available.",
        ),
    ]


def write_feedback_memory(
    report_dirs: Sequence[Path],
    output_path: Path,
    *,
    problem: str,
    baseline_objective: float,
    asset_version: str,
) -> dict[str, Any]:
    """生成并写出冻结 JSONL，同时返回不含原始响应的摘要。"""

    records = collect_dev_samples(report_dirs)
    cards = build_feedback_cards(
        records,
        problem=problem,
        baseline_objective=baseline_objective,
        asset_version=asset_version,
    )
    save_corpus(cards, output_path)
    return {
        "output": str(output_path.resolve()),
        "source_suites": sorted({str(item["suite"]) for item in records}),
        "sample_count": len(records),
        "code_count": sum(bool(item["has_code"]) for item in records),
        "valid_count": sum(item["objective"] is not None for item in records),
        "card_ids": [card.id for card in cards],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dev-only feedback RAG memory")
    parser.add_argument("--report-dir", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--problem", default="tsp_search_controller")
    parser.add_argument("--baseline-objective", type=float, required=True)
    parser.add_argument("--asset-version", default="feedback_v1")
    args = parser.parse_args()

    summary = write_feedback_memory(
        [Path(path) for path in args.report_dir],
        Path(args.output),
        problem=args.problem,
        baseline_objective=args.baseline_objective,
        asset_version=args.asset_version,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
