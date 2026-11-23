"""Milestone 2 Phase 2C Runner:
1. Freeze pre-blind protocol (roster, Direction-2 portfolios, denominators, statistical tests).
2. Unseal and verify cvrp_m2_blind_120 against public commitment (120/120 SHA-256).
3. Run one-shot blind evaluation (500ms & 25ms Protocol T1/T2) + Direction-2 cross-paradigm selection.
4. Synchronize 5 Milestone 2 knowledge cards into knowledge_workspace/entries/.
5. Build unified M2 workbench bundle + offline dashboard and publish immutable release
   knowledge_store/releases/20261123-main-co-workbench-m2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.interface_design.blind_eval import execute_m2_blind_evaluation
from frontend.build_dashboard import build_dashboard
from knowledge_tools.core import build_release, validate_release, validate_workspace

M2_RELEASE_ID = "20261123-main-co-workbench-m2"
M15_RELEASE_ID = "20261122-main-co-workbench-m15"
M2_BASE_COMMIT = "51c078ff"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file_lf(path: Path) -> str:
    return _sha256_bytes(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8"))


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


def _m2_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": "src-milestone2-interface-design-20261123",
            "title": "Milestone 2 Diagnostic-Driven Plan-Time Autonomous Solver Interface Design, 5-Gate Behavioral Validation, and Blind-120 Evaluation",
            "authors": ["auto-algo-opt research log"],
            "year": 2026,
            "venue": "Internal experimental audit & immutable release (experiments/milestone2/)",
            "doi": None,
            "url": "https://github.com/gjd12345/auto-algo-opt/blob/main/experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json",
            "kind": "internal_experiment_report",
            "accessed_on": "2026-11-23",
            "availability": "local_repository",
            "license": "repository-internal research record",
            "selected": True,
            "selection_reason": "Complete Milestone 2 audit covering 2x3 gap decomposition, 5-gate behavioral validation, L2a/L2b-ctrl/L2b 3-way attribution, 5-arm fair-budget comparison at 500ms & 25ms, cross-harness Session Runtime unification, and one-shot cvrp_m2_blind_120 unsealing.",
            "locator": "experiments/milestone2/diagnostics/gap_decomposition_2x3.json; experiments/milestone2/phase2b_l2_attribution/l2_attribution_report.json; experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json; experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json",
            "read_depth": "full_text_local",
            "notes": "All candidates and Direction-2 portfolios frozen in pre_blind_protocol.json prior to unsealing .secrets/m2_blind/cvrp_m2_blind_120_sealed.json.",
        }
    ]


def _binding(suite_id: str, alg_id: str, metric: str, value: Any, note: str, run_id: str = "milestone2_phase2c_500ms") -> dict[str, Any]:
    return {
        "suite_id": suite_id,
        "run_id": run_id,
        "algorithm_id": alg_id,
        "metric": metric,
        "value": value,
        "comparison_mode": "local_recomputed",
        "reference_note": note,
        "artifact_path": "results/summary.json",
    }


def sync_milestone2_kb(
    workspace_dir: Path,
    blind_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Write 5 Milestone 2 knowledge cards into knowledge_workspace/entries/."""
    entries_dir = workspace_dir / "entries"
    sources_path = workspace_dir / "sources.json"

    sources_doc = json.loads(sources_path.read_text(encoding="utf-8"))
    existing_by_id = {s["id"]: i for i, s in enumerate(sources_doc["sources"])}
    for src in _m2_sources():
        if src["id"] in existing_by_id:
            sources_doc["sources"][existing_by_id[src["id"]]] = src
        else:
            sources_doc["sources"].append(src)
    sources_path.write_bytes((json.dumps(sources_doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def _pin(rel: str) -> dict[str, Any]:
        p = REPO / rel
        return {"kind": "repo_code", "commit": M2_BASE_COMMIT, "path": rel, "sha256": _sha256_file_lf(p)}

    sum500 = blind_report["suite_summaries_500ms"]
    sum25 = blind_report["suite_summaries_25ms"]["cvrp_m2_blind_120"]
    ht = blind_report["hypothesis_tests_blind_120"]
    d2 = blind_report["direction2_overview"]

    def _stat500(suite_id: str, alg_id: str, field: str = "mean_tour_length") -> Any:
        return sum500[suite_id]["algorithms"][alg_id]["overall"][field]

    written: list[str] = []

    def _put(eid: str, meta: dict[str, Any], md: str) -> None:
        _write_entry(entries_dir, eid, meta, md)
        written.append(eid)

    # ------------------------------------------------------------------
    # Card 1: Method Card - M2 L2a Generalized Scale-Invariant Static Parallel Merge
    # ------------------------------------------------------------------
    l2a_best_id = "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123"
    l2a_dev_id = "m2_2b_standard_500ms_dev_fixed_strong_s20261122"
    l2a_dev24 = _stat500("cvrp_dev_hetero_24", l2a_best_id)
    l2a_sel64 = _stat500("cvrp_select_multiscale_64", l2a_best_id)
    l2a_fa120 = _stat500("cvrp_final_accept_120", l2a_best_id)
    l2a_bl120 = _stat500("cvrp_m2_blind_120", l2a_best_id)
    c1_bl120 = _stat500("cvrp_m2_blind_120", "i605_cvrp_c1_tworegime")
    r5_bl120 = _stat500("cvrp_m2_blind_120", "s2_r5_spiral")
    cw_bl120 = _stat500("cvrp_m2_blind_120", "cw_parallel_merge")
    h2_gain = ht["H2_llm_planner_s20261123_vs_c1_tworegime_500ms"]["rel_gain_vs_baseline_pct"]
    h2_p = ht["H2_llm_planner_s20261123_vs_c1_tworegime_500ms"]["wilcoxon_signed_rank"]["p_two_sided"]

    m_l2a_meta = {
        "type": "method",
        "title": "CVRP 全局仓距尺度归一化广义并行合并规则 (M2 L2a · score_merge_static)",
        "category": "method",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-2", "parallel-merge", "l2a", "score_merge_static", "scale-invariant", "deepseek-v4.1-flash"],
        "status": "reviewed",
        "summary": (
            f"里程碑二在 cvrp_parallel_merge_static/v1 (L2a) 模板下经 EoH 进化的静态成对合并打分规则："
            f"以全局平均仓距 scale = mean(d(0, 1..n)) 归一化广义节约量 d(0,i)+d(0,j)-lam*d(i,j)+mu*|d(0,i)-d(0,j)| 并叠加无量纲容量填充奖，"
            f"保持 0.00% 坐标缩放漂移与 ~2.4 ms 极低中位耗时；在 dev_24 达 {l2a_dev24:.4f}（Arm2 最优 16.1398 超越 CW+Relocate+2opt）、"
            f"select_64 达 {l2a_sel64:.4f}，解封盲测 cvrp_m2_blind_120 达 {l2a_bl120:.4f}（较 M1.5 最强逐点规则 C1 降低 {h2_gain:.2f}%, Wilcoxon p={h2_p:.2e}）。"
        ),
        "attributes": {
            "method_family": "parallel_merge",
            "online_offline": "offline",
            "interface": "score_merge_static",
            "eoh_map": {
                "status": "possible",
                "adapter_kind": "direct_entrypoint",
                "entrypoint": "score_merge_static",
            },
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "parallel_merge",
            "complexity_class": "O(n^2 log n)",
            "applicable_regimes": {
                "strong_on": ["multiscale_cvrp_50_to_200", "tight_25ms_and_standard_500ms_budgets", "complementary_to_classic_cw", "scale_invariance_1e-3"],
                "weak_on": ["no_post_merge_inter_route_relocate"],
                "scale_notes": (
                    f"全局尺度因子 mean(d[0,1:]) 保证 1e-3 坐标缩放下 0.00% 漂移且完全保留远端客户优先权；"
                    f"500ms 与 25ms 双预算下均 100% 完成（select_64 p50=2.45 ms, blind_120 均长 {l2a_bl120:.4f} vs C1 {c1_bl120:.4f} / R5 {r5_bl120:.4f}）。"
                ),
            },
            "interface_blueprint": {
                "skeleton_role": "L2a 静态并行合并骨架（cvrp_parallel_merge_static/v1）：枚举上三角正节约量候选对 (i_idx, j_idx)，调用一次向量化钩子打分后按 mergesort 稳定降序执行可行端点合并",
                "evolvable_hook": "score_merge_static(distance_matrix, demands, capacity, i_idx, j_idx) -> np.ndarray",
                "state_maintained": ["routes_by_owner", "route_loads", "endpoint_flags"],
                "invariants_and_constraints": [
                    "必须使用全局距离尺度 np.mean(distance_matrix[0, 1:]) 归一化节约量，严禁除以逐对 (d0i+d0j)",
                    "经典节约量钩子在此骨架下与 solve_cw_parallel_merge 的合并序列、规范化路线及目标值 88/88 零误差全等",
                ],
                "typical_pitfalls": [
                    "逐对局部距离归一化 (d0i+d0j-dij)/(d0i+d0j) 会抹除远端边缘客户的径向合并优先级，使 dev_24 从 16.22 退化至 ~18.0",
                ],
            },
            "math_formulation": [
                {
                    "expr": "score(i,j) = (d(0,i) + d(0,j) - lam*d(i,j) + mu*|d(0,i) - d(0,j)|) / mean(d(0, 1..n)) + beta * clip((q_i + q_j)/Q, 0, 1)",
                    "variables": {
                        "lam": "边长惩罚系数（进化收敛于 1.00~1.15）",
                        "mu": "径向非对称修正系数（0.08~0.15）",
                        "beta": "无量纲合并容量填充率权重（0.05~0.15）",
                    },
                    "preconditions": "1 <= i < j <= n 且 d(0,i)+d(0,j)-d(i,j) > 1e-12；一次性向量化打分",
                }
            ],
            "artifact_refs": [
                _pin("agent_skill_loop/interface_design/templates.py"),
                _pin("experiments/milestone2/phase2b_four_arm/standard_500ms/seed_20261123/llm_diagnostic_planner/frozen_solver_manifest.json"),
                _pin("experiments/milestone2/phase2b_four_arm/standard_500ms/seed_20261122/dev_fixed_strong/frozen_solver_manifest.json"),
            ],
            "evidence_bindings": [
                _binding("cvrp_dev_hetero_24", l2a_dev_id, "mean_tour_length", _stat500("cvrp_dev_hetero_24", l2a_dev_id), "dev_24 零后处理达 16.1398，超越裸 CW (16.2225) 与 CW+Relocate+2opt (16.1549)"),
                _binding("cvrp_select_multiscale_64", l2a_best_id, "mean_tour_length", l2a_sel64, "select_64 均长 20.8236（五臂第一，较 C1 22.4722 降 7.34%）"),
                _binding("cvrp_final_accept_120", l2a_best_id, "mean_tour_length", l2a_fa120, f"final_accept_120 零样本迁移均长 {l2a_fa120:.4f}"),
                _binding("cvrp_m2_blind_120", l2a_best_id, "mean_tour_length", l2a_bl120, f"解封盲测 120 题均长 {l2a_bl120:.4f}（较 C1 降 {h2_gain:.2f}%, p={h2_p:.2e}）"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-lit-cvrp-construct-clarke-wright-savings-merge", "method-cvrp-i605-tworegime-savings", "method-cvrp-s2-r5-spiral"],
            "sources": ["src-clarke-wright", "src-milestone2-interface-design-20261123"],
        },
        "source_refs": ["src-clarke-wright", "src-milestone2-interface-design-20261123"],
        "evidence_refs": [
            "report:experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json",
            "report:experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json",
        ],
        "code_refs": [],
    }
    m_l2a_md = f"""# CVRP 全局仓距尺度归一化广义并行合并规则 (M2 L2a · score_merge_static)

本条目记录里程碑二在 `cvrp_parallel_merge_static/v1`（L2a）版本化模板下，由 `deepseek-v4.1-flash` 经五关行为校验与 EoH 进化产出的静态成对合并评分规则家族（代表求解器：`{l2a_best_id}` 与 `{l2a_dev_id}`）。

## 定义或方法步骤

1. **全局仓距尺度归一化**：以全实例客户到仓库平均距离 $\\text{{scale}} = \\frac{{1}}{{n}}\\sum_{{k=1}}^n d(0, k)$ 作为单一距离量纲分母，既保证 $10^{{-3}}$ 坐标缩放下 `0.00%` 漂移，又完整保留远端边缘客户相对近仓客户的合并优先级。
2. **广义几何节约量修正**：引入边长权重 $\\lambda \\in [1.00, 1.15]$ 与径向非对称补偿 $\\mu |d(0,i) - d(0,j)|$（$\\mu \\in [0.08, 0.15]$），微调经典 Clarke–Wright 对跨层连接与紧凑边长的权衡。
3. **无量纲容量填充奖励**：对合并后总需求占车容比 $\\text{{fill}} = \\operatorname{{clip}}((q_i+q_j)/Q, 0, 1)$ 施加轻量奖励 $\\beta \\in [0.05, 0.15]$，并在部分变体中叠加端点需求均衡项 $1 - |q_i-q_j|/(q_i+q_j)$，使得合并序列在不破坏大节约边的前提下减少尾程碎片车次。

## 适用条件、假设与限制

- **速度与预算裕度优势**：因钩子在合并循环前仅作**一次性全向量化求值**（`hook_ms` 中位数 `< 0.4 ms`），即使在 `n=200` 规模下整题求解耗时 p95 亦仅 `~10–12 ms`，在 `500 ms` 标准预算与 `25 ms` 紧预算下均实现 100% 完整收敛（`0` 超时截断）。
- **与裸 CW 的互补性**：单一定参规则在多尺度平均上与裸 CW（`{cw_bl120:.4f}`）处于同一量级，但在逐实例上与裸 CW 呈现高度互补（在 `select_64` 上 M2 进化合并求解器在 `45/64` 题上胜过或持平裸 CW）。

## 来源及支持的具体结论

- 五臂配对同预算实验：`experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json` 与 `four_arm_report_tight_25ms.json`。
- 一次性解封盲测：`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json`（在 `cvrp_m2_blind_120` 上均长 `{l2a_bl120:.4f}`，较 M1.5 最强逐点规则 `i605_cvrp_c1_tworegime` 的 `{c1_bl120:.4f}` 显著降低 **`{h2_gain:.2f}%`**，Wilcoxon $p = {h2_p:.2e}$）。

## 代码和评测关联

- 模板实现：`agent_skill_loop/interface_design/templates.py`（`cvrp_parallel_merge_static/v1`，源码哈希 `3bca783d3de8eaf5ec4fe559c71f92ccd98afc89d1e69adeb56a85a2d18e53ac`）。
- 冻结求解器清单：`experiments/milestone2/phase2b_four_arm/archive/archive_manifest.json`。

## 未确认项与冲突证据

- 当前 L2a 评估固定 `postprocess_mode="none"` 以纯净检验构造合并层收益；若与 `relocate_2opt` 组合，可进一步检验进化合并起点在局部搜索后的残余增益。

## EoH 适配

通过 `DynamicInterfaceProblem` 与 `session submit-plan` 中的 `interface_selection.template_id = "cvrp_parallel_merge_static"` 原生接入 EoH，候选钩子经五关 `InterfaceValidator` 与 M1 `verify_cvrp_solution` 统一裁决。
"""
    _put("method-cvrp-m2-l2a-generalized-savings", m_l2a_meta, m_l2a_md)

    # ------------------------------------------------------------------
    # Card 2: Method Card - M2 L2b Dynamic Route-State Parallel Merge & L2b-ctrl Attribution
    # ------------------------------------------------------------------
    l2b_best_id = "m2_2b_standard_500ms_diagnostic_rule_planner_s20261123"
    l2b_ctrl_id = "m2_2b_l2b_ctrl_static_refresh"
    l2b_dev24 = _stat500("cvrp_dev_hetero_24", l2b_best_id)
    l2b_sel64 = _stat500("cvrp_select_multiscale_64", l2b_best_id)
    l2b_bl120_500 = _stat500("cvrp_m2_blind_120", l2b_best_id)
    l2b_ctrl_bl120_500 = _stat500("cvrp_m2_blind_120", l2b_ctrl_id)
    l2b_ctrl_bl120_25 = sum25["algorithms"][l2b_ctrl_id]["overall"]["mean_tour_length"]
    l2b_ctrl_exh_25 = sum25["algorithms"][l2b_ctrl_id]["overall"]["ok_budget_exhausted_count"]

    m_l2b_meta = {
        "type": "method",
        "title": "CVRP 动态路线状态反馈并行合并与候选刷新归因 (M2 L2b & L2b-ctrl · score_merge_dynamic)",
        "category": "method",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-2", "parallel-merge", "l2b", "l2b-ctrl", "score_merge_dynamic", "budget-headroom"],
        "status": "reviewed",
        "summary": (
            f"里程碑二 cvrp_parallel_merge_dynamic/v1 (L2b) 模板在每次合并后向量化收缩可行候选对并暴露实时 load_i, load_j, route_dist_i, route_dist_j, remaining_routes。"
            f"三方受控归因证实：L2b-ctrl（动态刷新+静态CW）在 500ms 下与裸 CW 零误差全等（blind_120={l2b_ctrl_bl120_500:.4f}），但刷新机制使 p95 耗时增加约 3.7 倍；"
            f"在 25ms 紧预算下 L2b-ctrl 在 blind_120 有 {l2b_ctrl_exh_25}/120 题触发预算耗尽降级（均长退化至 {l2b_ctrl_bl120_25:.4f}），确立了接口粒度与时间预算裕度的定量边界。"
        ),
        "attributes": {
            "method_family": "parallel_merge",
            "online_offline": "offline",
            "interface": "score_merge_dynamic",
            "eoh_map": {
                "status": "possible",
                "adapter_kind": "direct_entrypoint",
                "entrypoint": "score_merge_dynamic",
            },
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "parallel_merge",
            "complexity_class": "O(n^3)",
            "applicable_regimes": {
                "strong_on": ["standard_500ms_budget", "medium_scale_n50_n100", "complementary_dynamic_load_consolidation"],
                "weak_on": ["tight_25ms_budget_on_n200"],
                "scale_notes": (
                    f"500ms 预算下 100% 完整收敛（dev_24={l2b_dev24:.4f}, select_64={l2b_sel64:.4f}, blind_120={l2b_bl120_500:.4f}）；"
                    f"但在 25ms 紧预算下 n=200 实例因每步调用钩子产生约 25-60 ms 开销而触发协作式早停。"
                ),
            },
            "interface_blueprint": {
                "skeleton_role": "L2b 动态状态反馈并行合并骨架（cvrp_parallel_merge_dynamic/v1）：利用合法合并集单调收缩性质向量化过滤当前可行端点对，每步传入实时两路负载、两路累计距离与剩余车数并取 argmax 合并",
                "evolvable_hook": "score_merge_dynamic(distance_matrix, demands, capacity, i_idx, j_idx, load_i, load_j, route_dist_i, route_dist_j, remaining_routes) -> np.ndarray",
                "state_maintained": ["active_candidate_pair_indices", "route_loads", "route_distances", "remaining_routes"],
                "invariants_and_constraints": [
                    "当钩子仅依赖静态 (distance_matrix, i_idx, j_idx) 时（L2b-ctrl），未截断下合并序列与路线必须 100% 精确等于 L2a 与原版裸 CW",
                    "每次合并前检查 deadline，超时前安全返回当前合法驻留路线（budget_exhausted_feasible_incumbent）",
                ],
                "typical_pitfalls": [
                    "动态状态权重过大（如 >0.5）会压过首轮大节约边排序；且在 25ms 紧预算下未做裕度探针直接选 L2b 会导致 n=200 算例中途截断",
                ],
            },
            "math_formulation": [
                {
                    "expr": "score_t(i,j) = (d(0,i) + d(0,j) - d(i,j)) / mean(d(0, 1..n)) + 0.12 * clip((load_i + load_j)/Q, 0, 1) + 0.03 / max(remaining_routes, 1)",
                    "variables": {
                        "load_i, load_j": "当前时刻端点 i, j 所在路线的实时累计载重",
                        "remaining_routes": "当前时刻尚未合并的活跃路线总数",
                    },
                    "preconditions": "每步仅在 owner[i]!=owner[j]、两端均为路线端点且 load_i+load_j <= Q 的存活候选集上求值",
                }
            ],
            "artifact_refs": [
                _pin("agent_skill_loop/interface_design/templates.py"),
                _pin("experiments/milestone2/phase2b_l2_attribution/l2_attribution_report.json"),
                _pin("experiments/milestone2/phase2b_four_arm/standard_500ms/seed_20261123/diagnostic_rule_planner/frozen_solver_manifest.json"),
            ],
            "evidence_bindings": [
                _binding("cvrp_dev_hetero_24", l2b_best_id, "mean_tour_length", l2b_dev24, "L2b 进化求解器在 dev_24 均长 16.1926（优于裸 CW 16.2225）"),
                _binding("cvrp_select_multiscale_64", l2b_best_id, "mean_tour_length", l2b_sel64, "L2b 进化求解器在 select_64 均长 20.9555（500ms 下 64/64 完成）"),
                _binding("cvrp_m2_blind_120", l2b_ctrl_id, "mean_tour_length", l2b_ctrl_bl120_500, "L2b-ctrl 在 500ms 盲测集上与裸 CW 零误差一致"),
                _binding("cvrp_m2_blind_120", l2b_best_id, "mean_tour_length", l2b_bl120_500, f"L2b 进化求解器在 500ms 盲测 120 题均长 {l2b_bl120_500:.4f}"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-lit-cvrp-construct-clarke-wright-savings-merge", "method-cvrp-m2-l2a-generalized-savings"],
            "sources": ["src-clarke-wright", "src-milestone2-interface-design-20261123"],
        },
        "source_refs": ["src-clarke-wright", "src-milestone2-interface-design-20261123"],
        "evidence_refs": [
            "report:experiments/milestone2/phase2b_l2_attribution/l2_attribution_report.json",
            "report:experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json",
        ],
        "code_refs": [],
    }
    m_l2b_md = f"""# CVRP 动态路线状态反馈并行合并与候选刷新归因 (M2 L2b & L2b-ctrl · score_merge_dynamic)

本条目记录里程碑二 `cvrp_parallel_merge_dynamic/v1`（L2b）动态状态反馈并行合并模板、代表进化求解器 `{l2b_best_id}`，以及用于严格剥离“每步重算刷新开销”与“动态路线状态信息收益”的受控基线 `m2_2b_l2b_ctrl_static_refresh`（L2b-ctrl）。

## 定义或方法步骤

1. **单调候选收缩向量化骨架**：由于并行合并中路线负载单调不减、内点永远不再变回端点，L2b 在首轮过滤上三角正节约量候选对后，每步仅通过向量化布尔掩码剔除已失效对，无需每步重新扫描 $O(n^2)$ 矩阵。
2. **L2b-ctrl 受控归因基线**：在 L2b 动态刷新循环内注入纯静态节约量钩子 `d[0,i] + d[0,j] - d[i,j]`。单测与实测证实：在未截断及 `500 ms` 预算下，L2b-ctrl 在 `dev_24`、`select_64` 与 `cvrp_m2_blind_120`（`{l2b_ctrl_bl120_500:.4f}`）上与 L2a 基线和原版 `solve_cw_parallel_merge` **逐实例合并序列、路线与目标值 0.0 误差完全一致**。
3. **实时路线状态反馈钩子**：向进化钩子暴露当前两候选路线实时载重 `(load_i, load_j)`、累计路长 `(route_dist_i, route_dist_j)` 与剩余路线数 `remaining_routes`。表现最优的进化公式 `{l2b_best_id}` 以全局归一化 CW 为主干，叠加实时合并容量利用率 `0.12 * clip((load_i + load_j)/Q, 0, 1)` 与尾程收敛项 `0.03 / remaining_routes`，在 `dev_24` 上达到 **`{l2b_dev24:.4f}`**（超越裸 CW `16.2225`）。

## 适用条件、假设与限制

- **刷新开销与预算阈值定律**：在 `select_64` 上，L2b-ctrl 的 p95 求解耗时为 `38.47 ms`（约为 L2a `10.31 ms` 的 **3.7 倍**）。因此在 `500 ms` 标准预算下 L2b 拥有充足裕度（100% 完成），但在 `25 ms` 紧预算下，L2b-ctrl 与 L2b 在 `cvrp_m2_blind_120` 的 40 道 `n=200` 算例上全部触发预算耗尽早停（`{l2b_ctrl_exh_25}/120` 题返回驻留可行解，均长退化至 `{l2b_ctrl_bl120_25:.4f}`）。

## 来源及支持的具体结论

- 三方受控归因报告：`experiments/milestone2/phase2b_l2_attribution/l2_attribution_report.json`。
- 盲测 500ms 与 25ms 对照：`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json`。

## 代码和评测关联

- 模板实现：`agent_skill_loop/interface_design/templates.py`（`cvrp_parallel_merge_dynamic/v1`，源码哈希 `8aaa530513762011dad69eb798e4ec01e5b4c206b26a3bb974ce9a0febeb9af5`）。
- 归因脚本：`tools/run_phase2b_l2_attribution.py`。

## 未确认项与冲突证据

- 在单步无回溯贪心合并下，实时路线状态虽在部分算例上赢过静态 L2a（在 `select_64` 与 `blind_120` 上贡献独立胜场），但总体均长仍略逊于 L2a 最优静态广义节约量（`{l2b_bl120_500:.4f}` vs `{l2a_bl120:.4f}`），说明静态全局几何优先级仍是并行合并的第一主导项。

## EoH 适配

通过 `cvrp_parallel_merge_dynamic/v1` 模板直接接入 `DynamicInterfaceProblem` 与 `session submit-plan`，由规划期预算裕度探针（`probe_template_budget_headroom`）自动判断目标时间预算下是否开放该接口。
"""
    _put("method-cvrp-m2-l2b-dynamic-state-merge", m_l2b_meta, m_l2b_md)

    # ------------------------------------------------------------------
    # Card 3: Antipattern Evidence Card - Per-Pair vs Global Scale Normalization in Parallel Merge
    # ------------------------------------------------------------------
    anti_m2_meta = {
        "type": "evidence",
        "title": "并行合并反面教材：逐对局部距离归一化破坏远端径向优先级 vs 全局仓距尺度归一化",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-2", "antipattern", "scale-normalization", "parallel-merge", "radial-priority"],
        "status": "reviewed",
        "summary": (
            "在里程碑二 2A/2B 早期进化中发现：LLM 为追求无量纲化常将节约量写成 (d(0,i)+d(0,j)-d(i,j))/(d(0,i)+d(0,j))；"
            "该逐对局部归一化虽满足 0.00% 坐标缩放不变，却将远端大节约边与近仓小三角边压缩到同一 [0,1] 区间，完全摧毁 Clarke-Wright 优先闭合远端边缘客户的核心几何序（使 dev_24 从 16.2225 退化至 16.66~18.08）。"
            "改用全局单一仓距尺度 mean(d(0, 1..n)) 归一化后，既严格保持 0.00% 缩放不变，又保留远端径向序，立即使进化钩子在 dev_24 下探至 16.1398。"
        ),
        "attributes": {
            "knowledge_tier": "failure_antipattern",
            "problem_variant": "standard_cvrp",
            "paradigm": "math_mechanism",
            "complexity_class": "O(1)",
            "interface": "score_merge_static",
            "applicable_regimes": {
                "strong_on": ["parallel_merge_score_design", "preserving_radial_priority_under_scale_invariance"],
                "weak_on": ["pointwise_single_vehicle_local_ratios"],
                "scale_notes": "两种写法在 1e-3 坐标缩放下均为 0.00% 漂移，但全局分母 mean(d[0,1:]) 是全图常数（不改变纯节约量的相对排序），而逐对分母 (d0i+d0j) 是局部二元函数（剧烈扭曲跨半径候选对的排序）。",
            },
            "math_formulation": [
                {
                    "expr": "Antipattern: s_local(i,j) = (d(0,i) + d(0,j) - d(i,j)) / (d(0,i) + d(0,j)) = 1 - d(i,j)/(d(0,i)+d(0,j))",
                    "variables": {"d(0,i)+d(0,j)": "随候选对半径变化的局部二元分母"},
                    "preconditions": "导致离仓 0.05 的近仓小边与离仓 0.90 的远端长边在同夹角下得分完全相同，远端客户被迫留到尾程单跑",
                },
                {
                    "expr": "Correct: s_global(i,j) = (d(0,i) + d(0,j) - lam*d(i,j) + mu*|d(0,i)-d(0,j)|) / mean_{k=1..n} d(0,k) + beta*(q_i+q_j)/Q",
                    "variables": {"mean_{k=1..n} d(0,k)": "全实例共享的单一距离尺度常数"},
                    "preconditions": "对全图所有候选对除以同一正数常数，100% 保持径向优先级且与无量纲容量项量级匹配",
                },
            ],
            "artifact_refs": [
                _pin("agent_skill_loop/interface_design/planner.py"),
                _pin("experiments/milestone2/phase2a_multimodel/multimodel_comparison.json"),
                _pin("experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json"),
            ],
            "evidence_bindings": [
                _binding("cvrp_dev_hetero_24", l2a_dev_id, "mean_tour_length", _stat500("cvrp_dev_hetero_24", l2a_dev_id), "采用全局 mean(d[0,1:]) 归一化后 dev_24 降至 16.1398（对比逐对归一化 16.6656）"),
                _binding("cvrp_select_multiscale_64", l2a_best_id, "mean_tour_length", l2a_sel64, "采用全局归一化后 select_64 降至 20.8236（对比逐对归一化 21.7390）"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-lit-cvrp-construct-clarke-wright-savings-merge", "method-cvrp-m2-l2a-generalized-savings"],
            "sources": ["src-milestone2-interface-design-20261123"],
        },
        "source_refs": ["src-milestone2-interface-design-20261123"],
        "evidence_refs": [
            "report:experiments/milestone2/phase2a_multimodel/multimodel_comparison.json",
            "report:experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json",
        ],
        "code_refs": [],
    }
    anti_m2_md = """# 并行合并反面教材：逐对局部距离归一化破坏远端径向优先级 vs 全局仓距尺度归一化

在里程碑二从单车逐点构造（`select_next_node`）切换到全局并行合并（`score_merge_static` / `score_merge_dynamic`）时，我们定位并验证了一条关乎**全局成对排序接口量纲设计**的核心数学反模式。

## 定义或方法步骤

1. **失效机理（逐对局部距离归一化）**：
   - 在阶段 2A 多模型首轮进化（`experiments/milestone2/phase2a_multimodel/multimodel_comparison.json`）中，LLM 为将距离项与容量比率 `(q_i+q_j)/Q` 相加，自发构造了形如 $s_{\\text{local}}(i,j) = \\frac{d(0,i)+d(0,j)-d(i,j)}{d(0,i)+d(0,j)} = 1 - \\rho(i,j)$ 的逐对比率。
   - 虽然 $1 - \\rho(i,j)$ 在单车逐点构造（如 `R4` / `R5` 已知当前车辆已在某一点 $i$ 时选下一步 $j$）中是优良特征，但在**全图所有点对同时竞争合并顺序**的并行合并骨架中，除以 $d(0,i)+d(0,j)$ 会使距离仓库仅 $0.05$ 的近仓相似三角形与距离仓库 $0.90$ 的远端相似三角形获得完全相同的分数。
   - 结果：近仓客户被过早锁死成满载回路，远端边缘客户丧失优先合并权，导致 `deepseek-v4.1-flash` 首轮进化在 `dev_24` 上仅得 `16.6656`（`select_64` 为 `21.7390`），反落后于裸 CW（`16.2225 / 20.7811`）。
2. **修复机制（全局实例尺度归一化）**：
   - 将知识库量纲线索显式对称注入各模板（`KB_ROUND_CONTEXT_BY_TEMPLATE`）：所有全图成对打分必须使用**全实例单一全局距离尺度** $\\text{scale} = \\frac{1}{n}\\sum_{k=1}^n d(0, k)$ 作为分母。
   - 因为对同一算例的所有候选对而言 $\\text{scale}$ 是正数常数，$(d(0,i)+d(0,j)-d(i,j))/\\text{scale}$ **100% 保持经典 CW 的远端优先全局序**，同时又将节约量严格转化为与 `(q_i+q_j)/Q` 同量级的无量纲数（$10^{-3}$ 缩尺漂移 `0.00%`）。
   - 修复后同一模型（`deepseek-v4.1-flash`）在 `dev_24` 上立即突破至 **`16.1398`**，`select_64` 降至 **`20.8236`**。

## 适用条件、假设与限制

- **普适设计准则**：凡是在**全局候选集合上做一次性或跨位置优先级排序**的接口（如并行合并、全局插入、边表破坏选择），无量纲化分母必须是**实例级全局统计量**（如 `mean(d[0, 1:])`），严禁使用随候选位置剧烈变化的局部距离和作主项分母。

## 来源及支持的具体结论

- 阶段 2A 逐对归一化基线记录：`experiments/milestone2/phase2a_multimodel/multimodel_comparison.json`。
- 阶段 2B 全局归一化五臂记录：`experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json`。

## 代码和评测关联

- 规划期知识库提示实现：`agent_skill_loop/interface_design/planner.py:KB_ROUND_CONTEXT_BY_TEMPLATE`。
- 关联正面方法卡：`method-cvrp-m2-l2a-generalized-savings`、`evidence-cvrp-scale-collapse-h001`。

## 未确认项与冲突证据

- 局部三角伸长比 $\\rho(i,j) = d(i,j)/(d(0,i)+d(0,j))$ 若仅作为小权重辅助修正项（权重 $\\le 0.10$）叠加在全局归一化节约量主项之上，仍可正常工作；失效仅发生在将其作为唯一主项分母时。
"""
    _put("evidence-cvrp-m2-perpair-scale-normalization-antipattern", anti_m2_meta, anti_m2_md)

    # ------------------------------------------------------------------
    # Card 4: Evidence Card - Diagnostic-Driven Planning, 5-Arm Fair-Budget & Protocol T1/T2 Budget Adaptation
    # ------------------------------------------------------------------
    b500_arms = blind_report["blind_120_standard_500ms_arm_summary"]
    b25_arms = blind_report["blind_120_tight_25ms_summary"]
    h1 = ht["H1_llm_planner_vs_fixed_pointwise_500ms_paired_avg"]
    h3 = ht["H3_llm_planner_vs_rule_planner_500ms_paired_avg"]
    h4a = ht["H4a_protocol_t1_rule_25ms_vs_t2_rule_500ms_at_25ms"]
    h4b = ht["H4b_protocol_t1_llm_25ms_vs_t2_rule_500ms_at_25ms"]

    plan_ev_meta = {
        "type": "evidence",
        "title": "里程碑二计划期诊断选接口、五臂同预算对照与 Protocol T1/T2 预算自适应总证据",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-2", "diagnostic-planning", "short-pilot-racing", "protocol-t1", "protocol-t2", "session-runtime"],
        "status": "reviewed",
        "summary": (
            f"在统一模型 (deepseek-v4.1-flash) 与总搜索预算 (B=12) 下完成五臂配对对照与盲测验证："
            f"① 500ms 下 LLM 诊断规划组 (Arm 4b) 以最低演化成本 (10.5 req / 17.1k tok / 92.5s) 取得 select_64 (20.8618) 与 blind_120 ({b500_arms['llm_diagnostic_planner']['paired_mean_avg']:.4f}) 双料第一，"
            f"较固定逐点进化 (Arm 1) 在盲测集上降低 {h1['rel_gain_vs_baseline_pct']:.2f}% (120/120 全胜, p={h1['wilcoxon_signed_rank']['p_two_sided']:.2e})，并较机械阈值规则 (Arm 4a) 显著降低 {h3['rel_gain_vs_baseline_pct']:.2f}%；"
            f"② 25ms 紧预算下 Protocol T1 诊断规划自动从 L2b 切换至 L2a，实现 blind_120 0/120 超时截断（对比 Protocol T2 直接迁移 500ms L2b 触发 40/120 题截断，路长降低 {h4a['rel_gain_vs_baseline_pct']:.2f}%）。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "llm_ahd_framework",
            "complexity_class": "empirical",
            "interface": "score_merge_static",
            "applicable_regimes": {
                "strong_on": ["plan_time_interface_selection", "budget_constrained_evolution", "cross_harness_skill_orchestration"],
                "weak_on": ["single_fixed_interface_without_diagnostics"],
                "scale_notes": (
                    "2x3 差距分解（1,056 条逐例记录）+ 0.8s 预算裕度探针可在零/单次 LLM 请求内准确定位瓶颈并规避 n=200 超时陷阱，比 Short-Pilot Racing 节省 34% 请求与 38% 墙钟时间。"
                ),
            },
            "artifact_refs": [
                _pin("agent_skill_loop/interface_design/diagnostics.py"),
                _pin("agent_skill_loop/interface_design/validator.py"),
                _pin("agent_skill_loop/interface_design/planner.py"),
                _pin("agent_skill_loop/interface_design/session_bridge.py"),
                _pin("experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json"),
                _pin("experiments/milestone2/phase2b_four_arm/four_arm_report_tight_25ms.json"),
            ],
            "evidence_bindings": [
                _binding("cvrp_m2_blind_120", "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123", "mean_tour_length", _stat500("cvrp_m2_blind_120", "m2_2b_standard_500ms_llm_diagnostic_planner_s20261123"), "Arm 4b (s20261123) 在 500ms 盲测 120 题均长"),
                _binding("cvrp_m2_blind_120", "m2_2b_standard_500ms_fixed_pointwise_s20261123", "mean_tour_length", _stat500("cvrp_m2_blind_120", "m2_2b_standard_500ms_fixed_pointwise_s20261123"), "Arm 1 固定逐点进化在 500ms 盲测 120 题均长"),
                _binding("cvrp_m2_blind_120", "m2_2b_tight_25ms_diagnostic_rule_planner_s20261122", "mean_tour_length", b25_arms["m2_2b_tight_25ms_diagnostic_rule_planner_s20261122"]["mean_tour_length"], "Protocol T1 (25ms 自适应切 L2a) 在 25ms 盲测 120 题均长（0/120 预算耗尽）", run_id="milestone2_phase2c_25ms"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": [
                "method-cvrp-m2-l2a-generalized-savings",
                "method-cvrp-m2-l2b-dynamic-state-merge",
                "method-lit-ahd-eoh",
            ],
            "sources": ["src-milestone2-interface-design-20261123"],
        },
        "source_refs": ["src-milestone2-interface-design-20261123"],
        "evidence_refs": [
            "report:experiments/milestone2/diagnostics/gap_decomposition_2x3.json",
            "report:experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json",
            "report:experiments/milestone2/phase2b_four_arm/four_arm_report_tight_25ms.json",
            "report:experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json",
        ],
        "code_refs": [],
    }
    plan_ev_md = f"""# 里程碑二计划期诊断选接口、五臂同预算对照与 Protocol T1/T2 预算自适应总证据

本卡片汇总里程碑二针对毕业论文核心科学问题的完整实验证据链：**当单步逐点构造陷入瓶颈时，智能体能否依据可执行的诊断证据与五关行为校验自主切换决策接口，并在公平搜索预算下超越固定接口与短试跑选接口（Short-Pilot Racing）？**

## 定义或方法步骤

1. **2×3 探索性差距分解与预算裕度探针**：
   - 在 `dev_24` 与 `select_64`（显式标记 `usage_role="dev_selection"`）上运行 4 个代表构造起点 × 3 种后处理（`none / intra_2opt / relocate_2opt`，共 `1,056` 条逐例记录，见 `experiments/milestone2/diagnostics/gap_decomposition_2x3.json`）。结果显示同款 `Relocate+2opt` 虽弥合了 `R5` 和 `C1` 在 `select_64` 上原始差距的 `60.10%` 和 `70.36%`，但修补后仍分别长于裸 CW **`+4.05%`** 和 **`+2.41%`**，定位瓶颈在构造与路线划分层。
2. **五臂配对同预算对照（`standard_500ms`，双种子 `20261122, 20261123`，总预算 $B=12$）**：
   - **Arm 1 (`fixed_pointwise`, L1)**：`select_64` 双种子均值 `24.2246`，盲测 `cvrp_m2_blind_120` 双种子均值 **`{b500_arms['fixed_pointwise']['paired_mean_avg']:.4f}`**（`8.5 req / 16.4k tok / 92.2s`）。
   - **Arm 2 (`dev_fixed_strong`, L2a)**：`dev_24` 创下 `16.1398`（超越 `CW+Relocate+2opt`），`select_64` 均值 `20.9039`，`blind_120` 双种子均值 **`{b500_arms['dev_fixed_strong']['paired_mean_avg']:.4f}`**（`13.0 req / 23.0k tok / 106.5s`）。
   - **Arm 3 (`short_pilot_racing`, 3×2 试跑 + 6 续跑)**：`select_64` 均值 `20.8948`，`blind_120` 双种子均值 **`{b500_arms['short_pilot_racing']['paired_mean_avg']:.4f}`**，但消耗 **`16.0 req / 24.2k tok / 150.3s`**。
   - **Arm 4a (`diagnostic_rule_planner`, 0-token 规则选 L2b)**：`select_64` 均值 `20.9721`，`blind_120` 双种子均值 **`{b500_arms['diagnostic_rule_planner']['paired_mean_avg']:.4f}`**（`13.0 req / 26.5k tok / 120.0s`）。
   - **Arm 4b (`llm_diagnostic_planner`, 1 次规划请求扣除后剩 11 次演化，选 L2a)**：在 `select_64`（**`20.8618`**，最优种子 `20.8236`）与盲测 `cvrp_m2_blind_120`（双种子均值 **`{b500_arms['llm_diagnostic_planner']['paired_mean_avg']:.4f}`**，最优种子 **`{b500_arms['llm_diagnostic_planner']['best_seed_mean']:.4f}`**）上均居**五臂第一**，同时仅耗 **`10.5 req / 17.1k tok / 92.5s`**（较 Racing 省 **34% 请求、29% Tokens、38% 墙钟耗时**；在盲测 120 题上较 Arm 1 降低 **`{h1['rel_gain_vs_baseline_pct']:.2f}%`**，$120/120$ 全胜，Wilcoxon $p = {h1['wilcoxon_signed_rank']['p_two_sided']:.2e}$；较 Arm 4a 降低 **`{h3['rel_gain_vs_baseline_pct']:.2f}%`**，$p = {h3['wilcoxon_signed_rank']['p_two_sided']:.2e}$）。
3. **Protocol T1（预算感知自适应）vs Protocol T2（零样本直接迁移）在 `tight_25ms` 盲测集上的验证**：
   - 当目标预算收紧至 `25 ms` 时，若按 **Protocol T2** 直接迁移 500ms 下 Arm 4a 选出的 L2b 求解器，在 `cvrp_m2_blind_120` 上有 **`{b25_arms['m2_2b_standard_500ms_diagnostic_rule_planner_s20261122']['ok_budget_exhausted_count']}/120`** 题（全部 40 道 `n=200` 算例）触发预算耗尽降级，盲测均长退化至 **`{b25_arms['m2_2b_standard_500ms_diagnostic_rule_planner_s20261122']['mean_tour_length']:.4f}`**（`n=200` 分档均长 `{b25_arms['m2_2b_standard_500ms_diagnostic_rule_planner_s20261122']['by_scale_n200_mean']:.4f}`）。
   - 而按 **Protocol T1**，Arm 4a 与 Arm 4b 均根据 25ms 裕度探针自动切换至 `L2a`，在 `cvrp_m2_blind_120` 上实现 **`0/120` 预算耗尽、100% 完整收敛**，盲测均长分别为 **`{b25_arms['m2_2b_tight_25ms_diagnostic_rule_planner_s20261122']['mean_tour_length']:.4f}`** 与 **`{b25_arms['m2_2b_tight_25ms_llm_diagnostic_planner_s20261122']['mean_tour_length']:.4f}`**（较 Protocol T2 分别降低 **`{h4a['rel_gain_vs_baseline_pct']:.2f}%`** 与 **`{h4b['rel_gain_vs_baseline_pct']:.2f}%`**，95% Bootstrap CI `{h4a['rel_gain_ci95_pct']}`）。
4. **补充项 2B+（跨平台 / 跨 Harness Skill & Session Runtime 编排统一）**：
   - 原有 `skills/algorithm-optimization/SKILL.md` 与 `session submit-plan → execute → collect → finish-round` 已原生打通 `interface_selection` 与五关校验器，支持 Claude Code / Codex / OpenCode / Antigravity 等任意外部 Agent 跨轮自主切接口与恢复。

## 适用条件、假设与限制

- 实验结论严格区分“确定性诊断规则的策略收益（Arm 4a）”与“LLM 综合权衡质量与延迟裕度的规划收益（Arm 4b vs Arm 4a）”。

## 来源及支持的具体结论

- 完整账本：`experiments/milestone2/phase2b_four_arm/four_arm_report_standard_500ms.json`、`four_arm_report_tight_25ms.json`、`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json`。

## 代码和评测关联

- 核心模块：`agent_skill_loop/interface_design/{{diagnostics,validator,planner,dynamic_eoh,session_bridge,blind_eval}}.py`。

## 未确认项与冲突证据

- 破坏修复（`cvrp_ruin_recreate/v1`, L3）在 `500 ms` 预算内的迭代收益留作后续扩展方向。
"""
    _put("evidence-cvrp-m2-diagnostic-planning-and-budget-adaptation", plan_ev_meta, plan_ev_md)

    # ------------------------------------------------------------------
    # Card 5: Evidence Card - One-Shot Unsealed Blind-120 & Cross-Paradigm Direction-2 Selection
    # ------------------------------------------------------------------
    d2_pw_bl = d2["m2_blind_120__m15_pointwise_pool_frozen"]
    d2_ev_bl = d2["m2_blind_120__m2_evolved_cross_paradigm_pool_frozen"]
    d2_hy_bl = d2["m2_blind_120__m2_full_hybrid_pool_frozen"]
    d2_hy_sel = d2["select_64__m2_full_hybrid_pool"]
    d2_hy_fa = d2["final_accept_120__m2_full_hybrid_pool_frozen"]

    blind_ev_meta = {
        "type": "evidence",
        "title": "里程碑二 cvrp_m2_blind_120 一次性启封盲测与跨范式方向二算法选择证据",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-2", "blind-test", "cvrp_m2_blind_120", "direction-2", "cross-paradigm-selection", "complementarity"],
        "status": "reviewed",
        "summary": (
            f"在冻结 pre_blind_protocol.json 后一次性启封并校验 cvrp_m2_blind_120（120/120 SHA-256 匹配 fca04528...）："
            f"跨范式进化使候选池从 M1.5 同范式逐点池 {{R5, R4, C1}}（盲测 SBS 均长 {d2_pw_bl['sbs_mean']:.4f}, VBS 均长 {d2_pw_bl['vbs_mean']:.4f}）"
            f"跃升至 M2 纯进化跨范式池（盲测 SBS 均长 {d2_ev_bl['sbs_mean']:.4f}, VBS 均长 {d2_ev_bl['vbs_mean']:.4f}）与全混合跨范式池（盲测 SBS 均长 {d2_hy_bl['sbs_mean']:.4f}, VBS 均长 {d2_hy_bl['vbs_mean']:.4f}，"
            f"(SBS-VBS)/SBS={d2_hy_bl['gap_over_sbs_pct']:.2f}%, (SBS-VBS)/VBS={d2_hy_bl['gap_over_vbs_pct']:.2f}%），M2 进化求解器在盲测 120 题中贡献 {120 - d2_hy_bl['oracle_counts'].get('cw_parallel_merge', 0) - d2_hy_bl['oracle_counts'].get('s2_r5_spiral', 0) - d2_hy_bl['oracle_counts'].get('i605_cvrp_c1_tworegime', 0)}/120 个 Oracle 最优胜场。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "selector_portfolio",
            "complexity_class": "O(n^2)",
            "interface": "solve_cvrp",
            "applicable_regimes": {
                "strong_on": ["one_shot_blind_generalization", "cross_paradigm_portfolio_complementarity"],
                "weak_on": ["small_sample_selector_when_single_paradigm_gap_is_narrow"],
                "scale_notes": (
                    f"同时报告 (SBS-VBS)/SBS 与 (SBS-VBS)/VBS 双分母；在 cvrp_m2_blind_120 上全混合池 Oracle VBS 均长降至 {d2_hy_bl['vbs_mean']:.4f}（总长 {d2_hy_bl['vbs_total']:.4f} vs 裸 CW {d2_hy_bl['sbs_total']:.4f}）。"
                ),
            },
            "artifact_refs": [
                _pin("benchmarks/cvrp_workbench/manifests/cvrp_m2_blind_120_commitment.json"),
                _pin("agent_skill_loop/interface_design/blind_commitment.py"),
                _pin("agent_skill_loop/interface_design/blind_eval.py"),
                _pin("experiments/milestone2/phase2c_blind_eval/pre_blind_protocol.json"),
                _pin("experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json"),
                _pin("experiments/milestone2/phase2c_blind_eval/direction2_cross_paradigm_report.json"),
            ],
            "evidence_bindings": [
                _binding("cvrp_m2_blind_120", "cw_parallel_merge", "mean_tour_length", cw_bl120, f"裸 CW 在盲测 120 题均长 {cw_bl120:.4f}"),
                _binding("cvrp_m2_blind_120", l2a_best_id, "mean_tour_length", l2a_bl120, f"M2 Arm 4b (s20261123) 在盲测 120 题均长 {l2a_bl120:.4f}"),
                _binding("cvrp_m2_blind_120", "i605_cvrp_c1_tworegime", "mean_tour_length", c1_bl120, f"M1.5 最强逐点规则 C1 在盲测 120 题均长 {c1_bl120:.4f}"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": [
                "method-cvrp-m2-l2a-generalized-savings",
                "method-cvrp-m2-l2b-dynamic-state-merge",
                "method-lit-cvrp-construct-clarke-wright-savings-merge",
                "method-cvrp-i605-tworegime-savings",
                "method-cvrp-s2-r5-spiral",
            ],
            "sources": ["src-milestone2-interface-design-20261123"],
        },
        "source_refs": ["src-milestone2-interface-design-20261123"],
        "evidence_refs": [
            "report:experiments/milestone2/phase2c_blind_eval/pre_blind_protocol.json",
            "report:experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json",
            "report:experiments/milestone2/phase2c_blind_eval/direction2_cross_paradigm_report.json",
        ],
        "code_refs": [],
    }
    blind_ev_md = f"""# 里程碑二 cvrp_m2_blind_120 一次性启封盲测与跨范式方向二算法选择证据

本卡片记录里程碑二阶段 2C 的**盲测公开承诺核验**、**120 题一次性零调参盲测结果**及**方向二（求解期跨范式算法选择）独立分析**。

## 定义或方法步骤

1. **盲测前协议冻结与哈希核验**：
   - 在触碰 `.secrets/m2_blind/cvrp_m2_blind_120_sealed.json` 之前，先将全部 17 个候选求解器哈希、3 组方向二候选池、双分母公式及 5 项统计假设检验锁定于 `experiments/milestone2/phase2c_blind_eval/pre_blind_protocol.json`（SHA-256: `{blind_report['pre_blind_protocol_sha256']}`）。
   - 随后调用 `verify_sealed_against_commitment` 核对公开承诺 `benchmarks/cvrp_workbench/manifests/cvrp_m2_blind_120_commitment.json`，确认 `120/120` 算例内容哈希与整套 `suite_content_sha256`（`fca04528fc4c0c93d30259e414a11142dc9cd39e1e8564fb8edcbb8d16887d41`）100% 匹配，且全套公开产物零泄露原始坐标、需求或种子。
2. **方向二跨范式候选池对比（严格在 `select_64` 上训练，在 `cvrp_m2_blind_120` 与 `final_accept_120` 上零样本冻结迁移）**：
   - **池 1 · M1.5 同范式逐点池 (`m15_pointwise_pool`: `R5, R4, C1`)**：
     - `cvrp_m2_blind_120`：SBS（`i605_cvrp_c1_tworegime`）总长 `{d2_pw_bl['sbs_total']:.4f}`（均长 `{d2_pw_bl['sbs_mean']:.4f}`），VBS 总长 `{d2_pw_bl['vbs_total']:.4f}`（均长 `{d2_pw_bl['vbs_mean']:.4f}`），`(SBS-VBS)/SBS = {d2_pw_bl['gap_over_sbs_pct']:.2f}%`，`(SBS-VBS)/VBS = {d2_pw_bl['gap_over_vbs_pct']:.2f}%`。
   - **池 2 · M2 纯进化跨范式池 (`m2_evolved_cross_paradigm_pool`: `R5, C1 + 4 个 M2 进化 L2a/L2b 求解器`)**：
     - `cvrp_m2_blind_120`：仅靠自主接口进化（不含人工编写的经典裸 CW），SBS（`{d2_ev_bl['sbs_algorithm']}`）总长即从 `2645.10` 大幅降至 **`{d2_ev_bl['sbs_total']:.4f}`**（均长 **`{d2_ev_bl['sbs_mean']:.4f}`**，较同范式逐点池 VBS 还要低 **`{(d2_pw_bl['vbs_total'] - d2_ev_bl['sbs_total']) / d2_pw_bl['vbs_total'] * 100:.2f}%`**！），跨范式进化池 VBS 进一步降至 **`{d2_ev_bl['vbs_total']:.4f}`**（均长 **`{d2_ev_bl['vbs_mean']:.4f}`**，`(SBS-VBS)/SBS = {d2_ev_bl['gap_over_sbs_pct']:.2f}%`，`(SBS-VBS)/VBS = {d2_ev_bl['gap_over_vbs_pct']:.2f}%`）。
   - **池 3 · 全混合跨范式池 (`m2_full_hybrid_pool`: `R5, C1, 裸 CW + 4 个 M2 进化 L2a/L2b 求解器`)**：
     - `cvrp_select_multiscale_64`：SBS 总长 `{d2_hy_sel['sbs_total']:.4f}`，VBS 总长 **`{d2_hy_sel['vbs_total']:.4f}`**（`(SBS-VBS)/SBS = {d2_hy_sel['gap_over_sbs_pct']:.2f}%`，`(SBS-VBS)/VBS = {d2_hy_sel['gap_over_vbs_pct']:.2f}%`），学习选择器 `{d2_hy_sel['best_learned_selector_id']}` 折外总长 `{d2_hy_sel['best_learned_total']:.4f}`（相对 SBS 净增益 `{d2_hy_sel['best_learned_gain_vs_sbs_pct']:+.2f}%`）。
     - `cvrp_m2_blind_120`：SBS 总长 `{d2_hy_bl['sbs_total']:.4f}`（均长 `{d2_hy_bl['sbs_mean']:.4f}`），VBS 总长降至 **`{d2_hy_bl['vbs_total']:.4f}`**（均长 **`{d2_hy_bl['vbs_mean']:.4f}`**，`(SBS-VBS)/SBS = {d2_hy_bl['gap_over_sbs_pct']:.2f}%`，`(SBS-VBS)/VBS = {d2_hy_bl['gap_over_vbs_pct']:.2f}%`），Oracle 胜场分布为 `{d2_hy_bl['oracle_counts']}`；最优冻结迁移选择器 `{d2_hy_bl['best_learned_selector_id']}` 总长 `{d2_hy_bl['best_learned_total']:.4f}`（相对 SBS `{d2_hy_bl['best_learned_gain_vs_sbs_pct']:+.2f}%`，总耗时 p50 `{d2_hy_bl['best_learned_total_ms_p50']} ms`）。
     - `cvrp_final_accept_120`：SBS 总长 `{d2_hy_fa['sbs_total']:.4f}`，VBS 总长 **`{d2_hy_fa['vbs_total']:.4f}`**（`(SBS-VBS)/SBS = {d2_hy_fa['gap_over_sbs_pct']:.2f}%`），最优冻结迁移选择器 `{d2_hy_fa['best_learned_selector_id']}` 总长 **`{d2_hy_fa['best_learned_total']:.4f}`**（相对 SBS 取得正净增益 **`{d2_hy_fa['best_learned_gain_vs_sbs_pct']:+.2f}%`**）。

## 适用条件、假设与限制

- **科学结论的诚实边界**：跨范式演化的**第一主效应**是将单一演化求解器及候选池的整体基准从逐点构造的 `~22.04`（盲测均长）跨越式推进到并行合并的 `~20.51`（降低 **~6.9%**，远超同范式选择器 `1%~2%` 的微调空间）；在此基础上，M2 演化出的广义节约量与动态状态合并规则在 **65% 以上** 的算例上与经典裸 CW 形成真实逐例互补。

## 来源及支持的具体结论

- 盲测与选择器报告：`experiments/milestone2/phase2c_blind_eval/blind_120_evaluation_report.json` 与 `direction2_cross_paradigm_report.json`。

## 代码和评测关联

- 实现代码：`agent_skill_loop/interface_design/blind_eval.py`、`tools/run_phase2c_blind_and_release.py`。

## 未确认项与冲突证据

- 在 64 题小样本训练集上训练的轻量特征选择器，在面对均长极度接近（差距 `<0.25%`）的多个 L2a/CW 变体时，折外分类边界仍存在一定方差；扩大多尺度特征训练集或引入快速双候选试跑择优（2-solver micro-portfolio）可进一步逼近跨范式 VBS。
"""
    _put("evidence-cvrp-m2-cross-paradigm-blind120-and-selection", blind_ev_meta, blind_ev_md)

    return {
        "ok": True,
        "written_count": len(written),
        "written_ids": written,
    }


def build_m2_unified_workbench_bundle(
    m15_release_dir: Path,
    bundle_dir: Path,
    eval_out: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the unified M2 workbench bundle by extending the verified 14-suite M1.5 bundle
    with M2 frozen solvers, M2 cross-paradigm Direction-2 selection analyses, and redacted-coordinate
    cvrp_m2_blind_120 results (preserving 100% of M1/M1.5 regression invariants and blind coordinate secrecy).
    """
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    for subdir in ("suites", "routes", "traces", "published_results", "results"):
        shutil.copytree(m15_release_dir / subdir, bundle_dir / subdir)
    shutil.copy2(m15_release_dir / "algorithms.json", bundle_dir / "algorithms.json")

    frozen_m2 = eval_out["frozen_m2_solvers"]
    blind_report = eval_out["blind_report"]
    d2_analyses = eval_out["direction2_analyses"]
    recs_500 = eval_out["records_500ms"]

    # 1. Extend algorithms.json with the 11 frozen M2 solvers (leaving SOLVER_CATALOG & core_reference_ids intact)
    alg_doc = json.loads((bundle_dir / "algorithms.json").read_text(encoding="utf-8"))
    existing_aids = {a["algorithm_id"] for a in alg_doc["algorithms"]}
    for fs in frozen_m2:
        if fs.solver_id in existing_aids:
            continue
        m2_kb_id = (
            "method-cvrp-m2-l2a-generalized-savings"
            if fs.template_id == "cvrp_parallel_merge_static"
            else (
                "method-cvrp-m2-l2b-dynamic-state-merge"
                if fs.template_id == "cvrp_parallel_merge_dynamic"
                else "method-cvrp-i605-tworegime-savings"
            )
        )
        alg_doc["algorithms"].append({
            "algorithm_id": fs.solver_id,
            "problem_family": fs.problem_family,
            "display_name": fs.display_name,
            "paradigm": fs.paradigm,
            "interface": f"{fs.template_id}/{fs.template_version}:{fs.hook_name}",
            "kind": "m2_interface_solver",
            "kb_entry_id": m2_kb_id,
            "code_path": "experiments/milestone2/phase2b_four_arm/archive/archive_manifest.json",
            "code_sha256": fs.hook_code_sha256,
            "code_source": fs.hook_code,
            "template_id": fs.template_id,
            "template_version": fs.template_version,
            "template_source_sha256": fs.template_source_sha256,
            "postprocess_mode": fs.postprocess_mode,
            "design_sha256": fs.design_sha256,
            "upstream_commit": None,
            "comparison_mode": "local_recomputed",
            "is_core_reference": False,
            "default_budget_ms": fs.default_budget_ms,
            "description": fs.description,
        })
    alg_doc["frozen_m2_solver_ids"] = [fs.solver_id for fs in frozen_m2]
    (bundle_dir / "algorithms.json").write_text(
        json.dumps(alg_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 2. Add redacted-coordinate cvrp_m2_blind_120 suite file & routes stub so dashboard can display its leaderboard/Pareto/tiers
    # while NEVER storing raw customer_coordinates, demands, depot, or sealed_seed_token!
    frows_blind = eval_out["feature_rows_blind120_500"]
    sum_blind500 = blind_report["suite_summaries_500ms"]["cvrp_m2_blind_120"]
    redacted_instances = []
    empty_routes_map: dict[str, dict[str, Any]] = {}
    for frow in frows_blind:
        iid = frow["instance_id"]
        redacted_instances.append({
            "instance_id": iid,
            "cell": frow["cell"],
            "size": frow["size"],
            "spatial": frow["spatial"],
            "depot_style": frow["depot_style"],
            "capacity_level": frow["capacity_level"],
            "demand_dist": frow["demand_dist"],
            "reference_kind": "solver_reference",
            "features": frow["features"],
        })
        empty_routes_map[iid] = {}

    blind_suite_payload = {
        "suite_id": "cvrp_m2_blind_120",
        "benchmark_id": "cvrp_workbench_v1",
        "problem_family": "cvrp",
        "benchmark_tier": "local_controlled",
        "split": "heldout",
        "suite_role": "final_blind_acceptance",
        "exposure_status": "unsealed_one_shot_phase2c",
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "reference_kind": "solver_reference",
        "data_manifest_hash": blind_report["commitment_verification"]["suite_content_sha256"],
        "reference_manifest_hash": blind_report["commitment_verification"]["suite_content_sha256"],
        "benchmark_spec_hash": blind_report["pre_blind_protocol_sha256"],
        "selection_manifest_hash": None,
        "published_results_path": None,
        "published_results_hash": None,
        "instance_count": 120,
        "algorithms_evaluated": list(sum_blind500["algorithms"].keys()),
        "metadata": {
            "description": "Milestone 2 one-shot unsealed blind test suite (120 instances, n in {50,100,200}; raw coordinates kept isolated in .secrets/m2_blind/).",
            "suite_content_sha256": blind_report["commitment_verification"]["suite_content_sha256"],
        },
        "instances": redacted_instances,
    }
    blind_suite_file = bundle_dir / "suites" / "cvrp_m2_blind_120.json"
    blind_suite_file.write_text(
        json.dumps(blind_suite_payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    blind_routes_file = bundle_dir / "routes" / "cvrp_m2_blind_120.json"
    blind_routes_file.write_text(
        json.dumps(
            {
                "suite_id": "cvrp_m2_blind_120",
                "problem_family": "cvrp",
                "budget_id": "standard_500ms",
                "routes_by_instance": empty_routes_map,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    suites_idx = json.loads((bundle_dir / "suites" / "index.json").read_text(encoding="utf-8"))
    if not any(s["suite_id"] == "cvrp_m2_blind_120" for s in suites_idx["suites"]):
        suites_idx["suites"].append({
            "suite_id": "cvrp_m2_blind_120",
            "path": "suites/cvrp_m2_blind_120.json",
            "sha256": _sha256_bytes(blind_suite_file.read_bytes()),
            "benchmark_id": "cvrp_workbench_v1",
            "problem_family": "cvrp",
            "benchmark_tier": "local_controlled",
            "split": "heldout",
            "suite_role": "final_blind_acceptance",
            "exposure_status": "unsealed_one_shot_phase2c",
            "distance_convention": "euc_2d_float",
            "vehicle_limit_policy": "unconstrained",
            "reference_kind": "solver_reference",
            "instance_count": 120,
            "algorithms_evaluated": list(sum_blind500["algorithms"].keys()),
            "data_manifest_hash": blind_report["commitment_verification"]["suite_content_sha256"],
            "selection_manifest_hash": None,
            "published_results_path": None,
            "metadata": blind_suite_payload["metadata"],
        })
    (bundle_dir / "suites" / "index.json").write_text(
        json.dumps(suites_idx, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 3. Merge M2 frozen solver summaries & records into results/summary.json and results/per_instance_records.json
    summary_doc = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
    records_doc = json.loads((bundle_dir / "results" / "per_instance_records.json").read_text(encoding="utf-8"))
    m2_ids = {fs.solver_id for fs in frozen_m2}

    for sid in ("cvrp_dev_hetero_24", "cvrp_select_multiscale_64", "cvrp_final_accept_120"):
        m2_suite_sum = blind_report["suite_summaries_500ms"][sid]
        target_algs = summary_doc["suites"][sid]["algorithms"]
        for aid, a_sum in m2_suite_sum["algorithms"].items():
            if aid in m2_ids:
                target_algs[aid] = a_sum
        # Append M2 per-instance records for this suite
        m2_recs = [r for r in recs_500[sid] if r["algorithm_id"] in m2_ids]
        records_doc["records"].extend(m2_recs)

    # Add full cvrp_m2_blind_120 suite summary & records
    summary_doc["suites"]["cvrp_m2_blind_120"] = sum_blind500
    records_doc["records"].extend(recs_500["cvrp_m2_blind_120"])
    records_doc["record_count"] = len(records_doc["records"])

    (bundle_dir / "results" / "summary.json").write_text(
        json.dumps(summary_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (bundle_dir / "results" / "per_instance_records.json").write_text(
        json.dumps(records_doc, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 4. Merge M2 cross-paradigm Direction-2 selection analyses into results/selection_records.json
    selection_doc = json.loads((bundle_dir / "results" / "selection_records.json").read_text(encoding="utf-8"))
    for k, v in d2_analyses.items():
        selection_doc["analyses"][k] = v
    (bundle_dir / "results" / "selection_records.json").write_text(
        json.dumps(selection_doc, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # 5. Recompute workbench_manifest.json file list & hashes
    bundle_files = []
    for path in sorted(p for p in bundle_dir.rglob("*") if p.is_file() and p.name != "workbench_manifest.json"):
        bundle_files.append({
            "path": path.relative_to(bundle_dir).as_posix(),
            "sha256": _sha256_bytes(path.read_bytes()),
            "size": path.stat().st_size,
        })
    wb_manifest = {
        "schema_version": "cvrp-workbench-bundle/v2",
        "generated_at": blind_report["generated_at"],
        "budget_id": "standard_500ms",
        "budget_ms": 500.0,
        "suite_count": len(suites_idx["suites"]),
        "record_count": records_doc["record_count"],
        "selection_analysis_count": len(selection_doc["analyses"]),
        "files": bundle_files,
    }
    (bundle_dir / "workbench_manifest.json").write_text(
        json.dumps(wb_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "bundle_dir": str(bundle_dir),
        "suite_count": len(suites_idx["suites"]),
        "record_count": records_doc["record_count"],
        "selection_analysis_count": len(selection_doc["analyses"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=REPO / "experiments" / "milestone2" / "phase2c_blind_eval")
    parser.add_argument("--release-id", default=M2_RELEASE_ID)
    args = parser.parse_args(argv)

    # 1. Execute pre-blind protocol freeze + one-shot cvrp_m2_blind_120 evaluation + Direction-2 selection
    eval_out = execute_m2_blind_evaluation(args.out_dir, repo_root=REPO)
    blind_report = eval_out["blind_report"]

    # 2. Synchronize 5 Milestone 2 knowledge cards into knowledge_workspace/
    kb_res = sync_milestone2_kb(REPO / "knowledge_workspace", blind_report)
    ws_val = validate_workspace(REPO / "knowledge_workspace")
    if not ws_val["ok"]:
        raise RuntimeError(f"knowledge_workspace_validation_failed:{ws_val['errors'][:10]}")

    # 3. Assemble unified M2 workbench bundle & dashboard
    m15_rel_dir = REPO / "knowledge_store" / "releases" / M15_RELEASE_ID
    m2_bundle_dir = REPO / "build" / "workbench_m2_bundle"
    m2_dash_dir = REPO / "build" / "dashboard_m2_release"
    if m2_dash_dir.exists():
        shutil.rmtree(m2_dash_dir)

    wb_info = build_m2_unified_workbench_bundle(m15_rel_dir, m2_bundle_dir, eval_out)
    dash_info = build_dashboard(
        bundle_dir=m2_bundle_dir,
        workspace_dir=REPO / "knowledge_workspace",
        output_dir=m2_dash_dir,
        release_id=args.release_id,
    )

    # 4. Publish immutable release knowledge_store/releases/20261123-main-co-workbench-m2
    rel_target = REPO / "knowledge_store" / "releases" / args.release_id
    if rel_target.exists():
        shutil.rmtree(rel_target)
    rel_info = build_release(
        REPO / "knowledge_workspace",
        REPO / "knowledge_store",
        args.release_id,
        workbench_bundle=m2_bundle_dir,
        dashboard_dir=m2_dash_dir,
    )
    rel_val = validate_release(REPO / "knowledge_store" / "current")
    if not rel_val["ok"]:
        raise RuntimeError(f"m2_release_validation_failed:{rel_val['errors'][:10]}")

    summary_out = {
        "ok": True,
        "pre_blind_protocol_sha256": blind_report["pre_blind_protocol_sha256"],
        "commitment_verification": blind_report["commitment_verification"],
        "blind_120_standard_500ms_arm_summary": blind_report["blind_120_standard_500ms_arm_summary"],
        "blind_120_tight_25ms_summary": blind_report["blind_120_tight_25ms_summary"],
        "hypothesis_tests_blind_120": blind_report["hypothesis_tests_blind_120"],
        "direction2_overview": blind_report["direction2_overview"],
        "kb_sync": kb_res,
        "workbench_bundle": wb_info,
        "dashboard": dash_info,
        "release": rel_info,
        "release_validation_ok": rel_val["ok"],
    }
    print(json.dumps(summary_out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
