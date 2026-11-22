"""Synchronize Milestone 1.5 knowledge cards (R4, Sweep/FI, island605 math families,
cross-domain hardcoded-capacity antipattern, and dual-track reproduction evidence).

Reads verified live metrics directly from:
  - ``build/workbench_m15_bundle/results/summary.json``
  - ``build/workbench_m15_bundle/results/selection_records.json``
  - ``experiments/milestone15/legacy_reproduction_605.json``
  - ``experiments/milestone15/workbench_screening_605.json``
and writes 16 UTF-8 LF cards with exact ``content_sha256`` and verified ``artifact_refs``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[1]
M15_BASE_COMMIT = "48134fc"


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


def _m15_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": "src-gillett-miller-1974-sweep",
            "title": "A Heuristic Algorithm for the Vehicle-Dispatch Problem",
            "authors": ["Billy E. Gillett", "Leland R. Miller"],
            "year": 1974,
            "venue": "Operations Research, 22(2), 340-349",
            "doi": "10.1287/opre.22.2.340",
            "url": "https://doi.org/10.1287/opre.22.2.340",
            "kind": "primary_article",
            "accessed_on": "2026-11-22",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and algorithmic summary only",
            "selected": True,
            "selection_reason": "Foundational Cartesian polar-angle Sweep algorithm for planar CVRP, implemented cleanly with multi-start rotation and 2-opt.",
            "locator": "agent_skill_loop/cvrp_workbench/solvers.py:solve_cvrp_sweep_2opt",
            "read_depth": "abstract",
            "notes": "Replaces defective HeurAgenix petal_algorithm_b384 which evaluated atan2(d[0,i], d[i,0]) == pi/4 on symmetric distance matrices.",
        },
        {
            "id": "src-island605-archive-20260630",
            "title": "auto-algo-opt June 2026 Three-Domain Island-Model Evolution Archive (605 Unique Programs)",
            "authors": ["auto-algo-opt research log"],
            "year": 2026,
            "venue": "Internal immutable archive (experiments/island605_archive)",
            "doi": None,
            "url": "https://github.com/gjd12345/auto-algo-opt/blob/main/experiments/island605_archive/README.md",
            "kind": "internal_experiment_report",
            "accessed_on": "2026-11-22",
            "availability": "local_repository",
            "license": "repository-internal research record",
            "selected": True,
            "selection_reason": "Complete AST-valid archive of 605 unique island-evolved rules (CVRP 207, TSP 206, BP 192) across 52 island runs.",
            "locator": "experiments/island605_archive/rules/all/manifest.json",
            "read_depth": "full_text_local",
            "notes": "Reproduced 604/605 under exact legacy June protocols (BP #61 differs by 0.000401 due to len(bins) cosine kernel) and screened under unified workbench.",
        },
        {
            "id": "src-milestone15-reproduction-20261122",
            "title": "Milestone 1.5 Historical Run Deduplication, Dual-Track Reproduction, and Mathematical Abstraction Audit",
            "authors": ["auto-algo-opt research log"],
            "year": 2026,
            "venue": "Internal experimental audit (experiments/milestone15/)",
            "doi": None,
            "url": "https://github.com/gjd12345/auto-algo-opt/blob/main/docs/RUN_INVENTORY_20261122.md",
            "kind": "internal_experiment_report",
            "accessed_on": "2026-11-22",
            "availability": "local_repository",
            "license": "repository-internal research record",
            "selected": True,
            "selection_reason": "Two-deliverable reproduction ledger separating exact legacy protocol checks from unified workbench evaluation, true runtime early-return census, and R4/Sweep/island605 integration.",
            "locator": "experiments/milestone15/legacy_reproduction_605.json; experiments/milestone15/workbench_screening_605.json; experiments/milestone15/run_inventory_deduped.json",
            "read_depth": "full_text_local",
            "notes": "Zero peeking at cvrp_final_accept_120 during candidate selection; explicitly discloses final_accept_120 Milestone-1 publication history (2,040 baseline records) and tsp_ext_eohs_128 screening role.",
        },
    ]


def _alg_stat(summary: Mapping[str, Any], suite_id: str, alg_id: str, field: str, scope: str = "overall") -> Any:
    return summary["suites"][suite_id]["algorithms"][alg_id][scope].get(field)


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "N/A"
    return f"{float(v) * 100:+.2f}%"


def _fmt_num(v: Any, d: int = 4) -> str:
    if v is None:
        return "N/A"
    return f"{float(v):.{d}f}"


def _binding(suite_id: str, alg_id: str, metric: str, value: Any, note: str, run_id: str = "milestone15_unified_500ms") -> dict[str, Any]:
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


def _make_method_card(
    *,
    entry_id: str,
    title: str,
    family: str,
    variant: str,
    variant_note: str | None,
    paradigm: str,
    interface: str,
    complexity: str,
    eoh_status: str,
    adapter_kind: str,
    summary_text: str,
    tags: list[str],
    tier: str,
    strong_on: list[str],
    weak_on: list[str],
    scale_notes: str,
    blueprint: dict[str, Any],
    math_formulation: list[dict[str, Any]],
    artifact_refs: list[dict[str, Any]],
    evidence_bindings: list[dict[str, Any]],
    rel_problems: list[str],
    rel_methods: list[str],
    source_refs: list[str],
    evidence_refs: list[str],
    md_lead: str,
    md_steps: str,
    md_limits: str,
    md_sources: str,
    md_code: str,
    md_open: str,
    md_eoh: str | None = None,
) -> tuple[dict[str, Any], str]:
    attrs: dict[str, Any] = {
        "method_family": paradigm,
        "online_offline": "online" if family == "online_bin_packing" else "offline",
        "interface": interface,
        "eoh_map": {
            "status": eoh_status,
            "adapter_kind": adapter_kind,
            "entrypoint": interface,
        },
        "knowledge_tier": tier,
        "problem_variant": variant,
        "paradigm": paradigm,
        "complexity_class": complexity,
        "applicable_regimes": {
            "strong_on": strong_on,
            "weak_on": weak_on,
            "scale_notes": scale_notes,
        },
        "interface_blueprint": blueprint,
        "math_formulation": math_formulation,
        "artifact_refs": artifact_refs,
        "evidence_bindings": evidence_bindings,
    }
    if variant != "standard_cvrp" and variant_note:
        attrs["variant_adaptation_note"] = variant_note

    meta = {
        "type": "method",
        "title": title,
        "category": "method",
        "problem_family": family,
        "tags": tags,
        "status": "reviewed",
        "summary": summary_text,
        "attributes": attrs,
        "relations": {
            "problems": rel_problems,
            "methods": rel_methods,
            "sources": source_refs,
        },
        "source_refs": source_refs,
        "evidence_refs": evidence_refs,
        "code_refs": [],
    }
    sections = [
        f"# {title}",
        "",
        md_lead.strip(),
        "",
        "## 定义或方法步骤",
        "",
        md_steps.strip(),
        "",
        "## 适用条件、假设与限制",
        "",
        md_limits.strip(),
        "",
        "## 来源及支持的具体结论",
        "",
        md_sources.strip(),
        "",
        "## 代码和评测关联",
        "",
        md_code.strip(),
        "",
        "## 未确认项与冲突证据",
        "",
        md_open.strip(),
    ]
    if eoh_status == "possible":
        sections.extend(["", "## EoH 适配", "", (md_eoh or f"直接通过 `{interface}` 入口接入 EoH 进化骨架，无需改写底层评测契约。").strip()])
    return meta, "\n".join(sections) + "\n"


def sync_milestone15_kb(workspace_dir: Path, bundle_dir: Path) -> dict[str, Any]:
    entries_dir = workspace_dir / "entries"
    sources_path = workspace_dir / "sources.json"
    summary = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
    selection = json.loads((bundle_dir / "results" / "selection_records.json").read_text(encoding="utf-8"))
    leg = json.loads((REPO / "experiments" / "milestone15" / "legacy_reproduction_605.json").read_text(encoding="utf-8"))
    scr = json.loads((REPO / "experiments" / "milestone15" / "workbench_screening_605.json").read_text(encoding="utf-8"))

    # 1. Upsert Milestone 1.5 sources idempotently
    sources_doc = json.loads(sources_path.read_text(encoding="utf-8"))
    existing_by_id = {s["id"]: i for i, s in enumerate(sources_doc["sources"])}
    for src in _m15_sources():
        if src["id"] in existing_by_id:
            sources_doc["sources"][existing_by_id[src["id"]]] = src
        else:
            sources_doc["sources"].append(src)
    sources_path.write_bytes((json.dumps(sources_doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    written: list[str] = []

    def _put(eid: str, meta: dict[str, Any], md: str) -> None:
        _write_entry(entries_dir, eid, meta, md)
        written.append(eid)

    # Helper to pin repo file tracked at M15_BASE_COMMIT
    def _pin(rel: str) -> dict[str, Any]:
        p = REPO / rel
        return {"kind": "repo_code", "commit": M15_BASE_COMMIT, "path": rel, "sha256": _sha256_file_lf(p)}

    r4_audit = leg["s2_r4_cos_audit"]
    # ------------------------------------------------------------------
    # 1. CVRP R4 (s2_r4_cos)
    # ------------------------------------------------------------------
    r4_rel = "experiments/cvrp_midterm/runs/s2_autonomous_math_r8/rounds/round_0004/eoh_run/skills/candidate_1/code.py"
    r4_fa = _alg_stat(summary, "cvrp_final_accept_120", "s2_r4_cos", "mean_tour_length")
    r4_abp_gap = _alg_stat(summary, "cvrp_ext_cvrplib_abp_74", "s2_r4_cos", "mean_rel_gap")
    r4_eohs_gap = _alg_stat(summary, "cvrp_ext_eohs_256", "s2_r4_cos", "mean_rel_gap")
    r4_x_gap = _alg_stat(summary, "cvrp_ext_cvrplib_x_100", "s2_r4_cos", "mean_rel_gap", "common_completed")
    meta, md = _make_method_card(
        entry_id="method-cvrp-s2-r4-cos",
        title="CVRP 两阶段出发与余弦角相干互补规则 (R4 / s2_r4_cos)",
        family="cvrp",
        variant="standard_cvrp",
        variant_note=None,
        paradigm="sequential_construct",
        interface="select_next_node",
        complexity="O(n^2)",
        eoh_status="possible",
        adapter_kind="direct_entrypoint",
        summary_text=(
            f"阶段二第 4 轮产出的尺度不变互补规则：结合两阶段剩余车队出发、常数径向项 alpha=0.75、三角伸长比 rho、"
            f"余弦定理射线角相干 cos(theta_0) 与陡峭容量自适应早返；共享 6 题 {r4_audit['shared6_mean']}（16 次早返），"
            f"select_64 上 22/64 胜 R5 并使 {{R5, R7}} 逐例理想最优降低 {r4_audit['select64_vbs_drop_pct']:.2f}%。"
        ),
        tags=["cvrp", "r4", "s2-r4-cos", "cosine-coherence", "complementary", "scale-invariant", "select_next_node"],
        tier="verified_experiment",
        strong_on=["complementary_to_r5_r7", "uniform_and_clustered", "scale_invariance_1e-3"],
        weak_on=["slightly_behind_r5_on_mean_p0_120", "vs_parallel_merge_and_local_search"],
        scale_notes=(
            f"共享 6 题均值 {r4_audit['shared6_mean']}（略优于 R5 的 10.2714），P0-120 为 {r4_audit['hist_p0_120_mean']}，"
            f"冻结后在 final_accept_120 均长 {_fmt_num(r4_fa)}；定位为与 R5/R7 强互补的算法选择候选。"
        ),
        blueprint={
            "skeleton_role": "单车顺序构造骨架，允许在可行客户非空时返回 0 主动早返仓",
            "evolvable_hook": "select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int",
            "state_maintained": ["current_node", "rest_capacity", "unvisited_nodes"],
            "invariants_and_constraints": ["全无量纲化评分（0.00% 坐标缩放漂移）", "仅在 current_node != depot 时触发主动早返"],
            "typical_pitfalls": ["中程保持常数 alpha=0.75，近满载阶段收口略弱于 R5 的状态内旋 alpha_eff"],
        },
        math_formulation=[
            {
                "expr": "score(i,j) = (d(i,j) - 0.75*d(0,j))/scale + 0.35*rho(i,j) - 0.10*fill(j) - 0.20*cos(theta_0)",
                "variables": {
                    "scale": "mean(d_dep) + mean(d_cur) + 1e-12",
                    "rho(i,j)": "d(i,j) / max(d(0,i)+d(0,j), 1e-12)",
                    "cos(theta_0)": "clip((d(0,j)^2 + d(0,i)^2 - d(i,j)^2)/(2*d(0,j)*d(0,i)), -1, 1)",
                },
                "preconditions": "中程步 current_node != depot；出发步按 rem_routes = sum(q)/rest_cap > 7 切换由外向内/紧致径向",
            }
        ],
        artifact_refs=[_pin(r4_rel)],
        evidence_bindings=[
            _binding("shared_diagnostic_6", "s2_r4_cos", "mean_tour_length", r4_audit["shared6_mean"], "共享 6 题 10.2078（16 次主动早返）"),
            _binding("cvrp_hist_p0_120", "s2_r4_cos", "mean_tour_length", r4_audit["hist_p0_120_mean"], "历史 P0-120 均值 19.8100"),
            _binding("cvrp_select_multiscale_64", "s2_r4_cos", "mean_tour_length", r4_audit["select64_r4_mean"], f"select_64 上 22/64 胜 R5，加入 {{R5,R7}} 降 VBS {r4_audit['select64_vbs_drop_pct']:.2f}%"),
            _binding("cvrp_final_accept_120", "s2_r4_cos", "mean_tour_length", r4_fa, "名单冻结后于 final_accept_120 统一验收"),
            _binding("cvrp_ext_eohs_256", "s2_r4_cos", "mean_rel_gap", r4_eohs_gap, f"EoH-S 256 例相对 LKH 差距 {_fmt_pct(r4_eohs_gap)}"),
            _binding("cvrp_ext_cvrplib_abp_74", "s2_r4_cos", "mean_rel_gap", r4_abp_gap, f"CVRPLib A/B/P 74 例相对 BKS 差距 {_fmt_pct(r4_abp_gap)}"),
            _binding("cvrp_ext_cvrplib_x_100", "s2_r4_cos", "common_completed_mean_rel_gap", r4_x_gap, f"Set X 共同完成交集差距 {_fmt_pct(r4_x_gap)}"),
        ],
        rel_problems=["problem-cvrp"],
        rel_methods=["method-cvrp-s2-r5-spiral", "method-cvrp-s2-r7-iso"],
        source_refs=["src-cvrp-midterm-20261121", "src-milestone15-reproduction-20261122"],
        evidence_refs=["report:experiments/milestone15/legacy_reproduction_605.json"],
        md_lead="R4（`s2_r4_cos`）是第二阶段自主数学分析第 4 轮验证 `H-006`（两阶段出发 + 余弦角花瓣相干）时生成的代表规则，此前代码留在原始轮次目录中未正式登记，现作为与 `R5 / R7` 互补的关键逐点构造候选入库。",
        md_steps=(
            "1. **出发步双阶段切换**：计算剩余需求估算车数 `rem_routes = sum(q) / rest_cap`；大于 7 时由外向内优先远端重货，否则切换为紧凑径向-载重种子。\n"
            "2. **中程几何与余弦角综合打分**：用 `scale = mean(d_dep) + mean(d_cur)` 消除尺度影响，线性组合径向节约（`alpha=0.75`）、三角伸长比 `0.35*rho`、载重填充 `-0.10*fill` 与余弦射线角相干 `-0.20*cos(theta_0)`。\n"
            "3. **容量自适应主动早返**：当最大可行需求超过 `0.55*rest_cap` 且最优候选归一化节约率 `1 - rho_best < 0.25 + 0.50*min(1, mean(q)/rest_cap)` 时主动返仓。"
        ),
        md_limits="中程采用固定 `alpha=0.75`，平均路程略逊于 R5 的状态内旋 `alpha_eff`，但在 64 题选优集上有 22/64 题反超 R5，最适合纳入多规则候选池而非单打独斗。",
        md_sources="原始轮次产物 `experiments/cvrp_midterm/runs/s2_autonomous_math_r8/rounds/round_0004/eoh_run/skills/candidate_1/code.py`；里程碑 1.5 复核见 `experiments/milestone15/legacy_reproduction_605.json`。",
        md_code="已注册至 `SOLVER_CATALOG['s2_r4_cos']`，支持前端路线对比与逐步早返轨迹回放。",
        md_open="与 `R5 / R7` 合并进 `POINTWISE_PLUS_M15_IDS` 后，其在全新未发布测试集上的折外选择器净收益仍待后续进一步验证。",
    )
    _put("method-cvrp-s2-r4-cos", meta, md)

    # ------------------------------------------------------------------
    # 2. CVRP True Cartesian Sweep + 2-opt (replacing defective HeurAgenix petal)
    # ------------------------------------------------------------------
    sw_abp = _alg_stat(summary, "cvrp_ext_cvrplib_abp_74", "cvrp_sweep_2opt", "mean_rel_gap")
    sw_eohs = _alg_stat(summary, "cvrp_ext_eohs_256", "cvrp_sweep_2opt", "mean_rel_gap")
    sw_fa = _alg_stat(summary, "cvrp_final_accept_120", "cvrp_sweep_2opt", "mean_tour_length")
    sw_x = _alg_stat(summary, "cvrp_ext_cvrplib_x_100", "cvrp_sweep_2opt", "mean_rel_gap", "common_completed")
    meta, md = _make_method_card(
        entry_id="method-cvrp-sweep-2opt",
        title="CVRP 真坐标极角扫描法 + 路内 2-opt (Gillett-Miller Sweep + 2-opt)",
        family="cvrp",
        variant="standard_cvrp",
        variant_note=None,
        paradigm="cluster_first",
        interface="solve_cvrp",
        complexity="O(n^2)",
        eoh_status="not_mappable",
        adapter_kind="full_route_skeleton",
        summary_text=(
            f"经典先聚类后路径的二维真坐标极角扫描算法（多起点正反旋转 + 路内 2-opt）；"
            f"显式修正了本机 HeurAgenix petal_algorithm_b384 在对称距离矩阵上将所有客户极角误算为 pi/4 的缺陷。"
            f"EoH-S 256 例差距 {_fmt_pct(sw_eohs)}，CVRPLib A/B/P 差距 {_fmt_pct(sw_abp)}。"
        ),
        tags=["cvrp", "sweep", "cluster-first", "2-opt", "classical-or", "petal-audit"],
        tier="local_implementation",
        strong_on=["central_depot", "planar_2d", "clustered_sectors", "scale_invariant"],
        weak_on=["eccentric_depot", "no_inter_route_relocate"],
        scale_notes="纯角度排序 + 比例缩放不变的 2-opt，具备 0.00% 坐标缩放漂移；在中心仓库平面算例上稳定优于单一逐点构造，落后于 CW+跨路线局部搜索。",
        blueprint={
            "skeleton_role": "按真实二维坐标极角 atan2(y_i-y_0, x_i-x_0) 排序，在最多 16 个均匀起点与正反两个方向中选出总路程最短的可行容量切片，再逐条路线运行 2-opt",
            "evolvable_hook": "angular_cluster_cut_score 与 intra_route_order_refiner",
            "state_maintained": ["polar_angles", "cluster_routes", "route_loads"],
            "invariants_and_constraints": ["必须使用真实二维坐标计算极角，严禁用对称距离矩阵 d[0,i]/d[i,0] 代替坐标差", "每条路线严格满足总需求 <= Q"],
            "typical_pitfalls": ["HeurAgenix petal_algorithm_b384 误写 atan2(d[0,i], d[i,0]) 导致对称矩阵上所有客户极角恒为 pi/4，退化为单客户首次适应追加"],
        },
        math_formulation=[
            {
                "expr": "theta_i = atan2(y_i - y_0, x_i - x_0),  i = 1..n",
                "variables": {"(x_0, y_0)": "仓库二维坐标", "(x_i, y_i)": "客户 i 二维坐标"},
                "preconditions": "二维欧氏平面 CVRP；按极角排序后顺/逆时针切分容量可行扇区并做路内 2-opt",
            }
        ],
        artifact_refs=[],
        evidence_bindings=[
            _binding("cvrp_ext_eohs_256", "cvrp_sweep_2opt", "mean_rel_gap", sw_eohs, f"EoH-S 256 例相对 LKH 差距 {_fmt_pct(sw_eohs)}"),
            _binding("cvrp_ext_cvrplib_abp_74", "cvrp_sweep_2opt", "mean_rel_gap", sw_abp, f"CVRPLib A/B/P 74 例相对 BKS 差距 {_fmt_pct(sw_abp)}"),
            _binding("cvrp_ext_cvrplib_x_100", "cvrp_sweep_2opt", "common_completed_mean_rel_gap", sw_x, f"Set X 共同完成交集差距 {_fmt_pct(sw_x)}"),
            _binding("cvrp_final_accept_120", "cvrp_sweep_2opt", "mean_tour_length", sw_fa, f"final_accept_120 均长 {_fmt_num(sw_fa)}"),
        ],
        rel_problems=["problem-cvrp"],
        rel_methods=["method-cvrp-petal-cluster-construct", "method-cvrp-intra-2opt"],
        source_refs=["src-gillett-miller-1974-sweep", "src-milestone15-reproduction-20261122"],
        evidence_refs=["code:agent_skill_loop/cvrp_workbench/solvers.py", "report:experiments/milestone15/legacy_reproduction_605.json"],
        md_lead="本条目实现了数学忠实的经典 Gillett–Miller 极角扫描法 + 路内 2-opt（`cvrp_sweep_2opt`），用于补齐“先聚类后路径”经典运筹对照，同时纠正了本机 HeurAgenix `petal_algorithm_b384` 的极角公式缺陷。",
        md_steps=(
            "1. **真实极角计算**：基于二维坐标计算每个客户相对仓库的极角 $\\theta_i = \\operatorname{atan2}(y_i-y_0, x_i-x_0)$。\n"
            "2. **多起点正反扫描聚类**：尝试最多 16 个均匀起始切口与顺/逆时针两个方向，按容量上限 $Q$ 顺序切分可行路线并保留总长最短的扇区划分。\n"
            "3. **路内 2-opt 精修**：对每条扇区路线运行有界 $O(1)$ 增量 2-opt，消除扇区内边交叉。"
        ),
        md_limits="依赖二维平面坐标（非纯距离矩阵输入）；当仓库严重偏心或扇区边界存在跨区最优解时，缺少路间节点搬移会限制最终质量。",
        md_sources="经典来源：Gillett & Miller (1974)；HeurAgenix `petal_algorithm_b384` 源码审计证实其在对称距离矩阵上将全部非重合客户极角算为 $\\pi/4$（见 `experiments/milestone15/legacy_reproduction_605.json`）。",
        md_code="实现于 `agent_skill_loop/cvrp_workbench/solvers.py:solve_cvrp_sweep_2opt`，注册为 `cvrp_sweep_2opt`。",
        md_open="后续里程碑二可在此基础上叠加 1-petal 最短路 DP 集合划分或路间 relocate，构建更强的聚类-划分基线。",
    )
    _put("method-cvrp-sweep-2opt", meta, md)

    # ------------------------------------------------------------------
    # 3. CVRP Classic Farthest Insertion
    # ------------------------------------------------------------------
    fi_abp = _alg_stat(summary, "cvrp_ext_cvrplib_abp_74", "cvrp_farthest_insertion", "mean_rel_gap")
    fi_eohs = _alg_stat(summary, "cvrp_ext_eohs_256", "cvrp_farthest_insertion", "mean_rel_gap")
    fi_fa = _alg_stat(summary, "cvrp_final_accept_120", "cvrp_farthest_insertion", "mean_tour_length")
    meta, md = _make_method_card(
        entry_id="method-cvrp-farthest-insertion",
        title="CVRP 经典最远客户最小代价插入法 (Farthest Insertion)",
        family="cvrp",
        variant="standard_cvrp",
        variant_note=None,
        paradigm="insertion",
        interface="solve_cvrp",
        complexity="O(n^2)",
        eoh_status="not_mappable",
        adapter_kind="full_route_skeleton",
        summary_text=(
            f"经典运筹学全局插入构造基线：按离仓库距离由远及近排序客户，逐个插入全车队容量可行且增量路程最小的位置（或新开路线）。"
            f"EoH-S 256 例差距 {_fmt_pct(fi_eohs)}，CVRPLib A/B/P 差距 {_fmt_pct(fi_abp)}。"
        ),
        tags=["cvrp", "farthest-insertion", "insertion", "classical-or", "solve_cvrp"],
        tier="local_implementation",
        strong_on=["global_insertion_baseline", "eccentric_customers", "scale_invariant"],
        weak_on=["no_post_local_search", "large_n_insertion_scan_cost"],
        scale_notes="纯距离增量比较，0.00% 坐标缩放漂移；作为不含 2-opt 的纯粹插入构造基线，与 HeurAgenix 最小代价插入+2-opt 形成清晰对照。",
        blueprint={
            "skeleton_role": "按 d(0,i) 降序遍历客户，扫描全车队所有容量可行插入切口 (prev, next)，取 argmin(d(prev,i)+d(i,next)-d(prev,next)) 与新开路线 2*d(0,i) 的较小者",
            "evolvable_hook": "insertion_priority(node, route, pos)",
            "state_maintained": ["routes", "route_loads", "uninserted_order"],
            "invariants_and_constraints": ["每条路线起止于仓库 0", "每次插入严格满足 load + q_i <= Q"],
            "typical_pitfalls": ["不含后续 2-opt/relocate 时，早期确定的路线骨架在末期可能出现次优交叉"],
        },
        math_formulation=[
            {
                "expr": "delta(r, pos, i) = d(prev, i) + d(i, next) - d(prev, next);  open_new = 2 * d(0, i)",
                "variables": {"prev, next": "路线 r 在位置 pos 的前后节点（边界为仓库 0）"},
                "preconditions": "客户按 d(0, i) 降序处理，仅考察 load(r) + q_i <= Q 的可行路线",
            }
        ],
        artifact_refs=[],
        evidence_bindings=[
            _binding("cvrp_ext_eohs_256", "cvrp_farthest_insertion", "mean_rel_gap", fi_eohs, f"EoH-S 256 例相对 LKH 差距 {_fmt_pct(fi_eohs)}"),
            _binding("cvrp_ext_cvrplib_abp_74", "cvrp_farthest_insertion", "mean_rel_gap", fi_abp, f"CVRPLib A/B/P 74 例相对 BKS 差距 {_fmt_pct(fi_abp)}"),
            _binding("cvrp_final_accept_120", "cvrp_farthest_insertion", "mean_tour_length", fi_fa, f"final_accept_120 均长 {_fmt_num(fi_fa)}"),
        ],
        rel_problems=["problem-cvrp"],
        rel_methods=["method-cvrp-cheapest-regret-insertion", "method-lit-ahd-heuragenix"],
        source_refs=["src-cvrp-workbench-20261121", "src-milestone15-reproduction-20261122"],
        evidence_refs=["code:agent_skill_loop/cvrp_workbench/solvers.py"],
        md_lead="经典仓库锚定最远插入构造器（`cvrp_farthest_insertion`），优先为边缘远点搭建多路线骨架，再把中近程客户低增量嵌入，是验证“单车顺序构造 vs 多车全局插入”范式差异的重要基线。",
        md_steps="1. 将所有客户按到仓库距离 $d(0, i)$ 降序排列。\n2. 对每个客户，计算插入所有容量可行路线各位置的精确边增量 $\\Delta$ 以及新开路线代价 $2 d(0, i)$。\n3. 执行全局最小增量操作，直到全部客户被覆盖。",
        md_limits="属于纯构造基线（未叠加坡度惩罚与 2-opt）；在大规模 $n \\ge 500$ 下嵌套遍历切口耗时随 $n^2$ 上升。",
        md_sources="经典运筹学插入构造基线，经里程碑 1.5 统一评测落盘于 `results/summary.json`。",
        md_code="实现于 `agent_skill_loop/cvrp_workbench/solvers.py:solve_cvrp_farthest_insertion`，注册为 `cvrp_farthest_insertion`。",
        md_open="后续可在里程碑二与 regret-k 排序及 2-opt 联用作为自主接口设计的候选骨架之一。",
    )
    _put("method-cvrp-farthest-insertion", meta, md)

    # ------------------------------------------------------------------
    # 4-7. Four mathematically verified island605 CVRP family cards
    # ------------------------------------------------------------------
    cvrp_i605_specs = [
        (
            "method-cvrp-i605-tworegime-savings",
            "i605_cvrp_c1_tworegime",
            "CVRP 岛屿流派一：两段容量切换节约 + 0.7 阈值主动早返 (Island605 C1)",
            "experiments/island605_archive/rules/all/cvrp/cvrp_000_E2_gen16_g16_r7__0028e678.py",
            1,
            "12.3564",
            "267",
            "当剩余载重较宽裕（rest_cap / (2*max_dem) > 0.4）时最大化经典逐点节约量，载重偏紧时切换为最近邻并在最近邻超过 0.7*d(cur,0) 时主动早返仓；0.00% 坐标缩放漂移。",
            "if i == 0: argmax d(0,j); elif rest_cap/(2*max_q) > 0.4: argmax (d(0,j)+d(0,i)-d(i,j)); else: nn if d(i,nn) < 0.7*d(i,0) else 0",
            "在 6 月独立进化的 207 条规则中旧题排名第 1，且在里程碑 1.5 现行工作台 92 题初筛上以 22.4722（select_64）在 49/64 题上战胜 R5，88 题实测触发 267 次真实主动早返仓，以 1.05 ms 极速验证了“出发远点 + 高载节约 + 低载几何早返”的简洁威力。",
        ),
        (
            "method-cvrp-i605-radial-early-return",
            "i605_cvrp_c8_radial_early",
            "CVRP 岛屿流派二：线性径向偏置 + 积极几何/低载主动早返 (Island605 C8)",
            "experiments/island605_archive/rules/all/cvrp/cvrp_007_E2_highgen_g8_r4__6103d27d.py",
            8,
            "12.5481",
            "700",
            "从仓库选最远点出发，中程以 d(i,j) - 0.3*d(0,j) 兼具近邻与远端优先，一旦到最优候选比回仓更远（d(i,0) < d(i,best)）或剩余容量低于 0.2*max_q 即积极主动早返仓；0.00% 缩放漂移。",
            "score(i,j) = d(i,j) - 0.3*d(0,j); return 0 iff d(i,0) < d(i,best) or rest_cap < 0.2*max_q",
            "88 题初筛实测触发高达 700 次真实主动早返仓（207 条中早返最积极的高分代表之一），select_64 均长 22.5822，清晰呈现“高频率早返减少回程绕路 vs 增加车次数”的权衡。",
        ),
        (
            "method-cvrp-i605-phase-noreturn",
            "i605_cvrp_c17_phase_noreturn",
            "CVRP 岛屿流派三：平均需求比两段切换（无主动早返消融对照，Island605 C17）",
            "experiments/island605_archive/rules/all/cvrp/cvrp_016_E2_highgen_g8_r2__f479a040.py",
            17,
            "12.6006",
            "0",
            "不含任何主动早返分支：仅以 rest_cap / mean(q_F) < 2.0 在最近邻与 min-max 归一化节约量 d(0,j)-d(i,j) 之间切换；88 题实测 0 次主动早返。",
            "if rest_cap / mean(q_F) < 2.0: argmin d(i,j); else: argmax norm(d(0,j) - d(i,j))",
            "作为严格不包含主动早返仓的纯净两阶段规则（88 题 0 次早返，select_64 = 22.7475），与 C1/C8 构成极佳的机理对照，证明两段容量切换本身已贡献核心收益，主动早返提供进一步收口增益。",
        ),
        (
            "method-cvrp-i605-relative-band-savings",
            "i605_cvrp_c22_band_savings",
            "CVRP 岛屿流派四：1.1× 相对近邻带节约 + 几何早返 (Island605 C22)",
            "experiments/island605_archive/rules/all/cvrp/cvrp_021_E2_highgen_g8_r35__c7e0a7ad.py",
            22,
            "12.6100",
            "211",
            "在最近邻 1.1 倍相对距离带宽内（d(i,j) <= 1.1*min_d）最大化节约量 d(0,j)-d(i,j)，并在 d(i,best) >= d(i,0) 时主动返仓；实现 0.00% 坐标缩放漂移。",
            "mask = (d(i,j) <= 1.1 * min d(i,u)); best = argmax_{j in mask} (d(0,j)-d(i,j)); return 0 if d(i,best) >= d(i,0)",
            "用无量纲相对带宽 1.1*min_d 天然规避了 Frozen C（H-001）混合绝对常数带宽导致的 +206.99% 尺度崩盘，88 题实测 211 次主动早返，是尺度不变带宽门控的正面教科书案例。",
        ),
    ]
    for eid, aid, title, rel, rk, arch_obj, er_cnt, summ, expr, lead in cvrp_i605_specs:
        s_sel64 = _alg_stat(summary, "cvrp_select_multiscale_64", aid, "mean_tour_length")
        s_fa = _alg_stat(summary, "cvrp_final_accept_120", aid, "mean_tour_length")
        s_p0 = _alg_stat(summary, "cvrp_hist_p0_120", aid, "mean_tour_length")
        s_eohs = _alg_stat(summary, "cvrp_ext_eohs_256", aid, "mean_rel_gap")
        s_abp = _alg_stat(summary, "cvrp_ext_cvrplib_abp_74", aid, "mean_rel_gap")
        s_x = _alg_stat(summary, "cvrp_ext_cvrplib_x_100", aid, "mean_rel_gap", "common_completed")
        meta, md = _make_method_card(
            entry_id=eid,
            title=title,
            family="cvrp",
            variant="standard_cvrp",
            variant_note=None,
            paradigm="sequential_construct",
            interface="select_next_node",
            complexity="O(n^2)",
            eoh_status="possible",
            adapter_kind="direct_entrypoint",
            summary_text=summ,
            tags=["cvrp", "island605", aid, "sequential-construct", "select_next_node"],
            tier="verified_experiment",
            strong_on=["fast_pointwise_construct", "multiscale_cvrp", "scale_invariance_verified"],
            weak_on=["vs_parallel_merge_and_local_search"],
            scale_notes=f"旧 6 月协议（16×n50 Q=40）精确复算 {arch_obj}；现行工作台 select_64={_fmt_num(s_sel64)}、冻结后 final_accept_120={_fmt_num(s_fa)}、EoH-S 256 差距 {_fmt_pct(s_eohs)}。",
            blueprint={
                "skeleton_role": "单车顺序构造骨架（与 EoH / 工作台 select_next_node 完全兼容）",
                "evolvable_hook": "select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int",
                "state_maintained": ["current_node", "rest_capacity", "unvisited_nodes"],
                "invariants_and_constraints": ["出发步与中程步显式解耦（独立印证 H-003）", "基于 88 题真实运行期追踪核验主动早返次数（非朴素代码关键字猜测）"],
                "typical_pitfalls": ["同批 207 条岛屿规则中有 34 条因混合 O(s) 与 O(1/s) 量纲存在缩尺漂移（最差 rank #61 达 +255.95%），入库前必须过缩尺压力测试"],
            },
            math_formulation=[
                {
                    "expr": expr,
                    "variables": {"d(0,j)": "仓库到客户 j 距离", "d(i,j)": "当前点 i 到客户 j 距离", "rest_cap": "当前剩余载重"},
                    "preconditions": "可行未访集合非空；所有代表规则均仅依据 dev_24 + select_64 筛选冻结",
                }
            ],
            artifact_refs=[_pin(rel)],
            evidence_bindings=[
                _binding("cvrp_select_multiscale_64", aid, "mean_tour_length", s_sel64, f"筛选集 select_64 均长 {_fmt_num(s_sel64)}（88 题实测主动早返 {er_cnt} 次）"),
                _binding("cvrp_hist_p0_120", aid, "mean_tour_length", s_p0, f"历史回归 P0-120 均长 {_fmt_num(s_p0)}"),
                _binding("cvrp_final_accept_120", aid, "mean_tour_length", s_fa, f"名单冻结后 final_accept_120 均长 {_fmt_num(s_fa)}"),
                _binding("cvrp_ext_eohs_256", aid, "mean_rel_gap", s_eohs, f"EoH-S 256 例相对 LKH 差距 {_fmt_pct(s_eohs)}"),
                _binding("cvrp_ext_cvrplib_abp_74", aid, "mean_rel_gap", s_abp, f"CVRPLib A/B/P 74 例相对 BKS 差距 {_fmt_pct(s_abp)}"),
                _binding("cvrp_ext_cvrplib_x_100", aid, "common_completed_mean_rel_gap", s_x, f"Set X 共同完成交集差距 {_fmt_pct(s_x)}"),
            ],
            rel_problems=["problem-cvrp"],
            rel_methods=["method-cvrp-s2-r5-spiral", "method-cvrp-savings-next-node"],
            source_refs=["src-island605-archive-20260630", "src-milestone15-reproduction-20261122"],
            evidence_refs=["report:experiments/milestone15/legacy_reproduction_605.json", "report:experiments/milestone15/workbench_screening_605.json"],
            md_lead=lead,
            md_steps=f"1. **数学公式**：`{expr}`。\n2. **旧协议复现**：在 6 月原题（16×n50 Q=40，seed=2024）上精确复算出归档成绩 `{arch_obj}`（旧协议精确 NN 基线 `13.6108`，README 旧注 `13.519`）。\n3. **统一工作台表现**：冻结后在全部 10 套 CVRP 考卷上统一分离测时复算完成。",
            md_limits="仍属单车逐点构造范式，在 CVRPLib A/B/P 与 Set X 上仍显著落后于并行 CW 合并与局部搜索；且在 Set A/B/P 上为自由车数求解，需同时查看精确-$k$ 合规率。",
            md_sources=f"原始归档程序：`{rel}`（6 月岛屿模型 CVRP 排名第 {rk}）；双轨复现记录：`experiments/milestone15/`。",
            md_code=f"已注册至 `SOLVER_CATALOG[{aid!r}]`，哈希与源码锚点已绑定。",
            md_open="后续方向二可进一步检验该规则并入多规则池后在不同规模与偏心度下的分工贡献。",
        )
        _put(eid, meta, md)

    # ------------------------------------------------------------------
    # 8-11. Four mathematically verified island605 TSP family cards
    # ------------------------------------------------------------------
    tsp_i605_specs = [
        (
            "method-tsp-i605-1step-rollout",
            "i605_tsp_t1_rollout",
            "TSP 岛屿流派一：一步贪心前瞻推演 Rollout / Pilot (Island605 T1, O(n^4))",
            "experiments/island605_archive/rules/all/tsp/tsp_000_E2_highgen_g8_r27__e80308da.py",
            1,
            "6.00393",
            "O(n^4)",
            "w_dir*d(i,u) + w_tour*NN_rollout(u->dest) - w_regret*(max-min) + 0.2*max(0, d-1.5*med)/med",
            "6 月岛屿模型 TSP 历史第 1 名：剩 m 个城市时对每个候选城市模拟完整最近邻后缀，单次选点最坏 O(m^3)、完整构造最坏 O(n^4)，叠加进度自适应权重与中位数归一化长边惩罚；在 500 ms 预算下仅完成部分中小实例，是“质量与完成率必须联合报告”的核心实证案例。",
        ),
        (
            "method-tsp-i605-mean-farness",
            "i605_tsp_t46_farness",
            "TSP 岛屿流派二：未访点平均孤立度牵引 (Island605 T46)",
            "experiments/island605_archive/rules/all/tsp/tsp_045_E2_highgen_g8_r5__29653b2e.py",
            46,
            "6.14821",
            "O(n^3)",
            "argmax_u ( -d(cur, u) + 0.7 * mean_{v in U\\{u}} d(u, v) )",
            "以极简公式平衡“走近点”与“先收容远离其余未访点的孤立城市”，在 EoH-S TSP 128 题（选优筛选集）上实现 128/128 满完成并取得全部满完成岛屿规则中的最优相对差距。",
        ),
        (
            "method-tsp-i605-dest-pull",
            "i605_tsp_t69_dest_regret",
            "TSP 岛屿流派三：极速向量化线性终点引力 (Island605 T69)",
            "experiments/island605_archive/rules/all/tsp/tsp_068_E2_highgen_g8_r7__d20ec2ca.py",
            69,
            "6.18904",
            "O(n^2)",
            "argmax_u ( 0.7 * (d(dest, u) - d(cur, u)) - 0.3 * d(cur, u) ) = argmax_u (0.7*d(dest,u) - d(cur,u))",
            "外表写作后悔值减插入代价，代数化简即为纯向量化线性终点引力 0.7*d(dest,u) - d(cur,u)；以亚毫秒级中位耗时（0.63 ms，快于 T46 约 40 倍）实现 128/128 满完成，构成 TSP 构造的速度–质量帕累托拐点。",
        ),
        (
            "method-tsp-i605-dimensionless-ratio",
            "i605_tsp_t81_norm_smooth",
            "TSP 岛屿流派四：无量纲最大归一化平滑度 (Island605 T81)",
            "experiments/island605_archive/rules/all/tsp/tsp_080_E2_highgen_g8_r12__6c1fc51c.py",
            81,
            "6.20007",
            "O(n^3)",
            "(1 - d(cur,u)/max_d) + 0.5*(avg_far(u)/max_far) + 0.2*I[d<0.3*max_d] - 0.1*I[d>0.7*max_d]",
            "全部特征均先除以当步最大值归一化，再辅以无量纲分段平滑奖励（<0.3 奖、>0.7 罚），天生对任意坐标尺度变换严格不变，128/128 满完成。",
        ),
    ]
    for eid, aid, title, rel, rk, arch_obj, comp, expr, lead in tsp_i605_specs:
        e128_ok = _alg_stat(summary, "tsp_ext_eohs_128", aid, "ok_count")
        e128_gap = _alg_stat(summary, "tsp_ext_eohs_128", aid, "mean_rel_gap")
        tsplib_ok = _alg_stat(summary, "tsp_ext_tsplib_euc2d", aid, "ok_count")
        tsplib_gap = _alg_stat(summary, "tsp_ext_tsplib_euc2d", aid, "mean_rel_gap")
        tsplib_cc = _alg_stat(summary, "tsp_ext_tsplib_euc2d", aid, "mean_rel_gap", "common_completed")
        meta, md = _make_method_card(
            entry_id=eid,
            title=title,
            family="tsp",
            variant="standard_tsp",
            variant_note="标准欧氏对称旅行商闭环构造（无容量与车队约束），直接复用 select_next_node(current, destination, unvisited, dist) 接口。",
            paradigm="sequential_construct",
            interface="select_next_node",
            complexity=comp,
            eoh_status="possible",
            adapter_kind="direct_entrypoint",
            summary_text=(
                f"{lead} EoH-S TSP 128（选优集）完成 {e128_ok}/128（差距 {_fmt_pct(e128_gap)}）；"
                f"外部标准库 TSPLIB 18 例完成 {tsplib_ok}/18（总差距 {_fmt_pct(tsplib_gap)}，共同交集差距 {_fmt_pct(tsplib_cc)}）。"
            ),
            tags=["tsp", "island605", aid, "sequential-construct", "select_next_node"],
            tier="verified_experiment",
            strong_on=["tsp_constructive_benchmark", "tsplib_external_validation"],
            weak_on=["o_n4_timeout_on_large_n" if aid == "i605_tsp_t1_rollout" else "vs_2opt_local_search"],
            scale_notes=(
                f"旧 6 月协议（8×n50 seed=2024）精确复算 {arch_obj}（旧精确 NN 基线 6.6079）；"
                f"注：tsp_ext_eohs_128 用于本次 206 条规则代表筛选，其 128 题成绩标为选优结果，外部泛化以 TSPLIB 18 例为准。"
            ),
            blueprint={
                "skeleton_role": "闭环 TSP 顺序构造骨架，从城市 0 出发逐步选择下一未访城市直至收环",
                "evolvable_hook": "select_next_node(current_node, destination_node, unvisited_nodes, distance_matrix) -> int",
                "state_maintained": ["current_node", "visited_mask", "tour"],
                "invariants_and_constraints": ["返回值必须属于 unvisited_nodes 且禁止原地重复", "受 500 ms 单实例预算约束，超预算记 timeout"],
                "typical_pitfalls": ["对每个候选模拟完整最近邻后缀导致单步 O(m^3)、全构造 O(n^4)，在 n>=100/TSPLIB 上极易触发 500 ms 超时，必须同时报告完成率"],
            },
            math_formulation=[{"expr": expr, "variables": {"d(cur,u)": "当前城市到候选 u 距离", "d(dest,u)": "候选 u 到终点 0 距离"}, "preconditions": "欧氏对称 TSP 距离矩阵"}],
            artifact_refs=[_pin(rel)],
            evidence_bindings=[
                _binding("tsp_ext_eohs_128", aid, "mean_rel_gap", e128_gap, f"[选优筛选集] EoH-S TSP 128 完成 {e128_ok}/128，相对 LKH 差距 {_fmt_pct(e128_gap)}"),
                _binding("tsp_ext_tsplib_euc2d", aid, "mean_rel_gap", tsplib_gap, f"[外部验证集] TSPLIB 18 例完成 {tsplib_ok}/18，相对 OPT 差距 {_fmt_pct(tsplib_gap)}"),
            ],
            rel_problems=["problem-tsp"],
            rel_methods=["method-tsp-nearest-neighbor-construct", "method-tsp-two-opt"],
            source_refs=["src-island605-archive-20260630", "src-milestone15-reproduction-20261122"],
            evidence_refs=["report:experiments/milestone15/legacy_reproduction_605.json", "report:experiments/milestone15/workbench_screening_605.json"],
            md_lead=lead,
            md_steps=f"1. **数学公式**：`{expr}`。\n2. **旧协议精确复现**：6 月原题（8×n50 seed=2024）精确复算 `{arch_obj}`（旧精确 NN 基线 `6.6079`，README 旧注 `6.56`）。\n3. **统一工作台评估**：在 `tsp_ext_eohs_128`（选优筛选集）与 `tsp_ext_tsplib_euc2d`（外部 OR 验证集）分别记录完成率、差距与耗时。",
            md_limits="单步构造不带 2-opt 路内重连，在 TSPLIB 上整体弱于 `tsp_nn_2opt`；同时 `tsp_ext_eohs_128` 已用于代表挑选，论文引用其成绩时须标注为选优结果。",
            md_sources=f"原始归档程序：`{rel}`（6 月岛屿模型 TSP 排名第 {rk}）；复现数据见 `experiments/milestone15/`。",
            md_code=f"已注册至 `TSP_SOLVER_CATALOG[{aid!r}]`，支持前端 TSP 榜单与路线对比。",
            md_open="对于 T1 一步前瞻推演，可在后续里程碑中通过限制候选前瞻近邻数 $K=15$ 将复杂度降至 $O(n^2 K)$ 以检验能否兼得高质量与 100% 完成率。",
        )
        _put(eid, meta, md)

    # ------------------------------------------------------------------
    # 12-14. Three positive island605 OBP family cards
    # ------------------------------------------------------------------
    obp_i605_specs = [
        (
            "method-obp-i605-exp-deadzone",
            "i605_obp_b1_exp_deadzone",
            "OBP 岛屿流派一：指数利用率 + 死区二次惩罚 (Island605 B1)",
            "experiments/island605_archive/rules/all/bp/bp_000_E2_highgen_g8_r27__6999b7b6.py",
            1,
            "0.00674",
            "exp(w / b) - I[0 < r < 2w] * (r - w)^2 / w,   r = b - w",
            "6 月岛屿模型装箱历史第 1 名：以指数利用率叠加残差死区二次惩罚，精确凑满（r=0）与对称配对（r=w）零惩罚，中间碎片残差受罚。同流控制消融证实：在完全相同的 5 条 Weibull-5000 流上，仅关闭主动开新箱就使 B1 从 0.006741 退化至 0.039038（+3.23pp，反落后于 B16 的 0.032196 与 B50 的 0.034309）；在相同 BPPLib 70 题上，允许主动开新箱更使 B1 暴涨至 +36.35%（仅评打开箱为 +10.80%）。",
        ),
        (
            "method-obp-i605-sqrt-close-bonus",
            "i605_obp_b50_sqrt_tier",
            "OBP 岛屿流派二：平方根利用率 + 85% 封箱阶跃奖励 (Island605 B50)",
            "experiments/island605_archive/rules/all/bp/bp_049_E2_highgen_g8_r5__08876e99.py",
            50,
            "0.02455",
            "sqrt(w / b) - 0.5*I[r < 0.6*w] + 40.0*I[r == 0 or r/b < 0.15]",
            "6 月旧协议仅排第 50 名，但在现行工作台“仅评已打开箱”多箱容初筛中跃居 192 条之首，且同流控制消融证实：在完全相同的 5 条 Weibull-5000 流关闭主动开新箱后 B50（0.034309）即反超 B1（0.039038），在相同 BPPLib 70 题上两协议均稳健（+7.22% vs +6.90%，仅次于 Best-Fit +6.47%），10× 箱容缩放漂移 0.00%。",
        ),
        (
            "method-obp-i605-log-half-symmetry",
            "i605_obp_b16_log_half",
            "OBP 岛屿流派三：半满偏离对数惩罚 + 90% 冲顶指数奖励 (Island605 B16)",
            "experiments/island605_archive/rules/all/bp/bp_015_E2_highgen_g8_r37__ba76c5bc.py",
            16,
            "0.01217",
            "-log(1 + 10*|w/b - 0.5|) + exp(10*(w/b - 0.9))*I[w/b > 0.9]",
            "纯无量纲比值公式：以对数鼓励均衡过渡（贴近半满）同时对超过 90% 填充率的箱子施加指数级封箱冲顶奖励，在旧协议与新协议下均稳健且 10× 箱容缩放漂移 0.00%。",
        ),
    ]
    for eid, aid, title, rel, rk, arch_obj, expr, lead in obp_i605_specs:
        w_ok = _alg_stat(summary, "obp_ext_eoh_weibull", aid, "ok_count")
        w_gap = _alg_stat(summary, "obp_ext_eoh_weibull", aid, "mean_rel_gap", "common_completed")
        b_ok = _alg_stat(summary, "obp_ext_bpplib", aid, "ok_count")
        b_gap = _alg_stat(summary, "obp_ext_bpplib", aid, "mean_rel_gap")
        meta, md = _make_method_card(
            entry_id=eid,
            title=title,
            family="online_bin_packing",
            variant="online_bp",
            variant_note="一维在线装箱评分函数 score(item, bins)；须严格区分旧岛屿协议（允许主动开新箱）与现行工作台协议（仅在可行已打开箱中评分，装不下才开新箱）。",
            paradigm="sequential_construct",
            interface="score",
            complexity="O(n^2)",
            eoh_status="possible",
            adapter_kind="direct_entrypoint",
            summary_text=(
                f"{lead} 现行工作台 Weibull 共同交集差距 {_fmt_pct(w_gap)}（完成 {w_ok}/173），BPPLib 70 例差距 {_fmt_pct(b_gap)}（完成 {b_ok}/70）。"
            ),
            tags=["obp", "island605", aid, "online-bin-packing", "score", "scale-invariant"],
            tier="verified_experiment",
            strong_on=["online_weibull_streams", "bpplib_generalization", "capacity_scale_invariant"],
            weak_on=["protocol_shift_between_open_new_bin_and_open_only"],
            scale_notes=f"旧 6 月允许开新箱协议精确复算 {arch_obj}（Best-Fit 旧基线 0.039843）；现行工作台仅评已打开箱协议下 10× 箱容缩放漂移 0.00%。",
            blueprint={
                "skeleton_role": "在线逐件装箱评分：现行工作台仅传入所有可行已打开箱剩余容量数组，无可行箱时才开新箱",
                "evolvable_hook": "score(item, bins) -> np.ndarray",
                "state_maintained": ["open_bin_remaining_capacities"],
                "invariants_and_constraints": ["严禁硬编码箱容常数（如 50 或 100），全部阈值须相对 item 或 bins 无量纲化", "旧协议与新协议成绩分轨报告"],
                "typical_pitfalls": ["在旧协议允许主动开新箱下最优的规则，迁移到仅评打开箱的现行协议时排名可能显著变化（如 B1 vs B50）"],
            },
            math_formulation=[{"expr": expr, "variables": {"w": "当前到达物品大小 item", "b": "候选箱当前剩余容量 bins", "r": "装入后残差 b - w"}, "preconditions": "所有输入箱满足 b >= w > 0"}],
            artifact_refs=[_pin(rel)],
            evidence_bindings=[
                _binding("obp_ext_eoh_weibull", aid, "common_completed_mean_rel_gap", w_gap, f"[现行工作台仅评打开箱协议] Weibull 共同交集差距 {_fmt_pct(w_gap)}（完成 {w_ok}/173）"),
                _binding("obp_ext_bpplib", aid, "mean_rel_gap", b_gap, f"[现行工作台仅评打开箱协议] BPPLib 70 例差距 {_fmt_pct(b_gap)}（完成 {b_ok}/70）"),
            ],
            rel_problems=["problem-online-bin-packing"],
            rel_methods=["method-obp-best-fit", "method-obp-first-fit", "method-obp-residual-utilization"],
            source_refs=["src-island605-archive-20260630", "src-milestone15-reproduction-20261122"],
            evidence_refs=["report:experiments/milestone15/legacy_reproduction_605.json", "report:experiments/milestone15/workbench_screening_605.json"],
            md_lead=lead,
            md_steps=f"1. **数学公式**：`{expr}`。\n2. **旧协议精确复现（允许主动开新箱）**：在 5 条 Weibull-5000 流（C=100）上精确复算 `{arch_obj}`。\n3. **现行工作台协议评估（仅评已打开箱）**：在 Weibull 173 例与 BPPLib 70 例上统一测时重算。",
            md_limits="两种在线装箱协议（是否允许主动开新箱）会改变最优策略形态，比较历史分数与现行工作台分数时必须分轨列示。",
            md_sources=f"原始归档程序：`{rel}`（6 月岛屿模型 BP 排名第 {rk}）；复现数据见 `experiments/milestone15/`。",
            md_code=f"已注册至 `OBP_SOLVER_CATALOG[{aid!r}]`，支持前端 OBP 榜单与填充率分布对比。",
            md_open="后续可在里程碑二检验“显式提供新箱虚拟槽位”与“仅评已打开箱”两类装箱接口对进化上限的影响。",
        )
        _put(eid, meta, md)

    # ------------------------------------------------------------------
    # 15. Cross-domain Antipattern Evidence Card: Hardcoded Capacity & Mixed-Unit Scale Drift
    # ------------------------------------------------------------------
    b117_rel = "experiments/island605_archive/rules/all/bp/bp_116_E2_highgen_g8_r39__ae12f32a.py"
    b3_rel = "experiments/island605_archive/rules/all/bp/bp_002_E2_gen16_g16_r8__28e1a354.py"
    c61_rel = "experiments/island605_archive/rules/all/cvrp/cvrp_060_E2_highgen_g8_r11__5743ace4.py"
    b117_w = _alg_stat(summary, "obp_ext_eoh_weibull", "i605_obp_b117_hardcap_anti", "mean_rel_gap", "common_completed")
    b117_b = _alg_stat(summary, "obp_ext_bpplib", "i605_obp_b117_hardcap_anti", "mean_rel_gap")
    anti_meta = {
        "type": "evidence",
        "title": "跨问题反面教材：硬编码箱容常数与混合单位尺度崩盘（OBP B117/B3 × CVRP C61/H-001）",
        "category": "evidence",
        "problem_family": "online_bin_packing",
        "tags": ["obp", "cvrp", "antipattern", "hardcoded-capacity", "scale-collapse", "island605"],
        "status": "reviewed",
        "summary": (
            f"证实硬编码绝对常数（OBP 写死 capacity=100 或 50）与混合量纲（CVRP 叠加 O(s) 与 O(1/s)）在跨容量/跨尺度测试中必然诱发性能退化："
            f"OBP B117 在 10× 箱容缩放下箱数漂移 +1.38%（BPPLib 差距 {_fmt_pct(b117_b)}），island605 CVRP #61 在 1e-3 缩尺下漂移 +255.95%，"
            f"与 CVRP Frozen C（H-001，+206.99%）构成跨问题同源失效机理。"
        ),
        "attributes": {
            "knowledge_tier": "failure_antipattern",
            "problem_variant": "online_bp",
            "variant_adaptation_note": "主归属在线装箱域（OBP），同时关联 CVRP 域尺度崩盘反例，构成跨问题统一量纲设计护栏。",
            "paradigm": "math_mechanism",
            "complexity_class": "O(1)",
            "interface": "score",
            "applicable_regimes": {
                "strong_on": ["auditing_dimensionless_invariance", "preventing_hardcoded_capacity_constants"],
                "weak_on": ["fixed_single_capacity_toy_benchmarks"],
                "scale_notes": "605 条岛屿规则实测：CVRP 有 34/207 条不满足缩尺不变（最差 rank #61 达 +255.95%）；OBP 有 9/192 条在 10× 箱容缩放下箱数退化 >0.5%（最差 B117 达 +1.38%）。",
            },
            "math_formulation": [
                {
                    "expr": "B117: density = 1 - (bins - item) / 100  (hardcodes C=100 -> negative/wrong sign when C=500 or 1000)",
                    "variables": {"100": "仅对 C=100 训练流成立的硬编码绝对常数"},
                    "preconditions": "当测试集箱容变为 C=500 或 BPPLib 大箱容（如 C=100,000）时量纲彻底失真",
                },
                {
                    "expr": "CVRP #61: score = w*d_cur + (1-w)*(1 / d_dep)  (mixes O(s) and O(1/s) -> +255.95% drift at s=1e-3)",
                    "variables": {"s": "坐标统一缩放因子"},
                    "preconditions": "当坐标缩小 1000 倍时 1/d_dep 相对 d_cur 放大 10^6 倍",
                },
            ],
            "artifact_refs": [_pin(b117_rel), _pin(b3_rel), _pin(c61_rel)],
            "evidence_bindings": [
                _binding("obp_ext_eoh_weibull", "i605_obp_b117_hardcap_anti", "common_completed_mean_rel_gap", b117_w, f"OBP B117 在 Weibull 多箱容共同交集差距 {_fmt_pct(b117_w)}"),
                _binding("obp_ext_bpplib", "i605_obp_b117_hardcap_anti", "mean_rel_gap", b117_b, f"OBP B117 在 BPPLib 70 例差距 {_fmt_pct(b117_b)}"),
            ],
        },
        "relations": {
            "problems": ["problem-online-bin-packing", "problem-cvrp"],
            "methods": ["method-obp-i605-sqrt-close-bonus", "method-cvrp-i605-relative-band-savings"],
            "sources": ["src-island605-archive-20260630", "src-milestone15-reproduction-20261122"],
        },
        "source_refs": ["src-island605-archive-20260630", "src-milestone15-reproduction-20261122"],
        "evidence_refs": ["report:experiments/milestone15/workbench_screening_605.json"],
        "code_refs": [],
    }
    anti_md = f"""# 跨问题反面教材：硬编码箱容常数与混合单位尺度崩盘（OBP B117/B3 × CVRP C61/H-001）

在里程碑 1.5 对 605 条岛屿规则执行跨容量与跨尺度压力体检时，发现 OBP 与 CVRP 共享同一类根本失效模式——**将仅在单一训练尺度下有效的绝对常数或非无量纲项写入启发式评分式**。

## 定义或方法步骤

1. **OBP 硬编码箱容陷阱（`B117` / `B3`）**：`B117` 在源码中直接写死 `capacity = 100` 并计算 `density = 1 - residual / 100`；`B3` 写死半箱常数 `abs(residual - 50) / 50.0`。当输入流箱容从 `C=100` 放大 10 倍至 `C=1000`（或测试 BPPLib `C=100..100000`）时，密度符号翻转、排序畸变。
2. **CVRP 混合量纲陷阱（`island605` CVRP #61）**：源码将 `d_cur`（$O(s)$）与 `1 / d_dep`（$O(1/s)$）直接相加；虽在标称 `select_64` 上拿到第 4 名（`22.6882`），在 `1e-3` 坐标缩放下瞬间崩盘（漂移 **`+255.95%`**），与中期发现的 `H-001`（Frozen C `+206.99%`）完全同源。

## 适用条件、假设与限制

- 对所有 LLM 自动启发式搜索均具通用警示意义：进化开发集若只含单一箱容或单一坐标范围，搜索必然会“投机取巧”写出硬编码常数。
- 解决路径已在工作台中制度化：搜索开发期强制引入 `1e-3` 缩尺压力测试（CVRP）与多箱容缩放检验（OBP）。

## 来源及支持的具体结论

- 全量 605 条体检数据：`experiments/milestone15/workbench_screening_605.json`。
- OBP `192` 条中 `9` 条在 10× 箱容缩放下退化 `>0.5%`（`B117` 达 `+1.38%`，145→147 箱）；CVRP `207` 条中 `34` 条存在缩尺漂移（`173/207` 严格 `<0.01%`）。

## 代码和评测关联

- 反例求解器已注册为 `OBP_SOLVER_CATALOG['i605_obp_b117_hardcap_anti']`；关联正面无量纲对照卡：`method-obp-i605-sqrt-close-bonus`、`method-cvrp-i605-relative-band-savings`、`evidence-cvrp-scale-collapse-h001`。

## 未确认项与冲突证据

- `B3` 在 7 题初筛的 10× 缩放对上恰好因 `1/(r^2)` 主导项掩盖了 `-|r-50|/50` 项而未产生箱数差，但在更大箱容与密集平局流下硬编码 `50` 仍会扭曲次级排序。
"""
    _put("evidence-obp-hardcoded-capacity-antipattern", anti_meta, anti_md)

    # ------------------------------------------------------------------
    # 16. Master Milestone 1.5 Dual-Track Reproduction Evidence Card
    # ------------------------------------------------------------------
    leg_sum = leg["island605_summary"]
    ma = leg["midterm_sessions_audit"]
    cv_s = scr["cvrp_summary"]
    ts_s = scr["tsp_summary"]
    ob_s = scr["obp_summary"]
    m15_sel_288 = selection["analyses"].get("hetero_288__pointwise_plus_m15", {})
    m15_sel_fa = selection["analyses"].get("final_accept_120__pointwise_plus_m15_frozen", {})
    m15_meta = {
        "type": "evidence",
        "title": "里程碑 1.5 双轨历史实验复现、真实运行期机理普查与去重审计总证据",
        "category": "evidence",
        "problem_family": "cvrp",
        "tags": ["milestone-1.5", "reproduction", "island605", "midterm-audit", "petal-audit", "deduplication"],
        "status": "reviewed",
        "summary": (
            f"双轨完成历史实验核验：轨道一（旧协议精确复算）命中 {leg_sum['total_matched_within_1e4']}/605（仅 BP #61 差 0.000401）、"
            f"核实 24 场仓内中期会话在 88 题呈 23 组路线输出（0 场全等同 NN）及 HeurAgenix petal 对称矩阵 pi/4 缺陷；"
            f"轨道二（统一工作台初筛）查明 CVRP 真实运行期主动早返为 {cv_s['true_runtime_voluntary_early_return']}/207（非朴素代码匹配 75.4%）、"
            f"尺度不变 {cv_s['scale_invariant_lt_0_01pct']}/207，冻结并全量验收 15 个精炼代表求解器（总库 45 个）。"
        ),
        "attributes": {
            "knowledge_tier": "verified_experiment",
            "problem_variant": "standard_cvrp",
            "paradigm": "math_mechanism",
            "complexity_class": "O(n^2)",
            "interface": "select_next_node",
            "applicable_regimes": {
                "strong_on": ["cross_stage_reproducibility", "mechanism_verification_before_kb_ingestion"],
                "weak_on": ["external_fme_pilot_raw_logs_absent_from_repo"],
                "scale_notes": (
                    "严格区分两类验收边界：① cvrp_final_accept_120 已随里程碑一发布过 2,040 条基线逐例结果，"
                    "里程碑 1.5 选优全程零接触该集、仅用于名单冻结后验收（若论文需完全未发布过结果的全新盲测应另行冻结新题）；"
                    "② tsp_ext_eohs_128 已用于 206 条 TSP 代表筛选，其成绩标注为选优结果，外部验证以 TSPLIB 18 例为准。"
                ),
            },
            "artifact_refs": [
                _pin("experiments/island605_archive/rules/all/manifest.json"),
                _pin("experiments/island605_archive/rules/all/bp/bp_060_E2_gen16_g16_r2__81f696a2.py"),
            ],
            "evidence_bindings": [
                _binding("cvrp_select_multiscale_64", "i605_cvrp_c1_tworegime", "mean_tour_length", _alg_stat(summary, "cvrp_select_multiscale_64", "i605_cvrp_c1_tworegime", "mean_tour_length"), "Island605 C1 在 64 题筛选集上 49/64 胜 R5"),
                _binding("cvrp_final_accept_120", "i605_cvrp_c1_tworegime", "mean_tour_length", _alg_stat(summary, "cvrp_final_accept_120", "i605_cvrp_c1_tworegime", "mean_tour_length"), "名单冻结后 C1 在 final_accept_120 验收均长"),
                _binding("cvrp_final_accept_120", "s2_r4_cos", "mean_tour_length", _alg_stat(summary, "cvrp_final_accept_120", "s2_r4_cos", "mean_tour_length"), "名单冻结后 R4 在 final_accept_120 验收均长"),
                _binding("tsp_ext_eohs_128", "i605_tsp_t1_rollout", "ok_count", _alg_stat(summary, "tsp_ext_eohs_128", "i605_tsp_t1_rollout", "ok_count"), "TSP 历史第 1 名在 500 ms 预算下仅完成部分实例，证明需联合报告完成率"),
                _binding("obp_ext_eoh_weibull", "i605_obp_b50_sqrt_tier", "common_completed_mean_rel_gap", _alg_stat(summary, "obp_ext_eoh_weibull", "i605_obp_b50_sqrt_tier", "mean_rel_gap", "common_completed"), "OBP B50 在现行工作台仅评打开箱协议下跃居岛屿代表之首"),
            ],
        },
        "relations": {
            "problems": ["problem-cvrp", "problem-tsp", "problem-online-bin-packing"],
            "methods": [
                "method-cvrp-s2-r4-cos",
                "method-cvrp-sweep-2opt",
                "method-cvrp-farthest-insertion",
                "method-cvrp-i605-tworegime-savings",
                "method-tsp-i605-1step-rollout",
                "method-tsp-i605-mean-farness",
                "method-obp-i605-exp-deadzone",
                "method-obp-i605-sqrt-close-bonus",
            ],
            "sources": ["src-island605-archive-20260630", "src-milestone15-reproduction-20261122"],
        },
        "source_refs": ["src-island605-archive-20260630", "src-milestone15-reproduction-20261122"],
        "evidence_refs": [
            "report:experiments/milestone15/legacy_reproduction_605.json",
            "report:experiments/milestone15/workbench_screening_605.json",
            "report:experiments/milestone15/run_inventory_deduped.json",
        ],
        "code_refs": [],
    }
    m15_md = f"""# 里程碑 1.5 双轨历史实验复现、真实运行期机理普查与去重审计总证据

本卡片汇总里程碑 1.5 对全机 1,769 个历史实验目录与 605 条三域岛屿规则的**双轨独立复现**、**真实运行期机理核验**与**精炼入库结果**。

## 定义或方法步骤

1. **交付轨道一（按旧题、旧评分规则与旧基线精确复算）**：
   - 605 条 `island605` 归档规则精确复算匹配 **`{leg_sum['total_matched_within_1e4']}/605`**（CVRP `207/207`、TSP `206/206`、BP `191/192`）。唯一差异为装箱第 61 名（`bp_060`，归档 `0.02767` vs 复算 `0.028071`，差 `0.000401`）；源码证实其内部使用依赖 `n = len(bins)` 的余弦核，但相对 6 月归档运行时的具体触发步仍待细粒度追踪定位。
   - **同流 OBP 开箱协议控制消融**（`experiments/milestone15/obp_protocol_ablation.json`）：在完全相同的 5 条 Weibull-5000 流上仅切换开箱协议，关闭主动开新箱使 `B1` 从 `0.006741` 退化至 `0.039038`（`+3.23pp`），直接被 `B16`（`0.032196`）与 `B50`（`0.034309`）反超；在相同 BPPLib 70 题上，允许主动开新箱使 `B1` 从 `+10.80%` 升至 `+36.35%`、`B117` 从 `+10.32%` 暴涨至 `+233.35%`，而 `B50` 保持稳健（`+7.22%` vs `+6.90%`）。
   - 旧协议精确基线复算：CVRP NN = **`13.6108`**（README 旧注 `13.519`）、TSP NN = **`6.6079`**（旧注 `6.56`）、BP Best-Fit = **`0.039843`**（旧注 `0.0398`），计算历史降幅须注明分母。
   - 11 月中期 24 场仓内非中止会话在 88 题（`dev_24 + select_64`）上呈现 **`{ma['n_distinct_88inst_route_outputs']}` 组不同路线输出**（仅 `a2_operations_only` 与 `a3_guided` 相同），**`0` 场在全部 88 题上等同最近邻**；此前清点报告中提到的 5 场 dev-4 NN 匹配全部位于 `_aborted/*` 目录。
   - `R5` 与 `R7` 溯源闭合（在 `s2_autonomous_math_r8` 第 5、7 轮候选目录中逐字节哈希一致）；`HeurAgenix petal_algorithm_b384` 实测证实在对称距离矩阵上将全部非重合客户极角算为 $\\pi/4$，故改用真二维坐标 `cvrp_sweep_2opt` 入库。
2. **交付轨道二（冻结精炼名单在统一工作台全量评估）**：
   - 初筛统计：CVRP 207 条中 `{cv_s['complete_92']}/207` 完成 92 题、`{cv_s['scale_invariant_lt_0_01pct']}/207` 严格缩尺不变（`<0.01%`）、AST 非空早返 `{cv_s['ast_non_empty_depot_return']}/207`，而**真实运行期触发过主动早返的仅 `{cv_s['true_runtime_voluntary_early_return']}/207`（26.6%）**（修正了此前基于关键字搜索高估至 75.4% 的统计）；TSP 206 条中 `{ts_s['complete_128']}/206` 在 500 ms 下完成 128 题，历史冠军 T1（单步 $O(m^3)$、全构造最坏 $O(n^4)$）仅完成 `{ts_s['rank1_historical']['ok_128']}/128`；OBP 192 条在现行“仅评已打开箱”协议下 `{ob_s['complete_7']}/192` 完成 7 题跨箱容体检，`{ob_s['capacity_10x_degraded_gt_0_5pct']}/192` 在 10× 缩放下退化 `>0.5%`。
   - 冻结并注册 15 个精炼代表求解器（总库 30 → 45，源码哈希清单见 `experiments/milestone15/frozen_roster_manifest.json`），在全部 14 套统一基准上完成分离测时评估与方向二扩充池（`POINTWISE_PLUS_M15_IDS`）选择器分析。
   - **方向二扩池选择器坦诚边界**：在 `final_accept_120__pointwise_plus_m15_frozen` 上，固定选 `C1` 总长为 **`3121.83`**（288 题 SBS 亦降至 `7093.54` 低于旧池 VBS `7096.72`），但 7 个基于 64 题训练的学习选择器在 120 题验收集上**全部落后于固定 `C1`**（最接近的 `rf_pairwise_cs` 仍长 `0.14%`，其余长 `0.16%–0.54%`），表明当单一固定规则大幅变强、理想互补上限由 `1.93%` 收窄至 `1.19%` 后，小样本折外学习选择器难以带来正净增益。

## 适用条件、假设与限制

- **装箱协议边界**：6 月旧协议允许主动开新箱，现行工作台仅在已打开可行箱中评分；两类成绩分轨列示，并已通过 `obp_protocol_ablation.json` 在同一物品流上独立证实协议效应。
- **题集使用历史披露**：`cvrp_final_accept_120` 已随里程碑一发布（含 2,040 条基线逐例结果）；里程碑 1.5 在筛选阶段仍严格零接触该集、仅在 15 条代表名单冻结后验收；若最终论文需要完全未发布过结果的全新盲测，须另行冻结新题集。`tsp_ext_eohs_128` 已用于 TSP 206 条代表筛选，其 128 题成绩标为选优结果，外部验证以 TSPLIB 18 例为准。
- **溯源与基线字段说明**：`manifest.json:source_main_sha`（`d6433549`）沿用知识库历史盘点基线快照，与里程碑 1.5 的代码构建提交（基于 `48134fc` 增量提交）分列说明；`frozen_roster_manifest.json` 为复审加固阶段补齐的候选哈希清单。
- **仓外缺失日志声明**：`fme_pilot` 原始请求与续跑日志、全机扫描明细位于仓外工作树，仅保留归档摘要而不做越界虚构。

## 来源及支持的具体结论

- 轨道一证据：`experiments/milestone15/legacy_reproduction_605.json`。
- 轨道二筛选：`experiments/milestone15/workbench_screening_605.json`。
- 去重账本：`experiments/milestone15/run_inventory_deduped.json` 与 `.csv`。
- 方向二扩充池：`hetero_288__pointwise_plus_m15` 与 `final_accept_120__pointwise_plus_m15_frozen`（`results/selection_records.json`）。

## 代码和评测关联

- 复现工具：`tools/reproduce_milestone15.py`、`tools/analyze_milestone15_selection.py`、`tools/export_milestone15_ledger.py`、`tools/sync_milestone15_kb.py`。
- 15 个新增求解器分布于 `SOLVER_CATALOG`（+7）、`TSP_SOLVER_CATALOG`（+4）与 `OBP_SOLVER_CATALOG`（+4）。

## 未确认项与冲突证据

- 后续里程碑二将在计划期自主接口设计中系统探索突破单步逐点构造范式上限的跨范式算法（如并行合并、插入与局部搜索自动组合）。
"""
    _put("evidence-milestone15-historical-reproduction", m15_meta, m15_md)

    return {
        "ok": True,
        "written_count": len(written),
        "written_ids": written,
        "total_sources": len(sources_doc["sources"]),
        "has_m15_selection_288": bool(m15_sel_288),
        "has_m15_selection_fa": bool(m15_sel_fa),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=REPO / "knowledge_workspace")
    parser.add_argument("--bundle", type=Path, default=REPO / "build" / "workbench_m15_bundle")
    args = parser.parse_args()
    res = sync_milestone15_kb(args.workspace, args.bundle)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
