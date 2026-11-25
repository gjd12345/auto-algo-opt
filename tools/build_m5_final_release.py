"""Build Milestone 5 Stage 1 & 2 final immutable knowledge release (20261125-main-co-workbench-m5-final).

1. Synchronize 4 reviewed Stage 1 causal closure & M5 trajectory-control knowledge cards
   and 1 source record into ``knowledge_workspace/`` (bringing total curated entries from 354 -> 358).
2. Validate ``knowledge_workspace/`` strictly via ``knowledge_tools.core.validate_workspace``.
3. Copy the immutable M4 workbench bundle cleanly (never modifying any prior release),
   rebuild offline ``dashboard.html`` with all 358 knowledge cards, publish new immutable
   release ``knowledge_store/releases/20261125-main-co-workbench-m5-final``, and atomically
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

M4_RELEASE_ID = "20261124-main-co-workbench-m4"
M5_RELEASE_ID = "20261125-main-co-workbench-m5-final"
M5_SOURCE_ID = "src-milestone5-stage1-causal-closure-20261125"


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
    rel_norm = rel_path.replace("\\", "/")
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--", rel_norm], cwd=REPO, text=True
        ).strip()
    except Exception:
        dirty = ""
    pin: dict[str, Any] = {
        "kind": "repo_code",
        "commit": "worktree" if dirty else commit,
        "path": rel_norm,
        "sha256": _sha256_bytes(full.read_bytes()),
    }
    if dirty:
        pin["worktree_base_commit"] = commit
    return pin


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
        "id": M5_SOURCE_ID,
        "title": (
            "Milestone 5 Trajectory Control Closure (21/21), Exp 1 Numerical Sandbox Causal Ablation, "
            "Exp 2 Dual-Timing & Pure 2x2 Multiscale Screening, and Exp 3 Unified-Base-KB Memory Retest"
        ),
        "authors": ["auto-algo-opt research log"],
        "year": 2026,
        "venue": (
            "Internal experimental audit & immutable release "
            "(experiments/milestone5_paratera/, milestone5_s1_sandbox_ablation/, "
            "milestone5_s2_multiscale/, milestone3_5_pure_kb_retest/, baselines_2026/)"
        ),
        "doi": None,
        "url": "https://github.com/gjd12345/auto-algo-opt/blob/main/experiments/milestone5_s2_multiscale/exp2c/s2_multiscale_ablation_report.md",
        "kind": "internal_experiment_report",
        "accessed_on": "2026-11-26",
        "availability": "local_repository",
        "license": "repository-internal research record",
        "selected": True,
        "selection_reason": (
            "Covers complete 21/21 M5 trajectory-control evaluation, Exp 1 30-cell (1,080-req) "
            "numerical sandbox single-variable causal ablation, Exp 2A dual-timing Track-3 audit, "
            "Exp 2B zero-leakage synthetic multiscale threshold lock validated on CVRPLIB Set X-100, "
            "Exp 2C 24-cell (2,400-req) pure 2x2 multiscale x early-stop ablation, and "
            "Exp 3 12-cell (432-req) unified-base-KB memory loop retest."
        ),
        "locator": (
            "experiments/milestone5_paratera/m5_trajectory_control_report.json; "
            "experiments/milestone5_s1_sandbox_ablation/s1_sandbox_ablation_report.json; "
            "experiments/milestone5_s2_multiscale/setx_validation.json; "
            "experiments/milestone5_s2_multiscale/exp2c/s2_multiscale_ablation_report.json; "
            "experiments/milestone3_5_pure_kb_retest/runs/m35_pure_kb_retest_report.json"
        ),
        "read_depth": "full_text_local",
        "notes": "All blind suites evaluated strictly one-shot against externally sealed custody suites; seeds never pooled.",
    }
    replaced = False
    for idx, item in enumerate(sources):
        if item.get("id") == M5_SOURCE_ID:
            sources[idx] = new_src
            replaced = True
            break
    if not replaced:
        sources.append(new_src)
    doc["sources"] = sources
    src_path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def sync_milestone5_kb(workspace_dir: Path) -> dict[str, Any]:
    commit = _head_short_commit()
    _ensure_source(workspace_dir)
    entries_dir = workspace_dir / "entries"
    written: list[str] = []

    def _put(entry_id: str, meta: dict[str, Any], md: str) -> None:
        _write_entry(entries_dir, entry_id, meta, md)
        written.append(entry_id)

    # 1. Exp 1: Numerical sandbox single-variable causal ablation
    s1_meta = {
        "type": "evidence",
        "title": "里程碑 5 攻关一：自编数值沙箱严格单变量因果消融（双模型 5 种子 1,080 请求 + Blind-120 / Set X）",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": [
            "cvrp",
            "milestone-5",
            "causal-ablation",
            "numerical-sandbox",
            "stagnation-diagnosis",
            "cvrp_s1_sandbox_blind_120",
        ],
        "status": "reviewed",
        "summary": (
            "固定接口集合、提示材料、统一基础知识库与 36 请求预算，仅改变停滞后必做诊断动作完成 3 臂 × 2 模型 × 5 种子 = 30 格（1,080 请求）："
            "DeepSeek-V4.1-Flash 三臂在 cvrp_s1_sandbox_blind_120 均达 100.0% 完赛（加罚均值 24.8747–24.9243）；"
            "Qwen4-Max 显现强烈因果差异，自由工具 arm_s1_0 完赛率仅 60.0%（加罚 43.8948, SD=10.6765），"
            "仅切片诊断 arm_s1_1 升至 80.0%（34.3668, SD=13.0595），"
            "强制自编数值沙箱 arm_s1_2 达 100.0% 完赛与 24.8900±0.0719 极低方差；"
            "独立 Set X-100 上 Qwen 完赛率由 23.0% -> 59.0% -> 96.6%（加罚 114,164.12 -> 69,889.96），"
            "同时如实披露 10 路 sandbox_only 中共记录 14 份脚本、2 次成功校验与 6 次因达到 outer_step_cap（round_diagnostic_blocks=0）触发的门禁绕过。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "ruin_and_recreate",
            "complexity_class": "empirical",
            "interface": "score_ruin_nodes",
            "applicable_regimes": {
                "strong_on": [
                    "cross_model_variance_compression",
                    "qwen4_max_stagnation_recovery",
                    "large_scale_set_x_stability",
                ],
                "weak_on": [
                    "outer_step_cap_gate_bypass_under_tight_round_limits",
                ],
                "scale_notes": "双模型 5 种子独立配对评测，严格分种子列报 Holm-Bonferroni p 值与跨种子样本标准差，绝不混池。",
            },
            "artifact_refs": [
                _pin("tools/run_s1_sandbox_ablation.py", commit),
                _pin("research_agent/tools/math_sandbox.py", commit),
                _pin("tests/test_s1_sandbox_ablation.py", commit),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-research-agent-m3-autonomous-loop", "method-cvrp-m3-ruin-recreate-l3"],
            "sources": [M5_SOURCE_ID],
        },
        "source_refs": [M5_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/milestone5_s1_sandbox_ablation/s1_sandbox_ablation_report.json",
            "report:experiments/milestone5_s1_sandbox_ablation/s1_locked_script_audit.json",
        ],
        "code_refs": [],
    }
    s1_md = """# 里程碑 5 攻关一：自编数值沙箱严格单变量因果消融

本卡片记录在固定接口集合、提示材料、统一静态基础知识库与 `36` 请求上限下，对停滞诊断动作执行单变量因果消融（30 格 = 1,080 物理请求）的实证结论与审计留痕。

## 定义或方法步骤

1. **三臂单变量设计**：`arm_s1_0_free_tool`（自由工具提示）、`arm_s1_1_slice_only`（仅切片诊断）、`arm_s1_2_sandbox_only`（强制执行自编数值 `.py` 沙箱诊断脚本）。
2. **`cvrp_s1_sandbox_blind_120`（`free_fleet`, 5 种子均值 ± 跨种子 SD）**：
   - `DeepSeek-V4.1-Flash`：`arm0 = 24.8747 ± 0.0624`（`100.0%`）、`arm1 = 24.9243 ± 0.0551`（`100.0%`）、`arm2 = 24.8924 ± 0.0703`（`100.0%`）。
   - `Qwen4-Max`：`arm0 = 43.8948 ± 10.6765`（完赛 **`60.0%`**）、`arm1 = 34.3668 ± 13.0595`（完赛 **`80.0%`**）、`arm2 = 24.8900 ± 0.0719`（完赛 **`100.0%`**）。
3. **外部标准库泛化（`free_fleet`, 5 种子）**：
   - `ABP-74`：DeepSeek 三臂 `100.0%`（`907.8595–909.6973`）；Qwen `98.92% -> 99.73% -> 100.0%`（`909.2892 -> 905.9730 -> 907.4081`，SD 降至 `2.1253`）。
   - `Set X-100`：DeepSeek `97.2% / 99.0% / 98.2%`；Qwen 由 `23.0%`（`114,164.12 ± 23,660.07`）与 `59.0%`（`92,827.90 ± 29,272.61`）提升至 **`96.6%`**（`69,889.96 ± 3,293.02`）。

## 适用条件、假设与限制

- **防空壳审计透明披露**：10 路 `arm_s1_2_sandbox_only` 留存 14 份脚本，成功通过非空数值校验 `2` 次、记录 `gate_bypass_count = 6`（全部事件原因为 `reason = outer_step_cap`、`round_diagnostic_blocks = 0`，因外层轮次预算到顶退出而触发，而非两次停滞拦截放行）。

## 来源及支持的具体结论

- `experiments/milestone5_s1_sandbox_ablation/s1_sandbox_ablation_report.json`、`s1_locked_script_audit.json`。

## 代码和评测关联

- `tools/run_s1_sandbox_ablation.py`、`research_agent/tools/math_sandbox.py`、`tests/test_s1_sandbox_ablation.py`。

## 未确认项与冲突证据

- DeepSeek 基座本身稳定在 100% 完赛平台期，沙箱因果收益主要体现在高异质弱模型家族（Qwen4-Max）崩溃风险消除与跨种子方差收窄。
"""
    _put("evidence-m5-s1-sandbox-causal-ablation-20261125", s1_meta, s1_md)

    # 2. Exp 2: Dual timing + multiscale threshold lock + pure 2x2 factorial ablation
    s2_meta = {
        "type": "evidence",
        "title": "里程碑 5 攻关二：双计时口径统一（Track 3）、零泄露多尺度锁阈与纯净 2×2 消融（2,400 请求）",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": [
            "cvrp",
            "milestone-5",
            "dual-timing",
            "multiscale-screening",
            "factorial-ablation",
            "cvrplib-set-x",
        ],
        "status": "reviewed",
        "summary": (
            "统一列报 feasible_before_deadline 与 returned_before_deadline 双计时口径及 preprocess/solve/verify 边界："
            "(1) Track 3 重校显示 PyVRP 在 EoH-S-256 与 Set X-100 上 feasible=100% 但严格按时返回 returned=0.0%；"
            "(2) 严格仅用合成 N=100/200/400/500 锁定阈值（max_ratio_200_100=8.0, n200_abs_cap_ms=50.5964, min_t200_trigger_ms=10.0），"
            "在零泄露 Set X-100（4,700 对，free_fleet）上对超时逃逸拦截召回达 88.60%（785/886）、误杀率仅 3.02%（115/3,814）；"
            "(3) 统一白名单下完成 2×2 在线因子消融（24 格 = 2,400 请求），"
            "Qwen4-Max 在 Set X-100 严格 returned_before_deadline 口径由 arm_s2_00 的 41.3%（104,687.57±31,251.52）与 arm_s2_01 的 43.3%（104,193.37±30,865.06）"
            "跃升至开启多尺度筛查后的 98.7%（67,809.34±1,875.02 与 67,940.49±1,317.77，penalized_2x 下 3 种子 multiscale_main 原始 p<=4.15e-16、报告舍入 p_holm=0；共同完赛交集 n=16/10/18 下均长差 +386.09/+265.05/+201.06，p_holm=0.4126/1.0/1.0），"
            "且在 blind_120 由 84.2%/90.8% 恢复至 100.0%（120/120）。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "ruin_and_recreate",
            "complexity_class": "empirical",
            "interface": "score_ruin_nodes",
            "applicable_regimes": {
                "strong_on": [
                    "strict_returned_before_deadline_enforcement",
                    "large_scale_timeout_interception_n200_to_n1000",
                    "synthetic_only_threshold_calibration",
                ],
                "weak_on": [
                    "feasible_only_deadline_reporting_masks_timeouts",
                ],
                "scale_notes": "Set X-100 分尺段拦截召回：100-200=100.0%，201-400=100.0%，401-600=96.15%，601-800=80.58%，801-1000=56.13%。",
            },
            "artifact_refs": [
                _pin("tools/s2_multiscale_calibration.py", commit),
                _pin("tools/run_s2_multiscale_ablation.py", commit),
                _pin("tools/run_external_baselines_2026.py", commit),
                _pin("tests/test_s2_timing_and_calibration.py", commit),
                _pin("tests/test_s2_multiscale_ablation.py", commit),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp", "problem-lit-cvrp-large"],
            "methods": ["method-cvrp-m3-ruin-recreate-l3", "method-research-agent-m3-autonomous-loop"],
            "sources": [M5_SOURCE_ID],
        },
        "source_refs": [M5_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/baselines_2026/dual_timing_s20261124_b500.json",
            "report:experiments/baselines_2026/dual_timing_s20261124_b2000.json",
            "report:experiments/baselines_2026/dual_timing_s20261125_b500.json",
            "report:experiments/baselines_2026/dual_timing_s20261125_b2000.json",
            "report:experiments/baselines_2026/dual_timing_s20261126_b500.json",
            "report:experiments/baselines_2026/dual_timing_s20261126_b2000.json",
            "report:experiments/milestone5_s2_multiscale/multiscale_threshold_lock.json",
            "report:experiments/milestone5_s2_multiscale/setx_validation.json",
            "report:experiments/milestone5_s2_multiscale/exp2c/s2_multiscale_ablation_report.json",
        ],
        "code_refs": [],
    }
    s2_md = """# 里程碑 5 攻关二：双计时口径统一、零泄露多尺度锁阈与纯净 2×2 消融

本卡片汇总结构超时逃逸与时间语义混淆的三项递进实证（Exp 2A + 2B + 2C）。

## 定义或方法步骤

1. **Exp 2A：Track 3 双计时重校（`500 ms` 与 `2000 ms`, `free_fleet` 3 种子均值）**
   - 严格区分“截止前已产生可行解（`feasible_before_deadline`）”与“截止前已完成全流程并返回（`returned_before_deadline`）”，并拆解 `preprocess / solve / verify` 边界。
   - `PyVRP` 在 `cvrp_ext_eohs_256` 与 `Set X-100` 上 `feasible_before_deadline=1.0000` 但严格 `returned_before_deadline=0.0000`；`500 ms Set X` 下 `AutoFolio` 按时返回率 `0.3900`、`ReEvo` `0.1233`。
2. **Exp 2B：零泄露合成锁阈 + `Set X-100` 独立验证**
   - 仅用合成算例（`N=100, 200, 400, 500`, `Set X` 零触碰）锁定策略（`lock_sha256: e44cd57...`）：`floor_ms=1.0`、`min_t200_trigger_ms=10.0`、`max_ratio_200_100=8.0`、`n200_abs_cap_ms=50.5964`。
   - `Set X-100`（`free_fleet`, 4,700 对）：总拦截召回 **`88.60%` (`785/886`)**、误杀 **`3.02%` (`115/3,814`)**（`100–200` 与 `201–400` 均达 `100.0%`，`401–600` 达 `96.15%`）。`exact-k` 为 `89.24%` (`780/874`)、误杀 `1.66%` (`26/1,568`)。
3. **Exp 2C：统一白名单底座纯净 `2×2`（24 格 = 2,400 请求, `free_fleet` 3 种子）**
   - `DeepSeek-V4.1-Flash`：四臂在 `blind_120` 均达 **`100.0%`**（`24.57–24.66`），在 `Set X-100` 严格返回率达 `98.3%–99.3%`。
   - `Qwen4-Max`（揭示口径遮蔽现象）：在 `feasible_before_deadline` 下四臂均显示 `100.0%`，但在严格 `returned_before_deadline` 下：
     - `Set X-100`：`arm_s2_00` = **`41.3%`**（`104,687.57 ± 31,251.52`）、`arm_s2_01` = **`43.3%`**（`104,193.37 ± 30,865.06`） -> `arm_s2_10`（仅多尺度）= **`98.7%`**（`67,809.34 ± 1,875.02`）、`arm_s2_11`（联合）= **`98.7%`**（`67,940.49 ± 1,317.77`）；`penalized_2x` 口径 3 种子 `multiscale_main` 原始 `p<=4.15e-16`（报告舍入 `p_holm=0`），而 `common_completed` 小交集（`n=16, 10, 18`）均值差 `+386.09 / +265.05 / +201.06`（`p_holm=0.4126 / 1.0 / 1.0`），清晰印证增益主要源于高规模超时截断而非以弱胜强牺牲简单题。
     - `cvrp_s2_multiscale_blind_120`：`arm_s2_00 = 84.2% (32.14±8.53)`、`arm_s2_01 = 90.8% (29.20±5.85)` -> `arm_s2_10` 与 `arm_s2_11` 均达 **`100.0%`**（`24.57±0.09` 与 `24.57±0.06`）。

## 适用条件、假设与限制

- 多尺度筛查针对 `201–600` 客户超高阶复杂度膨胀截断极强；`801–1000`（`56.13%`）仍存在少量高常数因子但低增长率算子的长尾超时，需与运行期时间监控配合。

## 来源及支持的具体结论

- `experiments/baselines_2026/dual_timing_s*.json`、`experiments/milestone5_s2_multiscale/multiscale_threshold_lock.json`、`setx_validation.json`、`exp2c/s2_multiscale_ablation_report.json`。

## 代码和评测关联

- `tools/s2_multiscale_calibration.py`、`tools/run_s2_multiscale_ablation.py`、`tools/run_external_baselines_2026.py`、`tests/test_s2_timing_and_calibration.py`、`tests/test_s2_multiscale_ablation.py`。

## 未确认项与冲突证据

- 独立早停重分配在无多尺度筛查时的边际增益远小于多尺度复杂度闸门主效应。
"""
    _put("evidence-m5-s2-multiscale-dual-timing-ablation-20261125", s2_meta, s2_md)

    # 3. Exp 3: Unified-Base-KB Memory Loop Pure Retest
    m35_meta = {
        "type": "evidence",
        "title": "里程碑 3.5 攻关三：统一基础知识库同起点记忆闭环纯净重测（12 格 432 请求 + 双口径全集）",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": [
            "cvrp",
            "milestone-3.5",
            "memory-loop",
            "unified-base-kb",
            "common-completed",
            "penalized-2x",
        ],
        "status": "reviewed",
        "summary": (
            "基于 690a2c36 终审修补代码构建同起点四臂对照（所有臂挂载一致基础静态 KB 20261124-main-co-workbench-m4，12 格 = 432 请求）："
            "明确区分 online_writeback（arm1）、离线整理记忆读取 + 合并式 L3 KB 切换（无在线写回 arm2）与 full_closed_loop（arm3）。"
            "在独立评测集 cvrp_final_accept_120（120/120 全完赛）上 arm2 在 20261125 (-0.0764, p_holm=8.52e-5) 与 20261126 (-0.0441, p_holm=0.0109) 显著优于无记忆底座，"
            "在 ABP-74 全员 74/74 完赛且显著缩短 8.93–10.42 (约 1.0%–1.14%, p_holm<=4.71e-6)；"
            "在 Set X-100 共同完赛交集下记忆/L3 臂稳定领先 -246.92 至 -430.73 (p_holm<=0.00011412)，但在未完成 2x 加罚全集下因 3–5% 超时算例反向拉高加罚均值（69,627.50–71,920.36 vs 66,352.22），揭示了记忆提升局部质量时并发的复杂度膨胀风险。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "ruin_and_recreate",
            "complexity_class": "empirical",
            "interface": "score_ruin_nodes",
            "applicable_regimes": {
                "strong_on": [
                    "unified_base_kb_isolation",
                    "abp74_and_blind120_quality_gain",
                    "common_completed_setx_quality_gain",
                ],
                "weak_on": [
                    "unscreened_memory_complexity_bloat_on_set_x_penalized_2x",
                ],
                "scale_notes": "arm2 明确标注为“离线整理记忆读取 + 合并式 L3 KB 切换（无在线写回）”。",
            },
            "artifact_refs": [
                _pin("tools/run_m35_pure_kb_retest.py", commit),
                _pin("tools/m35_pure_kb_analysis.py", commit),
                _pin("tests/test_m35_pure_kb_retest.py", commit),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-research-agent-m3-autonomous-loop", "method-cvrp-m3-ruin-recreate-l3"],
            "sources": [M5_SOURCE_ID],
        },
        "source_refs": [M5_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/milestone3_5_pure_kb_retest/runs/m35_pure_kb_retest_report.json",
        ],
        "code_refs": [],
    }
    m35_md = """# 里程碑 3.5 攻关三：统一基础知识库同起点记忆闭环纯净重测

本卡片基于 `690a2c36` 修补后代码，报告统一基础静态 KB（`20261124-main-co-workbench-m4`）下的 4 臂 × 3 种子（432 请求）独立评测结论。

## 定义或方法步骤

1. **四臂同起点拆分**：
   - `arm_m35v2_0_base_kb_only`：仅基础静态 KB，记忆关闭；
   - `arm_m35v2_1_online_writeback`：仅开启在线策略血缘写回（`m35_l12`）；
   - `arm_m35v2_2_offline_l3_switch`：**离线整理记忆读取 + 合并式 L3 KB 切换（无在线写回）**；
   - `arm_m35v2_3_full_closed_loop`：全闭环（L3 切换 + 在线写回）。
2. **独立评测双口径结果（`free_fleet`, 3 种子 `20261124 / 20261125 / 20261126`）**：
   - **`cvrp_final_accept_120`（全数 `120/120` 完赛，`overall == common_completed`）**：底座 `24.3383`；`20261125` 种子下 `arm2` 降至 `24.2619`（`-0.0764`, `p_holm=8.52e-5`）、`arm3` 降至 `24.2583`（`-0.0799`, `p_holm=1.62e-4`）；`20261126` 种子下 `arm1` 降至 `24.2544`（`-0.0839`, `p_holm=6.95e-5`）、`arm2` 降至 `24.2942`（`p_holm=0.0109`）。
   - **`cvrp_ext_cvrplib_abp_74`（全数 `74/74` 完赛）**：底座 `914.6757`，有效触发种子下 `arm1/arm2/arm3` 达 `904.2568–905.7432`（`-8.93` 至 `-10.42`, `p_holm<=4.71e-6`）。
   - **`cvrp_ext_cvrplib_x_100`（双口径分化）**：在 `common_completed` 交集下（`n=95–97`），记忆/L3 臂稳定领先底座 `-246.92` 至 `-430.73`（`p_holm<=0.00011412`）；但在严格 `overall (penalized_2x)` 下，因 `3–5` 个超大型算例超时（`95–97/100` 完赛）拉高加罚均值（`69,627.50–71,920.36` vs `66,352.22`）。

## 适用条件、假设与限制

- `arm1` 仅在部分种子中产生超越静态默认阈值的候选，验证了探索随机性与记忆触发门槛的现实约束。

## 来源及支持的具体结论

- `experiments/milestone3_5_pure_kb_retest/runs/m35_pure_kb_retest_report.json`。

## 代码和评测关联

- `tools/run_m35_pure_kb_retest.py`、`tools/m35_pure_kb_analysis.py`、`tests/test_m35_pure_kb_retest.py`。

## 未确认项与冲突证据

- 需如攻关二所示与多尺度复杂度闸门协同使用，防止记忆引导生成的高复杂度算子在 `Set X` 超时。
"""
    _put("evidence-m35-pure-kb-memory-retest-20261125", m35_meta, m35_md)

    # 4. M5 21-run trajectory control closure
    m5_meta = {
        "type": "evidence",
        "title": "里程碑 5 21 路轨迹控制闭环全量实测收口证据（21/21 完备）",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": [
            "cvrp",
            "milestone-5",
            "trajectory-control",
            "21-run-closure",
            "paratera",
        ],
        "status": "reviewed",
        "summary": (
            "完成里程碑 5 全部 21 路在线搜索与盲测汇总（正式替代早期 13/21 中间态）："
            "DeepSeek-V4.1-Flash 三组（legacy_baseline_500ms / whitelist_latency_500ms / trajectory_ctrl_full_500ms，各 5 种子）在 Blind-120 均获 100.0% 完赛（加罚均值 24.6404 / 24.6472 / 24.6979）；"
            "Qwen4-Max 组 model2_legacy_500ms（3 种子）达 100.0%（24.6097），而未接入统一白名单+多尺度筛查的 model2_ctrl_full_500ms（3 种子）出现 6.67/120 超时（free_fleet 完赛 94.44%, 原始可行 24.4856, 加罚 27.2350；exact-k 完赛 63.89%, 原始可行 23.3435, 加罚 38.8252），直接驱动并促成第一阶段攻关一与攻关二的严格归因闭环。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "ruin_and_recreate",
            "complexity_class": "empirical",
            "interface": "score_ruin_nodes",
            "applicable_regimes": {
                "strong_on": ["deepseek_v41_flash_100pct_completion", "full_21_cell_matrix_audit"],
                "weak_on": ["legacy_unscreened_qwen_control_arm_without_multiscale_gate"],
                "scale_notes": "本条证据作为历史全量归档，与后续攻关一（1,080 请求）及攻关二纯净 2×2（2,400 请求）配合解读。",
            },
            "artifact_refs": [
                _pin("tools/run_m5_trajectory_control.py", commit),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp"],
            "methods": ["method-research-agent-m3-autonomous-loop", "method-cvrp-m3-ruin-recreate-l3"],
            "sources": [M5_SOURCE_ID],
        },
        "source_refs": [M5_SOURCE_ID],
        "evidence_refs": [
            "report:experiments/milestone5_paratera/m5_trajectory_control_report.json",
        ],
        "code_refs": [],
    }
    m5_md = """# 里程碑 5 21 路轨迹控制闭环全量实测收口证据（21/21 完备）

本卡片归档里程碑 5 全部 21 路轨迹控制矩阵（DeepSeek 3 臂 × 5 种子 + Qwen 2 臂 × 3 种子 = 21 路，取代此前 `13/21` 中间态标注）。

## 定义或方法步骤

1. **DeepSeek-V4.1-Flash（各 5 种子，Blind-120 `free_fleet`）**：`legacy_baseline_500ms = 24.6404 (100.0%)`、`whitelist_latency_500ms = 24.6472 (100.0%)`、`trajectory_ctrl_full_500ms = 24.6979 (100.0%)`。
2. **Qwen4-Max（各 3 种子，Blind-120）**：`model2_legacy_500ms` 在 `free_fleet` 达 `24.6097 (100.0%)`；`model2_ctrl_full_500ms` 原始可行均值更优（`free_fleet = 24.4856`、`exact-k = 23.3435`），但受高复杂度超时拖累（平均 `6.67/120` 超时），`free_fleet` 完赛 `94.44%`（加罚 `27.2350`）、严格 `exact-k` 完赛降至 `63.89%`（加罚 `38.8252`）。

## 适用条件、假设与限制

- M5 底座因 `legacy_baseline_500ms` 与 `ctrl` 之间混杂了白名单扩充与诊断门禁，故不可直接作单因子因果裁决；严格单因子分解已由攻关一（Exp 1）与攻关二（Exp 2B/2C）接棒完成。

## 来源及支持的具体结论

- `experiments/milestone5_paratera/m5_trajectory_control_report.json`。

## 代码和评测关联

- `tools/run_m5_trajectory_control.py`。

## 未确认项与冲突证据

- 全部 21/21 实测完备，相关缺陷均已在第一阶段攻关一与攻关二中剥离验证。
"""
    _put("evidence-m5-21run-trajectory-control-closure-20261125", m5_meta, m5_md)

    return {"written": written, "total_entries": len(list(entries_dir.glob("*.json")))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=M5_RELEASE_ID)
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.release_id):
        parser.error("invalid release ID")
    store = REPO / "knowledge_store"
    if os.path.lexists(store / "releases" / args.release_id):
        parser.error(f"release already exists and is immutable: {args.release_id}")

    workspace = REPO / "knowledge_workspace"
    kb_res = sync_milestone5_kb(workspace)
    ws_val = validate_workspace(workspace)
    if not ws_val["ok"]:
        raise RuntimeError(f"knowledge_workspace_validation_failed:{ws_val['errors'][:10]}")

    m4_rel = store / "releases" / M4_RELEASE_ID
    if not m4_rel.is_dir():
        raise FileNotFoundError(f"Prior immutable M4 release missing: {m4_rel}")

    build_dir = REPO / "build"
    build_dir.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="m5-release-", dir=build_dir))
    wb_dir = staging / "workbench"
    dash_dir = staging / "dashboard"
    wb_dir.mkdir(parents=True, exist_ok=True)
    for dname in ("suites", "routes", "traces", "results", "published_results"):
        src_d = m4_rel / dname
        if src_d.is_dir():
            shutil.copytree(src_d, wb_dir / dname)
    for fname in ("algorithms.json", "workbench_manifest.json"):
        src_f = m4_rel / fname
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
    if rel_val.get("pointer") not in {"symlink", "git_symlink_text"}:
        raise RuntimeError(f"knowledge_store/current pointer degraded to {rel_val.get('pointer')!r}")
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
