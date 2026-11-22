"""Top-venue literature sources & 10 benchmark/LLM-AHD cards synchronizer.

Invoked by ``tools/sync_cvrp_workbench_kb.py`` to register all 10 authoritative
top-venue benchmark & method sources and create/upsert the 10 required knowledge
cards with strictly separated ``evidence_bindings`` (``local_recomputed``) and
``paper_reported_results`` (``paper_reported_reference``).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_entry(entries_dir: Path, entry_id: str, metadata: dict[str, Any], markdown: str) -> None:
    md_text = markdown.replace("\r\n", "\n").rstrip("\n") + "\n"
    md_bytes = md_text.encode("utf-8")
    (entries_dir / f"{entry_id}.md").write_bytes(md_bytes)
    meta = dict(metadata)
    meta["id"] = entry_id
    meta["content_sha256"] = _sha256_bytes(md_bytes)
    (entries_dir / f"{entry_id}.json").write_bytes(
        (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def top_venue_sources() -> list[dict[str, Any]]:
    """All 10 authoritative top-venue benchmark & LLM-AHD sources."""
    return [
        {
            "id": "src-romera-paredes-2024-funsearch",
            "title": "Mathematical discoveries from program search with large language models",
            "authors": ["Bernardino Romera-Paredes", "Mohammadamin Barekatain", "Alexander Novikov", "Matej Balog", "M. Pawan Kumar", "Emilien Dupont", "Francisco J. R. Ruiz", "Jordan S. Ellenberg", "Pengming Wang", "Omar Fawzi", "Pushmeet Kohli", "Alhussein Fawzi"],
            "year": 2024,
            "venue": "Nature, 625, 468-475",
            "doi": "10.1038/s41586-023-06924-6",
            "url": "https://doi.org/10.1038/s41586-023-06924-6",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_open_access",
            "license": "CC BY 4.0",
            "selected": True,
            "selection_reason": "Foundational island-based evolutionary LLM program search (FunSearch) and OBP OR1-OR4 & Weibull Table 1 benchmark.",
            "locator": "Nature 2024 Table 1; google-deepmind/funsearch",
            "read_depth": "abstract",
            "notes": "Table 1 OBP excess bins verified in published_results/funsearch_eoh_2024_tables.json.",
        },
        {
            "id": "src-feiliu-2024-eoh",
            "title": "Evolution of Heuristics: Towards Efficient Automatic Algorithm Design Using Large Language Model",
            "authors": ["Fei Liu", "Xialiang Tong", "Mingxuan Yuan", "Xi Lin", "Fu Luo", "Zhenkun Wang", "Zhichao Lu", "Qingfu Zhang"],
            "year": 2024,
            "venue": "ICML 2024 (arXiv:2401.02051)",
            "doi": "10.48550/arXiv.2401.02051",
            "url": "https://arxiv.org/abs/2401.02051",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "MIT",
            "selected": True,
            "selection_reason": "Co-evolution of thoughts and code (EoH) and Tables 1/3/9/10 across OBP Weibull, TSP-GLS, and FSSP Taillard.",
            "locator": "FeiLiu36/EoH@47254578; arXiv:2401.02051",
            "read_depth": "full_text_local",
            "notes": "Repository cloned locally at commit 472545785c936dcfc863d2bc0d6109cf23c7ce62 including ALL_tsp official .opt.tour.gz.",
        },
        {
            "id": "src-feiliu-2025-eohs",
            "title": "EoH-S: Evolution of Heuristic Set Using LLMs for Automated Heuristic Design",
            "authors": ["Fei Liu", "Yilu Liu", "Qingfu Zhang", "Xialiang Tong", "Mingxuan Yuan"],
            "year": 2025,
            "venue": "AAAI 2026 (arXiv:2508.03082)",
            "doi": "10.48550/arXiv.2508.03082",
            "url": "https://arxiv.org/abs/2508.03082",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "MIT",
            "selected": True,
            "selection_reason": "Complementary Heuristic Set evolution (CPI evaluation) and Tables 1-3 covering OBP/TSP/CVRP + CVRPLib/TSPLib/BPPLib.",
            "locator": "FeiLiu36/EoH-S@7d4b1f77; arXiv:2508.03082",
            "read_depth": "full_text_local",
            "notes": "Datasets (256 CVRP, 128 TSP, 128+50 OBP) and run1 Top-10 heuristics pinned verbatim at commit 7d4b1f77.",
        },
        {
            "id": "src-ye-2024-reevo",
            "title": "ReEvo: Large Language Models as Hyper-Heuristics with Reflective Evolution",
            "authors": ["Haoran Ye", "Jiarui Wang", "Zhiguang Cao", "Federico Berto", "Chuanbo Hua", "Haeyeon Kim", "Jinkyoo Park", "Guojie Song"],
            "year": 2024,
            "venue": "NeurIPS 2024 (arXiv:2402.01145)",
            "doi": "10.48550/arXiv.2402.01145",
            "url": "https://arxiv.org/abs/2402.01145",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "MIT",
            "selected": True,
            "selection_reason": "Short- and long-term reflective evolution LHH framework; Tables 1-3 verified verbatim from arXiv:2402.01145 PDF.",
            "locator": "ai4co/reevo@6dce1825; arXiv:2402.01145",
            "read_depth": "full_text_local",
            "notes": "Primary PDF verified: Table 1 (TSP-GLS), Table 2 (TSPLIB constructive), Table 3 (both TSP-NCO & CVRP-NCO); §5.2 ACO is Fig. 2 only.",
        },
        {
            "id": "src-msra-2025-heuragenix",
            "title": "HeurAgenix: Leveraging LLMs for Solving Complex Combinatorial Optimization Challenges",
            "authors": ["Microsoft Research Asia"],
            "year": 2025,
            "venue": "arXiv:2506.15196",
            "doi": "10.48550/arXiv.2506.15196",
            "url": "https://arxiv.org/abs/2506.15196",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "MIT",
            "selected": True,
            "selection_reason": "Two-stage heuristic evolution + online LLM hyper-heuristic selection; Appendix F Tables 5-6 verified verbatim from PDF.",
            "locator": "microsoft/HeurAgenix@e84bfb19; arXiv:2506.15196",
            "read_depth": "full_text_local",
            "notes": "Repository cloned at commit e84bfb19; 11 basic + 3 evolved CVRP heuristics inspected and min_cost_insertion adapted for local recomputation.",
        },
        {
            "id": "src-sun-2025-cobench",
            "title": "CO-Bench: Benchmarking Language Model Agents in Algorithm Search for Combinatorial Optimization",
            "authors": ["Weiwei Sun", "Shengyu Feng", "Shanda Li", "Yiming Yang"],
            "year": 2025,
            "venue": "AAAI / arXiv:2504.04310",
            "doi": "10.48550/arXiv.2504.04310",
            "url": "https://arxiv.org/abs/2504.04310",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "Apache-2.0 / arXiv",
            "selected": True,
            "selection_reason": "36-problem real-world OR benchmark comparing FunSearch (0.842), EoH (0.840), Greedy Refine (0.840), Classical (0.797), ReEvo (0.774).",
            "locator": "thuiar/CO-Bench; arXiv:2504.04310 Fig. 3 p.5",
            "read_depth": "full_text_local",
            "notes": "Primary PDF verified exact 3-decimal Avg Score for EoH = 0.840 and Claude-3.7 Sonnet = 0.651.",
        },
        {
            "id": "src-reinelt-1991-tsplib",
            "title": "TSPLIB - A Traveling Salesman Problem Library",
            "authors": ["Gerhard Reinelt"],
            "year": 1991,
            "venue": "ORSA Journal on Computing, 3(4), 376-384",
            "doi": "10.1287/ijoc.3.4.376",
            "url": "https://doi.org/10.1287/ijoc.3.4.376",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "public research benchmark instances",
            "selected": True,
            "selection_reason": "Canonical TSPLIB EUC_2D nearest-integer distance specification and official .opt.tour files.",
            "locator": "FeiLiu36/EoH@47254578 ALL_tsp/*.{tsp,opt.tour}.gz (18/18 zero-error verified)",
            "read_depth": "full_text_local",
            "notes": "All 18 EUC_2D instances with official .opt.tour.gz verified 18/18 to 0.0 integer discrepancy.",
        },
        {
            "id": "src-delorme-2018-bpplib",
            "title": "BPPLIB: A Library for Bin Packing and Cutting Stock Problems",
            "authors": ["Maxence Delorme", "Manuel Iori", "Silvano Martello"],
            "year": 2018,
            "venue": "INFORMS Journal on Computing, 30(1), 160-173",
            "doi": "10.1287/ijoc.2017.0772",
            "url": "https://doi.org/10.1287/ijoc.2017.0772",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "public research benchmark instances",
            "selected": True,
            "selection_reason": "Official 1D Bin Packing benchmark library including Scholl 1/2/3 (Sch_1, Sch_2, Scholl_H) and Hard28 with exact Solutions.xlsx.",
            "locator": "mdelorme2/BPPLIB@fc3aa784 (2_Scholl.rar, 5_Hard28.rar, Solutions.xlsx)",
            "read_depth": "full_text_local",
            "notes": "70 stratified instances (24 Sch_1, 24 Sch_2, 10 Scholl_3 HARD0-9, 12 Hard28) imported in obp_ext_bpplib.",
        },
    ]


def _pub_to_kb_item(rec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "paper_source_id": rec["paper_source_id"],
        "table_ref": rec["table_ref"],
        "suite_id": rec["suite_id"],
        "subset": rec["subset"],
        "method_name": rec["method_display_name"],
        "paradigm": rec["paradigm"],
        "metric": rec["metric_name"],
        "value": rec["value"],
        "unit": rec["unit"],
        "reference_kind": rec["reference_kind"],
        "comparison_mode": "paper_reported_reference",
        "verification_status": rec["verification_status"],
        "protocol_boundary_note": rec["protocol_boundary_note"],
    }


def _local_binding(summary: Mapping[str, Any], suite_id: str, alg_id: str, metric: str = "mean_rel_gap") -> dict[str, Any] | None:
    overall = (((summary.get("suites") or {}).get(suite_id) or {}).get("algorithms") or {}).get(alg_id, {}).get("overall")
    if not overall or overall.get(metric) is None:
        return None
    suite_obj = (summary.get("suites") or {}).get(suite_id) or {}
    common = ((suite_obj.get("algorithms") or {}).get(alg_id) or {}).get("common_completed") or {}
    b_ex = int(overall.get("ok_budget_exhausted_count") if overall.get("ok_budget_exhausted_count") is not None else (overall.get("budget_exhausted_count") or 0))
    to_cnt = int(overall.get("timeout_count") if overall.get("timeout_count") is not None else max(0, int(overall.get("n_instances") or 0) - int(overall.get("ok_count") or 0)))
    b_note = f", ok_budget_exhausted={b_ex}" if b_ex > 0 else ""
    to_note = f", timeout={to_cnt}" if to_cnt > 0 else ""
    conv = overall.get("local_opt_convergence_rate")
    conv_note = f", conv={conv}" if isinstance(conv, (int, float)) and conv < 1.0 else ""
    k_note = ""
    if suite_id == "cvrp_ext_cvrplib_abp_74" and overall.get("exact_k_checked"):
        ex_c = overall.get("exact_k_count")
        ex_n = overall.get("exact_k_checked")
        ex_g = overall.get("exact_k_mean_rel_gap")
        k_note = f", exact_k={ex_c}/{ex_n}(gap={ex_g})"
    c_note = ""
    if common.get("n_instances") and common.get("n_instances") < overall.get("n_instances") and common.get("mean_rel_gap") is not None:
        c_note = f", common_completed({common['n_instances']})_gap={common['mean_rel_gap']}"
    return {
        "suite_id": suite_id,
        "run_id": "cvrp_workbench_v2_standard_500ms",
        "algorithm_id": alg_id,
        "metric": metric,
        "value": overall[metric],
        "comparison_mode": "local_recomputed",
        "reference_note": f"N={overall.get('n_instances')}, ok={overall.get('ok_count')}{b_note}{to_note}{conv_note}{k_note}{c_note}, mean={overall.get('mean_tour_length')}, solve_ms P50={overall.get('solve_ms_p50')}/P95={overall.get('solve_ms_p95')}",
        "artifact_path": "results/per_instance_records.json",
    }


def sync_top_venue_kb(
    workspace: Path,
    bundle_dir: Path,
    *,
    upgraded: list[str],
    created: list[str],
) -> dict[str, Any]:
    entries_dir = workspace / "entries"
    summary = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
    pub_idx = json.loads((bundle_dir / "published_results" / "index.json").read_text(encoding="utf-8"))
    pub_all: list[dict[str, Any]] = list(pub_idx.get("records", []))

    # Ensure all 10 top-venue sources exist / are up to date in sources.json
    sources_path = workspace / "sources.json"
    sources_doc = json.loads(sources_path.read_text(encoding="utf-8"))
    by_sid = {s["id"]: i for i, s in enumerate(sources_doc.get("sources", [])) if isinstance(s, Mapping)}
    added_sources = 0
    for src in top_venue_sources():
        if src["id"] in by_sid:
            sources_doc["sources"][by_sid[src["id"]]] = src
        else:
            sources_doc["sources"].append(src)
            by_sid[src["id"]] = len(sources_doc["sources"]) - 1
            added_sources += 1
    sources_path.write_bytes((json.dumps(sources_doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def _upsert(entry_id: str, meta: dict[str, Any], md: str) -> None:
        existed = (entries_dir / f"{entry_id}.json").is_file()
        _write_entry(entries_dir, entry_id, meta, md)
        if existed:
            if entry_id not in upgraded:
                upgraded.append(entry_id)
        else:
            if entry_id not in created:
                created.append(entry_id)

    def _filter_pub(paper_source_id: str, *, table_prefix: str | None = None, method_ids: set[str] | None = None) -> list[dict[str, Any]]:
        out = []
        for r in pub_all:
            if r["paper_source_id"] != paper_source_id:
                continue
            if table_prefix and not str(r["table_ref"]).startswith(table_prefix):
                continue
            if method_ids and r["method_id"] not in method_ids:
                continue
            out.append(_pub_to_kb_item(r))
        return out

    # ------------------------------------------------------------------
    # PART 1: 5 Top-Venue Benchmark Protocol & Published Results Cards
    # ------------------------------------------------------------------

    # 1. evidence-bench-eohs-multi-problem-protocol
    eohs_local = [
        b for b in (
            _local_binding(summary, "cvrp_ext_eohs_256", "s2_r5_spiral"),
            _local_binding(summary, "cvrp_ext_eohs_256", "eohs_cvrp_f1"),
            _local_binding(summary, "cvrp_ext_eohs_256", "eohs_cvrp_set10_cpi"),
            _local_binding(summary, "cvrp_ext_eohs_256", "cw_relocate_2opt"),
            _local_binding(summary, "tsp_ext_eohs_128", "tsp_nn_2opt"),
            _local_binding(summary, "tsp_ext_eohs_128", "eohs_tsp_f1"),
            _local_binding(summary, "obp_ext_eoh_weibull", "obp_best_fit"),
            _local_binding(summary, "obp_ext_eoh_weibull", "eohs_obp_f1"),
        ) if b is not None
    ]
    eohs_paper = _filter_pub("src-feiliu-2025-eohs")
    _upsert(
        "evidence-bench-eohs-multi-problem-protocol",
        {
            "type": "evidence",
            "title": "EoH-S multi-problem benchmark protocol & Tables 1-3 (OBP / TSP / CVRP / OR Libraries)",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["eoh-s", "benchmark-protocol", "cvrp", "tsp", "obp", "cvrplib", "tsplib", "bpplib", "cpi", "paper-reported"],
            "status": "reviewed",
            "summary": "Codifies EoH-S (AAAI 2026, arXiv:2508.03082) multi-problem CPI protocol across OBP (Table 1), synthetic TSP & CVRP (Table 2), and OR standard libraries CVRPLib/TSPLib/BPPLib (Table 3), physically separated from local recomputations.",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "complementary_constructive_set",
                "complexity_class": "empirical",
                "interface": "select_next_node",
                "applicable_regimes": {
                    "strong_on": ["cross_distribution_generalization", "complementary_heuristic_sets", "cvrp_tsp_obp_comparison"],
                    "weak_on": ["single_heuristic_vs_cpi_conflation"],
                    "scale_notes": "EoH-S 评测以 K=10 启发式互补集合的每例最优 (CPI) 为主口径；必须与单算法成绩及全解并行合并/局部搜索明确分轨。",
                },
                "evidence_bindings": eohs_local,
                "paper_reported_results": eohs_paper,
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": ["method-lit-ahd-eohs", "method-cvrp-s2-r5-spiral"],
                "sources": ["src-feiliu-2025-eohs", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-feiliu-2025-eohs", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
            "code_refs": [],
        },
        """# EoH-S 多问题基准协议与原表参照（Tables 1–3）

本卡片系统归档 **EoH-S**（Liu et al., AAAI 2026 / `arXiv:2508.03082`，仓库 `FeiLiu36/EoH-S@7d4b1f77`）覆盖 **OBP / TSP / CVRP** 三大组合优化问题及 **CVRPLib / TSPLib / BPPLib** 标准库的完整评测协议与原表数值。

## 定义或方法步骤

1. **三问题训练与多规模测试集**：
   - CVRP：`cvrp_ext_eohs_256`（256 例多分布，带 LKH 参考解），测试至 $n=500$。
   - TSP：`tsp_ext_eohs_128`（4 类聚类分布 × 32 = 128 例，带 LKH 参考解），测试至 $n=500$。
   - OBP：`obp_ext_eoh_weibull`（128 例训练 + 1k/5k/10k × C=200,500 Weibull 测试，相对 L1 下界）。
2. **互补性能指标（CPI）**：对规模 $K=10$ 的启发式集合，每实例取集合内最优个体得分后再求平均相对差距。
3. **本机同协议复跑与原表物理隔离**：已将 `FeiLiu36/EoH-S@7d4b1f77` 的 CVRP/TSP/OBP 公开启发式接入本机同一评测器复跑（`local_recomputed`），原论文 Table 1–3 全量 216 条精确值（含 Table 1 OBP 全部 9 列：3 个训练分档 `n200-500/c100`、`n500-1k/c100`、`n1k-2k/c100` 与 6 个测试分档 `n1k/5k/10k × c200/c500`，其中 `EoH-S n1k/c200 = 1.13%`、`n10k/c500 = 0.10%`）单独落盘至 `published_results/eohs_2025_tables_1_3.json`（`paper_reported_reference`）。

## 适用条件、假设与限制

- EoH-S Table 1–3 的 `Top 10` 与 `EoH-S (Set)` 属于 10 启发式集合每例取最优（等价于理想事后 Oracle 选择），不能直接等同于单个构造规则或零选择代价的单次求解。
- 500 ms 预算门控与样本范围：在 `cvrp_ext_eohs_256` 上本机 `eohs_cvrp_set10_cpi` 平均差距为 `18.39%`（`256/256` 产出可行解，其中 `49/256` 例在运行 10 个候选规则途中触发 500 ms 预算截断并保留已找到的最优可行解）；在 `cvrp_ext_cvrplib_x_100`（Set X）上，`eohs_cvrp_f1` 单规则完成 `59/100`（`+27.05%`），而 `s2_r5_spiral` 与 `cw_relocate_2opt` 完成 `100/100`（在共同完成的 `59` 例交集 `N_common=59` 上，三者平均差距分别为 **`27.05%` vs `16.36%` vs `5.69%`**）。

## 来源及支持的具体结论

- 原表数据来自 `src-feiliu-2025-eohs`（Table 1 OBP 9 档：`EoH-S` 训练 `5.15% / 2.30% / 3.14%`，测试 `1.13% (1k/c200) / 1.24% (1k/c500) / 0.33% (5k/c200) / 0.25% (5k/c500) / 0.14% (10k/c200) / 0.10% (10k/c500)`；Table 2 CVRP：`Train 0.173`, `n50 0.135`, `n100 0.188`, `n200 0.180`, `n500 0.169`；Table 2 TSP：`Train 0.097`, `n50 0.040`, `n100 0.065`, `n200 0.090`, `n500 0.111`；Table 3 CVRPLib A/B/P/X：`0.231 / 0.183 / 0.169 / 0.196`，TSPLib `0.093`，BPPLib `Sch_1/Sch_2/Scholl_H/IRUP/NonIRUP`：`0.152 / 0.141 / 0.095 / 0.072 / 0.073`）。
- 本机复跑结果绑定在 `attributes.evidence_bindings`（`results/per_instance_records.json`），原表数值绑定在 `attributes.paper_reported_results`。

## 代码和评测关联

- 基准套件：`cvrp_ext_eohs_256`、`tsp_ext_eohs_128`、`obp_ext_eoh_weibull`、`cvrp_ext_cvrplib_abp_74`、`cvrp_ext_cvrplib_x_100`、`tsp_ext_tsplib_euc2d`、`obp_ext_bpplib`。
- 源码固定：`agent_skill_loop/cvrp_workbench/upstream_rules.py`（锁定 `FeiLiu36/EoH-S@7d4b1f77`）。

## 未确认项与冲突证据

- 上游 `heuristics_cvrp_eohs_run1_top10.py` 与 `heuristics_tsp_eohs_run1_top10.py` 内含 `np.random.rand()` 随机扰动项；本机复跑时按实例固定种子 `20261122` 以保证 100% 可复现，并在大 $n$ 实例下严格遵守 500 ms 预算门控。
""",
    )

    # 2. evidence-bench-eoh-funsearch-obp-tsp-fssp
    eoh_fs_local = [
        b for b in (
            _local_binding(summary, "obp_ext_eoh_weibull", "obp_first_fit"),
            _local_binding(summary, "obp_ext_eoh_weibull", "obp_best_fit"),
            _local_binding(summary, "obp_ext_eoh_weibull", "eoh_obp_f1"),
            _local_binding(summary, "obp_ext_eoh_weibull", "funsearch_obp_f1"),
            _local_binding(summary, "tsp_ext_eohs_128", "eoh_tsp_f1"),
            _local_binding(summary, "cvrp_ext_eohs_256", "eoh_cvrp_f1"),
        ) if b is not None
    ]
    eoh_fs_paper = _filter_pub("src-romera-paredes-2024-funsearch") + _filter_pub("src-feiliu-2024-eoh")
    _upsert(
        "evidence-bench-eoh-funsearch-obp-tsp-fssp",
        {
            "type": "evidence",
            "title": "FunSearch (Table 1) & EoH (Tables 1/3/9/10) benchmark protocol across OBP, TSP-GLS, and FSSP",
            "category": "evidence",
            "problem_family": "online_bin_packing",
            "tags": ["funsearch", "eoh", "obp", "weibull", "tsp-gls", "fssp", "taillard", "paper-reported"],
            "status": "reviewed",
            "summary": "Documents FunSearch (Nature 2024 Table 1) and EoH (ICML 2024 Tables 1/3/9/10) protocols and exact verified table baselines across OBP OR/Weibull, TSP-GLS (1,000 instances vs Concorde), and FSSP Taillard.",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "online_bp",
                "paradigm": "sequential_construct",
                "complexity_class": "empirical",
                "interface": "priority",
                "variant_adaptation_note": "本卡片覆盖在线一维装箱（online_bp）、TSP 导向局部搜索（GLS）与流水车间调度（FSSP）；向标准 CVRP 迁移时仅借鉴进化搜索范式与评估隔离机制，不可跨问题混算指标。",
                "applicable_regimes": {
                    "strong_on": ["obp_weibull_1k_to_100k", "tsp_gls_penalty_evolution", "fssp_taillard_ils"],
                    "weak_on": ["direct_comparison_between_gls_and_single_pass_construct"],
                    "scale_notes": "OBP 采用相对 L1 理论下界超额箱数百分比；TSP-GLS 采用 1,000 例相对 Concorde 差距与原表耗时。",
                },
                "evidence_bindings": eoh_fs_local,
                "paper_reported_results": eoh_fs_paper,
            },
            "relations": {
                "problems": ["problem-online-bin-packing", "problem-tsp"],
                "methods": ["method-lit-ahd-funsearch", "method-lit-ahd-eoh", "method-obp-best-fit", "method-obp-first-fit"],
                "sources": ["src-romera-paredes-2024-funsearch", "src-feiliu-2024-eoh", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-romera-paredes-2024-funsearch", "src-feiliu-2024-eoh", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
            "code_refs": [],
        },
        """# FunSearch（Table 1）与 EoH（Tables 1/3/9/10）跨问题基准协议

整合 **FunSearch**（*Nature* 2024）与 **EoH**（ICML 2024 / `arXiv:2401.02051`）在 OBP、TSP-GLS 与 FSSP Taillard 上的官方原表评测协议与精确对照结果。

## 定义或方法步骤

1. **FunSearch Table 1（OBP）**：在 OR1–OR4 与 Weibull 5k / 10k / 100k 流上比较相对 `L1` 下界的超额箱数比例（`First Fit` `6.42%..4.00%`、`Best Fit` `5.81%..3.79%`、`FunSearch` `5.30%..0.03%`）。
2. **EoH Table 1 / Table 9（OBP Weibull 15 组）**：覆盖 `C=100..500 × {1k, 5k, 10k}`，15 组均值 `First Fit 4.51%`、`Best Fit 4.13%`、`FunSearch 2.23%`、`EoH 1.18%`。
3. **EoH Table 10（TSP-GLS）**：1,000 例 TSP20/50/100 相对 Concorde 最优差距与耗时，`EoH (GLS)` 达 `0.000% / 0.000% / 0.025%`。
4. **EoH Table 3 / Appendix Table 12（FSSP Taillard 11 档 + Average）**：直接核自 `arXiv:2401.02051` p.23 Table 12，`20×5` 至 `200×20` 相对上界差距分别为 `0.09% / 0.30% / 0.10% / 0.02% / 0.19% / 0.60% / -0.04% (100×5) / 0.14% / 0.41% (100×20) / 0.12% (200×10) / 0.61% (200×20)`，全集平均 `0.23%`。

## 适用条件、假设与限制

- TSP-GLS 属于多步迭代导向局部搜索（耗时 0.5–4.5s/例），与单遍顺序构造启发式（毫秒级）处于不同计算预算与范式层级，前端与 LaTeX 导出必须分节列示。
- OBP 在 `C=100` 与 `C=500` 上对规则的数值溢出鲁棒性要求不同（如 `eoh.py` 中的 `np.exp(diff)` 在大 `C` 下须保护上溢）。

## 来源及支持的具体结论

- 全部 64 条原表数值已结构化入库 `published_results/funsearch_eoh_2024_tables.json`（`verified_from_paper_table`），并同步写入 `attributes.paper_reported_results`。
- 本机已在 `obp_ext_eoh_weibull` 与 `obp_ext_bpplib` 上完成 `First Fit`、`Best Fit` 及上游 `eoh.py` / `funsearch.py` 的同协议复跑（`local_recomputed`）。

## 代码和评测关联

- 基准套件：`obp_ext_eoh_weibull`、`obp_ext_bpplib`、`tsp_ext_eohs_128`。
- 评测模块：`agent_skill_loop/cvrp_workbench/tsp_obp.py`、`agent_skill_loop/cvrp_workbench/published_results.py`。

## 未确认项与冲突证据

- FSSP Taillard 仅作为跨问题原表文献参照入库，本仓库暂未注册 FSSP 本地执行器。
""",
    )

    # 3. evidence-bench-reevo-aco-gls-nco
    reevo_local = [
        b for b in (
            _local_binding(summary, "cvrp_ext_reevo_scale", "s2_r5_spiral"),
            _local_binding(summary, "cvrp_ext_reevo_scale", "cw_relocate_2opt"),
            _local_binding(summary, "obp_ext_eoh_weibull", "reevo_obp_f1"),
        ) if b is not None
    ]
    reevo_paper = _filter_pub("src-ye-2024-reevo")
    _upsert(
        "evidence-bench-reevo-aco-gls-nco",
        {
            "type": "evidence",
            "title": "ReEvo (NeurIPS 2024) benchmark protocol & PDF-verified Tables 1-3 (TSP-GLS, TSPLIB, NCO TSP & CVRP)",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["reevo", "gls", "nco", "aco", "pomo", "lehd", "cvrp", "tsp", "paper-reported"],
            "status": "reviewed",
            "summary": "Primary-PDF-verified benchmark tables for ReEvo (arXiv:2402.01145): Table 1 (KGLS-ReEvo TSP20-200), Table 2 (TSPLIB constructive), Table 3 (both TSP-NCO and CVRP-NCO 200/500/1000), plus honest pending flag for §5.2 ACO Fig. 2.",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "llm_ahd_framework",
                "complexity_class": "empirical",
                "interface": "solve_cvrp",
                "applicable_regimes": {
                    "strong_on": ["gls_penalty_evolution", "nco_attention_reshaping", "sample_efficient_reflection"],
                    "weak_on": ["cpu_only_comparison_against_gpu_nco_solvers"],
                    "scale_notes": "直接核对 arXiv:2402.01145 p.8 发现 Table 3 包含 TSP 与 CVRP 两半表：CVRP LEHD+ReEvo 在 200/500/1000 上为 20.85(3.30%) / 38.57(2.94%) / 39.11(4.76%)；TSP LEHD+ReEvo 为 10.77(0.74%) / 16.78(1.55%) / 23.82(2.97%)。",
                },
                "evidence_bindings": reevo_local,
                "paper_reported_results": reevo_paper,
            },
            "relations": {
                "problems": ["problem-cvrp", "problem-tsp"],
                "methods": ["method-lit-ahd-reevo"],
                "sources": ["src-ye-2024-reevo", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-ye-2024-reevo", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
            "code_refs": [],
        },
        """# ReEvo（NeurIPS 2024）多范式基准协议与 PDF 原表核验（Tables 1–3）

直接依据一手原论文 PDF（`arXiv:2402.01145`）与官方仓库 `ai4co/reevo@6dce1825` 核对并入库 ReEvo 在 GLS、构造式 TSPLIB、NCO 注意力重塑与 ACO 上的评测口径。

## 定义或方法步骤

1. **Table 1 · TSP-GLS（p.5）**：在 TSP20/50/100/200 上评估导向局部搜索惩罚函数，`KGLS-ReEvo` 达 `0.000% / 0.000% / 0.000% / 0.216%`（对比 `KGLS` `0.004% / 0.017% / 0.002% / 0.284%`、`EoH` `0.000% / 0.000% / 0.025% / 0.338%`）。
2. **Table 2 · TSPLIB 构造式启发式（p.7）**：平均最优差距 `Human 25.4%`、`GHPP 16.7%`、`ReEvo 14.6%`。
3. **Table 3 · NCO 注意力重塑（p.8，一手 PDF 修正双半表）**：
   - **TSP**：`POMO+ReEvo` `11.12 (4.02%) / 20.54 (24.32%) / 29.86 (29.08%)`；`LEHD+ReEvo` `10.77 (0.74%) / 16.78 (1.55%) / 23.82 (2.97%)`。
   - **CVRP**：`POMO+ReEvo` `22.30 (10.48%) / 47.10 (25.70%) / 118.80 (218.22%)`；`LEHD+ReEvo` `20.85 (3.30%) / 38.57 (2.94%) / 39.11 (4.76%)`。
4. **本地协议对齐集 `cvrp_ext_reevo_scale`**：按 `ai4co/reevo/problems/cvrp_aco/gen_inst.py` 精确参数（`C=50`, `depot=[0.5,0.5]`, `demand∈[1,9]`, `n∈{50,100,200}`）生成 48 例并开展本机 CPU 启发式复跑。

## 适用条件、假设与限制

- Table 3 的 POMO / LEHD 属于需 GPU 预训练的神经组合优化（NCO）求解器，仅作跨范式学术定位参照，绝不与无训练 CPU 启发式混排耗时。

## 来源及支持的具体结论

- 全部 55 条验证数值 + 1 条诚实待提取标记写入 `published_results/reevo_2024_tables.json` 与 `attributes.paper_reported_results`。

## 代码和评测关联

- 基准套件：`cvrp_ext_reevo_scale`、`tsp_ext_eohs_128`、`tsp_ext_tsplib_euc2d`、`obp_ext_eoh_weibull`。

## 未确认项与冲突证据

- 经逐页核验 `arXiv:2402.01145` 原文：**§5.2 ACO 跨五问题对比结果仅以折线/柱状图 Figure 2（p.6）呈现**，原文 Table 4 实为适应度地形自相关分析（Autocorrelation），无公开数值表。因此 ACO 条目严格标注 `verification_status: "pending_pdf_or_repo_table_extraction"`、`value: null`，严禁从图目测估数。
""",
    )

    # 4. evidence-bench-heuragenix-and-cobench
    hx_local = [
        b for b in (
            _local_binding(summary, "cvrp_ext_cvrplib_abp_74", "heuragenix_min_cost_ins"),
            _local_binding(summary, "cvrp_ext_cvrplib_x_100", "heuragenix_min_cost_ins"),
            _local_binding(summary, "cvrp_ext_eohs_256", "heuragenix_min_cost_ins"),
        ) if b is not None
    ]
    hx_cb_paper = _filter_pub("src-msra-2025-heuragenix") + _filter_pub("src-sun-2025-cobench")
    _upsert(
        "evidence-bench-heuragenix-and-cobench",
        {
            "type": "evidence",
            "title": "HeurAgenix (Appendix F Tables 5-6) & CO-Bench (36 CO Problems Fig. 3) PDF-verified benchmarks",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["heuragenix", "co-bench", "cvrplib", "tsplib", "hyper-heuristic", "paper-reported"],
            "status": "reviewed",
            "summary": "Primary-PDF-verified tables for HeurAgenix (arXiv:2506.15196 Appendix F Tables 5-6: CVRPLib 6-instance avg 6.49%, TSPLIB 13-instance avg 0.50%, MKP/JSSP/MaxCut) and CO-Bench (arXiv:2504.04310 Fig. 3: FunSearch 0.842, EoH 0.840, Classical 0.797, ReEvo 0.774).",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "llm_ahd_framework",
                "complexity_class": "empirical",
                "interface": "solve_cvrp",
                "applicable_regimes": {
                    "strong_on": ["large_scale_or_benchmarks", "online_hyper_heuristic_selection", "multi_operator_portfolios"],
                    "weak_on": ["zero_llm_inference_cost_real_time_routing"],
                    "scale_notes": "直接解析两篇一手 arXiv PDF 补齐了规划文档中全部待核数字：CO-Bench EoH = 0.840（精确到第三位小数），HeurAgenix Table 6 CVRP 均值 6.49%（对比 OR-Tools 9.57% / ReEvo+ACO 21.62%）、TSP 均值 0.50%。",
                },
                "evidence_bindings": hx_local,
                "paper_reported_results": hx_cb_paper,
            },
            "relations": {
                "problems": ["problem-cvrp", "problem-tsp"],
                "methods": ["method-lit-ahd-heuragenix", "method-cvrp-inter-relocate"],
                "sources": ["src-msra-2025-heuragenix", "src-sun-2025-cobench", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-msra-2025-heuragenix", "src-sun-2025-cobench", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
            "code_refs": [],
        },
        """# HeurAgenix（Appendix F Tables 5–6）与 CO-Bench（36 题总榜）原表核验

通过直接解析一手 arXiv PDF（`arXiv:2506.15196` p.26–27 与 `arXiv:2504.04310` p.5）并克隆 `microsoft/HeurAgenix@e84bfb19`，完整锁定两篇 2025 顶会/前沿基准的精确原表数据与本机算子复跑对照。

## 定义或方法步骤

1. **HeurAgenix Appendix F Table 6（p.27，五类 CO 基准平均最优差距 %）**：
   - **CVRPLib 6 例**（`A-n80-k10, B-n78-k10, E-n101-k14, F-n135-k7, M-n200-k17, P-n101-k4`）：`OR-Tools 9.57%`、`ACO 43.00%`、`ReEvo+ACO 21.62%`、**`HeurAgenix 6.49%`**（逐例 `3.97 / 2.54 / 10.97 / 8.52 / 9.88 / 3.08%`）。
   - **TSPLIB 13 例**（`kroA100..pr2392`）：`GLS 3.93%`、`ACO 5.08%`、`OR-Tools 8.67%`、`EoH+GLS 1.93%`、`ReEvo+GLS 0.98%`、`ReEvo+ACO 5.80%`、**`HeurAgenix 0.50%`**。
   - **跨问题**：MKP `0.68%`、JSSP `0.25%`、MaxCut `0.60%`。
2. **HeurAgenix Appendix F Table 5（p.26，CVRP 单算子进化前后均值 %）**：`Cheapest Insertion 36.55% -> 25.70%`、`Farthest Insertion 51.59% -> 30.56%`、`NN 48.80% -> 36.55%`。
3. **CO-Bench 36 问题总榜（Fig. 3 p.5，归一化得分 `Avg Score ∈ [0,1]`）**：`FunSearch 0.842`、**`EoH 0.840`**（一手 PDF 核准第三位小数）、`Greedy Refine 0.840`、`Classical Solver 0.797`、`ReEvo 0.774`、`BestOfN 0.774`、`MCTS-AHD 0.762`、`AIDE 0.753`、`Claude-3.7 Sonnet (one-shot) 0.651`。

## 适用条件、假设与限制

- HeurAgenix 在求解阶段调用在线 LLM（GPT-4o / 微调 Qwen-7B）做步级超启发式算子选择，其表 6 成绩包含多算子协同与在线 LLM 推理预算，与纯离线单规则或毫秒级 CPU 启发式属不同范式。

## 来源及支持的具体结论

- 全部 30 条一手核实记录写入 `published_results/heuragenix_cobench_2025_tables.json`（均标 `verified_from_paper_table`）。
- 已将 `microsoft/HeurAgenix@e84bfb19` 的 `min_cost_insertion_3b2b.py` + `two_opt_0554.py` 适配为本机可复跑全解求解器 `heuragenix_min_cost_ins`（`local_recomputed`）。

## 代码和评测关联

- 本机适配求解器：`agent_skill_loop/cvrp_workbench/solvers.py:solve_heuragenix_min_cost_ins`。
- 原表参照：`benchmarks/cvrp_workbench/published_results/heuragenix_cobench_2025_tables.json`。

## 未确认项与冲突证据

- HeurAgenix CVRP 6 个测试例中的 `E-n101-k14 / F-n135-k7 / M-n200-k17` 属于 CVRPLib E/F/M 系列，而本仓库 OR 黄金标准库重点聚焦 A/B/P 全量 74 例与 Uchoa Set X 全量 100 例；横向引用时须注明实例子集差异。
""",
    )

    # 5. evidence-bench-cvrplib-abpx-standard
    cvrplib_local = [
        b for b in (
            _local_binding(summary, "cvrp_ext_cvrplib_abp_74", "s2_r5_spiral"),
            _local_binding(summary, "cvrp_ext_cvrplib_abp_74", "cw_parallel_merge"),
            _local_binding(summary, "cvrp_ext_cvrplib_abp_74", "cw_relocate_2opt"),
            _local_binding(summary, "cvrp_ext_cvrplib_abp_74", "eohs_cvrp_set10_cpi"),
            _local_binding(summary, "cvrp_ext_cvrplib_x_100", "s2_r5_spiral"),
            _local_binding(summary, "cvrp_ext_cvrplib_x_100", "cw_parallel_merge"),
            _local_binding(summary, "cvrp_ext_cvrplib_x_100", "cw_relocate_2opt"),
            _local_binding(summary, "cvrp_ext_cvrplib_x_100", "eohs_cvrp_set10_cpi"),
        ) if b is not None
    ]
    cvrplib_paper = [r for r in _filter_pub("src-feiliu-2025-eohs", table_prefix="Table 3 (CVRPLib")]
    _upsert(
        "evidence-bench-cvrplib-abpx-standard",
        {
            "type": "evidence",
            "title": "CVRPLib OR gold standard protocol: Set A/B/P (74) + Uchoa Set X (100) EUC_2D nint & BKS verification",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["cvrplib", "set-a", "set-b", "set-p", "set-x", "uchoa-2017", "augerat-1995", "euc_2d_nint", "bks"],
            "status": "reviewed",
            "summary": "Locks the full 174-instance CVRPLib OR gold standard (74 Set A/B/P + all 100 Uchoa Set X stratified into X-S/X-M/X-L) with TSPLIB EUC_2D nearest-integer verification and 100/100 Set X zero-error .sol recomputation.",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "parallel_merge",
                "complexity_class": "empirical",
                "interface": "solve_cvrp",
                "applicable_regimes": {
                    "strong_on": ["absolute_bks_calibration", "scale_stress_n100_to_n1000", "cross_paper_ood_benchmark"],
                    "weak_on": ["floating_point_distance_assumption"],
                    "scale_notes": "Set A/B/P 官方 .sol 为固定路线数 k (74/74)；自由车数评估时需另列 exact_k_compliance_rate 与同 k 子集均差（如 cw_relocate_2opt 全 74 例 +4.85%，其中 48/74 满足 ==k 且同 k 子集均差 +4.78%；814 次有效运行中共 200 次路线数 != k）。Set X 为自由车数协议（k 为最少车数下界），按 X-S/X-M/X-L 三档统计且默认按共同完成集 N_common=59 排名。",
                },
                "math_formulation": [
                    {
                        "expr": "d_nint(i, j) = floor(sqrt((x_i - x_j)^2 + (y_i - y_j)^2) + 0.5)",
                        "variables": {"(x_i, y_i)": "节点二维坐标", "d_nint(i,j)": "TSPLIB / CVRPLib 标准整数欧氏距离"},
                        "preconditions": "EDGE_WEIGHT_TYPE = EUC_2D；不可使用 Python 银行家舍入 round() 代替 floor(d + 0.5)",
                    }
                ],
                "evidence_bindings": cvrplib_local,
                "paper_reported_results": cvrplib_paper,
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": [
                    "method-lit-cvrp-construct-clarke-wright-savings-merge",
                    "method-cvrp-inter-relocate",
                    "method-cvrp-s2-r5-spiral",
                ],
                "sources": ["src-augerat-1995-cvrplib-abp", "src-uchoa-2017-cvrplib-x", "src-feiliu-2025-eohs", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-augerat-1995-cvrplib-abp", "src-uchoa-2017-cvrplib-x", "src-feiliu-2025-eohs", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
            "code_refs": [],
        },
        r"""# CVRPLib 黄金标准库协议：Set A/B/P（74 例）与 Uchoa Set X（全量 100 例）

本卡片固化运筹学黄金标准库 **CVRPLib**（`vidalt/CVRPLIB@34985dd2`）两套独立注册套件的精确距离取整、官方 `.sol` BKS 零误差校验与三档规模切分口径。

## 定义或方法步骤

1. **`cvrp_ext_cvrplib_abp_74`（74 例）**：完整导入 Augerat 1995 Set A（27 例）、Set B（23 例，聚类结构）与 Set P（24 例），固化全部官方 `.vrp` / `.sol` SHA-256 及显式 BKS 路线。
2. **`cvrp_ext_cvrplib_x_100`（全量 100 例）**：完整导入 Uchoa et al. 2017 EJOR Set X 全部 100 例（$n=100\text{–}1000$），在汇总与前端按 **`X-S (100–250)` / `X-M (251–500)` / `X-L (501–1000)`** 三档呈现。
3. **严格取整与 `.sol` 自检**：采用 TSPLIB 标准 `floor(hypot(dx, dy) + 0.5)`（`euc_2d_nint`）；独立重算官方 `.sol` 路线长度，Set X 达到 **100/100 严格 `0.0` 误差**，Set A 27/27 与 Set P 24/24 严格 `0.0` 误差。

## 适用条件、假设与限制

- **车数口径严格区分**：
  - `cvrp_ext_cvrplib_abp_74`（Set A/B/P）官方 `.sol` BKS **全部固定为指定车数 $k$（74/74 吻合）**；本地构造与局部搜索求解器当前以容量为硬约束、车数自由（`vehicle_limit_policy = "fixed_k_unconstrained_eval"`），因此除全 74 例 BKS 均差（如 `CW + relocate + 2-opt` 为 `+4.85%`）外，单独统计并列报严格固定车数合规率（`exact_k_compliance_rate`）与同 $k$ 子集均值（`exact_k_mean_rel_gap`：例如 `CW + relocate + 2-opt` 为 **48/74 = 64.9%** 满足 `==k`，同 $k$ 子集均差 **`+4.78%`**，另有 1 例 `P-n55-k8` 少用 1 辆、25 例超出 $k$；全部 11 算法 814 次有效运行中共 200 次路线数 $\ne k$）。
  - `cvrp_ext_cvrplib_x_100`（Uchoa Set X）本身采用**自由车数协议**（`vehicle_limit_policy = "free_fleet_min_k_lb"`），实例名中的 $k$ 仅为最小车数下界 $\lceil \sum q_i / Q \rceil$（官方 BKS 本身在多例上使用 $>k$ 辆车）。
- 500 ms 预算下，$O(n^3)$ 复杂度规则（如 `s2_r7_iso`）在 Set X 大例（$n \ge 500$）会诚实触发超时并计入 `completion_rate`，禁止静默跳过；`common_completed`（`N_common = 59/100`）用于消去样本幸存者偏差。

## 来源及支持的具体结论

- 本机全解评测结果绑定在 `attributes.evidence_bindings`（见 `results/per_instance_records.json`），EoH-S Table 3 原表 OOD 参照绑定在 `attributes.paper_reported_results`。

## 代码和评测关联

- 导入与校验实现：`agent_skill_loop/cvrp_workbench/suites.py`、`agent_skill_loop/cvrp_workbench/protocol.py`。
- 自动化零误差自检：`tests/cvrp_workbench/test_cvrp_workbench.py`。

## 未确认项与冲突证据

- Set B 历史上存在 2 例上游归档 `.sol` 路线记录缺陷：
  1. `B-n50-k8.sol` 第三条路线首客户误录为 `2`（导致客户 `2` 重复访问、客户 `3` 漏访，非法路线长度 `1319`）；按发表的最优解将第三条路线首客户修正为 `3` 后，路线 100% 合法且精确 `euc_2d_nint` 长度为 **`1312`**（与官方 BKS `1312` 严格一致）。
  2. `B-n57-k7.sol` 第五条路线未做组内 2-opt/移位精修（长度 `1155` vs 官方最优值 `1153`）；恢复其组内最优序列 `[0, 52, 50, 37, 39, 42, 30, 2, 55, 1, 0]` 后，路线 100% 合法且精确 `euc_2d_nint` 长度为 **`1153`**（与官方 BKS `1153` 严格一致）。
- 修正上述两例归档路线后，`cvrp_ext_cvrplib_abp_74` 全部 **74/74** 例与 `cvrp_ext_cvrplib_x_100` 全部 **100/100** 例均满足 `verify_cvrp_solution` 100% 可行且 `bks_recomputed_nint_cost == bks_reported_cost == reference_objective`（零误差）。
""",
    )

    # ------------------------------------------------------------------
    # PART 2: 5 Top-Venue LLM-AHD Method Comparison Cards
    # ------------------------------------------------------------------

    ahd_specs = [
        (
            "method-lit-ahd-funsearch",
            "FunSearch: Island-based evolutionary program search with LLMs (Nature 2024)",
            "src-romera-paredes-2024-funsearch",
            ["funsearch", "llm-ahd", "island-evolution", "program-search", "obp", "co-bench"],
            "Island-based evolutionary program search (Romera-Paredes et al., Nature 2024) evolving compact Python priority functions via best-shot prompt sampling across isolated islands.",
            {
                "skeleton_role": "多岛屿程序数据库（Programs Database）维护按得分聚类的候选函数，异步采样两个高分父代构造 few-shot 提示生成新函数并在沙盒评测器打分回库",
                "evolvable_hook": "priority(item, bins) -> np.ndarray 等无状态纯函数评分器",
                "state_maintained": ["islands", "score_clusters", "evaluator_sandbox"],
                "invariants_and_constraints": ["仅进化单个受限入口函数，外层求解循环固定", "周期性重置弱岛屿防止早熟收敛"],
                "typical_pitfalls": ["缺乏自然语言思路（thought）协同表达时，复杂多约束问题的样本效率低于 EoH/ReEvo", "在 CO-Bench 复杂约束题上易触发超时错误"],
            },
            [b for b in (_local_binding(summary, "obp_ext_eoh_weibull", "funsearch_obp_f1"), _local_binding(summary, "obp_ext_bpplib", "funsearch_obp_f1")) if b],
            _filter_pub("src-romera-paredes-2024-funsearch") + _filter_pub("src-sun-2025-cobench", method_ids={"funsearch"}) + _filter_pub("src-feiliu-2025-eohs", method_ids={"funsearch_top1", "funsearch_top10"})[:8],
            """# FunSearch：基于多岛屿进化的 LLM 程序搜索（*Nature* 2024）

Romera-Paredes 等（*Nature* 2024）提出的代表性 LLM 自动启发式设计方法，通过“预训练代码大模型 + 确定性评估器 + 多岛屿程序库”在在线装箱（OBP）与组合数学问题上自动发现超越人工设计的新函数。

## 定义或方法步骤

1. **多岛屿程序数据库初始化**：将种子基线函数放入 $M$ 个独立进化岛屿，各岛按评测得分向量聚类（signature clusters）。
2. **双亲 Few-Shot 采样**：随机择岛并按 Boltzmann 温度采样两个不同簇的精英程序，拼接为版本递增提示（`v0 -> v1 -> v2`）交由 LLM 续写。
3. **沙盒评测与岛屿重置**：在固定评估器上计算客观得分，有效程序回库；定期清空表现最差的半数岛屿并以最优岛屿精英重新播种。

## 适用条件、假设与限制

- 极适合接口简洁、目标评估快且存在非平凡代数结构的单函数评分问题（如 OBP Weibull 100k 达到 `0.03%` 超额箱数，CO-Bench 36 题总榜 `0.842` 居首）。
- 仅在代码层面做隐式变异，缺少显式数学机理/反思总结，在大规模多因子路由问题上单次进化成本高。

## 来源及支持的具体结论

- 原表结果见 `src-romera-paredes-2024-funsearch`（Table 1 OBP）与 `src-sun-2025-cobench`（Fig. 3 `0.842`），已写入 `attributes.paper_reported_results`。
- 本机复跑上游 `funsearch.py` 的 OBP 结果写入 `attributes.evidence_bindings`。

## 代码和评测关联

- 本机复跑规则：`agent_skill_loop/cvrp_workbench/upstream_rules.py:FUNSEARCH_OBP_CODE`、`tsp_obp.py`。

## 未确认项与冲突证据

- FunSearch 原始论文未公开 CVRP 评测；CVRP 对比值来自 EoH-S Table 2 的同框架复现（`FunSearch Top1` 0.294–0.365）。

## EoH 适配

- 本仓库 `agent_skill_loop` 借鉴其无状态评分器与确定性沙盒评测原则，并在外层补充了阶段审计、数学机理归因与资产冻结。
""",
        ),
        (
            "method-lit-ahd-eoh",
            "EoH: Evolution of Heuristics via co-evolution of thoughts and code (ICML 2024)",
            "src-feiliu-2024-eoh",
            ["eoh", "llm-ahd", "thought-code-coevolution", "obp", "tsp-gls", "fssp", "co-bench"],
            "Evolution of Heuristics (Liu et al., ICML 2024) co-evolving natural-language algorithmic thoughts and executable Python code via E1/E2 exploration and M1/M2/M3 modification operators.",
            {
                "skeleton_role": "维护含 (thought, code, fitness) 的精英种群，每代调用 E1/E2 交叉探索与 M1/M2/M3 局部/参数变异算子生成新启发式",
                "evolvable_hook": "单入口启发式函数（OBP priority / TSP-GLS edge_penalty / CVRP select_next_node / FSSP ILS）",
                "state_maintained": ["population_thoughts_and_code", "fitness_history", "operator_schedule"],
                "invariants_and_constraints": ["每次变异必须同步输出算法思想摘要与可执行代码", "按固定训练评测集淘汰低分个体"],
                "typical_pitfalls": ["易陷入单套训练分布过拟合或生成冗长难解释的启发式组合项", "单规则输出难以覆盖强异构工况"],
            },
            [b for b in (_local_binding(summary, "cvrp_ext_eohs_256", "eoh_cvrp_f1"), _local_binding(summary, "tsp_ext_eohs_128", "eoh_tsp_f1"), _local_binding(summary, "obp_ext_eoh_weibull", "eoh_obp_f1")) if b],
            _filter_pub("src-feiliu-2024-eoh")[:16] + _filter_pub("src-sun-2025-cobench", method_ids={"eoh"}),
            """# EoH：算法思想与代码协同进化（ICML 2024）

Liu 等（ICML 2024 / `arXiv:2401.02051`）提出的 **Evolution of Heuristics (EoH)** 框架，将启发式表示为“自然语言算法思想 + 可执行代码”二元组，通过五类提示进化算子显著提升 LLM 自动算法设计的样本效率。

## 定义或方法步骤

1. **双模态个体表示**：每个个体保存自然语言思想描述 `thought` 与对应 Python 代码 `code`。
2. **五类 LLM 进化算子**：
   - `E1`（差异化交叉）：从多父代中综合设计全新思路；
   - `E2`（共性提炼）：提取多父代共同有效机制并重构；
   - `M1`（思路改进）：对单个精英提出结构性改进；
   - `M2`（参数调优）：调整已有启发式关键权重与函数形式；
   - `M3`（简化去冗余）：裁剪无效项增强泛化能力。
3. **种群选择**：在固定训练集打分并保留 Top-$N$ 精英进入下一代。

## 适用条件、假设与限制

- 在 OBP Weibull 15 组均值取得 `1.18%`（优于 FunSearch `2.23%`），TSP-GLS 100 节点达 `0.025%`，CO-Bench 36 题总榜达 **`0.840`**。
- 原生 EoH 仅输出单一最优启发式，面对空间/容量/规模强异构的 CVRP 工况时存在单规则天花板。

## 来源及支持的具体结论

- 原表结果见 `src-feiliu-2024-eoh`（Tables 1/3/9/10）与 `src-sun-2025-cobench`（Fig. 3 `0.840`），绑定在 `attributes.paper_reported_results`。
- 上游 `eoh` CVRP/TSP/OBP 规则的本机复跑结果绑定在 `attributes.evidence_bindings`。

## 代码和评测关联

- 本仓库冻结参考：`eoh_frozen/`（只读）；本机复跑代码：`agent_skill_loop/cvrp_workbench/upstream_rules.py`。

## 未确认项与冲突证据

- 在我们的 Stage-2 消融中，纯无机理引导的进化对照臂在 `P0-120` 上弱于带自主数学机理归因的 `R5`（降幅 4.92%），印证仅靠黑盒思想-代码进化仍易错过主动早返仓等结构机制。

## EoH 适配

- 本仓库内核直接承接 EoH 评估契约并在其上扩展了全解路线骨架、独立 `selection` split 与多范式知识引导。
""",
        ),
        (
            "method-lit-ahd-eohs",
            "EoH-S: Evolution of Complementary Heuristic Set with LLMs (AAAI 2026)",
            "src-feiliu-2025-eohs",
            ["eoh-s", "llm-ahd", "heuristic-set", "cpi", "cvrp", "tsp", "obp", "portfolio"],
            "EoH-S (Liu et al., AAAI 2026 / arXiv:2508.03082) evolves a complementary set of K heuristics evaluated under Complementary Performance Index (CPI) via complementary-aware memetic search.",
            {
                "skeleton_role": "维护互补启发式集合 S（|S|=K），基于逐实例胜出矩阵计算 CPI 与互补贡献度，结合互补交叉与局部精修算子迭代更新集合",
                "evolvable_hook": "集合内每个成员遵循单入口接口（CVRP/TSP select_next_node 或 OBP priority），外层按 CPI 评估互补收益",
                "state_maintained": ["heuristic_set_S", "instance_performance_matrix", "cpi_contributions"],
                "invariants_and_constraints": ["显式优化集合级互补指标 CPI 而非单规则均值", "部署单次推理时需配合外置实例特征选择器（如方向二 RF/Ridge）"],
                "typical_pitfalls": ["CPI 本身等价于事后 Oracle VBS（运行全部 K 个规则取优），与单次求解存在 K 倍算力或选择器遗憾差异"],
            },
            [b for b in (_local_binding(summary, "cvrp_ext_eohs_256", "eohs_cvrp_f1"), _local_binding(summary, "cvrp_ext_eohs_256", "eohs_cvrp_set10_cpi"), _local_binding(summary, "cvrp_ext_cvrplib_abp_74", "eohs_cvrp_set10_cpi"), _local_binding(summary, "cvrp_ext_cvrplib_x_100", "eohs_cvrp_set10_cpi"), _local_binding(summary, "tsp_ext_eohs_128", "eohs_tsp_f1"), _local_binding(summary, "obp_ext_eoh_weibull", "eohs_obp_f1")) if b],
            _filter_pub("src-feiliu-2025-eohs", method_ids={"eoh_s_set10"}),
            """# EoH-S：面向互补启发式集合的 LLM 自动进化（AAAI 2026）

Liu 等（AAAI 2026 / `arXiv:2508.03082`）针对单一启发式难以覆盖异构分布的痛点，提出直接进化一组规模为 $K$ 的互补启发式集合 **EoH-S**，与本课题方向二（性能互补与折外算法选择）形成最直接的顶会对话关系。

## 定义或方法步骤

1. **互补性能指标（CPI）**：对集合 $S = \\{h_1, \\dots, h_K\\}$ 与实例集 $I$，定义 $\\text{CPI}(S) = \\frac{1}{|I|} \\sum_{x \\in I} \\min_{h \\in S} g(h, x)$。
2. **互补感知搜索与管理**：计算各启发式对集合 CPI 的边际贡献与弱势实例覆盖度，通过互补导向交叉/局部改进生成专攻难例的新个体并执行贪心集合管理。
3. **本机同协议复跑**：已将 `FeiLiu36/EoH-S@7d4b1f77` 公开的 CVRP run1 Top-10 集合完整接入本机评测器，同时列报单规则 `eohs_cvrp_f1` 与 10 成员 CPI 集合 `eohs_cvrp_set10_cpi`。

## 适用条件、假设与限制

- 在 EoH-S 原论文 Table 1–3 中全面领先单规则与 Top-10 基线（CVRPLib Set A `0.231`、Set B `0.183`、Set P `0.169`、Set X `0.196`、TSPLib `0.093`、BPPLib Scholl_H `0.095`）。
- 重要范式边界：EoH-S 的 CPI 评测在测试时运行全部 $K=10$ 个启发式并取最优（或依赖选择机制），而本工作台方向二显式计入预求解特征提取 `feat_ms` 与折外选择器推理 `infer_ms` 及选择失误遗憾。

## 来源及支持的具体结论

- 原表 28 条 `EoH-S (Set, K=10)` 精确值见 `attributes.paper_reported_results`；本机同协议复跑结果见 `attributes.evidence_bindings`。

## 代码和评测关联

- 锁定源码：`agent_skill_loop/cvrp_workbench/upstream_rules.py`（`FeiLiu36/EoH-S@7d4b1f77`）。
- 复跑求解器：`eohs_cvrp_f1`、`eohs_cvrp_set10_cpi`、`eohs_tsp_f1`、`eohs_obp_f1`。

## 未确认项与冲突证据

- 本机实测可见：即使在 CVRPLib Set A/B/P/X 上运行完整的 10 成员逐点集合 `eohs_cvrp_set10_cpi`，其质量仍明显落后于并行合并+局部搜索范式（`cw_parallel_merge` / `cw_relocate_2opt`），再次验证“打破单步构造接口天花板”是迈向 OR SOTA 的核心一步。

## EoH 适配

- 直接对齐本仓库的 `select_next_node` 与 `priority` 评测接口，并作为方向二组合互补基准。
""",
        ),
        (
            "method-lit-ahd-reevo",
            "ReEvo: Reflective Evolution LLM Hyper-Heuristic (NeurIPS 2024)",
            "src-ye-2024-reevo",
            ["reevo", "llm-ahd", "reflective-evolution", "gls", "aco", "nco", "co-bench"],
            "Reflective Evolution (Ye et al., NeurIPS 2024 / arXiv:2402.01145) coupling evolutionary search with short-term pairwise reflections and long-term verbal gradient summaries across GLS, ACO, GA, and NCO attention reshaping.",
            {
                "skeleton_role": "双角色 LLM 循环（Generator + Reflector）：基于成对好坏个体对比生成短期反思，提炼为长期反思提示以指导精英交叉与变异",
                "evolvable_hook": "面向多种外层框架的启发式矩阵/评分函数（GLS penalty、ACO heuristic matrix、NCO attention bias、constructive score）",
                "state_maintained": ["population", "short_term_reflections", "long_term_reflection_memory"],
                "invariants_and_constraints": ["反思与进化解耦，支持白盒与黑盒问题提示", "每轮仅保留精炼长期反思防止上下文膨胀"],
                "typical_pitfalls": ["在 CO-Bench 复杂多约束通用问题上（0.774）受限于约束违反错误率，低于 FunSearch/EoH"],
            },
            [b for b in (_local_binding(summary, "obp_ext_eoh_weibull", "reevo_obp_f1"), _local_binding(summary, "obp_ext_bpplib", "reevo_obp_f1")) if b],
            _filter_pub("src-ye-2024-reevo", method_ids={"kgls_reevo", "reevo_constructive", "pomo_reevo", "lehd_reevo", "aco_reevo"}) + _filter_pub("src-sun-2025-cobench", method_ids={"reevo"}),
            """# ReEvo：带反思机制的 LLM 超启发式进化（NeurIPS 2024）

Ye 等（NeurIPS 2024 / `arXiv:2402.01145`）提出的 **ReEvo** 将 LLM 同时作为演化生成器与“语言梯度反思器”，通过短期成对对比反思与长期经验提炼，在 GLS、ACO、GA、构造启发式及 NCO 注意力重塑等异构范式上展现高样本效率。

## 定义或方法步骤

1. **短期反思（Short-term Reflection）**：对同一代中得分一高一低的两个启发式代码做对比，让 Reflector LLM 归纳性能差异原因。
2. **长期反思（Long-term Reflection）**：将多轮短期反思压缩汇总为精简设计准则，防止上下文膨胀。
3. **精英交叉与变异（Elitist Mutation）**：Generator LLM 依据长期反思定向改进精英启发式并回传评测。

## 适用条件、假设与限制

- 显著平滑搜索地形（原文 Table 4 自相关分析），适合低预算黑盒与白盒启发式生成；在 KGLS-ReEvo（TSP200 `0.216%`）与 LEHD+ReEvo（CVRP200 `3.30%`, CVRP500 `2.94%`, CVRP1000 `4.76%`）上取得强结果。
- 当耦合对象为 POMO/LEHD 等 GPU 预训练 NCO 模型时，不可与纯 CPU 无训练算法直接比较运行时间。

## 来源及支持的具体结论

- 原论文 Tables 1–3（经一手 PDF 核对修正 TSP/CVRP 双半表）与 CO-Bench `0.774` 已写入 `attributes.paper_reported_results`；上游 OBP 规则本机复跑写入 `attributes.evidence_bindings`。

## 代码和评测关联

- 官方仓库参考：`ai4co/reevo@6dce1825`；本机复跑 OBP 规则：`agent_skill_loop/cvrp_workbench/upstream_rules.py:REEVO_OBP_CODE`。

## 未确认项与冲突证据

- ReEvo 原文 §5.2 ACO 跨五问题对比仅在 Figure 2 以图像呈现，无数值表；本库严格标为 `pending_pdf_or_repo_table_extraction`。

## EoH 适配

- ReEvo 的“反思记忆”思路与本仓库科研循环的 `research_finding` 相互呼应，但本仓库进一步要求每条假设必须经过受控反事实消融检验（如 H-001 / H-003 / H-004a）。
""",
        ),
        (
            "method-lit-ahd-heuragenix",
            "HeurAgenix: Two-stage heuristic evolution + online LLM hyper-heuristic selection (MSRA 2025)",
            "src-msra-2025-heuragenix",
            ["heuragenix", "llm-ahd", "hyper-heuristic", "online-selection", "cvrplib", "tsplib"],
            "HeurAgenix (Microsoft Research Asia 2025, arXiv:2506.15196) decouples offline multi-operator heuristic evolution from online state-conditioned hyper-heuristic selection across TSP, CVRP, MKP, JSSP, and MaxCut.",
            {
                "skeleton_role": "两阶段架构：阶段一基于问题状态提取与算子进化构建多样化启发式池（构造+局部搜索）；阶段二在求解每步按当前解状态动态选择最合适算子执行",
                "evolvable_hook": "状态条件化移动算子 operator(problem_state, algorithm_data) -> (Operator, dict) 与在线选择策略",
                "state_maintained": ["current_solution", "vehicle_loads", "unvisited_nodes", "problem_state_features", "evolved_operator_pool"],
                "invariants_and_constraints": ["算子通过显式 Operator 对象（Insert / MergeRoutes / ReverseSegment / Relocate）原子更新解状态并保持可行性"],
                "typical_pitfalls": ["在线步级调用大模型推理延迟高、部署成本昂贵（文中通过微调 Qwen-7B 缓解）；传统基础算子如 saving_algorithm_710e 原版存在局部合并条件限制"],
            },
            [b for b in (_local_binding(summary, "cvrp_ext_cvrplib_abp_74", "heuragenix_min_cost_ins"), _local_binding(summary, "cvrp_ext_cvrplib_x_100", "heuragenix_min_cost_ins"), _local_binding(summary, "cvrp_ext_eohs_256", "heuragenix_min_cost_ins"), _local_binding(summary, "cvrp_final_accept_120", "heuragenix_min_cost_ins")) if b],
            _filter_pub("src-msra-2025-heuragenix", method_ids={"heuragenix", "cheapest_insertion_evolved", "farthest_insertion_evolved", "nn_evolved"}),
            """# HeurAgenix：算子进化与在线超启发式动态选择框架（MSRA 2025）

Microsoft Research Asia（`arXiv:2506.15196`，仓库 `microsoft/HeurAgenix@e84bfb19`）提出的端到端 LLM 驱动超启发式框架，突破单步构造接口限制，围绕“全解状态 + 原子移动算子池 + 在线状态选择”在五大 OR 标准库上显著领先先前方法。

## 定义或方法步骤

1. **阶段一 · 多算子离线进化**：为每个问题定义结构化状态（`problem_state.py`）与原子算子（如 CVRP 的 `InsertOperator / MergeRoutesOperator / ReverseSegmentOperator / Relocate`），从 11 个基础算子出发自动进化出更强变体（如 `min_cost_insertion_3b2b.py`：引入仓库半径展宽惩罚 `0.05` 与周期性 2-opt/移位）。
2. **阶段二 · 在线超启发式选择**：在求解过程中按实时解状态由 GPT-4o 或经双奖励（POR）微调的 Qwen-7B 选择下一步算子。

## 适用条件、假设与限制

- 直接核自一手 PDF Appendix F Table 6（p.27）：在 CVRPLib 6 大例均值达到 **`6.49%`**（优于 OR-Tools `9.57%`、ReEvo+ACO `21.62%`），TSPLIB 13 例均值达到 **`0.50%`**（优于 ReEvo+GLS `0.98%`、EoH+GLS `1.93%`）。
- 启发了本课题里程碑二的“全解接口骨架（`solve_cvrp`）与轻量级离线选择器”结合路线：以毫秒级特征选择器替代昂贵的在线步级 LLM 调用。

## 来源及支持的具体结论

- 原论文 Appendix F Table 5 & 6 精确数据已写入 `attributes.paper_reported_results`。
- 已将仓库 `min_cost_insertion_3b2b.py` + `two_opt_0554.py` 适配为本机可复跑求解器 `heuragenix_min_cost_ins`（`local_recomputed`），实测数据绑定在 `attributes.evidence_bindings`。

## 代码和评测关联

- 本机复跑实现：`agent_skill_loop/cvrp_workbench/solvers.py:solve_heuragenix_min_cost_ins`（源 commit `e84bfb19e785ae2d670af6e3ab68890c71c536ea`）。

## 未确认项与冲突证据

- 检查上游源码发现基础算子 `saving_algorithm_710e.py` 存在 `not len(route2) <= 1` 与 `rotated_route2 = route1[...]` 的原仓库实现笔误，因此本机复跑优先忠实适配其已验证进化算子 `min_cost_insertion_3b2b.py` 及 `two_opt_0554.py`。

## EoH 适配

- 原生基于 `solve_cvrp` 全解状态与算子对象，不可直接塞入 `select_next_node` 单步构造骨架（`not_mappable`）；需在全解状态骨架下作为可进化算子模块集成。
""",
        ),
    ]

    for eid, title, primary_src, tags, summ, blueprint, ev_b, pr_b, md_text in ahd_specs:
        _upsert(
            eid,
            {
                "type": "method",
                "title": title,
                "category": "optimization_frameworks_experiments",
                "problem_family": "unknown",
                "tags": tags,
                "status": "reviewed",
                "summary": summ,
                "attributes": {
                    "method_family": "llm_ahd_framework",
                    "online_offline": "offline",
                    "objective": "cross-problem combinatorial optimization gap",
                    "knowledge_tier": "literature_abstract" if not ev_b else "verified_experiment",
                    "problem_variant": "standard_cvrp",
                    "paradigm": "llm_ahd_framework",
                    "complexity_class": "empirical",
                    "interface": "solve_cvrp",
                    "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                    "applicable_regimes": {
                        "strong_on": ["automated_heuristic_design", "cross_problem_benchmarking"],
                        "weak_on": ["zero_budget_single_pass_without_evolution"],
                        "scale_notes": "顶会 LLM-AHD 方法横向对比卡，严格分轨记录本机同协议复跑 (evidence_bindings) 与原论文发表成绩 (paper_reported_results)。",
                    },
                    "interface_blueprint": blueprint,
                    "evidence_bindings": ev_b,
                    "paper_reported_results": pr_b,
                },
                "relations": {
                    "problems": ["problem-cvrp", "problem-tsp", "problem-online-bin-packing"],
                    "sources": sorted({primary_src, "src-cvrp-workbench-20261121"}),
                },
                "source_refs": sorted({primary_src, "src-cvrp-workbench-20261121"}),
                "evidence_refs": ["report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
                "code_refs": [],
            },
            md_text,
        )

    return {"added_top_venue_sources": added_sources, "top_venue_cards_count": 10}
