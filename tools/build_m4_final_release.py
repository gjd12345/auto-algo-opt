"""Build Milestone 4 final immutable knowledge release (20261124-main-co-workbench-m4).

1. Synchronize 4 reviewed M3.1 / M3.2 / M4 knowledge cards and 1 source record into
   ``knowledge_workspace/`` (bringing total curated entries from 350 -> 354).
2. Validate ``knowledge_workspace/`` strictly via ``knowledge_tools.core.validate_workspace``.
3. Copy the immutable M3 workbench bundle cleanly (never modifying any prior release),
   rebuild offline ``dashboard.html`` with all 354 knowledge cards, publish new immutable
   release ``knowledge_store/releases/20261124-main-co-workbench-m4``, and atomically
   verify & switch symlink ``knowledge_store/current`` (preserving Git mode ``120000``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from frontend.build_dashboard import build_dashboard
from knowledge_tools.core import activate_verified_release, build_release, validate_workspace

M3_RELEASE_ID = "20261123-main-co-workbench-m3"
M4_RELEASE_ID = "20261124-main-co-workbench-m4"
M4_SOURCE_ID = "src-milestone4-m31-m32-math-closure-20261124"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _head_short_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True).strip()
        return out or "main"
    except Exception:
        return "main"


def _pin(rel_path: str, commit: str) -> dict[str, Any]:
    full = REPO / rel_path
    return {
        "kind": "repo_code",
        "commit": commit,
        "path": rel_path.replace("\\", "/"),
        "sha256": _sha256_bytes(full.read_bytes()),
    }


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


def _ensure_source(workspace_dir: Path) -> None:
    src_path = workspace_dir / "sources.json"
    doc = json.loads(src_path.read_text(encoding="utf-8"))
    sources = list(doc.get("sources") or [])
    new_src = {
        "id": M4_SOURCE_ID,
        "title": "Milestone 3.1 Cross-Problem Generalization (TSP/OBP/BPP), Milestone 3.2 400-Request Scaling Law & Controls, and Milestone 4 Mathematical Closure",
        "authors": ["auto-algo-opt research log"],
        "year": 2026,
        "venue": "Internal experimental audit & immutable release (experiments/milestone3_1/, milestone3_2/, milestone4/)",
        "doi": None,
        "url": "https://github.com/gjd12345/auto-algo-opt/blob/main/experiments/milestone4/m4_math_closure_part1.md",
        "kind": "internal_experiment_report",
        "accessed_on": "2026-11-24",
        "availability": "local_repository",
        "license": "repository-internal research record",
        "selected": True,
        "selection_reason": (
            "Covers M3.1 cross-problem Blind-72 & external TSPLIB-18/BPPLib-70 benchmarks, "
            "M3.2 21-cell 36->400 scaling law + single-factor controls + cvrp_m32_blind_120 one-shot evaluation, "
            "and M4 exact 2^5=32 Shapley + order-2 synergy, HRK 3-pool/pure-geometry lower-bound closure, "
            "similarity/E(2) invariance, full multi-scale alpha=1 bifurcation, and 12-champion AST dissection."
        ),
        "locator": (
            "experiments/milestone3_1/m31_cross_problem_report.json; "
            "experiments/milestone3_2/m32_scaling_report.json; "
            "experiments/milestone4/m4_math_closure_part1.json; "
            "experiments/milestone4/m4_m32_operator_dissection.json"
        ),
        "read_depth": "full_text_local",
        "notes": "All blind evaluations executed strictly one-shot against externally sealed custody suites.",
    }
    replaced = False
    for idx, item in enumerate(sources):
        if item.get("id") == M4_SOURCE_ID:
            sources[idx] = new_src
            replaced = True
            break
    if not replaced:
        sources.append(new_src)
    doc["sources"] = sources
    src_path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def sync_milestone4_kb(workspace_dir: Path) -> dict[str, Any]:
    commit = _head_short_commit()
    _ensure_source(workspace_dir)
    entries_dir = workspace_dir / "entries"
    written: list[str] = []

    def _put(entry_id: str, meta: dict[str, Any], md: str) -> None:
        _write_entry(entries_dir, entry_id, meta, md)
        written.append(entry_id)

    # 1. M3.1 Cross-problem generalization evidence card
    m31_meta = {
        "type": "evidence",
        "title": "里程碑 3.1 跨问题泛化（TSP / 在线 OBP / 独立离线 BPP）72 例盲测与外部标准库证据",
        "category": "evidence",
        "problem_family": "tsp",
        "tags": ["tsp", "obp", "bpp", "milestone-3.1", "cross-problem", "blind-72", "tsplib", "bpplib"],
        "status": "reviewed",
        "summary": (
            "在不改动 research_agent 核心闭环的前提下完成 TSP (tsp/v1)、严格在线 OBP (obp_online/v1) 与独立离线 BPP (bpp_offline/v1) 实测（12 槽位 432 请求实费 $0.1639）："
            "TSP Blind-72 上 tsp_l2 达 83,833.4340 显著击败 tsp_nn_2opt (84,610.3681, -0.9182%, 43/0/29, p_holm=0.0400)；"
            "在线 OBP 在 Blind-72 (28.2222) 与 BPPLib-70 (72.9143) 均逼平 Best-Fit；离线 BPP (27.7500) 持平 FFD；"
            "TSPLIB-18 确定性基准下 tsp_nn_2opt=54,830.7222，tsp_l1 (58,916.1667) 优于纯最近邻 tsp_nn (64,150.6667) 达 -8.16%。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_tsp",
            "variant_adaptation_note": "Extends the CVRP ResearchAgent loop and 5-gate validator to TSP (tsp/v1), strict online OBP (obp_online/v1), and separate offline BPP (bpp_offline/v1).",
            "paradigm": "insertion",
            "complexity_class": "empirical",
            "interface": "score_insertion",
            "applicable_regimes": {
                "strong_on": ["tsp_guided_insertion_n50_n100", "strict_online_prefix_invariance"],
                "weak_on": ["tsplib_n2392_global_insertion_extrapolation", "stateless_tight_greedy_obp_fixed_point"],
                "scale_notes": "每问题新增适配与探针代码量仅 387–573 LOC；在线 OBP 与离线 BPP 严格分表隔离。",
            },
            "artifact_refs": [
                _pin("tools/run_m31_cross_problem.py", commit),
                _pin("agent_skill_loop/interface_design/tsp_templates.py", commit),
                _pin("agent_skill_loop/interface_design/obp_templates.py", commit),
                _pin("agent_skill_loop/interface_design/bpp_templates.py", commit),
            ],
        },
        "relations": {
            "problems": ["problem-tsp", "problem-online-bin-packing", "problem-lit-bp-1d-offline"],
            "methods": ["method-research-agent-m3-autonomous-loop"],
            "sources": [M4_SOURCE_ID],
        },
        "source_refs": [M4_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/milestone3_1/m31_cross_problem_report.json",
            "report:experiments/milestone3_1/external_benchmarks_report.json",
        ],
        "code_refs": [],
    }
    m31_md = """# 里程碑 3.1 跨问题泛化（TSP / 在线 OBP / 独立离线 BPP）72 例盲测与外部标准库证据

本卡片记录将无人值守研究代理与五关行为校验推广至旅行商（`tsp/v1`）、严格在线一维装箱（`obp_online/v1`）与独立离线一维装箱（`bpp_offline/v1`）后的统一盲测与外部标准库复核结论。

## 定义或方法步骤

1. **盲测结果（72 例独立封存盲测，100% 按时可行）**：
   - **TSP 引导插入 (`tsp_l2`)**：均长 **`83,833.4340`**，较 `tsp_nn_2opt`（`84,610.3681`）缩短 **`0.9182%`**（`43/0/29`, `p_holm = 0.0400`），在聚集/网格/均匀三类分布与 `n=50, 100` 均占优，`n=200` 出现小幅反超（`+0.42%`）。
   - **严格在线 OBP (`obp_online`)**：Blind-72 均箱数 **`28.2222`**（`0/72/0` 持平 `obp_best_fit`，优于 `obp_first_fit 28.3333`）；BPPLib-70 达 **`72.9143`**（与 `obp_best_fit` 完全一致）。
   - **独立离线 BPP (`bpp_offline`)**：Blind-72 均箱数 **`27.7500`**（`0/72/0` 持平 `bpp_ffd`，优于 `bpp_bfd 27.7639`）。
2. **TSPLIB-18 确定性外部大考**：`tsp_nn_2opt = 54,830.7222`、`tsp_farthest_insertion = 56,434.3333`、`tsp_l1 = 58,916.1667`（纯单步无 2-opt 优于 `tsp_nn 64,150.6667` 达 `-8.16%`）、`tsp_l2 = 67,421.0556`（受 `pr2392` 超大规模插点骨架外推退化影响）。

## 适用条件、假设与限制

- 在强制“优先装入已有开启箱”的无状态单特征在线接口下，紧致余量贪心构成局部极值不动点；两例 `tsp_l1` 运行因触发 `np.ix_ / np.fill_diagonal` 白名单拦截记为 `no_champion` 并显式列报于 `excluded_runs`。

## 来源及支持的具体结论

- 跨问题总报告与选优清单：`experiments/milestone3_1/m31_cross_problem_report.json`、`experiments/milestone3_1/m31_selection_report.json`。

## 代码和评测关联

- `tools/run_m31_cross_problem.py`、`agent_skill_loop/interface_design/tsp_templates.py`、`obp_templates.py`、`bpp_templates.py`。

## 未确认项与冲突证据

- 需在允许主动开新箱的有状态策略或重尾物品分布下进一步探索在线 OBP 超越 Best-Fit 的空间。
"""
    _put("evidence-m31-cross-problem-tsp-obp-bpp-20261124", m31_meta, m31_md)

    # 2. M3.2 Scaling law & latency collision evidence card
    m32_meta = {
        "type": "evidence",
        "title": "里程碑 3.2 大预算 Scaling Law (36->400) 与 n=200 延迟墙 / 2000ms 解封盲测证据",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-3.2", "scaling-law", "latency-wall", "timeout-2000ms", "cvrp_m32_blind_120"],
        "status": "reviewed",
        "summary": (
            "完成 21 格预锁盘实测（3 种子 × 4 档主曲线 + 3 项 400 请求单因子对照，4,800 请求实费 $4.8419）与 cvrp_m32_blind_120 一次性开封："
            "主曲线 500ms 下未加罚原始可行解均值严格单调改善（23.1931 -> 23.0521 -> 23.0372 -> 23.0257），exact-k 达标率由 0.683 单调升至 0.792，"
            "n=50/100 全部 100% 按时完成并超越强基准，但 n=200 因复杂脚本开销触及 500ms 发生 113/120 (94.2%) 超时导致加罚均值升至 39.1999；"
            "timeout_2000ms 完整对照实现 3/3 种子 0/120 超时、均长 23.1111±0.1142，全部 3 种子显著胜过 l3_ctrl@2000ms (23.2230, p <= 4.00e-6)，最优种子达 22.9796 (exact-k=0.850)。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "ruin_and_recreate",
            "complexity_class": "empirical",
            "interface": "score_ruin_nodes",
            "applicable_regimes": {
                "strong_on": ["large_budget_400_requests", "matched_2000ms_deadline_n200", "exact_k_fleet_consolidation"],
                "weak_on": ["unconstrained_hook_complexity_under_tight_500ms_n200"],
                "scale_notes": "双轨报告原始可行均长与硬截止加罚均长；l3_ctrl@500ms 在非截断路径记录 9/120 超时（严格硬截止等效 26.4966）。",
            },
            "artifact_refs": [
                _pin("tools/run_m32_scaling.py", commit),
                _pin("tools/build_m32_trajectory_report.py", commit),
                _pin("agent_skill_loop/milestone_checkpoint.py", commit),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-cvrp-m3-ruin-recreate-l3", "method-research-agent-m3-autonomous-loop"],
            "sources": [M4_SOURCE_ID],
        },
        "source_refs": [M4_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/milestone3_2/m32_scaling_report.json",
            "report:experiments/milestone3_2/m32_evolution_trajectory.html",
        ],
        "code_refs": [],
    }
    m32_md = """# 里程碑 3.2 大预算 Scaling Law (36->400) 与 n=200 延迟墙 / 2000ms 解封盲测证据

本卡片汇总里程碑 3.2 共 **21 个预锁单元格**（`36 -> 100 -> 200 -> 400` 主曲线与 `model_routing / l3b_dual_hook / timeout_2000ms` 三组 400 请求单因子对照）在 `cvrp_m32_blind_120` 上的一次性盲测实证结果。

## 定义或方法步骤

1. **主曲线双轨趋势（500 ms 硬截止）**：
   - **未加罚原始可行均值（严格单调改善）**：`36: 23.1931 -> 100: 23.0521 -> 200: 23.0372 -> 400: 23.0257`（可行率恒为 `1.000`，均优于 `cw_relocate_2opt 23.2113`）。
   - **车队达标率 (`exact-k`)**：`0.683 -> 0.739 -> 0.761 -> 0.792` 严格单调上升；`n=50 / 100` 全部 `100%` 按时完成。
   - **延迟碰撞**：`n=200` 触发 `40/40, 40/40, 33/40`（`94.2%`）超时，按 $2\times\text{ref}$ 记罚使主加罚均长升至 `39.1999`。
2. **三项单因子对照**：
   - `timeout_2000ms`：全 3 种子 **`0 / 120` 超时**，均长 **`23.1111 ± 0.1142`**，全部 3 种子显著击败 `l3_ctrl@2000ms`（`23.2230`，`p = 9.88e-21 / 2.91e-09 / 4.00e-06`），最优种子 `s20261124 = 22.9796`（`exact-k = 0.850`, vs `cw_relocate_2opt` `109/7/4`, `p = 5.68e-20`）。
   - `model_routing`（`40.5434`, 费用 ~1.65x）与 `l3b_dual_hook`（`48.8565`, 有效产率骤降至 `74–101` 候选）均受困于 500 ms 解释器耗时墙。

## 适用条件、假设与限制

- 揭示了小规模开发集大预算演化中的“计算延迟过拟合”定律；已在 `InterfaceValidator.validate_evolved_hook_n200_latency()` 补齐演化期 `n=200` 耗时筛查入口。

## 来源及支持的具体结论

- `experiments/milestone3_2/m32_scaling_report.json`、`m32_scaling_report.md`、`m32_evolution_trajectory.html`。

## 代码和评测关联

- `tools/run_m32_scaling.py`、`tools/build_m32_trajectory_report.py`、`agent_skill_loop/interface_design/validator.py`。

## 未确认项与冲突证据

- 未来可将 `validate_evolved_hook_n200_latency()` 作为显式多目标门控以在 500 ms 窗口内兼顾 `n=200` 速度与质量。
"""
    _put("evidence-m32-scaling-latency-cliff-20261124", m32_meta, m32_md)

    # 3. M3.2 Emergent Operator Mechanisms method card
    em_meta = {
        "type": "method",
        "title": "大预算自发涌现的无量纲退火破坏算子（三阶段 Gumbel 整合与 Gibbs–Boltzmann 配额阶梯）",
        "category": "method",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-3.2", "milestone-4", "emergent-operator", "gumbel-annealing", "gibbs-boltzmann", "score_ruin_nodes"],
        "status": "reviewed",
        "summary": (
            "在无人工公式提示下，400 请求大预算自主演化于 L3 破坏修复底盘涌现两类完全无量纲的统计物理类比破坏算子："
            "(1) ckpt_cand_8c4dfb41aa（timeout_2000ms s20261124，盲测 22.9796 / exact-k=0.850）：显式构造路径余量比与停靠稀疏度、最大节约种子径向核及确定性 Gumbel 扰动，按 exploit->neutral->diversify 三阶段退火，前期拆散稀疏低载路径实现车队合并；"
            "(2) ckpt_cand_22af9ec1ab（curve s20261126:400，未加罚全局均长最优 22.9430）：融合单位路长绕行节省比、容量压力与饱和仓库偏心率，通过停滞自适应逆温度构造竞争 Gibbs 分布与累积存活概率阶梯。"
        ),
        "attributes": {
            "method_family": "ruin_recreate",
            "online_offline": "offline",
            "interface": "score_ruin_nodes",
            "eoh_map": {
                "status": "possible",
                "adapter_kind": "direct_entrypoint",
                "entrypoint": "score_ruin_nodes",
            },
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "ruin_and_recreate",
            "complexity_class": "O(n^3)",
            "applicable_regimes": {
                "strong_on": ["fleet_consolidation_exact_k", "multi_scale_cvrp_2000ms", "scale_invariant_scoring"],
                "weak_on": ["sub_500ms_python_overhead_at_n200"],
                "scale_notes": "全部 12 份 400 请求冻结冠军在 select_16 (n=50) 上均达到 16/16 合法且满足无量纲群不变约束。",
            },
            "artifact_refs": [
                _pin("tools/run_m4_math_closure.py", commit),
                _pin("experiments/milestone4/m4_m32_operator_dissection.json", commit),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-cvrp-m3-ruin-recreate-l3"],
            "sources": [M4_SOURCE_ID],
        },
        "source_refs": [M4_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/milestone4/m4_m32_operator_dissection.json",
            "report:experiments/milestone4/m4_math_closure_part2.md",
        ],
        "code_refs": [],
    }
    em_md = """# 大预算自发涌现的无量纲退火破坏算子（三阶段 Gumbel 整合与 Gibbs–Boltzmann 配额阶梯）

本卡片总结 M4 第二部分对 M3.2 全部 12 份 400 请求冻结冠军的语法树（AST）与随时性（`10->25->100->250->500 ms`）解剖发现。

## 定义或方法步骤

1. **三阶段温度退火与稀疏路径整合 (`ckpt_cand_8c4dfb41aa`)**：
   - 重构路径剩余容量比与停靠点稀疏度 `1/n_stops`，叠加最大节约种子节点的尺度不变径向核 `1 / (1 + (d(seed, j) / mean(d_0))^2)` 与确定性 Gumbel 噪声 `-log(-log(u))`，依据 `(iter_frac, stagnation_ratio)` 在强化、过渡、分散三阶段平滑调度，将 `exact-k` 车队达标率从 `0.675` 提升至 **`0.850`**。
2. **无量纲 Gibbs–Boltzmann 配额阶梯 (`ckpt_cand_22af9ec1ab`)**：
   - 将单位路长绕行节省比 `removal_savings / route_dists`、容量压力乘积 `(route_loads/C)*(dem_c/C)` 与饱和仓库偏心率 `d_0 / (d_0 + mean(d_0))` 组合为无量纲能量，经逆温度 $\beta(\text{iter\_frac}, \text{stagnation\_ratio})$ 构造竞争 Gibbs 权重与累积排序阶梯，在 120 例盲测取得最低未加罚均长 `22.9430`。

## 适用条件、假设与限制

- 56–113 LOC 的 Python 评分表达式在 `n=200` 需匹配 2000 ms 时限或进行向量化/Cython 加速以避免 500 ms 硬截止超时。

## 来源及支持的具体结论

- `experiments/milestone4/m4_m32_operator_dissection.json`、`experiments/milestone4/m4_math_closure_part2.md`。

## 代码和评测关联

- `tools/run_m4_math_closure.py`（`dissect-m32`）、`experiments/milestone3_2/roster_snapshots/`。

## 未确认项与冲突证据

- 两种涌现机制的组件级消融与在更高规模（`n >= 500`）上的加速编译移植值得后续研究。

## EoH 适配

通过 `cvrp_ruin_recreate/v1` 的 `score_ruin_nodes` 单钩子接口直接接入 `DynamicInterfaceProblem` 与 `ResearchAgent` 演化会话。
"""
    _put("method-m32-emergent-gumbel-gibbs-ruin-20261124", em_meta, em_md)

    # 4. M4 Mathematical Closure Evidence Card
    m4_meta = {
        "type": "evidence",
        "title": "里程碑四数学理论闭环证据：32 组合精确 Shapley 协同、HRK 三池/纯几何下界与多规模 alpha=1 相变",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-4", "shapley", "order2-interaction", "hrk-lower-bound", "group-invariance", "alpha-bifurcation"],
        "status": "reviewed",
        "summary": (
            "完成 M4 数学理论五维闭环复核：(1) s2_r5_spiral 2^5=32 精确 Shapley 全开比特差 0.0、效率残差 <=4.44e-16，揭示二阶交互 F1×F2 高达 +0.8141 (+3.9335%) 居十对之首；"
            "(2) HRK 径向下界 R(I) 在 CVRPLib A/B/P 74 与 288 题全库 0 违背，厘清 single_step_pool (n=200 差距 0.3881%)、constructive_pool (0.0000%)、full_pool (0.0000%) 三层池口径，并验证纯几何无算法分母回归 corr(eta_geom, raw_gap) 在 abp_74 达 -0.4385 / -0.4100；"
            "(3) 三域相似群与 E(2) 等距漂移 <=9.25e-16；完整 64 题多规模 alpha=1 扫频验证 64/64 真实算例出发步精确归零平手，跨过 1 (0.99->1.01) 均长由 26.6122 骤降至 23.3190 (-12.37%)、空驶回程占比由 34.13% 降至 26.26%。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "math_mechanism",
            "complexity_class": "empirical",
            "interface": "select_next_node",
            "applicable_regimes": {
                "strong_on": ["non_additive_operator_attribution", "exogenous_geometric_lower_bound", "scale_and_isometry_verification"],
                "weak_on": ["integer_rounded_micro_coordinates_scale_equivariance"],
                "scale_notes": "同步覆盖 cvrp_select_multiscale_64 (N=64)、cvrp_hist_p0_120 (N=120)、cvrp_hist_hetero_288 (N=288) 与 cvrp_ext_cvrplib_abp_74 (N=74)。",
            },
            "artifact_refs": [
                _pin("tools/run_m4_math_closure.py", commit),
                _pin("tests/test_m4_math_closure.py", commit),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp", "problem-tsp", "problem-online-bin-packing"],
            "methods": ["method-cvrp-m3-ruin-recreate-l3"],
            "sources": [M4_SOURCE_ID],
        },
        "source_refs": [M4_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/milestone4/m4_math_closure_part1.json",
            "report:experiments/milestone4/m4_math_closure_part1.md",
        ],
        "code_refs": [],
    }
    m4_md = """# 里程碑四数学理论闭环证据：32 组合精确 Shapley 协同、HRK 三池/纯几何下界与多规模 alpha=1 相变

本卡片沉淀第四阶段精确数学检验的全部可复算证据。

## 定义或方法步骤

1. **精确 $2^5=32$ Shapley 归因与二阶交互**：
   - 在 `cvrp_select_multiscale_64`（残差 `0.00e+00`）与 `cvrp_hist_p0_120`（残差 `4.44e-16`）上全开构型 `11111` 比特级复现原版 `s2_r5_spiral`。
   - 二阶交互矩阵揭示 **`F1_depot_two_phase_override × F2_adaptive_inward_spiral_alpha`** 正协同高达 **`+0.8141`（`+3.9335%`）**（`p0_120` 上 `+0.3839` / `+2.2270%`），解释了 `F2` 均值近零但留一损失显著的非线性耦合机理。
2. **HRK 下界与三层候选池 / 纯几何外生回归**：
   - `R(I)` 在 `abp_74` 官方 OPT 上 0 违背；区分 `single_step_pool`（`n=200` 保留 `0.3881%` 互补）、`constructive_pool`（`0.0000%`）与 `full_pool`（`0.0000%`）彻底消除口径冲突。
   - 引入纯几何尺度 $G(I) = R(I) + \sqrt{n \cdot A_{\text{bbox}}(I)}$，无共享算法分母的相关系数 `corr(eta_geom, raw_gap)` 在 `abp_74` 上保持稳定负相关（`-0.4385` 与 `-0.4100`）。
3. **三域群不变性与完整 64 题 $\alpha=1$ 相变**：
   - 缩尺与 $E(2)$ 刚体漂移全在 $10^{-16}$ 量级（OBP 漂移 `0.0`），并显式记录整数取整、防除零稳定偏置与墙钟截断三类例外。
   - 在完整 `cvrp_select_multiscale_64`（`N=64`）上，$\alpha = 1.0$ 触发 `64/64` 真实算例出发步精确归零平手（`max_score_spread = 0.0`），跨越 `0.99 -> 1.01` 使均长由 `26.6122` 骤降至 `23.3190`（`-12.37%`）、空驶回程占比由 `34.13%` 降至 `26.26%`。

## 适用条件、假设与限制

- `abp_74` 跨 45 个不同规模 $n \in [15, 100]$ 汇总，非固定 $n$ 控制；极小坐标下 `euc_2d_nint` 整数取整在离散意义下打破连续相似等变性。

## 来源及支持的具体结论

- `experiments/milestone4/m4_math_closure_part1.json`、`experiments/milestone4/m4_math_closure_part1.md`。

## 代码和评测关联

- `tools/run_m4_math_closure.py`、`tests/test_m4_math_closure.py`。

## 未确认项与冲突证据

- 已全部闭环并纳入 `tests/test_m4_math_closure.py` 自动化回归覆盖。
"""
    _put("evidence-m4-shapley-hrk-invariance-closure-20261124", m4_meta, m4_md)

    return {"written": written, "total_entries": len(list(entries_dir.glob("*.json")))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=M4_RELEASE_ID)
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.release_id):
        parser.error("invalid release ID")
    store = REPO / "knowledge_store"
    if os.path.lexists(store / "releases" / args.release_id):
        parser.error(f"release already exists and is immutable: {args.release_id}")

    workspace = REPO / "knowledge_workspace"
    kb_res = sync_milestone4_kb(workspace)
    ws_val = validate_workspace(workspace)
    if not ws_val["ok"]:
        raise RuntimeError(f"knowledge_workspace_validation_failed:{ws_val['errors'][:10]}")

    m3_rel = store / "releases" / M3_RELEASE_ID
    if not m3_rel.is_dir():
        raise FileNotFoundError(f"Prior immutable M3 release missing: {m3_rel}")

    build_dir = REPO / "build"
    build_dir.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="m4-release-", dir=build_dir))
    wb_dir = staging / "workbench"
    dash_dir = staging / "dashboard"
    wb_dir.mkdir(parents=True, exist_ok=True)
    for dname in ("suites", "routes", "traces", "results", "published_results"):
        src_d = m3_rel / dname
        if src_d.is_dir():
            shutil.copytree(src_d, wb_dir / dname)
    for fname in ("algorithms.json", "workbench_manifest.json"):
        src_f = m3_rel / fname
        if src_f.is_file():
            shutil.copy2(src_f, wb_dir / fname)

    dash_info = build_dashboard(
        bundle_dir=wb_dir,
        workspace_dir=workspace,
        output_dir=dash_dir,
        release_id=args.release_id,
    )
    rel_info = build_release(
        workspace,
        store,
        args.release_id,
        workbench_bundle=wb_dir,
        dashboard_dir=dash_dir,
        activate=False,
    )
    rel_val = activate_verified_release(store, Path(rel_info["release"]))
    rel_info["pointer"] = rel_val["pointer"]
    print(json.dumps({
        "ok": True,
        "kb_sync": kb_res,
        "dashboard": dash_info,
        "release": rel_info,
        "release_validation_ok": rel_val["ok"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
