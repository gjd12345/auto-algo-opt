"""
模块：backfill_card_outcomes（卡片效果记忆回填工具）
功能：从已保存的实验汇总文件 summary.json 中反推每张“知识卡片”的使用效果，
      生成一份符合 CardOutcomeRecord 结构的效果记忆，供“带效果感知的重排序”做冷启动。
职责：读取汇总目录下每个实验套件的 summary.json；把其中的
      success_funnel（漏斗明细）与 problems（各问题的运行行）拆成一条条以“卡片”为主体的
      CardOutcomeRecord 记录；再统计各卡片的整体表现并写出 JSONL 数据与 Markdown 报告。
接口：build_backfill_records(reports_dir) -> list[CardOutcomeRecord] 构建全部回填记录；
      summarize_backfill(records) -> dict 汇总统计；
      write_report(path, summary) 写 Markdown 报告；
      main() 命令行入口。
输入：--reports-dir 指向汇总报告目录（内含 <套件>/summary.json）；
      --output 指定输出的 card_outcomes.jsonl 路径；
      --report 指定输出的 Markdown 报告路径。
输出：一份 card_outcomes.jsonl（每行一条卡片效果记录）、一份 Markdown 汇总报告，
      并把统计摘要以 JSON 形式打印到标准输出。
示例：python -m eoh_rag.experiments.reports.backfill_card_outcomes \
          --reports-dir eoh_rag_workspace/reports/auto_experiment_reports
"""
from __future__ import annotations

# 标准库依赖：命令行解析、JSON 读写、数学取整、计数器、dataclass 转字典、路径与类型标注
import argparse
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

# 复用效果记忆的数据结构与工具：记录类型、卡片组合 ID、决策提示、落盘与汇总函数
from eoh_rag.rag.card_outcomes import (
    CardOutcomeRecord,
    compute_card_set_id,
    compute_decision_hint,
    save_outcomes,
    summarize_all_cards,
)


# 回填记录统一使用的时间戳（原始运行时间不可得，用固定值标记为回填数据）
BACKFILL_TIMESTAMP = "2026-06-28T00:00:00Z"
# 证据来源层级：来自漏斗明细（success_funnel），是汇总里最强的证据
TIER_FUNNEL = "summary_backfill_funnel"
# 证据来源层级：来自各问题的运行行（problems[].rows），覆盖更广但可信度略弱
TIER_PROBLEM_ROW = "summary_backfill_problem_row"


def _load_json(path: Path) -> dict[str, Any]:
    """读取 JSON 文件并解析为字典（按 UTF-8 编码）。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _card_source(card_id: str) -> str:
    """根据卡片 ID 前缀判断来源：以 history_ 开头视为历史经验，否则视为文献。"""
    return "history" if card_id.startswith("history_") else "literature"


def _parse_valid(value: str | None) -> tuple[int, int]:
    """解析形如 "有效数/总数" 的字符串，返回 (有效候选数, 种群总数)。

    传入空值或不含 "/" 时返回 (0, 0)；数字解析失败也退化为 (0, 0)。
    """
    if not value or "/" not in value:
        return 0, 0
    left, right = value.split("/", 1)
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return 0, 0


def _repeat_from_id(run_id: str) -> int | None:
    """从运行 ID 中抽取重复实验编号：取 ":r" 之后的数字，取不到则返回 None。"""
    marker = ":r"
    if marker not in run_id:
        return None
    try:
        return int(run_id.rsplit(marker, 1)[1])
    except ValueError:
        return None


def _delta_pct(best: float | None, baseline: float | None) -> float | None:
    """计算相对基线的变化百分比（保留两位小数）；缺少数据或基线为 0 时返回 None。"""
    if best is None or baseline in (None, 0):
        return None
    return round((best - baseline) / abs(baseline) * 100, 2)


def _objective_success(best: float | None, baseline: float | None) -> bool:
    """判断目标是否达标：最优值与基线都存在，且最优值严格优于（小于）基线。"""
    return best is not None and baseline is not None and best < baseline


def _collapse_failure(
    *,
    valid_candidates: int,
    population_size: int,
    expected_pop: int | None,
    failure_reason: str | None,
) -> str | None:
    """推断该次运行的失败原因；识别“有效个体骤减”这类种群坍缩情况。

    已有明确失败原因时原样返回；否则当实际种群或有效个体明显少于预期时，
    判定为 "valid_collapse"（有效候选坍缩），其余情况返回 None。
    """
    if failure_reason:
        return failure_reason
    # 实际种群规模不足预期，视为坍缩
    if expected_pop and population_size < expected_pop:
        return "valid_collapse"
    # 有效候选数不足预期规模的一半（且至少要有 2 个），也视为坍缩
    if expected_pop and valid_candidates < max(2, math.ceil(0.5 * expected_pop)):
        return "valid_collapse"
    return None


def _record(
    *,
    suite: str,
    source_path: Path,
    confidence: str,
    run_id: str,
    problem: str,
    arm: str,
    generation: int,
    repeat: int | None,
    cards: list[str],
    card_id: str,
    card_rank: int,
    population_size: int,
    valid_candidates: int,
    best_objective: float | None,
    pure_baseline: float | None,
    generation_success: bool,
    objective_success: bool,
    failure_reason: str | None,
) -> CardOutcomeRecord:
    """把单张卡片在某次运行中的表现，组装成一条 CardOutcomeRecord 效果记录。

    关键入参：cards 为该次运行选用的全部卡片，card_id/card_rank 是本条针对的卡片及其排名；
    population_size/valid_candidates 用于算有效率；best_objective/pure_baseline 用于算相对提升。
    返回：填好各字段（含由 compute_decision_hint 推出的 decision_hint）的效果记录。
    """
    # 有效率 = 有效候选数 / 种群规模（分母做下限保护，避免除零）
    valid_rate = valid_candidates / max(population_size, 1)
    # 依据是否进化成功、是否达标、有效率与失败原因，推出正/中/负向的决策提示
    decision = compute_decision_hint(
        generation_success=generation_success,
        objective_success=objective_success,
        valid_rate=valid_rate,
        failure_reason=failure_reason,
    )
    return CardOutcomeRecord(
        run_id=run_id,
        # 证据来源路径带上 confidence 标签，便于回溯这条记录来自哪一层
        trace_path=f"{source_path.as_posix()}#{confidence}",
        problem=problem,
        arm=arm,
        generation=generation,
        repeat=repeat,
        card_set_id=compute_card_set_id(cards),
        selected_card_ids=list(cards),
        card_id=card_id,
        card_rank=card_rank,
        card_source=_card_source(card_id),
        # 汇总数据不保留注入细节，统一假设为“完整注入”
        injection_status="full_assumed",
        injected_chars=0,
        population_size=population_size,
        valid_candidates=valid_candidates,
        valid_rate=round(valid_rate, 4),
        best_objective=best_objective,
        pure_baseline=pure_baseline,
        delta_pct=_delta_pct(best_objective, pure_baseline),
        generation_success=generation_success,
        objective_success=objective_success,
        failure_reason=failure_reason,
        decision_hint=decision,
        confidence=confidence,
        timestamp=BACKFILL_TIMESTAMP,
    )


def _suite_problem_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """把汇总中 problems 下各问题的运行行摊平成一个列表。

    为每行补上所属 problem 与从 1 开始的行号 row_index，并过滤掉没有选用任何卡片的行。
    """
    rows: list[dict[str, Any]] = []
    for problem, problem_rows in (summary.get("problems") or {}).items():
        for row_index, row in enumerate(problem_rows, start=1):
            cards = [card for card in (row.get("cards") or []) if card]
            if not cards:
                continue
            rows.append({"problem": problem, "row_index": row_index, **row, "cards": cards})
    return rows


def _problem_baselines(summary: dict[str, Any]) -> dict[str, float]:
    """为每个问题确定纯基线目标值（后续用于计算相对提升）。

    先取该问题下 pure_eoh 组各行 best 的均值作为基线；
    若漏斗数据里给出了 pure_baselines，则以其为准覆盖上面的均值。
    """
    baselines: dict[str, float] = {}
    for problem, rows in (summary.get("problems") or {}).items():
        # 收集纯基线组（arm 为 pure_eoh）中数值型的 best
        pure = [
            row.get("best")
            for row in rows
            if row.get("arm") == "pure_eoh" and isinstance(row.get("best"), (int, float))
        ]
        if pure:
            baselines[problem] = sum(pure) / len(pure)
    # 漏斗里若直接给了基线，优先采用
    for problem, baseline in ((summary.get("success_funnel") or {}).get("pure_baselines") or {}).items():
        if isinstance(baseline, (int, float)):
            baselines[problem] = baseline
    return baselines


def _successful_problem_row_cards(summary: dict[str, Any]) -> dict[str, set[str]]:
    """按问题收集“出现在成功运行行里的卡片集合”。

    某行既没有失败原因、目标又达标时，视为成功，把该行选用的卡片计入对应问题。
    返回 {问题名: 成功卡片集合}，供后续避免误伤这些卡片。
    """
    successful: dict[str, set[str]] = {}
    baselines = _problem_baselines(summary)
    for row in _suite_problem_rows(summary):
        problem = str(row.get("problem") or "")
        # valid 字段形如 "有效/总数"，据此拿到有效候选数与观测到的种群规模
        valid_candidates, observed_population = _parse_valid(row.get("valid"))
        # pop 为该问题设定的期望种群规模
        expected_pop = row.get("pop") if isinstance(row.get("pop"), int) else None
        population_size = observed_population or expected_pop or valid_candidates
        failure_reason = _collapse_failure(
            valid_candidates=valid_candidates,
            population_size=population_size,
            expected_pop=expected_pop,
            failure_reason=row.get("failure_reason"),
        )
        best = row.get("best")
        baseline = baselines.get(problem)
        # 无失败原因且目标达标，才认定为成功行
        if failure_reason is None and _objective_success(best, baseline):
            successful.setdefault(problem, set()).update(row.get("cards") or [])
    return successful


def _funnel_records(summary_path: Path, summary: dict[str, Any]) -> tuple[list[CardOutcomeRecord], set[tuple[str, str, int, tuple[str, ...]]]]:
    """从最强证据层 success_funnel.per_run 生成卡片效果记录。

    对每次运行按 (问题, 分支, 代数, 卡片组合) 记为一个分组键，并逐张卡片展开成记录。
    返回：(记录列表, 已覆盖分组集合)；后者用于避免弱证据层重复统计同一批运行。
    """
    # 套件名取自 summary.json 所在目录名
    suite = summary_path.parent.name
    records: list[CardOutcomeRecord] = []
    covered_groups: set[tuple[str, str, int, tuple[str, ...]]] = set()
    for row in (summary.get("success_funnel") or {}).get("per_run") or []:
        cards = [card for card in (row.get("selected_card_ids") or []) if card]
        if not cards:
            continue
        population_size = int(row.get("population_size") or 0)
        valid_candidates = int(row.get("valid_candidates") or 0)
        if population_size <= 0:
            continue
        problem = str(row.get("problem") or "")
        arm = str(row.get("arm") or "")
        generation = int(row.get("gen") or 0)
        # 优先用原始运行 ID，缺失时按 问题:分支:代数 拼一个占位 ID
        run_id = str(row.get("best_code_record_id") or f"{problem}:{arm}:g{generation}:funnel")
        baseline = row.get("pure_baseline")
        best = row.get("best_objective")
        failure_reason = row.get("failure_reason")
        generation_success = bool(row.get("generation_success"))
        # 达标标记优先取字段值，缺失时按最优值与基线比较推断
        objective_success = bool(row.get("objective_success")) if row.get("objective_success") is not None else _objective_success(best, baseline)
        group_key = (problem, arm, generation, tuple(cards))
        covered_groups.add(group_key)
        # 同一次运行选用的每张卡片各记一条，rank 为卡片在组合中的次序
        for rank, card_id in enumerate(cards, start=1):
            records.append(_record(
                suite=suite,
                source_path=summary_path,
                confidence=TIER_FUNNEL,
                run_id=run_id,
                problem=problem,
                arm=arm,
                generation=generation,
                repeat=_repeat_from_id(run_id),
                cards=cards,
                card_id=card_id,
                card_rank=rank,
                population_size=population_size,
                valid_candidates=valid_candidates,
                best_objective=best,
                pure_baseline=baseline,
                generation_success=generation_success,
                objective_success=objective_success,
                failure_reason=failure_reason,
            ))
    return records, covered_groups


def _problem_row_records(
    summary_path: Path,
    summary: dict[str, Any],
    covered_funnel_groups: set[tuple[str, str, int, tuple[str, ...]]],
) -> list[CardOutcomeRecord]:
    """从各问题运行行生成弱证据层记录，跳过已被漏斗层覆盖的分组。

    覆盖面比漏斗层更广，用于补齐漏斗未记录的运行；结果与漏斗记录合并后一起统计。
    """
    suite = summary_path.parent.name
    baselines = _problem_baselines(summary)
    # 预先收集各问题的成功卡片，冷启动时用于保护同问题里已被验证有效的卡片
    successful_cards = _successful_problem_row_cards(summary)
    rows = _suite_problem_rows(summary)
    # 为相同 (问题, 分支, 代数, 卡片组合) 计数，充当重复实验编号
    counters: Counter[tuple[str, str, int, tuple[str, ...]]] = Counter()
    records: list[CardOutcomeRecord] = []
    for row in rows:
        problem = str(row.get("problem") or "")
        arm = str(row.get("arm") or "")
        generation = int(row.get("gen") or 0)
        cards = list(row.get("cards") or [])
        group_key = (problem, arm, generation, tuple(cards))
        # 漏斗层已记过的分组直接跳过，避免重复统计
        if group_key in covered_funnel_groups:
            continue
        counters[group_key] += 1
        repeat = counters[group_key]
        valid_candidates, observed_population = _parse_valid(row.get("valid"))
        expected_pop = row.get("pop") if isinstance(row.get("pop"), int) else None
        population_size = observed_population or expected_pop or valid_candidates
        best = row.get("best")
        baseline = baselines.get(problem)
        row_failure_reason = _collapse_failure(
            valid_candidates=valid_candidates,
            population_size=population_size,
            expected_pop=expected_pop,
            failure_reason=row.get("failure_reason"),
        )
        # 未坍缩、且有效候选数达到期望规模一半以上，才算进化成功
        row_generation_success = row_failure_reason != "valid_collapse" and (
            valid_candidates >= max(2, math.ceil(0.5 * (expected_pop or population_size or 1)))
        )
        objective_success = _objective_success(best, baseline)
        run_id = f"{problem}:{arm}:g{generation}:r{repeat}:summary_backfill"
        for rank, card_id in enumerate(cards, start=1):
            # 多卡片归因存在歧义：若某卡片在同一问题的成功组合里也出现过，
            # 就不因为“这个组合整体坍缩”而单独给它记为失败（冷启动阶段避免误伤）。
            failure_reason = row_failure_reason
            generation_success = row_generation_success
            if row_failure_reason == "valid_collapse" and card_id in successful_cards.get(problem, set()):
                failure_reason = None
                generation_success = False
            records.append(_record(
                suite=suite,
                source_path=summary_path,
                confidence=TIER_PROBLEM_ROW,
                run_id=run_id,
                problem=problem,
                arm=arm,
                generation=generation,
                repeat=repeat,
                cards=cards,
                card_id=card_id,
                card_rank=rank,
                population_size=population_size,
                valid_candidates=valid_candidates,
                best_objective=best,
                pure_baseline=baseline,
                generation_success=generation_success,
                objective_success=objective_success,
                failure_reason=failure_reason,
            ))
    return records


def build_backfill_records(reports_dir: Path) -> list[CardOutcomeRecord]:
    """扫描报告目录下所有 <套件>/summary.json，构建全部卡片效果回填记录。

    每个套件先取漏斗层记录，再补充未被覆盖的问题行记录；最后按稳定顺序排序返回。
    """
    records: list[CardOutcomeRecord] = []
    for summary_path in sorted(reports_dir.glob("*/summary.json")):
        summary = _load_json(summary_path)
        # 先取强证据（漏斗层），并拿到其覆盖的分组
        funnel_records, covered_groups = _funnel_records(summary_path, summary)
        records.extend(funnel_records)
        # 再用弱证据（问题行）补齐漏斗未覆盖的部分
        records.extend(_problem_row_records(summary_path, summary, covered_groups))
    # 统一排序，保证多次运行产出的记录顺序稳定
    records.sort(key=lambda r: (r.problem, r.arm, r.generation, r.repeat or 0, r.card_rank, r.card_id, r.confidence))
    return records


def summarize_backfill(records: list[CardOutcomeRecord]) -> dict[str, Any]:
    """汇总全部回填记录，产出可打印/可写报告的统计字典。

    包含记录总数、卡片数，以及按证据层、问题、决策提示、卡片的分布，
    并附上每张卡片的整体决策摘要（来自 summarize_all_cards）。
    """
    by_confidence = Counter(r.confidence for r in records)
    by_problem = Counter(r.problem for r in records)
    by_card = Counter(r.card_id for r in records)
    by_decision = Counter(r.decision_hint for r in records)
    summaries = summarize_all_cards(records)
    return {
        "records": len(records),
        "cards": len(summaries),
        "by_confidence": dict(sorted(by_confidence.items())),
        "by_problem": dict(sorted(by_problem.items())),
        "by_decision_hint": dict(sorted(by_decision.items())),
        "by_card": dict(by_card.most_common()),
        "card_decisions": {
            card_id: asdict(summary)
            for card_id, summary in summaries.items()
        },
    }


def write_report(path: Path, summary: dict[str, Any]) -> None:
    """把统计摘要渲染成 Markdown 报告并写入指定路径（自动创建父目录）。

    报告含证据分层说明、各类计数、每张卡片的覆盖表；对“正例证据+正向均值提升”的卡片
    额外给出高方差提醒，末尾附上口径与注意事项。
    """
    lines = [
        "# Card Outcome Backfill Report",
        "",
        "This report records the summary-derived cold-start outcome memory generated from archived `summary.json` files.",
        "",
        "## Source Tiers",
        "",
        "| tier | confidence | use |",
        "|---|---|---|",
        "| A | `summary_backfill_funnel` | Uses `success_funnel.per_run.selected_card_ids`; strongest summary source. |",
        "| B | `summary_backfill_problem_row` | Uses `problems[].rows[].cards`; broader coverage, weaker than raw trace. |",
        "| C | manual notes | `best_results.md` is not written into JSONL; use only as audit notes. |",
        "",
        "## Counts",
        "",
        f"- records: `{summary['records']}`",
        f"- cards: `{summary['cards']}`",
        f"- by_confidence: `{summary['by_confidence']}`",
        f"- by_problem: `{summary['by_problem']}`",
        f"- by_decision_hint: `{summary['by_decision_hint']}`",
        "",
        "## Card Coverage",
        "",
        "| card | records | decision | avg_valid_rate | avg_delta_pct | positive | negative | collapse |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for card_id, card_summary in summary["card_decisions"].items():
        lines.append(
            "| {card} | {total} | {decision} | {valid:.4f} | {delta} | {pos} | {neg} | {collapse} |".format(
                card=card_id,
                total=card_summary["total_injections"],
                decision=card_summary["decision"],
                valid=card_summary["avg_valid_rate"],
                delta="-" if card_summary["avg_delta_pct"] is None else card_summary["avg_delta_pct"],
                pos=card_summary["positive_count"],
                neg=card_summary["negative_count"],
                collapse=card_summary["collapse_count"],
            )
        )
    # 挑出决策为 boost 但平均提升为正的卡片：证据不稳定，需在报告里提醒谨慎对待
    unstable_boosts = [
        (card_id, card_summary)
        for card_id, card_summary in summary["card_decisions"].items()
        if card_summary["decision"] == "boost"
        and card_summary["avg_delta_pct"] is not None
        and card_summary["avg_delta_pct"] > 0
    ]
    if unstable_boosts:
        lines.extend([
            "",
            "## Interpretation Warnings",
            "",
            "These cards have positive-count evidence but positive average delta; treat them as high-variance exploratory signals, not stable boosts:",
            "",
            "| card | records | avg_delta_pct | positive | negative |",
            "|---|---:|---:|---:|---:|",
        ])
        for card_id, card_summary in unstable_boosts:
            lines.append(
                "| {card} | {total} | {delta} | {pos} | {neg} |".format(
                    card=card_id,
                    total=card_summary["total_injections"],
                    delta=card_summary["avg_delta_pct"],
                    pos=card_summary["positive_count"],
                    neg=card_summary["negative_count"],
                )
            )
    lines.extend([
        "",
        "## Caveats",
        "",
        "- `injection_status` is `full_assumed`; archived summaries do not preserve `rag_injected_items` or truncation metadata.",
        "- `injected_chars` is `0` for all backfilled rows.",
        "- Treat this as cold-start evidence for rerank smoke tests, not as full-fidelity raw trace evidence.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """命令行入口：解析参数，构建回填记录，写出 JSONL 与 Markdown，并打印统计摘要。"""
    parser = argparse.ArgumentParser(description="Backfill card_outcomes.jsonl from archived summary.json reports")
    parser.add_argument("--reports-dir", default="eoh_rag_workspace/reports/auto_experiment_reports")
    parser.add_argument("--output", default="eoh_rag_workspace/rag/corpus/card_outcomes.jsonl")
    parser.add_argument("--report", default="eoh_rag_workspace/reports/outcomes/card_outcome_backfill_report.md")
    args = parser.parse_args()

    # 构建全部效果记录
    records = build_backfill_records(Path(args.reports_dir))
    # 覆盖写出 JSONL（append=False 表示每次重新生成完整数据）
    save_outcomes(records, Path(args.output), append=False)
    # 统计并输出 Markdown 报告
    summary = summarize_backfill(records)
    write_report(Path(args.report), summary)
    # 把摘要以 JSON 打印到标准输出，便于流水线捕获
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
