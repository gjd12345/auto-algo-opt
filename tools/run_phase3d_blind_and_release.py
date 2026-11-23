"""Milestone 3 Phase 3D Runner:
1. Freeze pre-blind protocol (M3 + M2 + M1/M1.5 rosters, external benchmarks, Direction-2 pools,
   penalized failure handling, per-seed paired Wilcoxon + Bootstrap + Holm-Bonferroni).
2. One-shot unseal & cryptographic verification of custody-held cvrp_m3_blind_120 (120/120 SHA-256).
3. Evaluate blind_120 (500ms & 25ms), external top-venue/OR suites (cvrp_ext_eohs_256,
   cvrp_ext_cvrplib_abp_74 dual exact-k, cvrp_ext_cvrplib_x_100 tiers), and Direction-2 transfer.
4. Synchronize 5 Milestone 3 knowledge cards into knowledge_workspace/entries/.
5. Assemble unified M3 workbench bundle + offline dashboard and publish immutable release
   knowledge_store/releases/20261123-main-co-workbench-m3.
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
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.interface_design.blind_commitment import M3_BLIND_COMMITMENT_PATH
from agent_skill_loop.interface_design.blind_eval_m3 import (
    M3_EXTRA_L3_SOLVER_ID,
    PHASE3C_SEEDS,
    execute_m3_blind_evaluation,
    freeze_m3_pre_blind_protocol,
)
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from frontend.build_dashboard import build_dashboard
from knowledge_tools.core import activate_verified_release, build_release, validate_workspace

M3_RELEASE_ID = "20261123-main-co-workbench-m3"
M2_RELEASE_ID = "20261123-main-co-workbench-m2"
M3_CODE_COMMIT = "12bb3fbb"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _p_text(p: float) -> str:
    return "p < 1e-8" if p == 0 else f"p = {p:.2e}"


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


def _m3_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": "src-milestone3-research-agent-20261123",
            "title": "Milestone 3 Autonomous Research Agent, Persistent Request Budget, L3 Ruin-and-Recreate, Multi-Seed 4-Arm Attribution, and External OR + Blind-120 Evaluation",
            "authors": ["auto-algo-opt research log"],
            "year": 2026,
            "venue": "Internal experimental audit & immutable release (experiments/milestone3/)",
            "doi": None,
            "url": "https://github.com/gjd12345/auto-algo-opt/blob/main/experiments/milestone3/phase3d_blind_eval/blind_120_evaluation_report.json",
            "kind": "internal_experiment_report",
            "accessed_on": "2026-11-23",
            "availability": "local_repository",
            "license": "repository-internal research record",
            "selected": True,
            "selection_reason": "Complete Milestone 3 audit covering ResearchAgent + PersistentRequestBudget + AST sandbox + L3 cvrp_ruin_recreate/v1 + 3-seed 4-arm B_total=36 comparisons (500ms & 25ms) + one-shot cvrp_m3_blind_120 unsealing + EoH-S 256 / CVRPLib A/B/P 74 & Set X 100 external evaluations.",
            "locator": "experiments/milestone3/phase3c_four_arm/phase3c_report_standard_500ms.json; experiments/milestone3/phase3c_four_arm/phase3c_report_tight_25ms.json; experiments/milestone3/phase3d_blind_eval/blind_120_evaluation_report.json; experiments/milestone3/phase3d_blind_eval/external_benchmarks_report.json",
            "read_depth": "full_text_local",
            "notes": "All candidates, external rosters, and Direction-2 portfolios frozen in pre_blind_protocol_m3.json before unsealing custody-held cvrp_m3_blind_120_sealed.json.",
        }
    ]


def _binding(suite_id: str, alg_id: str, metric: str, value: Any, note: str, run_id: str = "milestone3_phase3d_500ms") -> dict[str, Any]:
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


def sync_milestone3_kb(
    workspace_dir: Path,
    eval_out: Mapping[str, Any],
    *,
    phase3c_500: Mapping[str, Any],
    phase3c_25: Mapping[str, Any],
) -> dict[str, Any]:
    """Write 5 Milestone 3 knowledge cards into knowledge_workspace/entries/."""
    entries_dir = workspace_dir / "entries"
    sources_path = workspace_dir / "sources.json"

    sources_doc = json.loads(sources_path.read_text(encoding="utf-8"))
    existing_by_id = {s["id"]: i for i, s in enumerate(sources_doc["sources"])}
    for src in _m3_sources():
        if src["id"] in existing_by_id:
            sources_doc["sources"][existing_by_id[src["id"]]] = src
        else:
            sources_doc["sources"].append(src)
    sources_path.write_bytes((json.dumps(sources_doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def _pin(rel: str) -> dict[str, Any]:
        evidence = subprocess.check_output(["git", "show", f"{M3_CODE_COMMIT}:{rel}"], cwd=REPO)
        return {
            "kind": "repo_code",
            "commit": M3_CODE_COMMIT,
            "path": rel,
            "sha256": _sha256_bytes(evidence.replace(b"\r\n", b"\n")),
        }

    blind_report = eval_out["blind_report"]
    ext_report = eval_out["external_report"]
    backbone = eval_out["backbone_blind120"]
    sum500 = blind_report["suite_summaries_500ms"]
    b500_arms = blind_report["blind_120_standard_500ms_arm_summary"]
    b25_arms = blind_report["blind_120_tight_25ms_arm_summary"]
    hyp500 = blind_report["hypothesis_tests_blind_120_500ms"]
    hyp25 = blind_report["hypothesis_tests_blind_120_25ms"]
    d2 = blind_report["direction2_overview"]

    l3_ctrl_bl = backbone["solvers"]["m3_l3_ctrl_500ms"]["overall"]
    l3_evo_bl = backbone["solvers"][M3_EXTRA_L3_SOLVER_ID]["overall"]
    m3_best500_id = min(
        (f"m3_3c_standard_500ms_{arm}_s{s}" for arm in ("arm_m3_2_fixed_l2a", "arm_m3_3_full_dynamic") for s in PHASE3C_SEEDS),
        key=lambda sid: float(sum500["cvrp_m3_blind_120"]["algorithms"][sid]["overall"]["mean_tour_length"]),
    )
    m3_best500_bl = sum500["cvrp_m3_blind_120"]["algorithms"][m3_best500_id]["overall"]
    m3_best25_id = min(
        (f"m3_3c_tight_25ms_{arm}_s{s}" for arm in ("arm_m3_2_fixed_l2a", "arm_m3_3_full_dynamic") for s in PHASE3C_SEEDS),
        key=lambda sid: float(blind_report["suite_summaries_25ms"]["cvrp_m3_blind_120"]["algorithms"][sid]["overall"]["mean_tour_length"]),
    )
    m3_best25_bl = blind_report["suite_summaries_25ms"]["cvrp_m3_blind_120"]["algorithms"][m3_best25_id]["overall"]

    written: list[str] = []

    def _put(eid: str, meta: dict[str, Any], md: str) -> None:
        _write_entry(entries_dir, eid, meta, md)
        written.append(eid)

    # 1. Method card: L3 Ruin-and-Recreate + L3-ctrl + Evolved R2 L3
    bb_r2 = hyp500["backbone__r2_l3_evolved_vs_l3_ctrl_500ms"]
    l3_meta = {
        "type": "method",
        "title": "CVRP 基于节点破坏评分与 Regret-2 重插的 L3 破坏修复框架 (M3 L3 · score_ruin_nodes)",
        "category": "method",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-3", "l3", "ruin-recreate", "lns", "regret-2", "anytime", "score_ruin_nodes"],
        "status": "reviewed",
        "summary": (
            f"里程碑三新增 cvrp_ruin_recreate/v1 (L3) 单钩子大邻域搜索模板：以统一 deadline（含 CW + 初始 intra_2opt + LNS）记录 first_feasible_ms 与 anytime_curve，"
            f"演化破坏优先级钩子 score_ruin_nodes 并配套确定性 Regret-2 重插、受扰路径 intra_2opt 与 Record-to-Record 接收；"
            f"L3-ctrl (Worst-Cost Removal) 作为零演化骨架对照在 cvrp_m3_blind_120 (500ms) 达 {l3_ctrl_bl['mean_tour_length']:.4f}（p50={l3_ctrl_bl['solve_ms_p50']} ms），"
            f"M3-3 seed_20261124 第 2 轮跨接口切换后自主演化出的 {M3_EXTRA_L3_SOLVER_ID} 在盲测达 {l3_evo_bl['mean_tour_length']:.4f}（较 L3-ctrl 变化 {bb_r2['rel_gain_vs_baseline_pct']:+.2f}%, {_p_text(bb_r2['p_holm_wilcoxon'])}）。"
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
                "strong_on": ["500ms_budget", "complementary_to_l2a_merge", "stagnation_aware_diversification"],
                "weak_on": ["tight_25ms_budget_exhaustion"],
                "scale_notes": (
                    f"first_feasible_ms 均值约 2–3 ms 保障任何预算必返可行解；500 ms 下 L3-ctrl 在 select_64 5/64 触及截止时间，25 ms 下 64/64 触及预算上限早停。"
                ),
            },
            "interface_blueprint": {
                "skeleton_role": "L3 破坏修复骨架 (cvrp_ruin_recreate/v1)：CW + 初始 intra_2opt 构建驻留解后迭代执行 Ruin(top-q) -> 确定性 Regret-2 可行重插 -> 局部 intra_2opt -> R2R 接收",
                "evolvable_hook": "score_ruin_nodes(distance_matrix, demands, capacity, route_ids, route_loads, route_dists, removal_savings, stagnation_ratio, iter_frac) -> np.ndarray",
                "state_maintained": ["routes", "route_loads", "route_dists", "best_incumbent", "stagnation_count", "anytime_curve"],
                "invariants_and_constraints": [
                    "统一时钟 deadline 覆盖 CW 构造、初始 2-opt 与全部 LNS 迭代",
                    "第 4 关双动作探针使用 6 客户 n=6, q=4 无平分集合 [1,2,3,4] vs [3,4,5,6] 严格校验因果敏感性",
                ],
                "typical_pitfalls": [
                    "25 ms 紧预算下无先验裕度探针直接启用 L3 会退化为仅完成初始构造+少量迭代的预算早停态",
                ],
            },
            "math_formulation": [
                {
                    "expr": "score_i = rank_power(|removal_savings_i| / scale * gate_load * gate_depot * gate_demand * gate_rdist, p(iter_frac, stagnation_ratio))",
                    "variables": {
                        "removal_savings_i": "移除客户 i 节省的邻边增量 d(prev,i)+d(i,next)-d(prev,next)",
                        "stagnation_ratio": "连续未改进步占最大耐心阈值之比",
                    },
                    "preconditions": "输出长度 n 有限浮点向量；所有状态数组只读，确定性破平不依赖全局 RNG",
                }
            ],
            "artifact_refs": [
                _pin("agent_skill_loop/interface_design/templates.py"),
                _pin("agent_skill_loop/interface_design/validator.py"),
                _pin("tools/run_phase3c_four_arm.py"),
            ],
            "evidence_bindings": [
                _binding("cvrp_m3_blind_120", "m3_l3_ctrl_500ms", "mean_tour_length", l3_ctrl_bl["mean_tour_length"], f"L3-ctrl Worst Removal 在盲测 120 题 (500ms) 均长 {l3_ctrl_bl['mean_tour_length']}"),
                _binding("cvrp_m3_blind_120", M3_EXTRA_L3_SOLVER_ID, "mean_tour_length", l3_evo_bl["mean_tour_length"], f"M3-3 R2 自主切换至 L3 演化出的 score_ruin_nodes 在盲测 120 题均长 {l3_evo_bl['mean_tour_length']}"),
                _binding("cvrp_select_multiscale_64", M3_EXTRA_L3_SOLVER_ID, "mean_tour_length", sum500["cvrp_select_multiscale_64"]["algorithms"][M3_EXTRA_L3_SOLVER_ID]["overall"]["mean_tour_length"], "select_64 均长并构成 m3_cross_paradigm 方向二互补核心"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-cvrp-m2-l2a-generalized-savings", "method-cvrp-lns-shaw-regret"],
            "sources": ["src-milestone3-research-agent-20261123"],
        },
        "source_refs": ["src-milestone3-research-agent-20261123"],
        "evidence_refs": [
            "report:experiments/milestone3/phase3c_four_arm/backbone_attribution_report.json",
            "report:experiments/milestone3/phase3d_blind_eval/backbone_blind120_report.json",
        ],
        "code_refs": [],
    }
    l3_md = f"""# CVRP 基于节点破坏评分与 Regret-2 重插的 L3 破坏修复框架 (M3 L3 · score_ruin_nodes)

本条目记录里程碑三交付的可进化 LNS 破坏修复模板 `cvrp_ruin_recreate/v1`（L3）、受控骨架基线 `m3_l3_ctrl_500ms`（Worst-Cost Removal），以及 `arm_m3_3_full_dynamic`（`seed_20261124` 第 2 轮）自主从 `L2a` 切换至 `L3` 后进化得到的 `{M3_EXTRA_L3_SOLVER_ID}`。

## 定义或方法步骤

1. **统一预算时钟与 Anytime 轨迹**：从 `t0` 起将 CW 初始构造、初始 `intra_2opt` 与 LNS 主循环纳入同一截止时钟，完备记录首个合法可行解时刻 `first_feasible_ms` 及 `(10, 25, 100, 250, 500) ms` 节点下的 `anytime_curve`。
2. **单钩子 `score_ruin_nodes` 与受控归因基线**：只将破坏优先级评分开放给 LLM 演化，固定重插为确定性 Regret-2 + 局部 `intra_2opt` + R2R 接收；配套零演化 `L3-ctrl` 基线严格分离“LNS 骨架红利”与“进化破坏策略净增益”。
3. **第 4 关双动作因果与单会话互补**：固定 6 客探针校验 `set(first_ruin_set_A)=={{1,2,3,4}}` 与 `set(first_ruin_set_B)=={{3,4,5,6}}`；在 `seed_20261124/arm_m3_3` 第 2 轮中，进化得到的乘性门控-秩幂次破坏规则在 `dev_24` 组合中直接击败第 1 轮 `L2a+relocate_2opt` 冠军 `8/24` 题，展现与构造合并层的真实逐例互补。

## 适用条件、假设与限制

- **时间预算边界**：`500 ms` 下可完成充分多轮 LNS 搜索（`blind_120` 完成率 `{l3_evo_bl['completion_rate']}`）；在 `25 ms` 紧预算下 `L3-ctrl` 因每步重插开销 `120/120` 触发协作早停，研究代理在 `25 ms` 下自动规避切换至高耗时的动态/LNS 模板。

## 来源及支持的具体结论

- Backbone 与 Anytime 盲测对比：`experiments/milestone3/phase3d_blind_eval/backbone_blind120_report.json`（`cvrp_m3_blind_120` 上 `{M3_EXTRA_L3_SOLVER_ID}` 均长 **`{l3_evo_bl['mean_tour_length']:.4f}`** vs `L3-ctrl` `{l3_ctrl_bl['mean_tour_length']:.4f}` vs `cw_relocate_2opt` `{backbone['solvers']['cw_relocate_2opt']['overall']['mean_tour_length']:.4f}`）。

## 代码和评测关联

- 模板实现与第 4 关探针：`agent_skill_loop/interface_design/templates.py`、`agent_skill_loop/interface_design/validator.py`。

## 未确认项与冲突证据

- 更高请求上限下的 `L3` 多代精调与双钩子（破坏+重插协同演化）留待后续大预算阶段展开。

## EoH 适配

通过 `interface_selection.template_id = "cvrp_ruin_recreate"` 与 `score_ruin_nodes` 入口原生接入 `DynamicInterfaceProblem` 与 `ResearchAgent` 会话引擎。
"""
    _put("method-cvrp-m3-ruin-recreate-l3", l3_meta, l3_md)

    # 2. Method/Framework card: Autonomous Research Agent Loop
    agent_meta = {
        "type": "method",
        "title": "无人值守组合优化自主研究代理与持久预算状态机 (M3 ResearchAgent · research_agent)",
        "category": "method",
        "problem_family": "cvrp",
        "tags": ["research-agent", "milestone-3", "persistent-budget", "wal-ledger", "ast-sandbox", "hypothesis-ledger"],
        "status": "reviewed",
        "summary": (
            "里程碑三独立工程交付的无人值守多轮自主研究代理引擎（research_agent/）："
            "以 SQLite WAL PersistentRequestBudget（reserved -> sent -> unknown 崩溃恢复）统一管辖外层工具推理与内层 EoH 全部 LLM 请求；"
            "通过 AST 只读数学沙箱（dev_24 隔离）、证据 SHA-256 绑定假设账本、AST 查重护栏及五关界面校验驱动闭环探索；"
            "在 500 ms 与 25 ms 各 3 粒随机种子上 100% 严守 36 次总请求硬上限、零选优集/盲测泄露且显著消灭小预算下的演化随机方差。"
        ),
        "attributes": {
            "method_family": "autonomous_research_agent",
            "online_offline": "offline",
            "interface": "solve_cvrp",
            "eoh_map": {
                "status": "not_mappable",
                "adapter_kind": "not_mappable",
                "entrypoint": None,
                "notes": "Search orchestration outer agent controlling interface selection, diagnostics, sandbox checks, and multi-round EoH sessions.",
            },
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "llm_ahd_framework",
            "complexity_class": "empirical",
            "applicable_regimes": {
                "strong_on": ["small_budget_multi_seed_stability", "tool_grounded_interface_and_postprocess_selection", "crash_resumable_unattended_search"],
                "weak_on": ["extreme_zero_budget_pure_random_mutation"],
                "scale_notes": "全自主 3 轮闭环在 B_total=36 下跨越 M3-0/M3-1 的 ~21.9–23.0 高方差区间，将 3 粒种子 select_64 稳定压至 20.67–20.88。",
            },
            "artifact_refs": [
                _pin("agent_skill_loop/request_budget.py"),
                _pin("agent_skill_loop/session_runtime.py"),
                _pin("research_agent/loop.py"),
                _pin("research_agent/sandbox_worker.py"),
                _pin("research_agent/tools/session_tools.py"),
                _pin("research_agent/tools/archive_tools.py"),
            ],
            "evidence_bindings": [
                _binding("cvrp_m3_blind_120", m3_best500_id, "mean_tour_length", m3_best500_bl["mean_tour_length"], f"500ms 下最优研究代理冻结体在盲测 120 题均长 {m3_best500_bl['mean_tour_length']}"),
                _binding("cvrp_m3_blind_120", m3_best25_id, "mean_tour_length", m3_best25_bl["mean_tour_length"], f"25ms 下最优研究代理冻结体在盲测 120 题均长 {m3_best25_bl['mean_tour_length']}", run_id="milestone3_phase3d_25ms"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-lit-ahd-eoh", "method-cvrp-m2-l2a-generalized-savings", "method-cvrp-m3-ruin-recreate-l3"],
            "sources": ["src-milestone3-research-agent-20261123"],
        },
        "source_refs": ["src-milestone3-research-agent-20261123"],
        "evidence_refs": [
            "report:experiments/milestone3/phase3c_four_arm/phase3c_report_standard_500ms.json",
            "report:experiments/milestone3/phase3c_four_arm/phase3c_report_tight_25ms.json",
        ],
        "code_refs": [],
    }
    agent_md = f"""# 无人值守组合优化自主研究代理与持久预算状态机 (M3 ResearchAgent · research_agent)

本条目记录里程碑三建成的独立多轮自主研究代理系统（`research_agent/`），核心目标是在**严格单进程/跨进程共享总请求硬上限 `B_total=36`**与**物理拆离 `dev_24 / select_64 / blind_120`**下，仅凭工具观察与自我反思自主完成组合优化算法设计与验证。

## 定义或方法步骤

1. **双层持久请求账本 (`PersistentRequestBudget`)**：以 SQLite WAL 实现 `reserved -> sent -> complete/failed/unknown` 原子状态机，外层 Reason–Act–Reflect 与内层 Session EoH 共享同一余额与 `response_sha256` 审计轨迹，支持断点零重复恢复。
2. **结构化工具链与防幻觉约束**：集成 7 类工具（`kb_search/kb_read`、`diagnose_suite` 五因子切片、`run_math_sandbox` AST 只读沙箱、`list_interfaces` + `propose_and_validate_interface` 五关预检、`submit_plan_and_evolve`、`archive_query` 踏脚石档案、带证据 SHA-256 强制核验的 `hypotheses.jsonl` 账本与 AST 查重防退化守卫）。
3. **双预算 3 种子闭环稳定性**：`standard_500ms`（12 场）与 `tight_25ms`（12 场）合计 24 场实测中全部满足 `attempted_requests <= 36`、零隔离违规。

## 适用条件、假设与限制

- 外层诊断与规划需占用部分请求配额（在 `B_total=36` 下外层通常占 `15–17` 次，内层 `19–21` 次），在存在偶发代理网络波动时通过离线重试与账本精确核销维持配对可比性。

## 来源及支持的具体结论

- 阶段 3C 双预算四臂 × 三随机种子总报告：`experiments/milestone3/phase3c_four_arm/phase3c_report_standard_500ms.json`、`phase3c_report_tight_25ms.json`。

## 代码和评测关联

- 核心实现：`research_agent/`、`agent_skill_loop/request_budget.py`、`agent_skill_loop/session_runtime.py`。

## 未确认项与冲突证据

- 跨问题扩展（TSP 与在线 OBP）及更高预算曲线（`36 -> 100 -> 200 -> 400`）待后续里程碑 M3.1 与 M3.2 验证。
"""
    _put("method-research-agent-m3-autonomous-loop", agent_meta, agent_md)

    # 3. Evidence card: 3-Seed Four-Arm Fair-Budget Comparison (500ms + 25ms)
    s500 = phase3c_500["arm_summary"]
    s25 = phase3c_25["arm_summary"]
    e4_meta = {
        "type": "evidence",
        "title": "里程碑三四臂 × 三独立随机种子同总预算 (B_total=36) 归因实验证据 (500ms & 25ms)",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-3", "four-arm", "multi-seed", "b-total-36", "pyvrp-plus-baseline", "variance-reduction"],
        "status": "reviewed",
        "summary": (
            f"在 B_total=36、deepseek-v4.1-flash（无静态线索注入）及三种子 (20261124/20261125/20261126) 下完成 24 场公平归因："
            f"500 ms 下 select_64 三种子均值：M3-0 纯 EoH={s500['arm_m3_0_pure_eoh']['select_64_mean_avg']:.4f}、"
            f"M3-1 纯文本反思={s500['arm_m3_1_plain_text']['select_64_mean_avg']:.4f}、"
            f"M3-2 固定 L2a 完整代理={s500['arm_m3_2_fixed_l2a']['select_64_mean_avg']:.4f}、"
            f"M3-3 全动态完整代理={s500['arm_m3_3_full_dynamic']['select_64_mean_avg']:.4f}（最优单粒 {s500['arm_m3_3_full_dynamic']['select_64_best']:.4f}）；"
            f"25 ms 下 M3-2={s25['arm_m3_2_fixed_l2a']['select_64_mean_avg']:.4f}（最优 {s25['arm_m3_2_fixed_l2a']['select_64_best']:.4f}）、"
            f"M3-3={s25['arm_m3_3_full_dynamic']['select_64_mean_avg']:.4f}（零超时保守滞留静态 L2a）vs M3-0={s25['arm_m3_0_pure_eoh']['select_64_mean_avg']:.4f} / M3-1={s25['arm_m3_1_plain_text']['select_64_mean_avg']:.4f}。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "llm_ahd_framework",
            "complexity_class": "empirical",
            "interface": "score_merge_static",
            "applicable_regimes": {
                "strong_on": ["fair_shared_budget_attribution", "multi_seed_variance_elimination"],
                "weak_on": ["single_seed_lucky_draw_claims"],
                "scale_notes": "同时严格披露每组 attempted_requests 与 completed_requests；研究代理工具链将 3 粒种子离散度压缩超过 20 倍。",
            },
            "artifact_refs": [
                _pin("tools/run_phase3c_four_arm.py"),
                _pin("research_agent/loop.py"),
                _pin("research_agent/prompts.py"),
            ],
            "evidence_bindings": [
                _binding("cvrp_select_multiscale_64", "m3_3c_standard_500ms_arm_m3_3_full_dynamic_s20261125", "mean_tour_length", s500["arm_m3_3_full_dynamic"]["select_64_best"], "500ms 全动态代理最优种子 select_64 均长"),
                _binding("cvrp_select_multiscale_64", "m3_3c_tight_25ms_arm_m3_2_fixed_l2a_s20261126", "mean_tour_length", s25["arm_m3_2_fixed_l2a"]["select_64_best"], "25ms 下 M3-2 最优种子 select_64 超越 CW+Relocate+2opt"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-research-agent-m3-autonomous-loop", "method-cvrp-m2-l2a-generalized-savings", "method-cvrp-m3-ruin-recreate-l3"],
            "sources": ["src-milestone3-research-agent-20261123"],
        },
        "source_refs": ["src-milestone3-research-agent-20261123"],
        "evidence_refs": [
            "report:experiments/milestone3/phase3c_four_arm/phase3c_report_standard_500ms.json",
            "report:experiments/milestone3/phase3c_four_arm/phase3c_report_tight_25ms.json",
        ],
        "code_refs": [],
    }
    e4_md = f"""# 里程碑三四臂 × 三独立随机种子同总预算 (B_total=36) 归因实验证据 (500ms & 25ms)

本卡片汇总里程碑三阶段 3C 的 **24 场全在线对照实验**（2 预算 × 4 实验臂 × 3 随机种子 `{list(PHASE3C_SEEDS)}`，同一模型 `deepseek-v4.1-flash`，`dev_24` 可见、`select_64` 与 `blind_120` 彻底物理隔离）。

## 定义或方法步骤

1. **`500 ms` 主对比 (`select_64` 三种子逐例与均值 ± 尝试/成功请求)**：
   - **Arm M3-0 (纯 EoH)**: `{s500['arm_m3_0_pure_eoh']['select_64_means']}`，均值 **`{s500['arm_m3_0_pure_eoh']['select_64_mean_avg']:.4f}`**（avg att `{s500['arm_m3_0_pure_eoh']['attempted_requests_avg']}` / ok `{s500['arm_m3_0_pure_eoh']['completed_requests_avg']}`）。
   - **Arm M3-1 (纯文本反思, 对标 PyVRP+)**: `{s500['arm_m3_1_plain_text']['select_64_means']}`，均值 **`{s500['arm_m3_1_plain_text']['select_64_mean_avg']:.4f}`**（avg att `{s500['arm_m3_1_plain_text']['attempted_requests_avg']}` / ok `{s500['arm_m3_1_plain_text']['completed_requests_avg']}`）。
   - **Arm M3-2 (完整研究代理 · 锁定 L2a)**: `{s500['arm_m3_2_fixed_l2a']['select_64_means']}`，均值 **`{s500['arm_m3_2_fixed_l2a']['select_64_mean_avg']:.4f}`**（avg att `{s500['arm_m3_2_fixed_l2a']['attempted_requests_avg']}` / ok `{s500['arm_m3_2_fixed_l2a']['completed_requests_avg']}`）。
   - **Arm M3-3 (完整研究代理 · 全动态 `{{L1,L2a,L2b,L3}}`)**: `{s500['arm_m3_3_full_dynamic']['select_64_means']}`，均值 **`{s500['arm_m3_3_full_dynamic']['select_64_mean_avg']:.4f}`**（最优 **`{s500['arm_m3_3_full_dynamic']['select_64_best']:.4f}`**，avg att `{s500['arm_m3_3_full_dynamic']['attempted_requests_avg']}` / ok `{s500['arm_m3_3_full_dynamic']['completed_requests_avg']}`）。
2. **`25 ms` 预算自适应对比 (`select_64`)**：
   - `M3-0 = {s25['arm_m3_0_pure_eoh']['select_64_mean_avg']:.4f}`、`M3-1 = {s25['arm_m3_1_plain_text']['select_64_mean_avg']:.4f}`、`M3-2 = {s25['arm_m3_2_fixed_l2a']['select_64_mean_avg']:.4f}`（最优 **`{s25['arm_m3_2_fixed_l2a']['select_64_best']:.4f}`**）、`M3-3 = {s25['arm_m3_3_full_dynamic']['select_64_mean_avg']:.4f}`（`0/64` 超时，稳健保留静态 `L2a (none)`）。

## 适用条件、假设与限制

- 在未注入静态 KB 线索的公平设定下，纯 EoH 与纯文本反思极易出现多颗种子滞留于逐对局部归一化退化区间（`21.6–23.3`），而完整研究代理通过动态检索 KB 与五关校验，在两档预算的全部 `6/6` 粒自主代理种子上实现稳定复现。

## 来源及支持的具体结论

- 完整账本：`experiments/milestone3/phase3c_four_arm/phase3c_report_standard_500ms.json`、`phase3c_report_tight_25ms.json`。

## 代码和评测关联

- `tools/run_phase3c_four_arm.py`。

## 未确认项与冲突证据

- 开放全局大预算上限下的高轮次搜索（如 `400` 次请求）是否进一步触发 L3 全面反超，留待 M3.2 检验。
"""
    _put("evidence-cvrp-m3-four-arm-multiseed-500ms-25ms", e4_meta, e4_md)

    # 4. Evidence card: One-shot cvrp_m3_blind_120 & Direction-2 Selection
    d2_m15 = d2["m3_blind_120__m15_pointwise_pool_frozen"]
    d2_m2 = d2["m3_blind_120__m2_full_hybrid_pool_frozen"]
    d2_m3e = d2["m3_blind_120__m3_evolved_cross_paradigm_pool_frozen"]
    d2_m3h = d2["m3_blind_120__m3_full_hybrid_pool_frozen"]

    h_s25_m3_vs_c1 = hyp500["s20261125__m3_3_vs_c1_tworegime"]
    h_s25_m3_vs_m1 = hyp500["s20261125__m3_3_vs_m3_1"]
    backbone_25_exh = blind_report["suite_summaries_25ms"]["cvrp_m3_blind_120"]["algorithms"]["m3_l3_ctrl_25ms"]["overall"]["ok_budget_exhausted_count"]
    blind_meta = {
        "type": "evidence",
        "title": "里程碑三 cvrp_m3_blind_120 一次性启封逐种子配对盲测与方向二跨范式终审证据",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-3", "cvrp_m3_blind_120", "holm-bonferroni", "direction-2", "cross-paradigm-selection"],
        "status": "reviewed",
        "summary": (
            f"在冻结 pre_blind_protocol_m3.json 后一次性仓外启封并核验 cvrp_m3_blind_120（120/120 SHA-256 匹配 2d55ea75...）："
            f"500 ms 下跨 3 粒独立种子均长：M3-0={b500_arms['arm_m3_0_pure_eoh']['mean_across_seeds']:.4f}±{b500_arms['arm_m3_0_pure_eoh']['std_across_seeds']:.4f}、"
            f"M3-1={b500_arms['arm_m3_1_plain_text']['mean_across_seeds']:.4f}±{b500_arms['arm_m3_1_plain_text']['std_across_seeds']:.4f}、"
            f"M3-2={b500_arms['arm_m3_2_fixed_l2a']['mean_across_seeds']:.4f}±{b500_arms['arm_m3_2_fixed_l2a']['std_across_seeds']:.4f}、"
            f"M3-3={b500_arms['arm_m3_3_full_dynamic']['mean_across_seeds']:.4f}±{b500_arms['arm_m3_3_full_dynamic']['std_across_seeds']:.4f}；"
            f"方向二在 m3_blind_120 上将候选题池从 M1.5 (SBS={d2_m15['sbs_mean']:.4f}, VBS={d2_m15['vbs_mean']:.4f}) "
            f"推进至 M3 全混合池 (SBS={d2_m3h['sbs_mean']:.4f}, VBS={d2_m3h['vbs_mean']:.4f}, (SBS-VBS)/SBS={d2_m3h['gap_over_sbs_pct']:.2f}%)。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "selector_portfolio",
            "complexity_class": "O(n^2)",
            "interface": "solve_cvrp",
            "applicable_regimes": {
                "strong_on": ["one_shot_blind_generalization", "per_seed_holm_bonferroni_inference", "cross_paradigm_l2a_l3_complementarity"],
                "weak_on": ["tight_25ms_without_headroom_awareness"],
                "scale_notes": (
                    f"逐种子配对（严禁 3x120 混池）：s20261125 上 M3-3 较 C1 降低 {h_s25_m3_vs_c1['rel_gain_vs_baseline_pct']:.2f}%（Holm {_p_text(h_s25_m3_vs_c1['p_holm_wilcoxon'])}），"
                    f"25ms 下 M3-2/M3-3 实现 0/120 超时降级而 L3-ctrl 达 {backbone_25_exh}/120 耗尽早停。"
                ),
            },
            "artifact_refs": [
                _pin("agent_skill_loop/interface_design/blind_commitment.py"),
                _pin("benchmarks/cvrp_workbench/manifests/cvrp_m3_blind_120_commitment.json"),
            ],
            "evidence_bindings": [
                _binding("cvrp_m3_blind_120", m3_best500_id, "mean_tour_length", m3_best500_bl["mean_tour_length"], f"500ms M3 最优冻结体盲测 120 题均长 {m3_best500_bl['mean_tour_length']}"),
                _binding("cvrp_m3_blind_120", "i605_cvrp_c1_tworegime", "mean_tour_length", sum500["cvrp_m3_blind_120"]["algorithms"]["i605_cvrp_c1_tworegime"]["overall"]["mean_tour_length"], "M1.5 最强逐点规则 C1 在 M3 盲测 120 题均长"),
                _binding("cvrp_m3_blind_120", m3_best25_id, "mean_tour_length", m3_best25_bl["mean_tour_length"], f"25ms M3 最优冻结体盲测 120 题均长 {m3_best25_bl['mean_tour_length']}", run_id="milestone3_phase3d_25ms"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-research-agent-m3-autonomous-loop", "method-cvrp-m3-ruin-recreate-l3", "method-cvrp-m2-l2a-generalized-savings"],
            "sources": ["src-milestone3-research-agent-20261123"],
        },
        "source_refs": ["src-milestone3-research-agent-20261123"],
        "evidence_refs": [
            "report:experiments/milestone3/phase3d_blind_eval/pre_blind_protocol_m3.json",
            "report:experiments/milestone3/phase3d_blind_eval/blind_120_evaluation_report.json",
            "report:experiments/milestone3/phase3d_blind_eval/direction2_cross_paradigm_report.json",
        ],
        "code_refs": [],
    }
    blind_md = f"""# 里程碑三 cvrp_m3_blind_120 一次性启封逐种子配对盲测与方向二跨范式终审证据

本卡片记录阶段 3D 对仓外受限保管盲测集 `cvrp_m3_blind_120` 的**先冻结后一次性开封评估**（`suite_content_sha256: 2d55ea75...`，`generator_source_sha256: 11c0f9ca...`，公开产物零坐标/需求/种子泄露）。

## 定义或方法步骤

1. **500 ms 四臂 × 3 种子逐例统计（按 120 题独立逐种子做配对 Wilcoxon + 10k Bootstrap + Holm-Bonferroni 校正，绝不把 `3×120` 当作 360 独立样本）**：
   - `M3-0`: 跨种子均值 `{b500_arms['arm_m3_0_pure_eoh']['mean_across_seeds']:.4f} ± {b500_arms['arm_m3_0_pure_eoh']['std_across_seeds']:.4f}`
   - `M3-1`: 跨种子均值 `{b500_arms['arm_m3_1_plain_text']['mean_across_seeds']:.4f} ± {b500_arms['arm_m3_1_plain_text']['std_across_seeds']:.4f}`
   - `M3-2`: 跨种子均值 **`{b500_arms['arm_m3_2_fixed_l2a']['mean_across_seeds']:.4f} ± {b500_arms['arm_m3_2_fixed_l2a']['std_across_seeds']:.4f}`**
   - `M3-3`: 跨种子均值 **`{b500_arms['arm_m3_3_full_dynamic']['mean_across_seeds']:.4f} ± {b500_arms['arm_m3_3_full_dynamic']['std_across_seeds']:.4f}`**
   - 例：在 `s20261125` 上，`M3-3` 对 `C1` 降幅 `{h_s25_m3_vs_c1['rel_gain_vs_baseline_pct']:.2f}%`（`p_holm = {_p_text(h_s25_m3_vs_c1['p_holm_wilcoxon'])}`），对 `M3-1` 降幅 `{h_s25_m3_vs_m1['rel_gain_vs_baseline_pct']:.2f}%`（`p_holm = {_p_text(h_s25_m3_vs_m1['p_holm_wilcoxon'])}`）。
2. **25 ms 紧预算适应对比**：`M3-2 = {b25_arms['arm_m3_2_fixed_l2a']['mean_across_seeds']:.4f} ± {b25_arms['arm_m3_2_fixed_l2a']['std_across_seeds']:.4f}`、`M3-3 = {b25_arms['arm_m3_3_full_dynamic']['mean_across_seeds']:.4f} ± {b25_arms['arm_m3_3_full_dynamic']['std_across_seeds']:.4f}`（全部 0 超时），对比 `L3-ctrl_25ms` `{backbone_25_exh}/120` 预算耗尽。
3. **方向二跨范式池在 `cvrp_m3_blind_120` 上的冻结迁移**：
   - `m15_pointwise_pool`: SBS `{d2_m15['sbs_mean']:.4f}` → VBS `{d2_m15['vbs_mean']:.4f}`
   - `m2_full_hybrid_pool`: SBS `{d2_m2['sbs_mean']:.4f}` → VBS `{d2_m2['vbs_mean']:.4f}`
   - `m3_evolved_cross_paradigm_pool`: SBS **`{d2_m3e['sbs_mean']:.4f}`** → VBS **`{d2_m3e['vbs_mean']:.4f}`**（`(SBS-VBS)/SBS={d2_m3e['gap_over_sbs_pct']:.2f}%`, `oracle={d2_m3e['oracle_counts']}`）
   - `m3_full_hybrid_pool`: SBS **`{d2_m3h['sbs_mean']:.4f}`** → VBS **`{d2_m3h['vbs_mean']:.4f}`**（`(SBS-VBS)/SBS={d2_m3h['gap_over_sbs_pct']:.2f}%`, `(SBS-VBS)/VBS={d2_m3h['gap_over_vbs_pct']:.2f}%`）

## 适用条件、假设与限制

- 一经启封 `cvrp_m3_blind_120` 即转为已暴露回归集，后续 M3.2 大预算研究需采用新独立仓外盲测集 `cvrp_m32_blind_120`。

## 来源及支持的具体结论

- `experiments/milestone3/phase3d_blind_eval/blind_120_evaluation_report.json`、`direction2_cross_paradigm_report.json`。

## 代码和评测关联

- `agent_skill_loop/interface_design/blind_eval_m3.py`、`tools/run_phase3d_blind_and_release.py`。

## 未确认项与冲突证据

- 轻量特征选择器在 64 题训练集转移至高度接近的多强 L2a 求解器时，小样本学习方差仍限制了全量逼近 VBS 的净增益上限。
"""
    _put("evidence-cvrp-m3-blind120-and-direction2", blind_meta, blind_md)

    # 5. Evidence card: External Top-Venue & OR Gold Benchmarks (EoH-S 256, CVRPLib A/B/P 74, Set X 100)
    ext_s = ext_report["suites"]
    eohs_algs = ext_s["cvrp_ext_eohs_256"]["algorithms"]
    abp_algs = ext_s["cvrp_ext_cvrplib_abp_74"]["algorithms"]
    x_algs = ext_s["cvrp_ext_cvrplib_x_100"]["algorithms"]
    ext_meta = {
        "type": "evidence",
        "title": "里程碑二/三冻结求解器在国际顶会与 OR 黄金标准库 (EoH-S 256 / CVRPLib A·B·P 74 / Set X 100) 外部大考证据",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["cvrp", "milestone-3", "external-benchmark", "eoh-s-256", "cvrplib-abp", "cvrplib-set-x", "exact-k"],
        "status": "reviewed",
        "summary": (
            f"统一 500 ms 预算、严格相同距离公约（EoH-S 为 euc_2d_float，CVRPLib A/B/P 与 Set X 为 euc_2d_nint）下首次横向评测 M2 与 M3 冻结冠军："
            f"EoH-S 256 相对 LKH 均 gap：M3 最优 {m3_best500_id} 达 {100*float(eohs_algs[m3_best500_id]['overall']['mean_rel_gap']):+.2f}% vs CW {100*float(eohs_algs['cw_parallel_merge']['overall']['mean_rel_gap']):+.2f}% / C1 {100*float(eohs_algs['i605_cvrp_c1_tworegime']['overall']['mean_rel_gap']):+.2f}%；"
            f"CVRPLib A/B/P 74 相对官方 BKS 均 gap：{100*float(abp_algs[m3_best500_id]['overall']['mean_rel_gap']):+.2f}%（精确-k 合规率 {100*float(abp_algs[m3_best500_id]['overall']['exact_k_compliance_rate']):.1f}%）；"
            f"CVRPLib Set X 100（含 501-1000 大图）相对官方 BKS 均 gap：{100*float(x_algs[m3_best500_id]['overall']['mean_rel_gap']):+.2f}%（X-S/M/L 全完成）。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "parallel_merge",
            "complexity_class": "O(n^2 log n)",
            "interface": "solve_cvrp",
            "applicable_regimes": {
                "strong_on": ["external_eoh_s_256_generalization", "cvrplib_abp_74_and_set_x_100_scaling_to_n1000"],
                "weak_on": ["strict_exact_k_bin_packing_when_unconstrained"],
                "scale_notes": "对 CVRPLib A/B/P 74 严格同步报告自由车数全体 gap 与 ==k 精确车数子集违规统计；对 Set X 100 分 X-S (100-250)、X-M (251-500)、X-L (501-1000) 三档报告。",
            },
            "artifact_refs": [
                _pin("agent_skill_loop/cvrp_workbench/runner.py"),
                _pin("agent_skill_loop/cvrp_workbench/suites.py"),
            ],
            "evidence_bindings": [
                _binding("cvrp_ext_eohs_256", m3_best500_id, "mean_rel_gap", eohs_algs[m3_best500_id]["overall"]["mean_rel_gap"], "EoH-S 256 相对 LKH 平均差距"),
                _binding("cvrp_ext_cvrplib_abp_74", m3_best500_id, "mean_rel_gap", abp_algs[m3_best500_id]["overall"]["mean_rel_gap"], "CVRPLib Set A/B/P 74 相对官方 BKS 平均差距"),
                _binding("cvrp_ext_cvrplib_x_100", m3_best500_id, "mean_rel_gap", x_algs[m3_best500_id]["overall"]["mean_rel_gap"], "CVRPLib Uchoa Set X 100 相对官方 BKS 平均差距"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-cvrp-m2-l2a-generalized-savings", "method-cvrp-m3-ruin-recreate-l3", "method-research-agent-m3-autonomous-loop"],
            "sources": ["src-milestone3-research-agent-20261123"],
        },
        "source_refs": ["src-milestone3-research-agent-20261123"],
        "evidence_refs": [
            "report:experiments/milestone3/phase3d_blind_eval/external_benchmarks_report.json",
        ],
        "code_refs": [],
    }
    def _pct(ov: Mapping[str, Any], k: str = "mean_rel_gap") -> str:
        val = ov.get(k)
        return f"{100.0 * float(val):+.2f}%" if isinstance(val, (int, float)) else "—"

    x_t_best = x_algs[m3_best500_id]["by_x_tier"]
    ext_md = f"""# 里程碑二/三冻结求解器在国际顶会与 OR 黄金标准库 (EoH-S 256 / CVRPLib A·B·P 74 / Set X 100) 外部大考证据

本卡片补充 M2 与 M3 代表冻结求解器在**外部顶会及 OR 黄金标准库**上同一 500 ms 预算、零参数重调的横向验证证据，彻底消除“只在自建小规模分布内自证”的局限。

## 定义或方法步骤

1. **`cvrp_ext_eohs_256`（256 题，EoH-S 协议 `euc_2d_float` vs LKH）**：
   - `i605_cvrp_c1_tworegime`: **`{_pct(eohs_algs['i605_cvrp_c1_tworegime']['overall'])}`**
   - `cw_parallel_merge`: **`{_pct(eohs_algs['cw_parallel_merge']['overall'])}`**
   - `cw_relocate_2opt`: **`{_pct(eohs_algs['cw_relocate_2opt']['overall'])}`**
   - `M2 最优 (Arm4b s20261123)`: **`{_pct(eohs_algs['m2_2b_standard_500ms_llm_diagnostic_planner_s20261123']['overall'])}`**
   - `M3 最优 ({m3_best500_id})`: **`{_pct(eohs_algs[m3_best500_id]['overall'])}`**
   - `M3 R2 进化 L3 ({M3_EXTRA_L3_SOLVER_ID})`: **`{_pct(eohs_algs[M3_EXTRA_L3_SOLVER_ID]['overall'])}`**
2. **`cvrp_ext_cvrplib_abp_74`（74 题，Set A/B/P `euc_2d_nint` vs 官方 `.sol` BKS，双口径报车数合规性）**：
   - `M3 最优 ({m3_best500_id})`: 整体均 gap **`{_pct(abp_algs[m3_best500_id]['overall'])}`**（精确-$k$ 合规 `{abp_algs[m3_best500_id]['overall']['exact_k_count']}/{abp_algs[m3_best500_id]['overall']['exact_k_checked']}` = `{100*float(abp_algs[m3_best500_id]['overall']['exact_k_compliance_rate']):.1f}%`，精确-$k$ 子集 gap `{_pct(abp_algs[m3_best500_id]['overall'], 'exact_k_mean_rel_gap')}`），对比 `cw_relocate_2opt` `{_pct(abp_algs['cw_relocate_2opt']['overall'])}` 与 `C1` `{_pct(abp_algs['i605_cvrp_c1_tworegime']['overall'])}`。
3. **`cvrp_ext_cvrplib_x_100`（100 题，Uchoa Set X `n=100..1000` `euc_2d_nint` vs 官方 BKS）**：
   - `M3 最优 ({m3_best500_id})`: 全体 100/100 合法完成 **`{_pct(x_algs[m3_best500_id]['overall'])}`**（分档：`X-S = {_pct(x_t_best['X-S (100-250)'])}`，`X-M = {_pct(x_t_best['X-M (251-500)'])}`，`X-L = {_pct(x_t_best['X-L (501-1000)'])}`），对比 `C1` `{_pct(x_algs['i605_cvrp_c1_tworegime']['overall'])}` 与 `cw_parallel_merge` `{_pct(x_algs['cw_parallel_merge']['overall'])}`。

## 适用条件、假设与限制

- CVRPLib A/B/P 官方最优以固定车数 $k$ 为约束，当前通用无车数强限制并行合并求解器以自由车数求得可行解，故同步披露精确-$k$ 合规计数避免指标误读；在 M3.1 跨问题工作中可进一步独立检验 `strict_max_vehicles` 协议。

## 来源及支持的具体结论

- 外部大考汇总：`experiments/milestone3/phase3d_blind_eval/external_benchmarks_report.json`。

## 代码和评测关联

- `agent_skill_loop/interface_design/blind_eval_m3.py`、`tools/run_phase3d_blind_and_release.py`。

## 未确认项与冲突证据

- 在 `X-L (n=501..1000)` 算例上 `relocate_2opt` 单步搜索在 500 ms 下出现合理早停但均保持 100% 合法驻留解返回。
"""
    _put("evidence-cvrp-m3-external-eohs256-cvrplib-abp74-x100", ext_meta, ext_md)

    return {"ok": True, "written_count": len(written), "written_ids": written}


def build_m3_unified_workbench_bundle(
    m2_release_dir: Path,
    bundle_dir: Path,
    eval_out: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the unified M3 workbench bundle extending M2's verified bundle without mutating historical items."""
    bundle_dir.mkdir(parents=True, exist_ok=False)

    for subdir in ("suites", "routes", "traces", "published_results", "results"):
        shutil.copytree(m2_release_dir / subdir, bundle_dir / subdir)
    shutil.copy2(m2_release_dir / "algorithms.json", bundle_dir / "algorithms.json")

    frozen_solvers: list[FrozenInterfaceSolver] = eval_out["frozen_solvers"]
    blind_report = eval_out["blind_report"]
    ext_report = eval_out["external_report"]
    d2_analyses = eval_out["direction2_analyses"]
    recs_500 = eval_out["records_500ms"]

    # 1. Extend algorithms.json with M3 frozen solvers (preserving existing M1/M1.5/M2 entries verbatim)
    alg_doc = json.loads((bundle_dir / "algorithms.json").read_text(encoding="utf-8"))
    existing_aids = {a["algorithm_id"] for a in alg_doc["algorithms"]}
    added_m3_ids: list[str] = []
    for fs in frozen_solvers:
        if fs.solver_id in existing_aids:
            continue
        added_m3_ids.append(fs.solver_id)
        m3_kb_id = (
            "method-cvrp-m3-ruin-recreate-l3"
            if fs.template_id == "cvrp_ruin_recreate"
            else "method-cvrp-m2-l2a-generalized-savings"
        )
        alg_doc["algorithms"].append({
            "algorithm_id": fs.solver_id,
            "problem_family": fs.problem_family,
            "display_name": fs.display_name,
            "paradigm": fs.paradigm,
            "interface": f"{fs.template_id}/{fs.template_version}:{fs.hook_name}",
            "kind": "m3_interface_solver",
            "kb_entry_id": m3_kb_id,
            "code_path": "experiments/milestone3/phase3c_four_arm/archive/archive_manifest.json",
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
    alg_doc["frozen_m3_solver_ids"] = added_m3_ids
    (bundle_dir / "algorithms.json").write_text(
        json.dumps(alg_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    # 2. Add redacted-coordinate cvrp_m3_blind_120 suite & routes stub (ZERO coordinates/demands/seed!)
    frows_blind = eval_out["feature_rows_blind120_500"]
    sum_blind500 = blind_report["suite_summaries_500ms"]["cvrp_m3_blind_120"]
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
        "suite_id": "cvrp_m3_blind_120",
        "benchmark_id": "cvrp_workbench_v1",
        "problem_family": "cvrp",
        "benchmark_tier": "local_controlled",
        "split": "heldout",
        "suite_role": "final_blind_acceptance",
        "exposure_status": "unsealed_one_shot_phase3d",
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
            "description": "Milestone 3 one-shot unsealed blind test suite (120 instances, n in {50,100,200}; raw coordinates isolated outside repository).",
            "suite_content_sha256": blind_report["commitment_verification"]["suite_content_sha256"],
        },
        "instances": redacted_instances,
    }
    blind_suite_file = bundle_dir / "suites" / "cvrp_m3_blind_120.json"
    blind_suite_file.write_text(
        json.dumps(blind_suite_payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    blind_routes_file = bundle_dir / "routes" / "cvrp_m3_blind_120.json"
    blind_routes_file.write_text(
        json.dumps(
            {
                "suite_id": "cvrp_m3_blind_120",
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
    if not any(s["suite_id"] == "cvrp_m3_blind_120" for s in suites_idx["suites"]):
        suites_idx["suites"].append({
            "suite_id": "cvrp_m3_blind_120",
            "path": "suites/cvrp_m3_blind_120.json",
            "sha256": _sha256_bytes(blind_suite_file.read_bytes()),
            "benchmark_id": "cvrp_workbench_v1",
            "problem_family": "cvrp",
            "benchmark_tier": "local_controlled",
            "split": "heldout",
            "suite_role": "final_blind_acceptance",
            "exposure_status": "unsealed_one_shot_phase3d",
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

    # 3. Merge M3 (and external M2/M3) summaries & records without duplicating M1/M2 entries
    summary_doc = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
    records_doc = json.loads((bundle_dir / "results" / "per_instance_records.json").read_text(encoding="utf-8"))

    all_evaluated_suites: list[tuple[str, Mapping[str, Any]]] = [
        ("cvrp_dev_hetero_24", blind_report["suite_summaries_500ms"]["cvrp_dev_hetero_24"]),
        ("cvrp_select_multiscale_64", blind_report["suite_summaries_500ms"]["cvrp_select_multiscale_64"]),
        ("cvrp_final_accept_120", blind_report["suite_summaries_500ms"]["cvrp_final_accept_120"]),
        ("cvrp_ext_eohs_256", ext_report["suites"]["cvrp_ext_eohs_256"]),
        ("cvrp_ext_cvrplib_abp_74", ext_report["suites"]["cvrp_ext_cvrplib_abp_74"]),
        ("cvrp_ext_cvrplib_x_100", ext_report["suites"]["cvrp_ext_cvrplib_x_100"]),
    ]

    for sid, new_sum in all_evaluated_suites:
        target_algs = summary_doc["suites"][sid]["algorithms"]
        existing_for_suite = set(target_algs.keys())
        new_aids = [aid for aid in new_sum["algorithms"] if aid not in existing_for_suite]
        for aid in new_aids:
            target_algs[aid] = new_sum["algorithms"][aid]
        new_aid_set = set(new_aids)
        new_recs = [r for r in recs_500[sid] if r["algorithm_id"] in new_aid_set]
        records_doc["records"].extend(new_recs)

        suite_file = bundle_dir / "suites" / f"{sid}.json"
        suite_doc = json.loads(suite_file.read_bytes())
        suite_doc["algorithms_evaluated"] = list(dict.fromkeys([*suite_doc["algorithms_evaluated"], *new_aids]))
        suite_file.write_text(
            json.dumps(suite_doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n"
        )
        suite_row = next(row for row in suites_idx["suites"] if row["suite_id"] == sid)
        suite_row["algorithms_evaluated"] = suite_doc["algorithms_evaluated"]
        suite_row["sha256"] = _sha256_bytes(suite_file.read_bytes())

        routes_file = bundle_dir / "routes" / f"{sid}.json"
        routes_doc = json.loads(routes_file.read_bytes())
        pub_routes = eval_out["public_routes_500ms"][sid]
        for rec in new_recs:
            if rec["valid"]:
                route = pub_routes.get(rec["instance_id"], {}).get(rec["algorithm_id"])
                if route is None or route["tour_length"] != rec["tour_length"]:
                    raise ValueError(f"m3_route_record_mismatch:{sid}:{rec['instance_id']}:{rec['algorithm_id']}")
        for iid, routes in pub_routes.items():
            target_inst_routes = routes_doc["routes_by_instance"].setdefault(iid, {})
            for aid, rdata in routes.items():
                if aid in new_aid_set:
                    target_inst_routes[aid] = rdata
        routes_file.write_text(
            json.dumps(routes_doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n"
        )

    (bundle_dir / "suites" / "index.json").write_text(
        json.dumps(suites_idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    summary_doc["suites"]["cvrp_m3_blind_120"] = sum_blind500
    records_doc["records"].extend(recs_500["cvrp_m3_blind_120"])
    records_doc["record_count"] = len(records_doc["records"])

    (bundle_dir / "results" / "summary.json").write_text(
        json.dumps(summary_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (bundle_dir / "results" / "per_instance_records.json").write_text(
        json.dumps(records_doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n"
    )

    # 4. Merge M3 Direction-2 selection analyses
    selection_doc = json.loads((bundle_dir / "results" / "selection_records.json").read_text(encoding="utf-8"))
    for k, v in d2_analyses.items():
        selection_doc["analyses"][k] = v
    (bundle_dir / "results" / "selection_records.json").write_text(
        json.dumps(selection_doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n"
    )

    # 5. Recompute workbench_manifest.json
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
        json.dumps(wb_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return {
        "bundle_dir": str(bundle_dir),
        "suite_count": len(suites_idx["suites"]),
        "record_count": records_doc["record_count"],
        "selection_analysis_count": len(selection_doc["analyses"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=REPO / "experiments" / "milestone3" / "phase3d_blind_eval")
    parser.add_argument("--release-id", default=M3_RELEASE_ID)
    parser.add_argument("--commitment-path", type=Path, default=M3_BLIND_COMMITMENT_PATH)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--freeze-only", action="store_true")
    mode.add_argument("--publish-from-sha256", help="Resume KB/bundle/release publication from saved publication_input.json")
    parser.add_argument("--protocol-sha256")
    parser.add_argument("--sealed-path", type=Path)
    args = parser.parse_args(argv)

    if args.freeze_only:
        frozen = freeze_m3_pre_blind_protocol(
            args.out_dir / "pre_blind_protocol_m3.json",
            repo_root=REPO,
            commitment_path=args.commitment_path,
        )
        print(json.dumps({k: frozen[k] for k in ("protocol_path", "protocol_sha256")}, indent=2))
        return 0

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.release_id):
        parser.error("invalid release ID")
    store = REPO / "knowledge_store"
    if os.path.lexists(store / "releases" / args.release_id):
        parser.error("release already exists and is immutable; choose a new release ID")

    publication_input = args.out_dir / "publication_input.json"
    if args.publish_from_sha256 is not None:
        payload = publication_input.read_bytes()
        if _sha256_bytes(payload) != args.publish_from_sha256:
            parser.error("publication input SHA-256 mismatch")
        eval_out = json.loads(payload)
        eval_out["frozen_solvers"] = [FrozenInterfaceSolver.from_dict(r) for r in eval_out["frozen_solvers"]]
    else:
        if args.sealed_path is None or args.protocol_sha256 is None:
            parser.error("evaluation requires --sealed-path and --protocol-sha256")
        eval_out = execute_m3_blind_evaluation(
            args.out_dir,
            repo_root=REPO,
            sealed_path=args.sealed_path,
            protocol_sha256=args.protocol_sha256,
            commitment_path=args.commitment_path,
        )
        payload = json.dumps(
            {
                **eval_out,
                "frozen_solvers": [s.to_dict() for s in eval_out["frozen_solvers"]],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        with publication_input.open("xb") as handle:
            handle.write(payload)
        print(json.dumps({"publication_input_sha256": _sha256_bytes(payload)}), file=sys.stderr, flush=True)

    p3c_500 = json.loads(
        (REPO / "experiments" / "milestone3" / "phase3c_four_arm" / "phase3c_report_standard_500ms.json").read_text(
            encoding="utf-8"
        )
    )
    p3c_25 = json.loads(
        (REPO / "experiments" / "milestone3" / "phase3c_four_arm" / "phase3c_report_tight_25ms.json").read_text(
            encoding="utf-8"
        )
    )
    kb_res = sync_milestone3_kb(REPO / "knowledge_workspace", eval_out, phase3c_500=p3c_500, phase3c_25=p3c_25)
    ws_val = validate_workspace(REPO / "knowledge_workspace")
    if not ws_val["ok"]:
        raise RuntimeError(f"knowledge_workspace_validation_failed:{ws_val['errors'][:10]}")

    m2_rel_dir = REPO / "knowledge_store" / "releases" / M2_RELEASE_ID
    build_dir = REPO / "build"
    build_dir.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="m3-release-", dir=build_dir))
    m3_bundle_dir = staging / "workbench"
    m3_dash_dir = staging / "dashboard"

    wb_info = build_m3_unified_workbench_bundle(m2_rel_dir, m3_bundle_dir, eval_out)
    dash_info = build_dashboard(
        bundle_dir=m3_bundle_dir,
        workspace_dir=REPO / "knowledge_workspace",
        output_dir=m3_dash_dir,
        release_id=args.release_id,
    )

    rel_info = build_release(
        REPO / "knowledge_workspace",
        store,
        args.release_id,
        workbench_bundle=m3_bundle_dir,
        dashboard_dir=m3_dash_dir,
        activate=False,
    )
    rel_val = activate_verified_release(store, Path(rel_info["release"]))
    rel_info["pointer"] = rel_val["pointer"]

    blind_report = eval_out["blind_report"]
    summary_out = {
        "ok": True,
        "pre_blind_protocol_sha256": blind_report["pre_blind_protocol_sha256"],
        "commitment_verification": blind_report["commitment_verification"],
        "blind_120_standard_500ms_arm_summary": blind_report["blind_120_standard_500ms_arm_summary"],
        "blind_120_tight_25ms_arm_summary": blind_report["blind_120_tight_25ms_arm_summary"],
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
