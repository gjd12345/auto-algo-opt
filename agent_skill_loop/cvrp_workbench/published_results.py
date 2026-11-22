"""Machine-readable published top-venue paper reference tables (published_results/*.json).

Every record strictly obeys docs/cvrp-kb-benchmark-frontend-final-plan.md §2.2:
- ``comparison_mode`` is ALWAYS ``"paper_reported_reference"`` (never mixed with
  ``"local_recomputed"`` timings or rankings).
- Every numeric value is verified directly from primary papers / arXiv PDFs
  (``verification_status: "verified_from_paper_table"``). Where a paper only
  presents a figure without a numerical table (e.g., ReEvo §5.2 ACO Fig. 2),
  the record carries ``value: null`` and
  ``verification_status: "pending_pdf_or_repo_table_extraction"``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


REQUIRED_PUBLISHED_FIELDS = (
    "record_id",
    "paper_source_id",
    "paper_citation",
    "table_ref",
    "suite_id",
    "subset",
    "problem_family",
    "method_id",
    "method_display_name",
    "paradigm",
    "metric_name",
    "value",
    "unit",
    "direction",
    "reference_kind",
    "comparison_mode",
    "verification_status",
    "protocol_boundary_note",
    "local_reproducible",
    "upstream_code_ref",
)

ALLOWED_VERIFICATION_STATUSES = frozenset({
    "verified_from_paper_table",
    "pending_pdf_or_repo_table_extraction",
})


def _rec(
    *,
    record_id: str,
    paper_source_id: str,
    paper_citation: str,
    table_ref: str,
    suite_id: str,
    subset: str,
    problem_family: str,
    method_id: str,
    method_display_name: str,
    paradigm: str,
    metric_name: str,
    value: float | None,
    unit: str,
    direction: str,
    reference_kind: str,
    protocol_boundary_note: str,
    verification_status: str = "verified_from_paper_table",
    local_reproducible: bool = False,
    upstream_code_ref: str = "",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "record_id": record_id,
        "paper_source_id": paper_source_id,
        "paper_citation": paper_citation,
        "table_ref": table_ref,
        "suite_id": suite_id,
        "subset": subset,
        "problem_family": problem_family,
        "method_id": method_id,
        "method_display_name": method_display_name,
        "paradigm": paradigm,
        "metric_name": metric_name,
        "value": value,
        "unit": unit,
        "direction": direction,
        "reference_kind": reference_kind,
        "comparison_mode": "paper_reported_reference",
        "verification_status": verification_status,
        "protocol_boundary_note": protocol_boundary_note,
        "local_reproducible": local_reproducible,
        "upstream_code_ref": upstream_code_ref,
    }
    if extra:
        row.update(extra)
    return row


def build_eohs_2025_tables() -> list[dict[str, Any]]:
    """EoH-S (AAAI 2026 / arXiv:2508.03082) Tables 1, 2, and 3."""
    cite = "Liu et al., AAAI 2026 (arXiv:2508.03082)"
    src = "src-feiliu-2025-eohs"
    ref = "FeiLiu36/EoH-S@7d4b1f77"
    rows: list[dict[str, Any]] = []

    # Table 1: OBP multi-capacity & scale (mean relative gap to L1 LB, ratio)
    # Verified directly from arXiv:2508.03082 PDF p.5 Table 1 (3 training regimes + 6 testing regimes = 9 columns)
    t1_note = "EoH-S Table 1 (arXiv:2508.03082 p.5) OBP 多规模多容量（3 个训练分档 c100 + 6 个测试分档 c200/c500）：Top10 与 EoH-S 按 10 启发式互补集合每例最优 (CPI) 计分，其余为单规则；与异机耗时不可混排。"
    obp_regimes = [
        "Train_n200_500_c100",
        "Train_n500_1k_c100",
        "Train_n1k_2k_c100",
        "n1k_c200",
        "n1k_c500",
        "n5k_c200",
        "n5k_c500",
        "n10k_c200",
        "n10k_c500",
    ]
    t1_data = {
        ("first_fit", "First Fit", "sequential_construct"): [0.0652, 0.0318, 0.0387, 0.0240, 0.0124, 0.0173, 0.0075, 0.0163, 0.0055],
        ("best_fit", "Best Fit", "sequential_construct"): [0.0627, 0.0310, 0.0372, 0.0220, 0.0124, 0.0161, 0.0070, 0.0154, 0.0050],
        ("funsearch_top1", "FunSearch (Top 1)", "sequential_construct"): [0.0623, 0.0298, 0.0367, 0.0213, 0.0124, 0.0159, 0.0070, 0.0152, 0.0051],
        ("funsearch_top10", "FunSearch (Top 10, CPI)", "complementary_constructive_set"): [0.0608, 0.0289, 0.0361, 0.0200, 0.0124, 0.0153, 0.0065, 0.0123, 0.0038],
        ("eoh_top1", "EoH (Top 1)", "sequential_construct"): [0.0619, 0.0307, 0.0371, 0.0240, 0.0133, 0.0182, 0.0075, 0.0170, 0.0059],
        ("eoh_top10", "EoH (Top 10, CPI)", "complementary_constructive_set"): [0.0618, 0.0299, 0.0368, 0.0216, 0.0124, 0.0158, 0.0065, 0.0152, 0.0051],
        ("reevo_top1", "ReEvo (Top 1)", "sequential_construct"): [0.0604, 0.0298, 0.0362, 0.0217, 0.0133, 0.0162, 0.0068, 0.0155, 0.0053],
        ("reevo_top10", "ReEvo (Top 10, CPI)", "complementary_constructive_set"): [0.0580, 0.0285, 0.0349, 0.0203, 0.0124, 0.0125, 0.0063, 0.0108, 0.0049],
        ("eoh_s_set10", "EoH-S (Heuristic Set, K=10)", "complementary_constructive_set"): [0.0515, 0.0230, 0.0314, 0.0113, 0.0124, 0.0033, 0.0025, 0.0014, 0.0010],
    }
    for (mid, mname, parad), vals in t1_data.items():
        for reg, val in zip(obp_regimes, vals):
            rows.append(_rec(
                record_id=f"pub-eohs-2025-tbl1-obp-{reg.lower()}-{mid}",
                paper_source_id=src,
                paper_citation=cite,
                table_ref=f"Table 1 (OBP {reg})",
                suite_id="obp_ext_eoh_weibull",
                subset=reg,
                problem_family="obp",
                method_id=mid,
                method_display_name=mname,
                paradigm=parad,
                metric_name="mean_rel_gap_to_lb",
                value=val,
                unit="ratio",
                direction="minimize",
                reference_kind="theoretical_lb",
                protocol_boundary_note=t1_note,
                local_reproducible=True,
                upstream_code_ref=ref,
            ))

    # Table 2: CVRP synthetic multi-scale (relative gap to LKH, ratio)
    t2_cvrp_note = "EoH-S Table 2 合成多分布 CVRP（相对 LKH 平均差距）；Top10 / EoH-S 为 10 启发式互补集合每例最优 (CPI)，Top1 为单规则。"
    cvrp_regimes = ["Train_256", "Test_n50", "Test_n100", "Test_n200", "Test_n500"]
    t2_cvrp = {
        ("funsearch_top1", "FunSearch (Top 1)", "sequential_construct"): [0.294, 0.315, 0.365, 0.296, 0.241],
        ("funsearch_top10", "FunSearch (Top 10, CPI)", "complementary_constructive_set"): [0.245, 0.267, 0.309, 0.247, 0.214],
        ("eoh_top1", "EoH (Top 1)", "sequential_construct"): [0.276, 0.274, 0.299, 0.261, 0.221],
        ("eoh_top10", "EoH (Top 10, CPI)", "complementary_constructive_set"): [0.230, 0.172, 0.232, 0.218, 0.198],
        ("reevo_top1", "ReEvo (Top 1)", "sequential_construct"): [0.265, 0.274, 0.296, 0.256, 0.203],
        ("reevo_top10", "ReEvo (Top 10, CPI)", "complementary_constructive_set"): [0.240, 0.214, 0.249, 0.173, 0.178],
        ("eoh_s_set10", "EoH-S (Heuristic Set, K=10)", "complementary_constructive_set"): [0.173, 0.135, 0.188, 0.180, 0.169],
    }
    for (mid, mname, parad), vals in t2_cvrp.items():
        for reg, val in zip(cvrp_regimes, vals):
            rows.append(_rec(
                record_id=f"pub-eohs-2025-tbl2-cvrp-{reg.lower()}-{mid}",
                paper_source_id=src,
                paper_citation=cite,
                table_ref=f"Table 2 (CVRP {reg})",
                suite_id="cvrp_ext_eohs_256",
                subset=reg,
                problem_family="cvrp",
                method_id=mid,
                method_display_name=mname,
                paradigm=parad,
                metric_name="mean_rel_gap_to_lkh",
                value=val,
                unit="ratio",
                direction="minimize",
                reference_kind="lkh_reference",
                protocol_boundary_note=t2_cvrp_note,
                local_reproducible=True,
                upstream_code_ref=ref,
            ))

    # Table 2: TSP synthetic multi-scale (relative gap to LKH, ratio)
    t2_tsp_note = "EoH-S Table 2 合成多分布 TSP（相对 LKH 平均差距）；Top10 / EoH-S 为 10 启发式互补集合每例最优 (CPI)。"
    tsp_regimes = ["Train_128", "Test_n50", "Test_n100", "Test_n200", "Test_n500"]
    t2_tsp = {
        ("funsearch_top1", "FunSearch (Top 1)", "sequential_construct"): [0.156, 0.144, 0.149, 0.169, 0.185],
        ("funsearch_top10", "FunSearch (Top 10, CPI)", "complementary_constructive_set"): [0.124, 0.091, 0.105, 0.124, 0.157],
        ("eoh_top1", "EoH (Top 1)", "sequential_construct"): [0.152, 0.142, 0.154, 0.168, 0.194],
        ("eoh_top10", "EoH (Top 10, CPI)", "complementary_constructive_set"): [0.127, 0.079, 0.123, 0.134, 0.175],
        ("reevo_top1", "ReEvo (Top 1)", "sequential_construct"): [0.155, 0.167, 0.183, 0.223, 0.221],
        ("reevo_top10", "ReEvo (Top 10, CPI)", "complementary_constructive_set"): [0.117, 0.092, 0.123, 0.157, 0.170],
        ("eoh_s_set10", "EoH-S (Heuristic Set, K=10)", "complementary_constructive_set"): [0.097, 0.040, 0.065, 0.090, 0.111],
    }
    for (mid, mname, parad), vals in t2_tsp.items():
        for reg, val in zip(tsp_regimes, vals):
            rows.append(_rec(
                record_id=f"pub-eohs-2025-tbl2-tsp-{reg.lower()}-{mid}",
                paper_source_id=src,
                paper_citation=cite,
                table_ref=f"Table 2 (TSP {reg})",
                suite_id="tsp_ext_eohs_128",
                subset=reg,
                problem_family="tsp",
                method_id=mid,
                method_display_name=mname,
                paradigm=parad,
                metric_name="mean_rel_gap_to_lkh",
                value=val,
                unit="ratio",
                direction="minimize",
                reference_kind="lkh_reference",
                protocol_boundary_note=t2_tsp_note,
                local_reproducible=True,
                upstream_code_ref=ref,
            ))

    # Table 3: CVRPLib (A/B/E/F/M/P/X), TSPLib, BPPLib (Sch_1/Sch_2/Scholl_H)
    t3_methods = [
        ("eoh_top1", "EoH (Top 1)", "sequential_construct"),
        ("eoh_top10", "EoH (Top 10, CPI)", "complementary_constructive_set"),
        ("reevo_top1", "ReEvo (Top 1)", "sequential_construct"),
        ("reevo_top10", "ReEvo (Top 10, CPI)", "complementary_constructive_set"),
        ("eoh_s_set10", "EoH-S (Heuristic Set, K=10)", "complementary_constructive_set"),
    ]
    t3_rows = [
        ("cvrp_ext_cvrplib_abp_74", "CVRPLib_Set_A", "cvrp", "Table 3 (CVRPLib A)", "mean_rel_gap_to_bks", "best_known", [0.326, 0.277, 0.329, 0.261, 0.231]),
        ("cvrp_ext_cvrplib_abp_74", "CVRPLib_Set_B", "cvrp", "Table 3 (CVRPLib B)", "mean_rel_gap_to_bks", "best_known", [0.374, 0.310, 0.352, 0.250, 0.183]),
        ("cvrp_ext_cvrplib_abp_74", "CVRPLib_Set_E", "cvrp", "Table 3 (CVRPLib E)", "mean_rel_gap_to_bks", "best_known", [0.334, 0.268, 0.305, 0.257, 0.242]),
        ("cvrp_ext_cvrplib_abp_74", "CVRPLib_Set_F", "cvrp", "Table 3 (CVRPLib F)", "mean_rel_gap_to_bks", "best_known", [0.539, 0.493, 0.687, 0.547, 0.427]),
        ("cvrp_ext_cvrplib_abp_74", "CVRPLib_Set_M", "cvrp", "Table 3 (CVRPLib M)", "mean_rel_gap_to_bks", "best_known", [0.461, 0.377, 0.442, 0.372, 0.299]),
        ("cvrp_ext_cvrplib_abp_74", "CVRPLib_Set_P", "cvrp", "Table 3 (CVRPLib P)", "mean_rel_gap_to_bks", "best_known", [0.273, 0.206, 0.270, 0.188, 0.169]),
        ("cvrp_ext_cvrplib_x_100", "CVRPLib_Set_X", "cvrp", "Table 3 (CVRPLib X)", "mean_rel_gap_to_bks", "best_known", [0.270, 0.237, 0.270, 0.224, 0.196]),
        ("tsp_ext_tsplib_euc2d", "TSPLib", "tsp", "Table 3 (TSPLib)", "mean_rel_gap_to_opt", "best_known", [0.184, 0.173, 0.220, 0.165, 0.093]),
        ("obp_ext_bpplib", "BPPLib_Sch_1", "obp", "Table 3 (BPPLib Sch_1)", "mean_rel_gap_to_lb", "theoretical_lb", [0.153, 0.153, 0.153, 0.153, 0.152]),
        ("obp_ext_bpplib", "BPPLib_Sch_2", "obp", "Table 3 (BPPLib Sch_2)", "mean_rel_gap_to_lb", "theoretical_lb", [0.142, 0.142, 0.142, 0.142, 0.141]),
        ("obp_ext_bpplib", "BPPLib_Scholl_H", "obp", "Table 3 (BPPLib Scholl_H)", "mean_rel_gap_to_lb", "theoretical_lb", [0.138, 0.138, 0.138, 0.138, 0.095]),
        ("obp_ext_bpplib", "BPPLib_IRUP", "obp", "Table 3 (BPPLib IRUP)", "mean_rel_gap_to_lb", "theoretical_lb", [0.077, 0.075, 0.079, 0.074, 0.072]),
        ("obp_ext_bpplib", "BPPLib_NonIRUP", "obp", "Table 3 (BPPLib Non-IRUP)", "mean_rel_gap_to_lb", "theoretical_lb", [0.077, 0.076, 0.080, 0.075, 0.073]),
    ]
    for suite_id, subset, fam, tref, metric_name, ref_kind, vals in t3_rows:
        for (mid, mname, parad), val in zip(t3_methods, vals):
            note = (
                "10 启发式互补集合按每例最优 (CPI) 计分；与本机单算法实测及异机耗时不可混排。"
                if parad == "complementary_constructive_set"
                else "EoH-S Table 3 逐点单规则原表 OOD 相对差距；异机协议仅作学术定位参照。"
            )
            rows.append(_rec(
                record_id=f"pub-eohs-2025-tbl3-{subset.lower()}-{mid}",
                paper_source_id=src,
                paper_citation=cite,
                table_ref=tref,
                suite_id=suite_id,
                subset=subset,
                problem_family=fam,
                method_id=mid,
                method_display_name=mname,
                paradigm=parad,
                metric_name=metric_name,
                value=val,
                unit="ratio",
                direction="minimize",
                reference_kind=ref_kind,
                protocol_boundary_note=note,
                local_reproducible=True,
                upstream_code_ref=ref,
            ))
    return rows


def build_funsearch_eoh_2024_tables() -> list[dict[str, Any]]:
    """FunSearch (Nature 2024) Table 1 + EoH (ICML 2024) Tables 1, 3, 9, 10."""
    rows: list[dict[str, Any]] = []

    # FunSearch Table 1: OBP excess bins over L1 lower bound (%)
    fs_cite = "Romera-Paredes et al., Nature 2024"
    fs_src = "src-romera-paredes-2024-funsearch"
    fs_note = "FunSearch Nature 2024 Table 1 在线装箱超额箱数百分比（相对 L1 下界）；与本机实测物理分轨。"
    fs_subsets = ["OR1", "OR2", "OR3", "OR4", "Weibull_5k", "Weibull_10k", "Weibull_100k"]
    fs_table = {
        ("first_fit", "First Fit", "sequential_construct"): [6.42, 6.45, 5.74, 5.23, 4.23, 4.20, 4.00],
        ("best_fit", "Best Fit", "sequential_construct"): [5.81, 6.06, 5.37, 4.94, 3.98, 3.90, 3.79],
        ("funsearch", "FunSearch", "sequential_construct"): [5.30, 4.19, 3.11, 2.47, 0.68, 0.32, 0.03],
    }
    for (mid, mname, parad), vals in fs_table.items():
        for sub, val in zip(fs_subsets, vals):
            rows.append(_rec(
                record_id=f"pub-funsearch-2024-tbl1-{sub.lower()}-{mid}",
                paper_source_id=fs_src,
                paper_citation=fs_cite,
                table_ref=f"Table 1 ({sub})",
                suite_id="obp_ext_eoh_weibull",
                subset=f"FunSearch_{sub}",
                problem_family="obp",
                method_id=mid,
                method_display_name=mname,
                paradigm=parad,
                metric_name="excess_bins_pct_over_l1",
                value=val,
                unit="percent",
                direction="minimize",
                reference_kind="theoretical_lb",
                protocol_boundary_note=fs_note,
                local_reproducible=True,
                upstream_code_ref="google-deepmind/funsearch",
            ))

    # EoH (ICML 2024) Table 9 / Table 1: OBP Weibull (15-setting mean & C=100, C=500)
    eoh_cite = "Liu et al., ICML 2024 (arXiv:2401.02051)"
    eoh_src = "src-feiliu-2024-eoh"
    eoh_ref = "FeiLiu36/EoH@47254578"
    eoh_obp_note = "EoH ICML 2024 Table 1 / Table 9 OBP Weibull 超额箱数百分比（相对 L1 下界）。"
    for mid, mname, val in [
        ("first_fit", "First Fit", 4.51),
        ("best_fit", "Best Fit", 4.13),
        ("funsearch", "FunSearch", 2.23),
        ("eoh", "EoH", 1.18),
    ]:
        rows.append(_rec(
            record_id=f"pub-eoh-2024-tbl9-obp-mean15-{mid}",
            paper_source_id=eoh_src,
            paper_citation=eoh_cite,
            table_ref="Table 1 / Table 9 (Weibull 15-setting Avg)",
            suite_id="obp_ext_eoh_weibull",
            subset="Weibull_15_Avg",
            problem_family="obp",
            method_id=mid,
            method_display_name=mname,
            paradigm="sequential_construct",
            metric_name="excess_bins_pct_over_l1",
            value=val,
            unit="percent",
            direction="minimize",
            reference_kind="theoretical_lb",
            protocol_boundary_note=eoh_obp_note,
            local_reproducible=True,
            upstream_code_ref=eoh_ref,
        ))
    for subset, eoh_v, fs_v in [
        ("Weibull_1k_C100", 2.24, 3.78),
        ("Weibull_5k_C100", 0.80, 0.80),
        ("Weibull_10k_C100", 0.61, 0.33),
        ("Weibull_1k_C500", 2.13, 6.75),
        ("Weibull_5k_C500", 0.78, 1.47),
        ("Weibull_10k_C500", 0.61, 0.74),
    ]:
        for mid, mname, val in (("eoh", "EoH", eoh_v), ("funsearch", "FunSearch", fs_v)):
            rows.append(_rec(
                record_id=f"pub-eoh-2024-tbl9-{subset.lower()}-{mid}",
                paper_source_id=eoh_src,
                paper_citation=eoh_cite,
                table_ref=f"Table 9 ({subset})",
                suite_id="obp_ext_eoh_weibull",
                subset=subset,
                problem_family="obp",
                method_id=mid,
                method_display_name=mname,
                paradigm="sequential_construct",
                metric_name="excess_bins_pct_over_l1",
                value=val,
                unit="percent",
                direction="minimize",
                reference_kind="theoretical_lb",
                protocol_boundary_note=eoh_obp_note,
                local_reproducible=True,
                upstream_code_ref=eoh_ref,
            ))

    # EoH Table 10: TSP Guided Local Search (1000 instances mean gap % vs Concorde)
    eoh_tsp_note = "EoH ICML 2024 Table 10 导向局部搜索 (GLS) 1,000 例相对 Concorde 差距（%）；属迭代局部搜索范式，与单步构造不可直接混排。"
    tsp_gls_rows = [
        ("concorde", "Concorde (Exact)", "exact_solver", [0.000, 0.000, 0.000], [0.010, 0.051, 0.224]),
        ("lkh3", "LKH3", "metaheuristic", [0.000, 0.000, 0.011], [0.020, 0.069, 0.118]),
        ("gls", "GLS", "local_search", [0.004, 0.045, 0.659], [None, None, None]),
        ("ebgls", "EBGLS", "local_search", [0.002, 0.003, 0.155], [None, None, None]),
        ("kgls", "KGLS", "local_search", [0.000, 0.000, 0.035], [None, None, None]),
        ("eoh_gls", "EoH (GLS)", "local_search", [0.000, 0.000, 0.025], [0.498, 1.494, 4.510]),
    ]
    for mid, mname, parad, gaps, times in tsp_gls_rows:
        for sz, gap, tsec in zip(("TSP20", "TSP50", "TSP100"), gaps, times):
            rows.append(_rec(
                record_id=f"pub-eoh-2024-tbl10-{sz.lower()}-{mid}",
                paper_source_id=eoh_src,
                paper_citation=eoh_cite,
                table_ref=f"Table 10 ({sz} GLS)",
                suite_id="tsp_ext_eohs_128",
                subset=f"EoH_{sz}_1000",
                problem_family="tsp",
                method_id=mid,
                method_display_name=mname,
                paradigm=parad,
                metric_name="mean_opt_gap_pct_vs_concorde",
                value=gap,
                unit="percent",
                direction="minimize",
                reference_kind="known_optimum",
                protocol_boundary_note=eoh_tsp_note,
                local_reproducible=False,
                upstream_code_ref=eoh_ref,
                extra=({"paper_reported_time_s": tsec} if tsec is not None else None),
            ))

    # EoH Table 3 / Appendix Table 12: FSSP Taillard 11 scales + Average (gap % vs upper bound)
    # Verified directly from arXiv:2401.02051 PDF p.23 Table 12 (100x5 = -0.04%, 100x20 = 0.41%, 200x10 = 0.12%, 200x20 = 0.61%, Avg = 0.23%)
    fssp_note = "EoH ICML 2024 Table 3 / Appendix Table 12 (arXiv:2401.02051 p.23) Flow Shop Scheduling (Taillard 11 档规模及均值相对上界差距 %)，纳入跨问题文献参照。"
    fssp_scales = ["20x5", "20x10", "20x20", "50x5", "50x10", "50x20", "100x5", "100x10", "100x20", "200x10", "200x20", "Average"]
    eoh_fssp_vals = [0.09, 0.30, 0.10, 0.02, 0.19, 0.60, -0.04, 0.14, 0.41, 0.12, 0.61, 0.23]
    for sc, val in zip(fssp_scales, eoh_fssp_vals):
        rows.append(_rec(
            record_id=f"pub-eoh-2024-tbl3-fssp-{sc.lower()}-eoh-ils",
            paper_source_id=eoh_src,
            paper_citation=eoh_cite,
            table_ref=f"Table 3 / Table 12 (FSSP Taillard {sc})",
            suite_id="fssp_taillard_paper_ref",
            subset=f"Taillard_{sc}",
            problem_family="fssp",
            method_id="eoh_ils",
            method_display_name="EoH (ILS)",
            paradigm="local_search",
            metric_name="mean_gap_pct_vs_ub",
            value=val,
            unit="percent",
            direction="minimize",
            reference_kind="best_known",
            protocol_boundary_note=fssp_note,
            local_reproducible=False,
            upstream_code_ref=eoh_ref,
        ))
    return rows


def build_reevo_2024_tables() -> list[dict[str, Any]]:
    """ReEvo (NeurIPS 2024 / arXiv:2402.01145) Tables 1, 2, 3 (verified directly from PDF) + ACO Fig. 2 note."""
    cite = "Ye et al., NeurIPS 2024 (arXiv:2402.01145)"
    src = "src-ye-2024-reevo"
    ref = "ai4co/reevo@6dce1825"
    rows: list[dict[str, Any]] = []

    # Table 1: TSP-GLS (TSP20 / 50 / 100 / 200 opt gap % & paper time)
    t1_note = "ReEvo NeurIPS 2024 Table 1 TSP-GLS 相对最优差距（%）；使用单核 AMD EPYC 7742 测时，属 GLS 局部搜索范式。"
    t1_rows = [
        ("neuopt", "NeuOpt (LS+RL)", "neural_local_search", [0.000, 0.000, 0.027, 0.403], [0.124, 1.32, 2.67, 4.81]),
        ("eoh_gls", "EoH (GLS)", "local_search", [0.000, 0.000, 0.025, 0.338], [0.563, 1.90, 5.87, 17.52]),
        ("kgls", "KGLS", "local_search", [0.004, 0.017, 0.002, 0.284], [0.001, 0.03, 1.55, 2.52]),
        ("kgls_reevo", "KGLS-ReEvo", "local_search", [0.000, 0.000, 0.000, 0.216], [0.001, 0.03, 1.55, 2.52]),
    ]
    for mid, mname, parad, gaps, times in t1_rows:
        for sz, gap, tsec in zip(("TSP20", "TSP50", "TSP100", "TSP200"), gaps, times):
            rows.append(_rec(
                record_id=f"pub-reevo-2024-tbl1-{sz.lower()}-{mid}",
                paper_source_id=src,
                paper_citation=cite,
                table_ref=f"Table 1 ({sz} GLS)",
                suite_id="tsp_ext_eohs_128",
                subset=f"ReEvo_{sz}",
                problem_family="tsp",
                method_id=mid,
                method_display_name=mname,
                paradigm=parad,
                metric_name="mean_opt_gap_pct",
                value=gap,
                unit="percent",
                direction="minimize",
                reference_kind="known_optimum",
                protocol_boundary_note=t1_note,
                local_reproducible=False,
                upstream_code_ref=ref,
                extra={"paper_reported_time_s": tsec},
            ))

    # Table 2: TSPLIB constructive heuristic comparison (Avg opt gap %)
    t2_note = "ReEvo NeurIPS 2024 Table 2 TSPLIB 构造式启发式平均最优差距（%），直接核自 arXiv:2402.01145 p.7。"
    for mid, mname, val in [
        ("human_constructive", "Human Constructive", 25.4),
        ("ghpp", "GHPP", 16.7),
        ("reevo_constructive", "ReEvo (Constructive)", 14.6),
    ]:
        rows.append(_rec(
            record_id=f"pub-reevo-2024-tbl2-tsplib-{mid}",
            paper_source_id=src,
            paper_citation=cite,
            table_ref="Table 2 (TSPLIB Constructive Avg)",
            suite_id="tsp_ext_tsplib_euc2d",
            subset="TSPLIB_ReEvo_Table2",
            problem_family="tsp",
            method_id=mid,
            method_display_name=mname,
            paradigm="sequential_construct",
            metric_name="mean_opt_gap_pct",
            value=val,
            unit="percent",
            direction="minimize",
            reference_kind="best_known",
            protocol_boundary_note=t2_note,
            local_reproducible=False,
            upstream_code_ref=ref,
        ))

    # Table 3: NCO Attention Reshaping — BOTH TSP AND CVRP verified verbatim from arXiv:2402.01145 p.8!
    t3_tsp_note = "ReEvo NeurIPS 2024 Table 3 (TSP 部分，直接核自 PDF p.8)：预训练 NCO 神经网络求解器 + 注意力重塑，与纯 CPU 启发式属不同范式。"
    t3_tsp = [
        ("pomo", "POMO", [(200, 11.16, 4.40), (500, 22.21, 34.43), (1000, 35.19, 52.11)]),
        ("pomo_dar", "POMO + DAR", [(200, 11.12, 3.98), (500, 21.63, 30.95), (1000, 33.32, 44.05)]),
        ("pomo_reevo", "POMO + ReEvo", [(200, 11.12, 4.02), (500, 20.54, 24.32), (1000, 29.86, 29.08)]),
        ("lehd", "LEHD", [(200, 10.79, 0.87), (500, 16.78, 1.55), (1000, 23.87, 3.17)]),
        ("lehd_dar", "LEHD + DAR", [(200, 10.79, 0.89), (500, 16.79, 1.62), (1000, 23.87, 3.19)]),
        ("lehd_reevo", "LEHD + ReEvo", [(200, 10.77, 0.74), (500, 16.78, 1.55), (1000, 23.82, 2.97)]),
    ]
    for mid, mname, entries in t3_tsp:
        for sz, obj, gap in entries:
            rows.append(_rec(
                record_id=f"pub-reevo-2024-tbl3-tsp{sz}-{mid}",
                paper_source_id=src,
                paper_citation=cite,
                table_ref=f"Table 3 (TSP{sz} NCO)",
                suite_id="tsp_ext_eohs_128",
                subset=f"NCO_TSP{sz}",
                problem_family="tsp",
                method_id=mid,
                method_display_name=mname,
                paradigm="neural_attention_reshaping",
                metric_name="mean_opt_gap_pct",
                value=gap,
                unit="percent",
                direction="minimize",
                reference_kind="lkh_reference",
                protocol_boundary_note=t3_tsp_note,
                local_reproducible=False,
                upstream_code_ref=ref,
                extra={"paper_reported_obj": obj},
            ))

    t3_cvrp_note = "ReEvo NeurIPS 2024 Table 3 (CVRP 部分，直接核自 PDF p.8)：预训练 NCO 神经网络求解器（POMO/LEHD）+ 注意力重塑，与无训练 CPU 启发式属不同范式。"
    t3_cvrp = [
        ("pomo", "POMO", [(200, 22.39, 10.93), (500, 50.12, 33.76), (1000, 145.40, 289.48)]),
        ("pomo_dar", "POMO + DAR", [(200, 22.36, 10.78), (500, 50.23, 34.05), (1000, 144.24, 286.37)]),
        ("pomo_reevo", "POMO + ReEvo", [(200, 22.30, 10.48), (500, 47.10, 25.70), (1000, 118.80, 218.22)]),
        ("lehd", "LEHD", [(200, 20.92, 3.68), (500, 38.61, 3.03), (1000, 39.12, 4.79)]),
        ("lehd_dar", "LEHD + DAR", [(200, 21.13, 4.67), (500, 39.16, 4.49), (1000, 39.70, 6.35)]),
        ("lehd_reevo", "LEHD + ReEvo", [(200, 20.85, 3.30), (500, 38.57, 2.94), (1000, 39.11, 4.76)]),
    ]
    for mid, mname, entries in t3_cvrp:
        for sz, obj, gap in entries:
            rows.append(_rec(
                record_id=f"pub-reevo-2024-tbl3-cvrp{sz}-{mid}",
                paper_source_id=src,
                paper_citation=cite,
                table_ref=f"Table 3 (CVRP{sz} NCO)",
                suite_id="cvrp_ext_reevo_scale",
                subset=f"NCO_CVRP{sz}",
                problem_family="cvrp",
                method_id=mid,
                method_display_name=mname,
                paradigm="neural_attention_reshaping",
                metric_name="mean_opt_gap_pct",
                value=gap,
                unit="percent",
                direction="minimize",
                reference_kind="lkh_reference",
                protocol_boundary_note=t3_cvrp_note,
                local_reproducible=False,
                upstream_code_ref=ref,
                extra={"paper_reported_obj": obj},
            ))

    # Explicit honest pending record for ReEvo §5.2 ACO (PDF only presents Figure 2, no numeric table; Table 4 is Autocorrelation)
    rows.append(_rec(
        record_id="pub-reevo-2024-fig2-aco-5cops-pending",
        paper_source_id=src,
        paper_citation=cite,
        table_ref="Section 5.2 / Figure 2 (ACO across TSP/CVRP/OP/MKP/BPP)",
        suite_id="cvrp_ext_reevo_scale",
        subset="ACO_5COPs_Fig2",
        problem_family="cvrp",
        method_id="aco_reevo",
        method_display_name="ACO-ReEvo (vs DeepACO / Human ACO)",
        paradigm="metaheuristic",
        metric_name="rel_improvement_pct_over_human_aco",
        value=None,
        unit="percent",
        direction="maximize",
        reference_kind="solver_reference",
        verification_status="pending_pdf_or_repo_table_extraction",
        protocol_boundary_note="经核验 arXiv:2402.01145 原文：§5.2 ACO 跨五问题结果仅以折线/柱状图 Figure 2 呈现（原文 Table 4 实为自相关分析），无公开数值表；严格不从图估数。",
        local_reproducible=True,
        upstream_code_ref=ref,
    ))
    return rows


def build_heuragenix_cobench_2025_tables() -> list[dict[str, Any]]:
    """HeurAgenix (MSRA 2025 / arXiv:2506.15196) Appendix F Tables 5-6 + CO-Bench (arXiv:2504.04310) Fig. 3."""
    rows: list[dict[str, Any]] = []

    # HeurAgenix Appendix F Table 6 (verified verbatim from arXiv:2506.15196 p.27)
    hx_cite = "Microsoft Research Asia, 2025 (arXiv:2506.15196)"
    hx_src = "src-msra-2025-heuragenix"
    hx_ref = "microsoft/HeurAgenix@e84bfb19"
    hx_cvrp_note = "HeurAgenix Appendix F Table 6 (p.27) CVRPLib 6 个大例（A-n80-k10, B-n78-k10, E-n101-k14, F-n135-k7, M-n200-k17, P-n101-k4）GPT-4o 在线超启发式选择平均最优差距（%）。"

    # CVRP 6-instance average + per-instance records
    cvrp_tbl6 = {
        ("ortools", "OR-Tools", "metaheuristic"): {"avg": 9.57, "per": [("A-n80-k10", 6.41), ("B-n78-k10", 3.69), ("E-n101-k14", 11.06), ("F-n135-k7", 13.43), ("M-n200-k17", 14.04), ("P-n101-k4", 8.81)]},
        ("aco", "ACO", "metaheuristic"): {"avg": 43.00, "per": [("A-n80-k10", 34.96), ("B-n78-k10", 0.20), ("E-n101-k14", 49.30), ("F-n135-k7", 50.17), ("M-n200-k17", 64.16), ("P-n101-k4", 59.18)]},
        ("reevo_aco", "ReEvo + ACO", "metaheuristic"): {"avg": 21.62, "per": [("A-n80-k10", 13.34), ("B-n78-k10", 11.37), ("E-n101-k14", 28.68), ("F-n135-k7", 17.47), ("M-n200-k17", 33.73), ("P-n101-k4", 25.11)]},
        ("heuragenix", "HeurAgenix (GPT-4o Hyper-Heuristic)", "llm_ahd_framework"): {"avg": 6.49, "per": [("A-n80-k10", 3.97), ("B-n78-k10", 2.54), ("E-n101-k14", 10.97), ("F-n135-k7", 8.52), ("M-n200-k17", 9.88), ("P-n101-k4", 3.08)]},
    }
    for (mid, mname, parad), data in cvrp_tbl6.items():
        rows.append(_rec(
            record_id=f"pub-heuragenix-2025-tbl6-cvrp-avg-{mid}",
            paper_source_id=hx_src,
            paper_citation=hx_cite,
            table_ref="Appendix F Table 6 (CVRPLib 6-instance Avg)",
            suite_id="cvrp_ext_cvrplib_abp_74",
            subset="CVRPLib_HeurAgenix_6",
            problem_family="cvrp",
            method_id=mid,
            method_display_name=mname,
            paradigm=parad,
            metric_name="mean_opt_gap_pct",
            value=data["avg"],
            unit="percent",
            direction="minimize",
            reference_kind="best_known",
            protocol_boundary_note=hx_cvrp_note,
            local_reproducible=(mid == "heuragenix"),
            upstream_code_ref=hx_ref,
            extra={"per_instance_gap_pct": dict(data["per"])},
        ))

    # HeurAgenix Table 5 CVRP heuristic evolution before/after averages (p.26)
    hx_t5_note = "HeurAgenix Appendix F Table 5 (p.26) 进化前后确定性单启发式在 6 例 CVRPLib 上的平均差距（%）。"
    for mid, mname, val in [
        ("cheapest_insertion_seed", "Cheapest Insertion (Seed)", 36.55),
        ("cheapest_insertion_evolved", "Cheapest Insertion (HeurAgenix Evolved)", 25.70),
        ("farthest_insertion_seed", "Farthest Insertion (Seed)", 51.59),
        ("farthest_insertion_evolved", "Farthest Insertion (HeurAgenix Evolved)", 30.56),
        ("nn_seed", "Nearest Neighbor (Seed)", 48.80),
        ("nn_evolved", "Nearest Neighbor (HeurAgenix Evolved)", 36.55),
    ]:
        rows.append(_rec(
            record_id=f"pub-heuragenix-2025-tbl5-cvrp-{mid}",
            paper_source_id=hx_src,
            paper_citation=hx_cite,
            table_ref="Appendix F Table 5 (CVRP Evolution Avg)",
            suite_id="cvrp_ext_cvrplib_abp_74",
            subset="CVRPLib_HeurAgenix_6",
            problem_family="cvrp",
            method_id=mid,
            method_display_name=mname,
            paradigm="insertion" if "insertion" in mid else "sequential_construct",
            metric_name="mean_opt_gap_pct",
            value=val,
            unit="percent",
            direction="minimize",
            reference_kind="best_known",
            protocol_boundary_note=hx_t5_note,
            local_reproducible=True,
            upstream_code_ref=hx_ref,
        ))

    # HeurAgenix Table 6 TSP 13-instance TSPLIB averages (p.27)
    hx_tsp_note = "HeurAgenix Appendix F Table 6 (p.27) TSPLIB 13 例（kroA100..pr2392）平均最优差距（%）。"
    for mid, mname, parad, val in [
        ("gls", "GLS", "local_search", 3.93),
        ("aco", "ACO", "metaheuristic", 5.08),
        ("ortools", "OR-Tools", "metaheuristic", 8.67),
        ("eoh_gls", "EoH + GLS", "local_search", 1.93),
        ("reevo_gls", "ReEvo + GLS", "local_search", 0.98),
        ("reevo_aco", "ReEvo + ACO", "metaheuristic", 5.80),
        ("heuragenix", "HeurAgenix (GPT-4o Hyper-Heuristic)", "llm_ahd_framework", 0.50),
    ]:
        rows.append(_rec(
            record_id=f"pub-heuragenix-2025-tbl6-tsp-avg-{mid}",
            paper_source_id=hx_src,
            paper_citation=hx_cite,
            table_ref="Appendix F Table 6 (TSPLIB 13-instance Avg)",
            suite_id="tsp_ext_tsplib_euc2d",
            subset="TSPLIB_HeurAgenix_13",
            problem_family="tsp",
            method_id=mid,
            method_display_name=mname,
            paradigm=parad,
            metric_name="mean_opt_gap_pct",
            value=val,
            unit="percent",
            direction="minimize",
            reference_kind="best_known",
            protocol_boundary_note=hx_tsp_note,
            local_reproducible=False,
            upstream_code_ref=hx_ref,
        ))

    # HeurAgenix Table 6 MKP / JSSP / MaxCut cross-problem averages (p.27)
    for fam, sub, tref, mid, mname, val in [
        ("mkp", "ORLib_MKP_10", "Appendix F Table 6 (MKP 10-instance Avg)", "heuragenix", "HeurAgenix (Ours)", 0.68),
        ("mkp", "ORLib_MKP_10", "Appendix F Table 6 (MKP 10-instance Avg)", "reevo_aco", "ReEvo + ACO", 5.20),
        ("jssp", "ORLib_JSSP_LA20", "Appendix F Table 6 (JSSP 20-instance Avg)", "heuragenix", "HeurAgenix (Ours)", 0.25),
        ("maxcut", "OPTSICOM_MaxCut_10", "Appendix F Table 6 (MaxCut 10-instance Avg)", "heuragenix", "HeurAgenix (Ours)", 0.60),
    ]:
        rows.append(_rec(
            record_id=f"pub-heuragenix-2025-tbl6-{fam}-{mid}",
            paper_source_id=hx_src,
            paper_citation=hx_cite,
            table_ref=tref,
            suite_id=f"heuragenix_{fam}_paper_ref",
            subset=sub,
            problem_family=fam,
            method_id=mid,
            method_display_name=mname,
            paradigm="llm_ahd_framework" if mid == "heuragenix" else "metaheuristic",
            metric_name="mean_opt_gap_pct",
            value=val,
            unit="percent",
            direction="minimize",
            reference_kind="best_known",
            protocol_boundary_note="HeurAgenix Appendix F Table 6 (p.27) 跨组合优化问题基准均值。",
            local_reproducible=False,
            upstream_code_ref=hx_ref,
        ))

    # CO-Bench (arXiv:2504.04310, Fig. 3 p.5) 36-problem overall leaderboard (verified verbatim to 3 decimals!)
    cb_cite = "Sun et al., AAAI / arXiv:2504.04310 (2025)"
    cb_src = "src-sun-2025-cobench"
    cb_note = "CO-Bench 36 个真实 OR 问题归一化平均分（Avg Score in [0,1]，越大越好；LLM Agents 均基于 o3-mini-medium），直接核自 arXiv:2504.04310 Fig. 3 (p.5)。"
    cb_rows = [
        ("funsearch", "FunSearch (o3-mini-medium)", "llm_ahd_framework", 0.842, 0.500, 0.639, 0.426),
        ("eoh", "EoH (o3-mini-medium)", "llm_ahd_framework", 0.840, 0.555, 0.555, 0.390),
        ("greedy_refine", "Greedy Refine (o3-mini-medium)", "llm_ahd_framework", 0.840, 0.555, 0.694, 0.448),
        ("classical_solver", "Classical Solver Baseline", "exact_or_classical", 0.797, 0.611, None, 0.394),
        ("reevo", "ReEvo (o3-mini-medium)", "llm_ahd_framework", 0.774, 0.555, 0.444, 0.320),
        ("best_of_n", "BestOfN (o3-mini-medium)", "llm_ahd_framework", 0.774, 0.472, 0.417, 0.285),
        ("mcts_ahd", "MCTS-AHD (o3-mini-medium)", "llm_ahd_framework", 0.762, 0.555, 0.444, 0.315),
        ("aide", "AIDE (o3-mini-medium)", "llm_ahd_framework", 0.753, 0.528, 0.278, 0.227),
        ("claude_37_sonnet", "Claude-3.7 Sonnet (one-shot)", "direct_llm", 0.651, 0.361, 0.194, 0.225),
    ]
    for mid, mname, parad, avg_s, valid_r, above_c, surv_r in cb_rows:
        rows.append(_rec(
            record_id=f"pub-cobench-2025-fig3-36co-{mid}",
            paper_source_id=cb_src,
            paper_citation=cb_cite,
            table_ref="Figure 3 (36 CO Problems Overall)",
            suite_id="cobench_36co_paper_ref",
            subset="COBench_36_Problems",
            problem_family="multi_co",
            method_id=mid,
            method_display_name=mname,
            paradigm=parad,
            metric_name="normalized_avg_score",
            value=avg_s,
            unit="score_0_1",
            direction="maximize",
            reference_kind="best_known",
            protocol_boundary_note=cb_note,
            local_reproducible=False,
            upstream_code_ref="thuiar/CO-Bench",
            extra={
                "valid_solution_rate": valid_r,
                "above_classical_rate": above_c,
                "survival_rate": surv_r,
            },
        ))
    return rows


def validate_published_records(records: list[Mapping[str, Any]]) -> list[str]:
    """Validate every record conforms strictly to §2.2 published_baselines schema."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for idx, rec in enumerate(records):
        for field in REQUIRED_PUBLISHED_FIELDS:
            if field not in rec:
                errors.append(f"record[{idx}] missing field {field!r}")
        rid = str(rec.get("record_id") or "")
        if rid in seen_ids:
            errors.append(f"duplicate published record_id {rid!r}")
        seen_ids.add(rid)
        if rec.get("comparison_mode") != "paper_reported_reference":
            errors.append(f"{rid}: comparison_mode must be 'paper_reported_reference'")
        vs = rec.get("verification_status")
        if vs not in ALLOWED_VERIFICATION_STATUSES:
            errors.append(f"{rid}: invalid verification_status {vs!r}")
        if vs == "verified_from_paper_table" and not isinstance(rec.get("value"), (int, float)):
            errors.append(f"{rid}: verified_from_paper_table requires numeric value")
        if not str(rec.get("protocol_boundary_note") or "").strip():
            errors.append(f"{rid}: empty protocol_boundary_note")
    return errors


def _write_lf_json(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize_published_results(output_dir: Path) -> dict[str, dict[str, Any]]:
    """Write all published_results/*.json files and return {filename: {rel_path, sha256, count}}."""
    pub_dir = Path(output_dir) / "published_results"
    pub_dir.mkdir(parents=True, exist_ok=True)

    datasets = {
        "eohs_2025_tables_1_3.json": {
            "paper": "EoH-S (AAAI 2026 / arXiv:2508.03082)",
            "paper_source_id": "src-feiliu-2025-eohs",
            "records": build_eohs_2025_tables(),
        },
        "funsearch_eoh_2024_tables.json": {
            "paper": "FunSearch (Nature 2024) & EoH (ICML 2024 / arXiv:2401.02051)",
            "paper_source_id": "src-feiliu-2024-eoh",
            "records": build_funsearch_eoh_2024_tables(),
        },
        "reevo_2024_tables.json": {
            "paper": "ReEvo (NeurIPS 2024 / arXiv:2402.01145)",
            "paper_source_id": "src-ye-2024-reevo",
            "records": build_reevo_2024_tables(),
        },
        "heuragenix_cobench_2025_tables.json": {
            "paper": "HeurAgenix (arXiv:2506.15196) & CO-Bench (arXiv:2504.04310)",
            "paper_source_id": "src-msra-2025-heuragenix",
            "records": build_heuragenix_cobench_2025_tables(),
        },
    }

    all_records: list[dict[str, Any]] = []
    manifest_info: dict[str, dict[str, Any]] = {}
    for fname, body in datasets.items():
        errs = validate_published_records(body["records"])
        if errs:
            raise ValueError(f"published_results_validation_failed:{fname}:{errs[:5]}")
        payload = {
            "schema_version": "top-venue-published-results/v1",
            "comparison_mode": "paper_reported_reference",
            "paper": body["paper"],
            "paper_source_id": body["paper_source_id"],
            "record_count": len(body["records"]),
            "records": body["records"],
        }
        sha = _write_lf_json(pub_dir / fname, payload)
        manifest_info[fname] = {
            "rel_path": f"published_results/{fname}",
            "sha256": sha,
            "record_count": len(body["records"]),
        }
        all_records.extend(body["records"])

    index_payload = {
        "schema_version": "top-venue-published-results-index/v1",
        "comparison_mode": "paper_reported_reference",
        "total_record_count": len(all_records),
        "verified_count": sum(1 for r in all_records if r["verification_status"] == "verified_from_paper_table"),
        "pending_count": sum(1 for r in all_records if r["verification_status"] == "pending_pdf_or_repo_table_extraction"),
        "files": manifest_info,
        "records": all_records,
    }
    idx_sha = _write_lf_json(pub_dir / "index.json", index_payload)
    manifest_info["index.json"] = {
        "rel_path": "published_results/index.json",
        "sha256": idx_sha,
        "record_count": len(all_records),
    }
    return manifest_info
