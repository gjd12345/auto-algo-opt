"""Auto Summarizer for experiment manifest runs.

Reads run_index.json + individual run summaries, generates
Chinese markdown report with per-problem tables, code snippets,
card decisions, and next actions.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _find_project_root(start: str | Path) -> Path:
    """Walk up from *start* until a directory containing ``eoh_rag/`` is found."""
    p = Path(start).resolve()
    for _ in range(10):
        if (p / "eoh_rag").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    # Fallback: try cwd
    cwd = Path.cwd()
    if (cwd / "eoh_rag").is_dir():
        return cwd
    raise FileNotFoundError(f"Cannot find project root from {start}")


def _load_summary(path: Path) -> dict[str, Any] | None:
    summary_path = path / "official_eoh_run_summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _best_code_snippet(code: str | None, max_lines: int = 12) -> str:
    if not code:
        return "（无代码）"
    lines = code.strip().split("\n")
    body: list[str] = []
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("import ", "from ", "#")):
            continue
        if '"""' in stripped or "'''" in stripped:
            marker = '"""' if '"""' in stripped else "'''"
            if stripped.count(marker) % 2 == 1:
                in_docstring = not in_docstring
            continue
        if in_docstring:
            continue
        if stripped in {"Args:", "Returns:"} or stripped.endswith(": ID of the current node"):
            continue
        body.append(line.rstrip())
    if len(body) < 3:
        body = [line.rstrip() for line in lines if line.strip()][:max_lines]
    snippet = "\n".join(body[:max_lines])
    return f"```python\n{snippet}\n```"


def _card_source_from_ids(card_ids: list[str]) -> str:
    if not card_ids:
        return "none"
    has_history = any(card_id.startswith("history_") for card_id in card_ids)
    has_non_history = any(not card_id.startswith("history_") for card_id in card_ids)
    if has_history and has_non_history:
        return "mixed"
    if has_history:
        return "history"
    return "literature"


def _compute_success_funnel(
    run_data: dict[str, Any],
    rag_trace: dict[str, Any] | None,
    pure_baseline: float | None,
) -> dict[str, Any]:
    """Compute the five-layer success funnel for a single run.

    Layers (aligned with HeuriGym 4-stage error classification):
    1. proposal_accept: run completed without infrastructure failure
    2. linkage_success: selected_card_ids matched rag_trace (if RAG arm)
    3. generation_success: valid_candidates >= max(2, ceil(0.5 * pop_size))
    4. objective_success: best < pure_baseline (minimize) or best > pure_baseline (maximize)
    5. diagnosis_success: requires agent pipeline data (marked as unknown here)

    Returns dict with boolean fields + computed stats.
    """
    run_sum = run_data.get("run_summary", {})
    valid = run_sum.get("valid_candidates", 0)
    pop = run_sum.get("population_size", 0)
    best = run_sum.get("best_objective")
    failure = run_sum.get("failure_reason")
    return_code = run_data.get("return_code", 0)

    # Layer 1: Proposal accept — run executed without infra failure
    proposal_accept = (return_code == 0 and not failure)

    # Layer 2: Linkage success — cards actually injected match requested
    linkage_success = None  # unknown by default
    selected = []
    if rag_trace and isinstance(rag_trace, dict):
        selected = [item.get("id", "") for item in rag_trace.get("rag_selected_items", [])]
        if selected:
            linkage_success = True  # cards were injected
        else:
            linkage_success = False  # RAG arm but no cards injected

    # Layer 3: Generation success — enough valid candidates
    min_valid = max(2, int(__import__("math").ceil(0.5 * pop))) if pop > 0 else 1
    generation_success = (valid >= min_valid) if pop > 0 else None

    # Layer 4: Objective success — better than pure baseline
    objective_success = None
    if best is not None and pure_baseline is not None:
        objective_success = best < pure_baseline  # minimize direction

    # Layer 5: Diagnosis success — requires agent pipeline
    diagnosis_success = None

    return {
        "proposal_accept": proposal_accept,
        "linkage_success": linkage_success,
        "generation_success": generation_success,
        "objective_success": objective_success,
        "diagnosis_success": diagnosis_success,
        "failure_reason": failure,
        "valid_candidates": valid,
        "population_size": pop,
        "best_objective": best,
        "pure_baseline": pure_baseline,
        "card_source": _card_source_from_ids(selected),
        "selected_card_ids": selected,
        "history_card_ids": [card_id for card_id in selected if card_id.startswith("history_")],
    }


def _compute_funnel_summary(funnels: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate funnel results across runs."""
    layers = ["proposal_accept", "linkage_success", "generation_success", "objective_success"]
    summary: dict[str, Any] = {"total_runs": len(funnels)}
    for layer in layers:
        known = [f[layer] for f in funnels if f.get(layer) is not None]
        if known:
            summary[layer] = {
                "passed": sum(1 for v in known if v),
                "total": len(known),
                "rate": round(sum(1 for v in known if v) / len(known), 3) if known else 0,
            }
        else:
            summary[layer] = {"passed": 0, "total": 0, "rate": 0, "note": "insufficient data"}
    return summary


def summarize(input_dir: str, no_card_memory: bool = False) -> dict[str, Any]:
    root = Path(input_dir).resolve()
    index_path = root / "run_index.json"
    if not index_path.exists():
        return {"error": f"run_index.json not found in {root}"}

    runs = json.loads(index_path.read_text(encoding="utf-8"))
    problems = defaultdict(list)
    for run in runs:
        problems[run["problem"]].append(run)

    # --- Compute pure baselines per problem ---
    pure_baselines: dict[str, float] = {}
    for problem, problem_runs in problems.items():
        pure_bests = []
        for run in problem_runs:
            if run["arm"] == "pure_eoh":
                s = _load_summary(Path(run["output_dir"]))
                if s:
                    rs = s.get("run_summary", {})
                    b = rs.get("best_objective")
                    if b is not None:
                        pure_bests.append(b)
        if pure_bests:
            pure_baselines[problem] = sum(pure_bests) / len(pure_bests)

    # --- Per-problem tables ---
    summary: dict[str, Any] = {"suite": root.name, "problems": {}, "success_funnel": {}}
    all_funnels: list[dict[str, Any]] = []

    for problem, problem_runs in sorted(problems.items()):
        rows = []
        for run in problem_runs:
            s = _load_summary(Path(run["output_dir"]))
            if not s:
                rows.append({
                    "arm": run["arm"],
                    "gen": run["generation"],
                    "status": run.get("status", "unknown"),
                    "best": None,
                    "valid": None,
                    "cards": [],
                })
                continue

            run_sum = s.get("run_summary", {})
            rag = s.get("rag_trace") or {}
            cards = [item.get("id", "") for item in rag.get("rag_selected_items", [])]

            # Compute success funnel + normalized score
            baseline = pure_baselines.get(problem)
            funnel = _compute_success_funnel(s, rag, baseline)
            funnel["problem"] = problem
            funnel["arm"] = run["arm"]
            funnel["gen"] = run["generation"]
            best_code_record_id = f"{problem}:{run['arm']}:g{run['generation']}:r{run.get('repeat', '?')}"
            funnel["best_code_record_id"] = best_code_record_id
            funnel["synthesized_card_id"] = None
            funnel["synthesized_card_written"] = False
            all_funnels.append(funnel)

            best_val = run_sum.get("best_objective")
            norm_score = None
            delta_pct = None
            if best_val is not None and baseline is not None and baseline > 0:
                norm_score = round(baseline / best_val, 4)  # >1 = improvement for minimize
                delta_pct = round((best_val - baseline) / baseline * 100, 1)

            rows.append({
                "arm": run["arm"],
                "gen": run["generation"],
                "pop": s.get("pop_size"),
                "status": run.get("status", "ok"),
                "best": best_val,
                "valid": f"{run_sum.get('valid_candidates',0)}/{run_sum.get('population_size',0)}",
                "cards": cards,
                "card_source": funnel["card_source"],
                "history_card_ids": funnel["history_card_ids"],
                "best_code_record_id": best_code_record_id,
                "synthesized_card_id": None,
                "norm_score": norm_score,
                "delta_pct": delta_pct,
                "code_snippet": _best_code_snippet(run_sum.get("best_code")),
                "algorithm": run_sum.get("best_algorithm", ""),
                "runtime_s": s.get("runtime_seconds"),
                "funnel": {k: funnel[k] for k in [
                    "proposal_accept", "linkage_success", "generation_success",
                    "objective_success", "failure_reason",
                ]},
            })

            # --- Best-code → Card feedback loop ---
            if funnel.get("objective_success") and not no_card_memory:
                best_code = run_sum.get("best_code")
                if best_code:
                    try:
                        from eoh_rag.rag.card_synthesis import (
                            extract_strategy_features,
                            synthesize_card,
                            append_card_to_corpus,
                        )
                        from eoh_rag.rag.build_corpus import default_corpus_dir
                        features = extract_strategy_features(best_code)
                        if features:
                            card = synthesize_card(
                                problem=problem,
                                code=best_code,
                                features=features,
                                run_info={
                                    "run_dir": run.get("output_dir", ""),
                                    "objective": best_val,
                                    "generation": run["generation"],
                                },
                            )
                            # Find project root by walking up to the dir containing eoh_rag/
                            project_root = _find_project_root(run.get("output_dir", str(root)))
                            corpus_dir = default_corpus_dir(project_root)
                            written = append_card_to_corpus(card, corpus_dir)
                            funnel["synthesized_card_id"] = card.id
                            funnel["synthesized_card_written"] = written
                            rows[-1]["synthesized_card_id"] = card.id
                            if written:
                                print(f"  [card-synthesis] New card: {card.id}")
                    except Exception as exc:
                        print(f"  [card-synthesis] Warning: {exc}")

            # --- Card Outcome Memory: record per-card evidence ---
            if rag and not no_card_memory:
                try:
                    from eoh_rag.rag.card_outcomes import build_outcome_records, save_outcomes
                    from eoh_rag.rag.build_corpus import default_corpus_dir

                    injected_items = rag.get("rag_injected_items", [])
                    if not injected_items:
                        injected_items = [
                            {"id": item.get("id", ""), "kind": item.get("kind", ""),
                             "section": "strategy", "status": "full", "chars": 0}
                            for item in rag.get("rag_selected_items", [])
                        ]
                    audit_for_outcome = {
                        "rag_injected_items": injected_items,
                        "rag_omitted_items": rag.get("rag_omitted_items", []),
                        "rag_truncated_item_id": rag.get("rag_truncated_item_id"),
                        "rag_context_truncated": rag.get("rag_context_truncated", False),
                    }
                    gen_result = {
                        "population_size": run_sum.get("population_size", 0),
                        "valid_candidates": run_sum.get("valid_candidates", 0),
                        "best_objective": best_val,
                        "pure_baseline": baseline,
                        "generation_success": funnel.get("generation_success", False),
                        "objective_success": funnel.get("objective_success", False),
                        "failure_reason": funnel.get("failure_reason"),
                    }
                    outcome_records = build_outcome_records(
                        run_id=best_code_record_id,
                        problem=problem,
                        generation=run["generation"],
                        injection_audit=audit_for_outcome,
                        generation_result=gen_result,
                        arm=run["arm"],
                        repeat=run.get("repeat"),
                        trace_path=str(Path(run.get("output_dir", "")) / "summary.json"),
                    )
                    if outcome_records:
                        project_root = _find_project_root(run.get("output_dir", str(root)))
                        outcomes_path = Path(default_corpus_dir(project_root)) / "card_outcomes.jsonl"
                        save_outcomes(outcome_records, outcomes_path, append=True)
                except Exception as exc:
                    print(f"  [card-outcomes] Warning: {exc}")

        # Sort: pure -> api -> default -> targeted, then by gen
        arm_order = {"pure_eoh": 0, "api_only": 1, "default_rag": 2, "targeted_rag": 3,
                     "tocc_corrected": 4}
        rows.sort(key=lambda r: (arm_order.get(r["arm"], 99), r.get("gen", 0)))

        summary["problems"][problem] = rows

    # --- Funnel summary ---
    summary["success_funnel"] = _compute_funnel_summary(all_funnels)
    summary["success_funnel"]["pure_baselines"] = pure_baselines
    summary["success_funnel"]["per_run"] = all_funnels

    return summary


def _write_markdown(summary: dict[str, Any], output_path: str) -> None:
    lines = [
        f"# 自动化实验报告：{summary['suite']}",
        "",
        "本报告由 Auto Summarizer 自动生成。结论措辞遵循 exploratory 约束：",
        "不写'已证明''稳定优于''sweet spot 已确定'等无统计支持的强结论。",
        "",
        "## 汇总表",
        "",
        "| problem | arm | gen | pop | best | norm | Δ% | valid | card_source | cards | status |",
        "|---|---|---:|---:|---:|---:|---:|---|---|---|---|",
    ]

    for problem, rows in sorted(summary.get("problems", {}).items()):
        for row in rows:
            cards_str = ", ".join(row.get("cards", [])) or "-"
            status = row.get("status", "")
            if isinstance(status, str) and "exit_" in status:
                status = "FAILED"
            elif isinstance(status, str) and status.startswith("ok"):
                status = "OK"
            norm_str = f"{row.get('norm_score',''):.3f}" if row.get('norm_score') is not None else "-"
            delta_str = f"{row.get('delta_pct',''):+.1f}%" if row.get('delta_pct') is not None else "-"
            lines.append(
                f"| {problem} | {row['arm']} | {row.get('gen','')} | {row.get('pop','')} | "
                f"{row.get('best','') or '-'} | {norm_str} | {delta_str} | "
                f"{row.get('valid','')} | {row.get('card_source','none')} | {cards_str} | {status} |"
            )

    lines.extend([
        "",
        "## 代码片段",
        "",
    ])
    for problem, rows in sorted(summary.get("problems", {}).items()):
        code_rows = [r for r in rows if r.get("code_snippet") and r["code_snippet"] != "（无代码）"]
        if code_rows:
            lines.append(f"### {problem}")
            lines.append("")
            best_by_arm: dict[str, dict[str, Any]] = {}
            for row in code_rows:
                arm = row["arm"]
                current = best_by_arm.get(arm)
                if current is None or (row.get("best") is not None and row.get("best") < current.get("best", float("inf"))):
                    best_by_arm[arm] = row
            for row in sorted(best_by_arm.values(), key=lambda r: (r.get("best") is None, r.get("best", float("inf")))):
                lines.append(f"**{row['arm']}** (gen={row.get('gen','')}, best={row.get('best','')}):")
                lines.append(row["code_snippet"])
                lines.append("")

    lines.extend([
        "## Card-memory / 选卡记录",
        "",
        "| problem | arm | gen | card_source | selected_card_ids | history_card_ids | best_code_record_id | synthesized_card_id |",
        "|---|---|---:|---|---|---|---|---|",
    ])
    for problem, rows in sorted(summary.get("problems", {}).items()):
        for row in rows:
            selected = ", ".join(row.get("cards", [])) or "-"
            history_ids = ", ".join(row.get("history_card_ids", [])) or "-"
            synthesized = row.get("synthesized_card_id") or "-"
            lines.append(
                f"| {problem} | {row['arm']} | {row.get('gen','')} | {row.get('card_source','none')} | "
                f"{selected} | {history_ids} | {row.get('best_code_record_id','-')} | {synthesized} |"
            )
    lines.append("")

    lines.extend([
        "## 下一步建议",
        "",
        "（由 TOCC controller 或人工审查后填入）",
        "",
        "---",
        "",
        "*本报告自动生成于 summarize_manifest_runs.py*",
    ])

    # Add success funnel section
    funnel = summary.get("success_funnel", {})
    if funnel and funnel.get("total_runs", 0) > 0:
        funnel_lines = [
            "",
            "## Agent 成功率漏斗 (Success Funnel)",
            "",
            "五层漏斗，与 HeuriGym (ICLR 2026) 四阶段错误分类对齐：",
            "",
            "| 层级 | 通过 | 总数 | 通过率 | 说明 |",
            "|---|---:|---:|---:|---|",
        ]
        layer_labels = {
            "proposal_accept": "1. Proposal Accept (gatekeeper 通过, 无 infra 失败)",
            "linkage_success": "2. Linkage (selected_card_ids 已注入 rag_trace)",
            "generation_success": "3. Generation (valid ≥ ceil(0.5×pop), 无 valid collapse)",
            "objective_success": "4. Objective (best 优于 pure baseline mean)",
            "diagnosis_success": "5. Diagnosis (需 agent pipeline 数据, 当前未统计)",
        }
        for layer, label in layer_labels.items():
            lf = funnel.get(layer, {})
            passed = lf.get("passed", 0)
            total = lf.get("total", 0)
            rate = lf.get("rate", 0)
            note = lf.get("note", "")
            rate_str = f"{rate:.1%}" if total > 0 else "-"
            note_str = f" ({note})" if note else ""
            funnel_lines.append(f"| {label} | {passed} | {total} | {rate_str} |{note_str} |")

        baselines = funnel.get("pure_baselines", {})
        if baselines:
            bl_str = ", ".join(f"{p}={v:.3f}" for p, v in baselines.items())
            funnel_lines.append("")
            funnel_lines.append(f"**Pure baseline (mean):** {bl_str}")
            funnel_lines.append("")
            funnel_lines.append("**注意:** diagnosis_success 需 agent pipeline 数据（LLM 诊断是否引用 ≥3 项 trace 证据），当前 marked as unknown。仅 generation 和 objective 层可由 run_summary 自动计算。")

        lines.extend(funnel_lines)

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-summarize experiment manifest runs")
    parser.add_argument("--input", required=True, help="Path to suite output directory")
    parser.add_argument("--output", help="Output markdown path (default: INPUT/summary.md)")
    parser.add_argument("--no-card-memory-write", action="store_true", help="Skip card memory update")
    args = parser.parse_args()

    summary = summarize(args.input, no_card_memory=args.no_card_memory_write)
    if "error" in summary:
        print(f"ERROR: {summary['error']}")
        return

    output_md = args.output or str(Path(args.input) / "summary.md")
    _write_markdown(summary, output_md)

    output_json = str(Path(output_md).with_suffix(".json"))
    json.dump(summary, Path(output_json).open("w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # Write standalone funnel JSON
    funnel = summary.get("success_funnel", {})
    if funnel:
        funnel_path = str(Path(args.input) / "success_funnel.json")
        json.dump(funnel, Path(funnel_path).open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"Success funnel written to {funnel_path}")

    print(f"Summary written to {output_md}")
    print(f"Summary JSON written to {output_json}")


if __name__ == "__main__":
    main()
