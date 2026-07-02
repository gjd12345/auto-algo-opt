"""
模块：run_summarizer（实验运行结果自动汇总器）
功能：读取一批实验运行的索引与各自的结果文件，汇总成中文 Markdown 报告与结构化 JSON。
职责：
    - 按问题（online bin packing / TSP / CVRP / InsertShips 等）分组整理每次运行的结果；
    - 计算每次运行的“成功率漏斗”（分层判断运行是否成功）；
    - 计算相对纯 EOH 基线（pure baseline）的归一化得分与提升百分比；
    - 把优质代码回写为知识卡片（card），并记录每张卡片的使用效果证据；
    - 生成 Markdown 报告、汇总 JSON 以及独立的漏斗 JSON。
接口：
    - summarize(input_dir, no_card_memory=False) -> dict：核心汇总逻辑，返回结构化结果字典。
    - main() -> None：命令行入口，解析参数并写出报告文件。
输入：
    - 命令行参数 --input（实验套件输出目录，内含 run_index.json）；
    - 每次运行目录下的 official_eoh_run_summary.json。
输出：
    - Markdown 报告（默认 INPUT/summary.md）；
    - 汇总 JSON（与 Markdown 同名的 .json）；
    - 成功率漏斗 JSON（INPUT/success_funnel.json）。
示例：
    python run_summarizer.py --input /path/to/suite_output
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _find_project_root(start: str | Path) -> Path:
    """从 *start* 目录逐层向上查找，直到找到包含 ``eoh_rag/`` 子目录的目录作为项目根。

    参数 start：起始路径（可以是文件或目录）。
    返回：项目根目录（Path）。
    若向上最多 10 层仍未找到，则尝试当前工作目录；再找不到则抛出 FileNotFoundError。
    """
    p = Path(start).resolve()
    for _ in range(10):
        if (p / "eoh_rag").is_dir():
            return p
        if p.parent == p:  # 已到达文件系统根目录，无法再向上
            break
        p = p.parent
    # 兜底：尝试用当前工作目录
    cwd = Path.cwd()
    if (cwd / "eoh_rag").is_dir():
        return cwd
    raise FileNotFoundError(f"Cannot find project root from {start}")


def _load_summary(path: Path) -> dict[str, Any] | None:
    """读取某次运行目录下的 official_eoh_run_summary.json 并解析为字典。

    参数 path：某次运行的输出目录。
    返回：解析后的字典；若该目录下没有结果文件则返回 None。
    """
    summary_path = path / "official_eoh_run_summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _best_code_snippet(code: str | None, max_lines: int = 12) -> str:
    """把一段代码整理成适合放进 Markdown 的精简片段。

    过滤掉 import 语句、注释行、文档字符串，只保留核心逻辑行，
    最多保留 max_lines 行，并包裹成 ```python 代码块。

    参数 code：原始代码文本，可能为空。
    参数 max_lines：最多保留的行数。
    返回：Markdown 代码块字符串；若无代码则返回“（无代码）”。
    """
    if not code:
        return "（无代码）"
    lines = code.strip().split("\n")
    body: list[str] = []
    in_docstring = False  # 标记当前是否处于文档字符串内部
    for line in lines:
        stripped = line.strip()
        # 跳过空行、import/from 语句、注释行
        if not stripped or stripped.startswith(("import ", "from ", "#")):
            continue
        # 遇到三引号：奇数个引号说明文档字符串边界，切换进入/退出状态
        if '"""' in stripped or "'''" in stripped:
            marker = '"""' if '"""' in stripped else "'''"
            if stripped.count(marker) % 2 == 1:
                in_docstring = not in_docstring
            continue
        if in_docstring:  # 处于文档字符串内部，整行跳过
            continue
        # 跳过 Google 风格 docstring 里遗留的字段标题行
        if stripped in {"Args:", "Returns:"} or stripped.endswith(": ID of the current node"):
            continue
        body.append(line.rstrip())
    # 若过滤后剩余行太少，退化为直接取非空行（保证片段不至于为空）
    if len(body) < 3:
        body = [line.rstrip() for line in lines if line.strip()][:max_lines]
    snippet = "\n".join(body[:max_lines])
    return f"```python\n{snippet}\n```"


def _card_source_from_ids(card_ids: list[str]) -> str:
    """根据选用卡片的 ID 列表判断卡片来源类别。

    以 ``history_`` 前缀区分“历史卡片”与“文献卡片”：
        - 无卡片 -> "none"
        - 同时含两类 -> "mixed"
        - 只有历史卡片 -> "history"
        - 只有文献卡片 -> "literature"
    """
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
    """计算单次运行的五层“成功率漏斗”。

    这些层次对齐 HeuriGym 的四阶段错误分类，从底层设施到高层效果逐级判断：
    1. proposal_accept（提案接受）：运行没有出现基础设施层面的失败即通过。
    2. linkage_success（选卡链路）：RAG 组是否确实注入了卡片（无卡片则视为失败）。
    3. generation_success（生成成功）：有效候选数 >= max(2, ceil(0.5 * 种群规模))。
    4. objective_success（目标提升）：最优目标值优于纯 EOH 基线（此处按最小化方向判断）。
    5. diagnosis_success（诊断成功）：需要 agent pipeline 数据，此处标记为未知（None）。

    参数：
        run_data：单次运行的完整结果字典。
        rag_trace：该次运行的 RAG 选卡轨迹（非 RAG 组可为 None）。
        pure_baseline：该问题的纯 EOH 基线值（可能为 None）。
    返回：包含各层布尔判定与统计信息的字典。
    """
    run_sum = run_data.get("run_summary", {})
    valid = run_sum.get("valid_candidates", 0)
    pop = run_sum.get("population_size", 0)
    best = run_sum.get("best_objective")
    failure = run_sum.get("failure_reason")
    return_code = run_data.get("return_code", 0)

    # 第 1 层：提案接受 —— 运行执行过程中未发生基础设施故障
    proposal_accept = (return_code == 0 and not failure)

    # 第 2 层：选卡链路 —— 实际注入的卡片是否与请求一致
    linkage_success = None  # 默认未知（非 RAG 组）
    selected = []
    if rag_trace and isinstance(rag_trace, dict):
        selected = [item.get("id", "") for item in rag_trace.get("rag_selected_items", [])]
        if selected:
            linkage_success = True  # 确实注入了卡片
        else:
            linkage_success = False  # 属于 RAG 组但没有注入任何卡片

    # 第 3 层：生成成功 —— 有效候选数量是否达标
    min_valid = max(2, int(__import__("math").ceil(0.5 * pop))) if pop > 0 else 1
    generation_success = (valid >= min_valid) if pop > 0 else None

    # 第 4 层：目标提升 —— 是否优于纯 EOH 基线
    objective_success = None
    if best is not None and pure_baseline is not None:
        objective_success = best < pure_baseline  # 最小化方向：越小越好

    # 第 5 层：诊断成功 —— 需要 agent pipeline 数据，此处无法计算
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
    """汇总多次运行的漏斗结果，逐层统计通过率。

    参数 funnels：每次运行的漏斗字典列表（由 _compute_success_funnel 产出）。
    返回：包含总运行数以及各层 passed/total/rate 的汇总字典；
        某层若没有可判定的数据（全为 None），则记为 0 并附 note 说明数据不足。
    """
    layers = ["proposal_accept", "linkage_success", "generation_success", "objective_success"]
    summary: dict[str, Any] = {"total_runs": len(funnels)}
    for layer in layers:
        # 只统计该层有明确判定（非 None）的运行
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
    """汇总一个实验套件目录下的所有运行，产出结构化结果字典。

    整体流程：
        1. 读取 run_index.json，按问题把各次运行分组；
        2. 对每个问题，用 pure_eoh 组的最优目标均值作为纯 EOH 基线；
        3. 对每次运行计算成功率漏斗、归一化得分、相对基线的提升百分比；
        4. 若目标层通过且允许写回，把优质代码合成为知识卡片写入语料库；
        5. 记录每张被注入卡片的使用效果证据（card outcomes）；
        6. 汇总各层漏斗通过率。

    参数：
        input_dir：实验套件输出目录，需包含 run_index.json。
        no_card_memory：为 True 时跳过卡片合成与效果记录的写回。
    返回：结构化结果字典；若找不到 run_index.json 则返回 {"error": ...}。
    """
    root = Path(input_dir).resolve()
    index_path = root / "run_index.json"
    if not index_path.exists():
        return {"error": f"run_index.json not found in {root}"}

    runs = json.loads(index_path.read_text(encoding="utf-8"))
    problems = defaultdict(list)
    for run in runs:
        problems[run["problem"]].append(run)  # 按问题名把运行分桶

    # --- 计算每个问题的纯 EOH 基线（pure baseline）---
    pure_baselines: dict[str, float] = {}
    for problem, problem_runs in problems.items():
        pure_bests = []
        for run in problem_runs:
            if run["arm"] == "pure_eoh":  # 只用无 RAG 的纯 EOH 组作基线
                s = _load_summary(Path(run["output_dir"]))
                if s:
                    rs = s.get("run_summary", {})
                    b = rs.get("best_objective")
                    if b is not None:
                        pure_bests.append(b)
        if pure_bests:
            pure_baselines[problem] = sum(pure_bests) / len(pure_bests)  # 取多次运行的均值

    # --- 逐问题构建表格数据 ---
    summary: dict[str, Any] = {"suite": root.name, "problems": {}, "success_funnel": {}}
    all_funnels: list[dict[str, Any]] = []

    for problem, problem_runs in sorted(problems.items()):
        rows = []
        for run in problem_runs:
            s = _load_summary(Path(run["output_dir"]))
            if not s:
                # 该次运行没有结果文件，只记录基本状态占位
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

            # 计算成功率漏斗，并补充问题/组别/代次等标识信息
            baseline = pure_baselines.get(problem)
            funnel = _compute_success_funnel(s, rag, baseline)
            funnel["problem"] = problem
            funnel["arm"] = run["arm"]
            funnel["gen"] = run["generation"]
            # 该次运行最优代码的唯一记录 ID：问题:组别:代次:重复次
            best_code_record_id = f"{problem}:{run['arm']}:g{run['generation']}:r{run.get('repeat', '?')}"
            funnel["best_code_record_id"] = best_code_record_id
            funnel["synthesized_card_id"] = None
            funnel["synthesized_card_written"] = False
            all_funnels.append(funnel)

            best_val = run_sum.get("best_objective")
            norm_score = None
            delta_pct = None
            # 有基线且基线为正时，计算归一化得分与相对提升百分比
            if best_val is not None and baseline is not None and baseline > 0:
                norm_score = round(baseline / best_val, 4)  # >1 表示（最小化问题上）有提升
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

            # --- 最优代码 → 知识卡片 的回写闭环 ---
            # 仅当目标层通过（确有提升）且允许写回时，把这段代码合成为可复用卡片
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
                            # 向上查找包含 eoh_rag/ 的目录作为项目根，定位语料库位置
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

            # --- 卡片效果记忆：为每张被注入的卡片记录使用证据 ---
            if rag and not no_card_memory:
                try:
                    from eoh_rag.rag.card_outcomes import build_outcome_records, save_outcomes
                    from eoh_rag.rag.build_corpus import default_corpus_dir

                    injected_items = rag.get("rag_injected_items", [])
                    if not injected_items:
                        # 若没有显式的注入清单，则退化为用“已选卡片”列表补齐
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
                        # 效果证据以追加方式写入语料库下的 card_outcomes.jsonl
                        outcomes_path = Path(default_corpus_dir(project_root)) / "card_outcomes.jsonl"
                        save_outcomes(outcome_records, outcomes_path, append=True)
                except Exception as exc:
                    print(f"  [card-outcomes] Warning: {exc}")

        # 表格行排序：按组别固定顺序 pure -> api -> default -> targeted -> tocc，再按代次
        arm_order = {"pure_eoh": 0, "api_only": 1, "default_rag": 2, "targeted_rag": 3,
                     "tocc_corrected": 4}
        rows.sort(key=lambda r: (arm_order.get(r["arm"], 99), r.get("gen", 0)))

        summary["problems"][problem] = rows

    # --- 漏斗汇总：把所有运行的分层结果聚合成总体通过率 ---
    summary["success_funnel"] = _compute_funnel_summary(all_funnels)
    summary["success_funnel"]["pure_baselines"] = pure_baselines
    summary["success_funnel"]["per_run"] = all_funnels

    return summary


def _write_markdown(summary: dict[str, Any], output_path: str) -> None:
    """把 summarize() 产出的结构化结果渲染成中文 Markdown 报告并写入文件。

    报告包含：汇总表、各问题最优代码片段、选卡记录表、下一步建议、成功率漏斗表。
    参数：
        summary：summarize() 返回的结果字典。
        output_path：Markdown 输出文件路径。
    """
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
            # 把原始状态归一化为易读的 OK / FAILED
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
            # 每个组别只保留最优（best 最小）的那一行代码
            for row in code_rows:
                arm = row["arm"]
                current = best_by_arm.get(arm)
                if current is None or (row.get("best") is not None and row.get("best") < current.get("best", float("inf"))):
                    best_by_arm[arm] = row
            # 按 best 升序展示（best 为 None 的排在最后）
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
    """命令行入口：解析参数、执行汇总，并写出 Markdown、汇总 JSON 与漏斗 JSON。"""
    parser = argparse.ArgumentParser(description="Auto-summarize experiment manifest runs")
    parser.add_argument("--input", required=True, help="Path to suite output directory")
    parser.add_argument("--output", help="Output markdown path (default: INPUT/summary.md)")
    parser.add_argument("--no-card-memory-write", action="store_true", help="Skip card memory update")
    args = parser.parse_args()

    summary = summarize(args.input, no_card_memory=args.no_card_memory_write)
    if "error" in summary:
        print(f"ERROR: {summary['error']}")
        return

    # 未指定 --output 时，默认写到输入目录下的 summary.md
    output_md = args.output or str(Path(args.input) / "summary.md")
    _write_markdown(summary, output_md)

    # 同时写出与 Markdown 同名的结构化 JSON
    output_json = str(Path(output_md).with_suffix(".json"))
    json.dump(summary, Path(output_json).open("w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 额外写出独立的成功率漏斗 JSON，便于单独消费
    funnel = summary.get("success_funnel", {})
    if funnel:
        funnel_path = str(Path(args.input) / "success_funnel.json")
        json.dump(funnel, Path(funnel_path).open("w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"Success funnel written to {funnel_path}")

    print(f"Summary written to {output_md}")
    print(f"Summary JSON written to {output_json}")


if __name__ == "__main__":
    main()
