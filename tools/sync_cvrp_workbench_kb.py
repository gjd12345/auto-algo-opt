"""Synchronize Milestone-1 CVRP knowledge cards with unified attributes & live evidence.

Reads computed benchmark statistics directly from a CVRP Workbench bundle
(``results/summary.json``, ``results/selection_records.json``,
``results/scale_stress_records.json``, ``algorithms.json``), upgrades key
existing CVRP cards without breaking any of the 299 stable IDs, adds complete
standard CVRP method/observation/antipattern cards, updates ``sources.json``,
and normalizes every Markdown/JSON file to UTF-8 LF with exact ``content_sha256``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parents[1]
MIDTERM_COMMIT_PIN = "5215ebd"
WORKBENCH_COMMIT_PIN = "d8b6ede"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file_lf(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return _sha256_bytes(text.encode("utf-8"))


def _write_entry(entries_dir: Path, entry_id: str, metadata: dict[str, Any], markdown: str) -> None:
    md_text = markdown.replace("\r\n", "\n").rstrip("\n") + "\n"
    md_bytes = md_text.encode("utf-8")
    md_path = entries_dir / f"{entry_id}.md"
    md_path.write_bytes(md_bytes)

    meta = dict(metadata)
    meta["id"] = entry_id
    meta["content_sha256"] = _sha256_bytes(md_bytes)
    json_path = entries_dir / f"{entry_id}.json"
    json_bytes = (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    json_path.write_bytes(json_bytes)


def _new_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": "src-cvrp-workbench-20261121",
            "title": "auto-algo-opt Milestone-1 CVRP Workbench Unified Benchmark & Multi-Paradigm Reference Evaluation",
            "authors": ["auto-algo-opt research log"],
            "year": 2026,
            "venue": "Internal immutable release bundle (cvrp_workbench_v1)",
            "doi": None,
            "url": "https://github.com/gjd12345/auto-algo-opt/blob/main/docs/cvrp-kb-benchmark-frontend-final-plan.md",
            "kind": "internal_experiment_report",
            "accessed_on": "2026-11-21",
            "availability": "local_repository",
            "license": "repository-internal research record",
            "selected": True,
            "selection_reason": "Unified separated-timing full-route benchmark results across 7 CVRP suites and Direction-2 out-of-fold/frozen transfer selection.",
            "locator": "benchmarks/cvrp_workbench/registry.json; results/per_instance_records.json; results/summary.json; results/selection_records.json",
            "read_depth": "full_text_local",
            "notes": "Every metric in evidence_bindings is directly backed by results/per_instance_records.json in the same immutable release.",
        },
        {
            "id": "src-uchoa-2017-cvrplib-x",
            "title": "New benchmark instances for the Capacitated Vehicle Routing Problem",
            "authors": ["Eduardo Uchoa", "Diego Pecin", "Artur Pessoa", "Marcus Poggi", "Thibaut Vidal", "Anand Subramanian"],
            "year": 2017,
            "venue": "European Journal of Operational Research (EJOR), 257(3), 845-858",
            "doi": "10.1016/j.ejor.2016.08.012",
            "url": "https://doi.org/10.1016/j.ejor.2016.08.012",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and open benchmark instances only",
            "selected": True,
            "selection_reason": "Canonical Set X CVRPLib benchmark design and EUC_2D protocol.",
            "locator": "vidalt/CVRPLIB@34985dd2 (Set X)",
            "read_depth": "abstract",
            "notes": "All 100 Set X instances (n=100..1000, X-S/X-M/X-L) included in cvrp_ext_cvrplib_x_100 with 100/100 zero-error .sol verification.",
        },
        {
            "id": "src-augerat-1995-cvrplib-abp",
            "title": "Computational results with a branch and cut code for the capacitated vehicle routing problem",
            "authors": ["Philippe Augerat", "Jose Manuel Belenguer", "Enrique Benavent", "Angel Corberan", "Denis Naddef", "Giovanni Rinaldi"],
            "year": 1995,
            "venue": "Research Report RR 949-M, Universite Joseph Fourier, Grenoble",
            "doi": None,
            "url": "http://vrp.galgos.inf.puc-rio.br/index.php/en/",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "public research benchmark instances",
            "selected": True,
            "selection_reason": "Canonical CVRPLib Set A (27), Set B (23), and Set P (24) instances.",
            "locator": "vidalt/CVRPLIB@34985dd2 (Sets A/B/P)",
            "read_depth": "metadata",
            "notes": "All 74 Set A/B/P instances and official .sol BKS files imported in cvrp_ext_cvrplib_abp_74.",
        },
        {
            "id": "src-croes-1958-2opt",
            "title": "A Method for Solving Traveling-Salesman Problems",
            "authors": ["G. A. Croes"],
            "year": 1958,
            "venue": "Operations Research, 6(6), 791-812",
            "doi": "10.1287/opre.6.6.791",
            "url": "https://doi.org/10.1287/opre.6.6.791",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and algorithmic summary only",
            "selected": True,
            "selection_reason": "Original 2-opt edge-exchange neighborhood adapted for intra-route CVRP refinement.",
            "locator": "agent_skill_loop/cvrp_workbench/solvers.py:_two_opt_single_route",
            "read_depth": "abstract",
            "notes": "Local deterministic O(1)-delta implementation verified in cw_2opt.",
        },
        {
            "id": "src-or-1976-or-opt",
            "title": "Traveling Salesman-Type Combinatorial Problems and Their Relation to the Logistics of Regional Blood Banking",
            "authors": ["Ilhan Or"],
            "year": 1976,
            "venue": "PhD Thesis, Northwestern University",
            "doi": None,
            "url": "https://en.wikipedia.org/wiki/2-opt#Or-opt",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "metadata_only",
            "license": "citation only",
            "selected": True,
            "selection_reason": "Canonical Or-opt contiguous segment relocation neighborhood (L in {1,2,3}).",
            "locator": "Standard VRP local search literature",
            "read_depth": "metadata_only",
            "notes": "Standard CVRP intra-route and inter-route segment relocation reference.",
        },
        {
            "id": "src-potvin-rousseau-1995-2opt-star",
            "title": "An exchange heuristic for routing problems with time windows",
            "authors": ["Jean-Yves Potvin", "Jean-Marc Rousseau"],
            "year": 1995,
            "venue": "Journal of the Operational Research Society, 46(12), 1433-1446",
            "doi": "10.1057/jors.1995.204",
            "url": "https://doi.org/10.1057/jors.1995.204",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and algorithmic summary only",
            "selected": True,
            "selection_reason": "Canonical inter-route 2-opt* tail-exchange neighborhood.",
            "locator": "DOI 10.1057/jors.1995.204",
            "read_depth": "abstract",
            "notes": "Used in standard CVRP by dropping time-window checks and enforcing prefix+suffix capacity feasibility.",
        },
        {
            "id": "src-mladenovic-hansen-1997-vns",
            "title": "Variable neighborhood search",
            "authors": ["Nenad Mladenovic", "Pierre Hansen"],
            "year": 1997,
            "venue": "Computers & Operations Research, 24(11), 1097-1100",
            "doi": "10.1016/S0305-0548(97)00031-2",
            "url": "https://doi.org/10.1016/S0305-0548(97)00031-2",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and algorithmic summary only",
            "selected": True,
            "selection_reason": "Canonical VNS / VND metaheuristic framework for standard CVRP.",
            "locator": "DOI 10.1016/S0305-0548(97)00031-2",
            "read_depth": "abstract",
            "notes": "Distinct from DARP VNS entry (method-lit-darp-iterated-vns-for-dial-a-ride).",
        },
        {
            "id": "src-shaw-1998-lns",
            "title": "Using Constraint Programming and Local Search Methods to Solve Vehicle Routing Problems",
            "authors": ["Paul Shaw"],
            "year": 1998,
            "venue": "Principles and Practice of Constraint Programming (CP 1998), LNCS 1520, 417-431",
            "doi": "10.1007/3-540-49481-2_30",
            "url": "https://doi.org/10.1007/3-540-49481-2_30",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and algorithmic summary only",
            "selected": True,
            "selection_reason": "Original Large Neighborhood Search (LNS) and Shaw relatedness removal operator for VRP.",
            "locator": "DOI 10.1007/3-540-49481-2_30",
            "read_depth": "abstract",
            "notes": "Foundation for ruin-and-recreate metaheuristics in standard CVRP.",
        },
        {
            "id": "src-ropke-pisinger-2006-alns",
            "title": "An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows",
            "authors": ["Stefan Ropke", "David Pisinger"],
            "year": 2006,
            "venue": "Transportation Science, 40(4), 455-472",
            "doi": "10.1287/trsc.1050.0135",
            "url": "https://doi.org/10.1287/trsc.1050.0135",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and algorithmic summary only",
            "selected": True,
            "selection_reason": "Canonical Regret-k insertion and adaptive ruin-and-recreate destroy/repair architecture.",
            "locator": "DOI 10.1287/trsc.1050.0135",
            "read_depth": "abstract",
            "notes": "Regret-k insertion and ALNS weight updates generalize directly to standard CVRP.",
        },
        {
            "id": "src-foster-ryan-1976-petal",
            "title": "An Integer Programming Approach to the Vehicle Scheduling Problem",
            "authors": ["Brian A. Foster", "David M. Ryan"],
            "year": 1976,
            "venue": "Operational Research Quarterly, 27(2), 367-384",
            "doi": "10.1057/jors.1976.63",
            "url": "https://doi.org/10.1057/jors.1976.63",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "publisher_abstract",
            "license": "copyrighted; citation and algorithmic summary only",
            "selected": True,
            "selection_reason": "Canonical Petal cluster-first set-partitioning heuristic extending Gillett-Miller Sweep.",
            "locator": "DOI 10.1057/jors.1976.63",
            "read_depth": "abstract",
            "notes": "Extends single-pass angular Sweep into multi-petal route generation + set partitioning.",
        },
        {
            "id": "src-feiliu-2025-eohs",
            "title": "EoH-S: Evolution of Heuristic Set Using LLMs for Automated Heuristic Design",
            "authors": ["Fei Liu", "Qingfu Zhang", "et al."],
            "year": 2025,
            "venue": "arXiv / GitHub FeiLiu36/EoH-S",
            "doi": None,
            "url": "https://github.com/FeiLiu36/EoH-S",
            "kind": "primary_article",
            "accessed_on": "2026-11-21",
            "availability": "public_benchmark",
            "license": "MIT",
            "selected": True,
            "selection_reason": "Upstream EoH-S CVRP 256-instance benchmark dataset and heuristic-set evaluation protocol.",
            "locator": "FeiLiu36/EoH-S@7d4b1f77 (examples/training/cvrp_set/data_cvrp_10_150_256_withbaseline.pkl)",
            "read_depth": "full_text_local",
            "notes": "Imported verbatim into cvrp_ext_eohs_256.",
        },
    ]


def _binding(
    summary: Mapping[str, Any],
    suite_id: str,
    alg_id: str,
    *,
    metric: str = "mean_rel_gap",
    note: str = "",
) -> dict[str, Any] | None:
    s_block = (summary.get("suites") or {}).get(suite_id) or {}
    a_block = (s_block.get("algorithms") or {}).get(alg_id) or {}
    overall = a_block.get("overall") or {}
    val = overall.get(metric)
    if val is None:
        return None
    n = overall.get("n_instances")
    p50 = overall.get("solve_ms_p50")
    p95 = overall.get("solve_ms_p95")
    mean_len = overall.get("mean_tour_length")
    ref_note = note or f"N={n}, mean_tour_length={mean_len}, solve_ms P50={p50} / P95={p95} ms"
    return {
        "suite_id": suite_id,
        "run_id": "cvrp_workbench_v2_standard_500ms",
        "algorithm_id": alg_id,
        "metric": metric,
        "value": val,
        "comparison_mode": "local_recomputed",
        "reference_note": ref_note,
        "artifact_path": "results/per_instance_records.json",
    }


def _collect_bindings(summary: Mapping[str, Any], alg_id: str, suites: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sid in suites:
        b_gap = _binding(summary, sid, alg_id, metric="mean_rel_gap")
        if b_gap is not None:
            out.append(b_gap)
        b_len = _binding(summary, sid, alg_id, metric="mean_tour_length")
        if b_len is not None:
            out.append(b_len)
    return out


def _fmt_suite_table(summary: Mapping[str, Any], alg_id: str, suites: list[str]) -> str:
    lines = [
        "| 套件 (`suite_id`) | 样本数 `N` | 均长 (`mean_tour_length`) | 平均相对差距 (`mean_rel_gap`) | 完成率 | 求解耗时 P50 / P95 (ms) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sid in suites:
        s_block = (summary.get("suites") or {}).get(sid) or {}
        overall = ((s_block.get("algorithms") or {}).get(alg_id) or {}).get("overall")
        if not overall:
            continue
        gap = overall.get("mean_rel_gap")
        gap_str = f"{gap * 100:+.2f}%" if isinstance(gap, (int, float)) else "—"
        comp = overall.get("completion_rate")
        comp_str = f"{comp * 100:.1f}%" if isinstance(comp, (int, float)) else "—"
        lines.append(
            f"| `{sid}` | {overall.get('n_instances')} | {overall.get('mean_tour_length')} | {gap_str} | {comp_str} | {overall.get('solve_ms_p50')} / {overall.get('solve_ms_p95')} |"
        )
    return "\n".join(lines)


def sync_kb(workspace: Path, bundle_dir: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    bundle_dir = bundle_dir.resolve()
    entries_dir = workspace / "entries"

    summary = json.loads((bundle_dir / "results" / "summary.json").read_text(encoding="utf-8"))
    selection = json.loads((bundle_dir / "results" / "selection_records.json").read_text(encoding="utf-8"))
    stress = json.loads((bundle_dir / "results" / "scale_stress_records.json").read_text(encoding="utf-8"))
    alg_doc = json.loads((bundle_dir / "algorithms.json").read_text(encoding="utf-8"))
    alg_by_id = {a["algorithm_id"]: a for a in alg_doc["algorithms"]}

    # 1. Merge new sources into sources.json (preserving all existing sources)
    sources_path = workspace / "sources.json"
    sources_doc = json.loads(sources_path.read_text(encoding="utf-8"))
    existing_sids = {s["id"] for s in sources_doc.get("sources", []) if isinstance(s, Mapping)}
    added_sources = 0
    for src in _new_sources():
        if src["id"] not in existing_sids:
            sources_doc["sources"].append(src)
            existing_sids.add(src["id"])
            added_sources += 1
    sources_path.write_bytes((json.dumps(sources_doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    solvers_sha = _sha256_file_lf(REPO / "agent_skill_loop" / "cvrp_workbench" / "solvers.py")
    protocol_sha = _sha256_file_lf(REPO / "agent_skill_loop" / "cvrp_workbench" / "protocol.py")
    selection_sha = _sha256_file_lf(REPO / "agent_skill_loop" / "cvrp_workbench" / "selection.py")
    r5_sha = alg_by_id["s2_r5_spiral"]["code_sha256"]
    r7_sha = alg_by_id["s2_r7_iso"]["code_sha256"]
    c_sha = alg_by_id["c"]["code_sha256"]

    core_suites = [
        "cvrp_dev_hetero_24",
        "cvrp_select_multiscale_64",
        "cvrp_hist_p0_120",
        "cvrp_hist_hetero_288",
        "cvrp_final_accept_120",
        "cvrp_ext_eohs_256",
        "cvrp_ext_reevo_scale",
        "cvrp_ext_cvrplib_abp_74",
        "cvrp_ext_cvrplib_x_100",
    ]

    upgraded: list[str] = []
    created: list[str] = []

    def _upsert(entry_id: str, meta: dict[str, Any], md: str) -> None:
        existed = (entries_dir / f"{entry_id}.json").is_file()
        _write_entry(entries_dir, entry_id, meta, md)
        if existed:
            upgraded.append(entry_id)
        else:
            created.append(entry_id)

    # ------------------------------------------------------------------
    # A. UPGRADE EXISTING CORE CVRP CARDS (stable IDs preserved 100%)
    # ------------------------------------------------------------------

    # 1) method-cvrp-nearest-feasible-construct (NN)
    nn_meta = json.loads((entries_dir / "method-cvrp-nearest-feasible-construct.json").read_text(encoding="utf-8"))
    nn_meta["tags"] = sorted(set(nn_meta.get("tags", []) + ["nn", "baseline", "select_next_node", "standard-cvrp"]))
    nn_meta["source_refs"] = sorted(set(nn_meta.get("source_refs", []) + ["src-cvrp-workbench-20261121"]))
    nn_meta["relations"]["sources"] = sorted(set(nn_meta.get("relations", {}).get("sources", []) + ["src-cvrp-workbench-20261121"]))
    nn_meta["attributes"] = {
        "method_family": "construction",
        "online_offline": "offline",
        "objective": "mean route length",
        "knowledge_tier": "verified_experiment",
        "problem_variant": "standard_cvrp",
        "paradigm": "sequential_construct",
        "complexity_class": "O(n^2)",
        "interface": "select_next_node",
        "eoh_map": {"status": "possible", "adapter_kind": "direct_entrypoint", "entrypoint": "select_next_node"},
        "applicable_regimes": {
            "strong_on": ["fast_reference_baseline", "strict_scale_invariance"],
            "weak_on": ["eccentric_depot", "clustered_multi_route", "large_n_200_plus"],
            "scale_notes": "O(n^2) 极快基线（n=200 求解 P50 < 2 ms），但因短视贪心且缺少远端出发与早返机制，在全部多规模与 CVRPLib 套件上均显著弱于 R5 与并行 CW。",
        },
        "interface_blueprint": {
            "skeleton_role": "单车顺序构造循环：维护当前位置、剩余载重与未访问集合；当无可行客户时强制回仓 0 并重置满载",
            "evolvable_hook": "select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int",
            "state_maintained": ["current_node", "rest_capacity", "unvisited_nodes"],
            "invariants_and_constraints": ["客户 1..n 恰好访问一次", "每步仅在 demands[j] <= rest_capacity 的可行集合中选择或主动返回 0", "输入矩阵与需求只读"],
            "typical_pitfalls": ["从仓库出发时按最近客户起步（inside-out），将远端孤立客户留到尾程产生高额空驶回程"],
        },
        "math_formulation": [
            {
                "expr": "j* = argmin_{j in F(r)} d(i, j)",
                "variables": {"i": "当前所在节点", "F(r)": "满足 q_j <= r 的未访问可行客户集", "d(i,j)": "节点 i 到 j 的距离"},
                "preconditions": "对称非负距离矩阵，且所有单客户需求 q_j <= Q",
            }
        ],
        "artifact_refs": [
            {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "agent_skill_loop/problems/cvrp.py", "sha256": _sha256_file_lf(REPO / "agent_skill_loop/problems/cvrp.py")},
            {"kind": "repo_code", "commit": WORKBENCH_COMMIT_PIN, "path": "agent_skill_loop/cvrp_workbench/solvers.py", "sha256": solvers_sha},
        ],
        "evidence_bindings": _collect_bindings(summary, "nn", core_suites),
    }
    nn_md = f"""# Nearest feasible customer construct (NN)

标准 CVRP 顺序构造最近邻基线（`nn`），直接对应 `agent_skill_loop/problems/cvrp.py` 官方基线模板，也是本地合成套件（`dev_24 / select_64 / P0-120 / hetero-288 / final_accept_120`）的 `solver_reference` 参考锚点。

## 定义或方法步骤

1. 初始化车辆位于仓库 `0`，剩余载重 `rest_capacity = Q`，未访问客户集合 `U = {{1..n}}`。
2. 过滤可行候选集 `F = {{j in U : q_j <= rest_capacity}}`；若 `F` 为空，则强制返回仓库 `0` 并重置 `rest_capacity = Q`。
3. 选取 `j* = argmin_{{j in F}} d(current_node, j)`，移动到 `j*` 并扣减 `rest_capacity -= q_{{j*}}`。
4. 重复直至 `U` 为空，最后返回仓库 `0` 闭合路线。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int`。
- 纯距离比较天然满足坐标缩放不变性（`scale_drift_pct = 0.0%`）。

## 适用条件、假设与限制

- 适用于标准容量约束 CVRP（单仓库、同质车队、无时间窗），时间复杂度 $O(n^2)$。
- 局限：完全忽略仓库方向、容量匹配与全局合并，在 `i=0` 处必然选择最近客户（inside-out），导致外围孤立点留在尾部形成高额空驶回程。

## 来源及支持的具体结论

- 本仓库统一测时与全解路线验证结果（`cvrp_workbench_v1`, 预算 `standard_500ms`）：

{_fmt_suite_table(summary, "nn", core_suites)}

## 代码和评测关联

- 历史实现卡片：`impl-cvrp-official-construct`；当前基线代码：`agent_skill_loop/problems/cvrp.py`、`agent_skill_loop/cvrp_workbench/solvers.py`。
- 逐实例记录与可查看路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- NN 在局部合成套件中用作 `solver_reference` 分母，因此其自身 `mean_rel_gap` 在合成套件上恒为 `0.00%`；在 CVRPLib（以官方 BKS 为分母）与 EoH-S（以上游 baseline 为分母）上可见其真实绝对质量差距。
"""
    _upsert("method-cvrp-nearest-feasible-construct", nn_meta, nn_md)

    # 2) method-cvrp-savings-next-node (Pointwise Savings)
    sav_meta = json.loads((entries_dir / "method-cvrp-savings-next-node.json").read_text(encoding="utf-8"))
    sav_meta["tags"] = sorted(set(sav_meta.get("tags", []) + ["savings-pointwise", "select_next_node", "standard-cvrp"]))
    sav_meta["source_refs"] = sorted(set(sav_meta.get("source_refs", []) + ["src-cvrp-workbench-20261121"]))
    sav_meta["relations"]["sources"] = sorted(set(sav_meta.get("relations", {}).get("sources", []) + ["src-cvrp-workbench-20261121"]))
    sav_meta["attributes"] = {
        "method_family": "construction",
        "online_offline": "offline",
        "objective": "mean route length",
        "knowledge_tier": "verified_experiment",
        "problem_variant": "standard_cvrp",
        "paradigm": "sequential_construct",
        "complexity_class": "O(n^2)",
        "interface": "select_next_node",
        "eoh_map": {"status": "possible", "adapter_kind": "direct_entrypoint", "entrypoint": "select_next_node"},
        "applicable_regimes": {
            "strong_on": ["uniform_n50_n100", "loose_capacity", "pointwise_baseline"],
            "weak_on": ["multi_route_global_merging", "large_n_cvrplib"],
            "scale_notes": "原 8 规则逐点池在 hetero-288 上的固定单一最佳（SBS），但本质仍为单车顺序构造，落后于 Stage-2 R5 与并行 Clarke-Wright 合并。",
        },
        "interface_blueprint": {
            "skeleton_role": "单车顺序构造循环（与 NN 相同外层骨架），单步内最大化局部节约量",
            "evolvable_hook": "select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int",
            "state_maintained": ["current_node", "rest_capacity", "unvisited_nodes"],
            "invariants_and_constraints": ["仓库出发步 i=0 时 s(0,j)=0 恒成立，必须显式定义破平规则（最远客户 argmax d(0,j)）", "路线需求总和 <= Q"],
            "typical_pitfalls": ["易与 1964 并行 Clarke-Wright 路径合并混淆；若忽略 i=0 处 s(0,j)=0 退化则变为按索引顺序选点"],
        },
        "math_formulation": [
            {
                "expr": "s(i, j) = d(i, 0) + d(0, j) - d(i, j);  at i=0: tie-break by argmax_j d(0, j)",
                "variables": {"i": "当前节点", "j": "可行候选客户", "d(0,j)": "仓库到客户 j 距离"},
                "preconditions": "单车顺序构造接口 select_next_node，且满足三角不等式",
            }
        ],
        "artifact_refs": [
            {"kind": "repo_code", "commit": WORKBENCH_COMMIT_PIN, "path": "agent_skill_loop/cvrp_workbench/solvers.py", "sha256": solvers_sha},
        ],
        "evidence_bindings": _collect_bindings(summary, "savings_pointwise", core_suites),
    }
    sav_md = f"""# Savings formula used as a next-node score (Pointwise Savings)

将 Clarke–Wright 节约量公式 `s(i, j) = d(i, 0) + d(0, j) - d(i, j)` 用作单车顺序构造 `select_next_node` 的单步评分函数，**不同于**经典的并行路径合并版 Clarke–Wright（见 `method-lit-cvrp-construct-clarke-wright-savings-merge`）。

## 定义或方法步骤

1. 对当前节点 `i` 和所有容量可行未访问客户 `j in F`，计算局部节约量 `s(i, j) = d(i, 0) + d(0, j) - d(i, j)`。
2. 当 `i = 0`（仓库出发步）时，由于 `d(0, 0) = 0`，对所有候选均有 `s(0, j) = 0` 完全打平；此时破平规则选择距离仓库最远的客户 `argmax d(0, j)`（outside-in 起步）。
3. 当 `i != 0` 时，选取使 `s(i, j)` 最大的可行客户（等价于最小化 `d(i, j) - d(0, j)`，即 $\\alpha = 1$ 边界）。
4. 容量不足时强制返回仓库并开启新路径。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node`。
- 严格满足坐标缩放不变性（`0.00%` 极差）。

## 适用条件、假设与限制

- 仅在单条活动路径的末端贪心延伸，无法同时维护多条子路径并进行全局端点合并，因此系统性弱于并行 CW（`cw_parallel_merge`）。
- 未启用主动早返仓（`return 0`），也未利用剩余容量或孤立紧迫度信号。

## 来源及支持的具体结论

- 公式来自 `src-clarke-wright`（仅借用节约量表达式），统一全解评测结果来自 `src-cvrp-workbench-20261121`：

{_fmt_suite_table(summary, "savings_pointwise", core_suites)}

## 代码和评测关联

- 历史实现：`impl-cvrp-final-batch-best`；统一工作台参照：`agent_skill_loop/cvrp_workbench/solvers.py`（`savings_pointwise`）。
- 关联机制观察：`evidence-cvrp-depot-start-phase-h003`（阐明 $\\alpha=1$ 破平临界点）。

## 未确认项与冲突证据

- 不可将其评测成绩当作完整并行 Clarke–Wright 合并算法的复现；两者在所有 7 个套件上的差距均稳定存在。
"""
    _upsert("method-cvrp-savings-next-node", sav_meta, sav_md)

    # 3) method-lit-cvrp-construct-clarke-wright-savings-merge (Parallel CW — major substantive upgrade!)
    cw_meta = json.loads((entries_dir / "method-lit-cvrp-construct-clarke-wright-savings-merge.json").read_text(encoding="utf-8"))
    cw_meta["tags"] = sorted(set(cw_meta.get("tags", []) + ["parallel-merge", "cw-parallel-merge", "solve_cvrp", "standard-cvrp"]))
    cw_meta["source_refs"] = sorted(set(cw_meta.get("source_refs", []) + ["src-cvrp-workbench-20261121"]))
    cw_meta["relations"]["sources"] = sorted(set(cw_meta.get("relations", {}).get("sources", []) + ["src-cvrp-workbench-20261121"]))
    cw_meta["relations"]["problems"] = sorted(set(cw_meta.get("relations", {}).get("problems", []) + ["problem-cvrp"]))
    cw_meta["summary"] = "Classic parallel Clarke-Wright route-endpoint savings merge (1964) with local full-route implementation and multi-suite benchmark evidence across synthetic, EoH-S, and CVRPLib A/B/P/X."
    cw_meta["attributes"] = {
        "method_family": "parallel_merge",
        "online_offline": "offline",
        "objective": "total route length",
        "knowledge_tier": "verified_experiment",
        "problem_variant": "standard_cvrp",
        "paradigm": "parallel_merge",
        "complexity_class": "O(n^2 log n)",
        "interface": "solve_cvrp",
        "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
        "not_the_original": "Full CW merge requires route-endpoint pool maintenance (solve_cvrp), not single-route select_next_node.",
        "origin": "openalex+grok-4.5-screen+local_verified_implementation",
        "applicable_regimes": {
            "strong_on": ["uniform", "clustered", "n_50_to_1000", "cvrplib_abpx", "fast_full_route_initialization"],
            "weak_on": ["strict_minimum_vehicle_packing_without_local_search"],
            "scale_notes": "全解并行合并 O(n^2 log n)，在全部 7 个套件上显著领先所有 select_next_node 逐点规则（含 R5 与 R7），且 n=200 求解 P50 仅数毫秒，是局部搜索的标准强初始解。",
        },
        "interface_blueprint": {
            "skeleton_role": "维护全部活动路径字典 routes、路径总负载 route_load 与节点归属表 owner；按节约量降序扫描所有客户对 (i,j)，仅合并两条不同路径的端点且满足载重和 <= Q",
            "evolvable_hook": "savings_score(i, j, dmat, demands, capacity, route_state) -> float 或动态合并优先级函数",
            "state_maintained": ["routes: dict[int, list[int]]", "route_load: dict[int, float]", "owner: list[int]"],
            "invariants_and_constraints": ["任意时刻客户 1..n 构成 routes 的精确划分", "每条路径负载 route_load[r] <= Q", "仅允许端点与端点合并（禁止内部节点合并形成分叉）", "必要时翻转子路径保持对称距离等价"],
            "typical_pitfalls": ["误合并内部节点导致非法分叉路径", "合并后漏更新被并入路径全部节点的 owner 映射", "将逐点 savings 评分误标为完整 CW 合并"],
        },
        "math_formulation": [
            {
                "expr": "s(i, j) = d(0, i) + d(0, j) - d(i, j),   for 1 <= i < j <= n",
                "variables": {"d(0,i)": "仓库到客户 i 距离", "d(0,j)": "仓库到客户 j 距离", "d(i,j)": "客户 i 与 j 间距离"},
                "preconditions": "对称距离矩阵（欧氏浮点 euc_2d_float 或 TSPLIB 取整 euc_2d_nint）；仅保留 s(i,j) > 0 的有效合并对",
            },
            {
                "expr": "Merge(R_a, R_b) feasible iff R_a != R_b, i in endpoints(R_a), j in endpoints(R_b), load(R_a) + load(R_b) <= Q",
                "variables": {"R_a, R_b": "两条不同活动路径", "load(R)": "路径客户需求之和", "Q": "车辆容量上限"},
                "preconditions": "无时间窗与最大车数硬约束；若需控制车数须在后处理或带约束变体中处理",
            },
        ],
        "artifact_refs": [
            {"kind": "repo_code", "commit": WORKBENCH_COMMIT_PIN, "path": "agent_skill_loop/cvrp_workbench/solvers.py", "sha256": solvers_sha},
            {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/selection_s2/run_matrix_s2.py", "sha256": _sha256_file_lf(REPO / "experiments/cvrp_midterm/selection_s2/run_matrix_s2.py")},
        ],
        "evidence_bindings": _collect_bindings(summary, "cw_parallel_merge", core_suites),
    }
    cw_md = f"""# Clarke-Wright savings merge (Parallel CW)

经典 1964 并行 Clarke–Wright 节约合并算法（`cw_parallel_merge`），已在本仓库落地为可独立校验的全解求解器并在全部 7 类 CVRP 套件上完成统一分离测时评测。

## 定义或方法步骤

1. **初始化单客户路径池**：为每个客户 $i \\in \\{{1,\\dots,n\\}}$ 建立独立往返路径 $R_i = [0, i, 0]$，记录 `route_load[i] = q_i` 与归属 `owner[i] = i`。
2. **计算并排序正节约量对**：对全部无序客户对 $1 \\le i < j \\le n$ 计算 $s(i, j) = d(0, i) + d(0, j) - d(i, j)$，过滤 $s(i, j) > 10^{{-12}}$ 后按降序稳定排序（`mergesort`）。
3. **并行端点合并主循环**：依次考察 $(i, j)$：
   - 若 `owner[i] == owner[j]`（同路径）或 `route_load[ri] + route_load[rj] > Q + 1e-12`（超容），跳过；
   - 检查端点不变量：$i$ 必须是 $R_{{ri}}$ 的首/尾节点，且 $j$ 必须是 $R_{{rj}}$ 的首/尾节点（禁止路径内部节点合并）；
   - 按端点朝向翻转必要子段使 $i$ 位于 $R_{{ri}}$ 尾部、$j$ 位于 $R_{{rj}}$ 头部，拼接为 `merged = seq_i + seq_j`，累加 `route_load[ri]` 并更新 $R_{{rj}}$ 内全部节点的 `owner`。
4. **输出与独立验证**：输出显式路径列表 `[0, ..., 0]`，经 `verify_cvrp_solution` 核验客户覆盖、容量上限与距离重算。

## 适用条件、假设与限制

- 适用于对称标准 CVRP（`euc_2d_float` 与 `euc_2d_nint` 均可直接支持），严格满足坐标缩放不变性。
- 无法直接映射到单车顺序接口 `select_next_node`（需要全局多路径状态 `solve_cvrp` 骨架）。
- 仅靠一次贪心合并后，部分路径内仍存在边交叉或跨路径载重微调空间，叠加 `2-opt` 与 `relocate` 可进一步显著缩减总路程（见 `method-cvrp-intra-2opt`、`method-cvrp-inter-relocate`）。

## 来源及支持的具体结论

- 文献来源：`src-clarke-wright`（Clarke & Wright, 1964, DOI `10.1287/opre.12.4.568`）。
- 本地实测全解评测证据（`src-cvrp-workbench-20261121`，预算 `standard_500ms`）：

{_fmt_suite_table(summary, "cw_parallel_merge", core_suites)}

## 代码和评测关联

- 全解实现：`agent_skill_loop/cvrp_workbench/solvers.py:solve_cw_parallel_merge`；独立校验：`agent_skill_loop/cvrp_workbench/protocol.py:verify_cvrp_solution`。
- 逐实例结果与完整路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- 在 CVRPLib Set A/B/P（`cvrp_ext_cvrplib_abp_74`）上，官方 `.sol` BKS 严格固定路线数为 $k$，而当前并行 CW（`cw_parallel_merge`）与叠加 `relocate` 均按自由车数运行（`fixed_k_unconstrained_eval`）：其中 `cw_parallel_merge` 在 48/74（64.9%）上严格满足 `route_count == k`（同 $k$ 子集均差 `+5.49%` vs 全 74 例 `+5.48%`），25 例超出 $k$、1 例（`P-n55-k8`）少于 $k$（具体见 `results/summary.json` 的 `exact_k_compliance_rate` 与 `exact_k_mean_rel_gap`）；若需严格满足固定车数契约，须进一步接入固定车队约束合并或车数惩罚项。

## EoH 适配

- target_problem_id：`cvrp_construct` 不可直接映射（`not_mappable`）；在里程碑二计划期动态接口骨架（`solve_cvrp` / `full_route_skeleton`）下，可将节约量权重与合并优先级作为可进化 Hook。
"""
    _upsert("method-lit-cvrp-construct-clarke-wright-savings-merge", cw_meta, cw_md)

    # 4) method-cvrp-s2-r5-spiral (R5 — upgrade attributes & bind live workbench evidence!)
    r5_meta = json.loads((entries_dir / "method-cvrp-s2-r5-spiral.json").read_text(encoding="utf-8"))
    r5_meta["source_refs"] = sorted(set(r5_meta.get("source_refs", []) + ["src-cvrp-workbench-20261121"]))
    r5_meta["relations"]["sources"] = sorted(set(r5_meta.get("relations", {}).get("sources", []) + ["src-cvrp-workbench-20261121"]))
    r5_meta["attributes"].update({
        "knowledge_tier": "verified_experiment",
        "problem_variant": "standard_cvrp",
        "paradigm": "sequential_construct",
        "complexity_class": "O(n^2)",
        "interface": "select_next_node",
        "eoh_map": {"status": "possible", "adapter_kind": "direct_entrypoint", "entrypoint": "select_next_node"},
        "applicable_regimes": {
            "strong_on": ["uniform", "clustered", "n_50_to_200", "eccentric_depot", "scale_invariance_1e-3_to_1e3"],
            "weak_on": ["vs_parallel_merge_and_local_search"],
            "scale_notes": "在单车顺序构造接口下全面领先传统逐点规则（P0-120 较配对对照降 4.92%、hetero-288 单规则低于旧 8 规则池 VBS），并在共享 6 例精确复现 10.2714 与 17 次主动回仓；但跨范式对比仍落后于并行 CW 与局部搜索。",
        },
        "interface_blueprint": {
            "skeleton_role": "单车顺序构造骨架，支持候选函数在可行集非空时返回 0 触发合法主动早返仓",
            "evolvable_hook": "select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int",
            "state_maintained": ["current_node", "rest_capacity", "unvisited_nodes", "route_idx"],
            "invariants_and_constraints": ["所有几何量均经 scale 或 pair 无量纲化，保证 0.00% 坐标缩放漂移", "仅在 current_node != depot 时允许主动返回 0", "pressure 仅依赖当前车辆状态，不引入反重货偏置"],
            "typical_pitfalls": ["若去除两阶段 rem_routes 仓库出发分支，大 n=200 会显著退化", "若用 sum(dem)/rest_cap 代替 mean(dem)/rest_cap 会导致 pressure 饱和引发过早回仓"],
        },
        "math_formulation": [
            {
                "expr": "score(i,j) = (d(i,j) - alpha_eff * d(0,j))/scale + 0.35*rho(i,j) - 0.10*fill(j) - 0.20*cos(theta_0)",
                "variables": {
                    "scale": "mean(d_dep) + mean(d_cur) + 1e-12",
                    "alpha_eff": "1.02 - 0.85 * min(1, mean(q_F)/rest_cap)",
                    "rho(i,j)": "d(i,j) / max(d(0,i) + d(0,j), 1e-12)",
                    "fill(j)": "q_j / (rest_cap + 1e-12)",
                    "cos(theta_0)": "(d(0,i)^2 + d(0,j)^2 - d(i,j)^2) / (2 d(0,i) d(0,j))",
                },
                "preconditions": "中程步 current_node != depot；欧氏/度量距离矩阵",
            },
            {
                "expr": "voluntary_early_return (return 0) iff max(q_F) > 0.55*rest_cap and (1 - rho_best) < 0.25 + 0.50*pressure",
                "variables": {"1 - rho_best": "最佳候选的归一化节约率 sigma", "pressure": "min(1, mean(q_F)/rest_cap)"},
                "preconditions": "避免跨仓库长距离跳接，在剩余载重收紧时提前回仓补满",
            },
        ],
        "artifact_refs": [
            {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/selection_s2/rules_s2/s2_r5_spiral.py", "sha256": r5_sha},
            {"kind": "repo_code", "commit": WORKBENCH_COMMIT_PIN, "path": "agent_skill_loop/cvrp_workbench/pointwise_adapter.py", "sha256": _sha256_file_lf(REPO / "agent_skill_loop/cvrp_workbench/pointwise_adapter.py")},
        ],
        "evidence_bindings": _collect_bindings(summary, "s2_r5_spiral", core_suites + ["shared_diagnostic_6"]),
    })
    r5_md = (entries_dir / "method-cvrp-s2-r5-spiral.md").read_text(encoding="utf-8")
    if "cvrp_final_accept_120" not in r5_md:
        r5_md = r5_md.replace(
            "## 代码和评测关联",
            f"### 统一工作台多套件复算结果（`cvrp_workbench_v1`, 预算 `standard_500ms`）\n\n{_fmt_suite_table(summary, 's2_r5_spiral', core_suites + ['shared_diagnostic_6'])}\n\n## 代码和评测关联",
        )
    _upsert("method-cvrp-s2-r5-spiral", r5_meta, r5_md)

    # 5) Upgrade Gillett-Miller Sweep
    sw_meta = json.loads((entries_dir / "method-lit-cvrp-clustered-gillett-miller-sweep.json").read_text(encoding="utf-8"))
    sw_meta["tags"] = sorted(set(sw_meta.get("tags", []) + ["sweep", "polar-angle", "cluster-first", "standard-cvrp"]))
    sw_meta["attributes"].update({
        "knowledge_tier": "literature_abstract",
        "problem_variant": "standard_cvrp",
        "paradigm": "cluster_first",
        "complexity_class": "O(n^2)",
        "interface": "solve_cvrp",
        "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
        "applicable_regimes": {
            "strong_on": ["central_depot", "clustered_spatial", "planar_2d_coordinates"],
            "weak_on": ["eccentric_depot", "non_euclidean_distance_matrix"],
            "scale_notes": "极角排序仅 O(n log n)，切分后各扇区做路内 TSP/2-opt 总复杂度 O(n^2)，适合中心仓库平面聚类算例。",
        },
        "interface_blueprint": {
            "skeleton_role": "先按仓库极角排序所有客户，再按容量上限顺时针/逆时针贪心切分扇区集群，最后对每个集群独立求 TSP 路线并做相邻扇区边界交换",
            "evolvable_hook": "sector_ordering_key(coords, demands, depot) 与 boundary_swap_priority(cluster_a, cluster_b)",
            "state_maintained": ["polar_angles", "clusters: list[list[int]]", "cluster_loads"],
            "invariants_and_constraints": ["客户严格二维坐标定义极角", "每个扇区需求总和 <= Q", "须枚举多个起始极角消除切口偏置"],
            "typical_pitfalls": ["偏心仓库下按单一极角切分易形成狭长径向带，质量明显劣于并行 CW", "仅做一次固定 0 弧度起扫会错过更优扇区边界"],
        },
        "math_formulation": [
            {
                "expr": "theta_i = atan2(y_i - y_0, x_i - x_0) in (-pi, pi]",
                "variables": {"(x_0, y_0)": "仓库坐标", "(x_i, y_i)": "客户 i 坐标"},
                "preconditions": "需要显式二维平面坐标，仅靠抽象距离矩阵无法直接计算极角",
            }
        ],
    })
    sw_md = (entries_dir / "method-lit-cvrp-clustered-gillett-miller-sweep.md").read_text(encoding="utf-8")
    _upsert("method-lit-cvrp-clustered-gillett-miller-sweep", sw_meta, sw_md)

    # 6) Upgrade Granular Tabu Search (Toth & Vigo)
    gts_meta = json.loads((entries_dir / "method-lit-cvrp-local-granular-tabu-search.json").read_text(encoding="utf-8"))
    gts_meta["tags"] = sorted(set(gts_meta.get("tags", []) + ["granular-tabu", "metaheuristic", "standard-cvrp"]))
    gts_meta["attributes"].update({
        "knowledge_tier": "literature_abstract",
        "problem_variant": "standard_cvrp",
        "paradigm": "metaheuristic",
        "complexity_class": "O(k*n^2)",
        "interface": "solve_cvrp",
        "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
        "applicable_regimes": {
            "strong_on": ["large_n_200_to_1000", "cvrplib_abpx", "high_quality_metaheuristic"],
            "weak_on": ["sub_millisecond_budget"],
            "scale_notes": "通过粒度阈值剪枝约 80%-90% 长边，使大 n 下的 Tabu 邻域评估仍保持接近线性稀疏度。",
        },
        "interface_blueprint": {
            "skeleton_role": "构建稀疏粒度边集 E_g = {(i,j) : d(i,j) <= beta * z_bar / (n + k)} 并保留仓库边与当前解边；仅在 E_g 诱导的候选移动（relocate/swap/2-opt*）上执行带禁忌表与破禁准则的迭代搜索",
            "evolvable_hook": "granularity_threshold_schedule(iter, stagnation, z_best) 与 move_penalized_score(delta, freq, tabu_state)",
            "state_maintained": ["routes", "granular_neighbors", "tabu_tenure_table", "penalty_weights"],
            "invariants_and_constraints": ["仓库关联边始终留在稀疏图中防止断连", "停滞期动态放宽 beta 触发多样性重启动", "最终输出必须满足严格容量可行"],
            "typical_pitfalls": ["beta 过小导致可行移动过稀陷入死胡同", "允许不可行中间解但未实现自适应容量惩罚恢复机制"],
        },
        "math_formulation": [
            {
                "expr": "vartheta = beta * (z_bar / (n + K));   E_g = {(i,j) : d(i,j) <= vartheta} U {(0,i)}",
                "variables": {"beta": "稀疏度系数（典型 1.0..2.0）", "z_bar": "快速初始解总路程", "n": "客户数", "K": "路径数"},
                "preconditions": "欧氏或度量 CVRP；需配合稀疏邻接表预先过滤候选对",
            }
        ],
    })
    gts_md = (entries_dir / "method-lit-cvrp-local-granular-tabu-search.md").read_text(encoding="utf-8")
    _upsert("method-lit-cvrp-local-granular-tabu-search", gts_meta, gts_md)

    # 7-10) Upgrade non-standard CVRP variant cards with explicit problem_variant & variant_adaptation_note
    variant_upgrades = [
        (
            "method-lit-cvrp-minveh-solomon-insertion-minimise-vehicles",
            "vrptw",
            "insertion",
            "原方法面向带时间窗的 VRPTW（最小化车数 + 里程），插入代价 c_1(i,u,j) 同时包含距离增量与推迟到达时间增量。向无时间窗标准 CVRP 迁移时，须将时间窗权重置零（alpha_2=0），仅保留纯空间绕行增量 c_11 = d(i,u)+d(u,j)-mu*d(i,j) 与容量约束 q_u <= rest_cap，并改用标准 CVRP 最便宜插入/Regret-k 校验（见 method-cvrp-cheapest-regret-insertion）。",
        ),
        (
            "method-lit-vrptw-solomon-i1-i2-insertion",
            "vrptw",
            "insertion",
            "Solomon I1/I2 原文包含严格时间窗 [e_i, l_i] 与等待时间推迟约束。迁移至标准无时间窗 CVRP 时，删除时间窗可行性判定与 b_j 时间推迟项，保留带径向偏置的 c_2(i,u,j) = lambda*d(0,u) - c_11(i,u,j) 即可转化为标准 CVRP 顺序/并行插入构造，须用独立 CVRP 路线校验器复核客户覆盖与容量。",
        ),
        (
            "method-lit-darp-iterated-vns-for-dial-a-ride",
            "darp",
            "metaheuristic",
            "原文献针对带乘客上下车配对、先后序与最大乘车时间约束的多目标拨号乘车问题（DARP），并非标准 CVRP 的 VNS。标准 CVRP 下的变邻域搜索请使用 method-cvrp-vns（直接基于单客户需求容量约束与 2-opt/Or-opt/relocate/swap/2-opt* 邻域，无需配对与时间窗校验）。",
        ),
        (
            "method-lit-ovrp-modified-clarke-wright-for-ovrp",
            "ovrp",
            "parallel_merge",
            "开放式车辆路径问题（OVRP）不要求车辆返回仓库，因此端点合并公式与标准闭环 CVRP 不同（不再节省返程边 d(i,0) 或 d(j,0)）。迁移回标准闭环 CVRP 时必须恢复完整闭环节约量 s(i,j)=d(0,i)+d(0,j)-d(i,j) 并强制所有路径起止于仓库 0（见 method-lit-cvrp-construct-clarke-wright-savings-merge）。",
        ),
    ]
    for eid, pvar, parad, adapt_note in variant_upgrades:
        m = json.loads((entries_dir / f"{eid}.json").read_text(encoding="utf-8"))
        m["attributes"].update({
            "knowledge_tier": "literature_abstract",
            "problem_variant": pvar,
            "paradigm": parad,
            "complexity_class": "O(k*n^2)" if parad == "metaheuristic" else "O(n^2)",
            "variant_adaptation_note": adapt_note,
        })
        body = (entries_dir / f"{eid}.md").read_text(encoding="utf-8")
        _upsert(eid, m, body)

    # 11) Upgrade evidence-cvrp-depot-start-phase-h003
    h3_meta = json.loads((entries_dir / "evidence-cvrp-depot-start-phase-h003.json").read_text(encoding="utf-8"))
    h3_meta["summary"] = (
        "For s_alpha(0,j)=(1-alpha)*d(0,j), minimizing rank switches at alpha=1; strictly preserving frozen V0's mid-route code and swapping only V0's depot-start step reduces P0-120 total tour length by 7.9730% (22.3910 -> 20.6058, 95% paired Bootstrap CI [6.88%, 9.00%], 94/120 wins); archived V0_decoupled_theory also omitted a -1e-6*dem tie-breaker in 1/24,397 mid-route states (heldout-200-08), yielding 7.9628% (20.6081, 94/120 wins)."
    )
    h3_meta["source_refs"] = sorted(set(h3_meta.get("source_refs", []) + ["src-cvrp-workbench-20261121"]))
    h3_meta["relations"]["sources"] = sorted(set(h3_meta.get("relations", {}).get("sources", []) + ["src-cvrp-workbench-20261121"]))
    if isinstance(h3_meta["attributes"].get("suites"), dict):
        h3_meta["attributes"]["suites"]["P0-120"] = {
            "instances": 120,
            "v0_native_mean": 22.391,
            "v0_depot_only_strict_mean": 20.6058,
            "total_length_reduction_pct": 7.973,
            "bootstrap_ci95_pct": [6.88, 9.00],
            "wins": 94,
            "v0_decoupled_theory_mean": 20.6081,
            "v0_decoupled_theory_reduction_pct": 7.9628,
            "mid_route_state_diffs": 1,
            "changed_instances_vs_archived": ["heldout-200-08"],
        }
    h3_meta["attributes"].update({
        "knowledge_tier": "math_observation",
        "problem_variant": "standard_cvrp",
        "paradigm": "math_mechanism",
        "complexity_class": "O(1)",
        "applicable_regimes": {
            "strong_on": ["sequential_construct", "uniform", "clustered", "n_50_to_200"],
            "weak_on": ["already_decoupled_full_route_solvers"],
            "scale_notes": "对所有线性径向构造规则 s_alpha(i,j)=d(i,j)-alpha*d(0,j) 在任意规模下均成立；严格保留冻结 V0 中程逻辑并仅替换出仓步，在 P0-120 降低总路程 7.9730%（22.3910 -> 20.6058，95% CI [6.88%, 9.00%]，94/120 胜）；早期简化脚本 V0_decoupled_theory 因中程省略 -1e-6*dem 在 heldout-200-08（1/24,397 状态）分歧，对应 7.9628%（20.6081，同为 94/120 胜）。",
        },
        "math_formulation": [
            {
                "expr": "s_alpha(0, j) = d(0, j) - alpha * d(0, j) = (1 - alpha) * d(0, j)",
                "variables": {"alpha": "中程径向拉回权重", "d(0,j)": "仓库到客户 j 距离"},
                "preconditions": "仓库出发步 i = 0 且 d(0,0) = 0；最小化 s_alpha(0,j) 在 alpha = 1 处发生排序反转",
            }
        ],
        "evidence_bindings": [
            {
                "suite_id": "cvrp_hist_p0_120",
                "run_id": "stage2a_counterfactual",
                "algorithm_id": "v0",
                "metric": "mean_tour_length",
                "value": summary["suites"]["cvrp_hist_p0_120"]["algorithms"]["v0"]["overall"]["mean_tour_length"],
                "comparison_mode": "local_recomputed",
                "reference_note": "V0 native 22.3910 -> strict depot_only 20.6058 (-7.9730% [6.88%, 9.00%], 94/120 wins); archived V0_decoupled_theory 20.6081 (-7.9628%, 1/24397 mid-route tie-break diff on heldout-200-08)",
                "artifact_path": "frontend/h003_preview/data.js",
            },
            *_collect_bindings(summary, "s2_r5_spiral", ["cvrp_hist_p0_120", "cvrp_final_accept_120"]),
        ],
    })
    h3_md = """# CVRP depot-start alpha=1 ranking switch and counterfactual swap (H-003)

严格区分 `i == 0` 仓库出发步与中程路径构造步评分机制；在 `s_alpha(i, j) = d(i, j) - alpha * d(0, j)` 下，仓库出发步退化为 `(1 - alpha) * d(0, j)`，并在 `alpha = 1` 处发生最小化排序反转。

## 机制与反事实实验归因

- **理论相变边界**：当 `alpha < 1` 时优先选择近仓客户（inside-out），`alpha = 1` 时距离项恒为 `0`，当 `alpha > 1` 时反转为优先选择远端客户（outside-in）。
- **独立 `P0-120` 严格反事实替换（主证据，`n = 50/100/200` 各 40 例）**：
  - 严格保留冻结 `V0` 中程代码 `100%` 不变、仅将 `i == 0` 出发分支替换为远端重货优先时，平均路长从 `22.3910` 降至 **`20.6058`**，总路程下降 **`7.9730%`**（`7.97%`，95% 配对 Bootstrap CI `[6.88%, 9.00%]`，10,000 次重采样 0 次非正，**`94/120` 胜、`26/120` 负**）。
  - 分规模均值：`n=50` `11.5344 -> 11.4556`（`-0.68%`）；`n=100` `20.1761 -> 18.4766`（`-8.42%`）；`n=200` `35.4626 -> 31.8852`（`-10.09%`，`40/40` 全胜）。
- **与历史 `V0_decoupled_theory` 脚本差异说明**：
  - 早期归档 `V0_decoupled_theory`（`experiments/cvrp_midterm/analysis/eval_s2_holdout.py`）在中程分支略去了冻结 `V0` 末尾 `-1e-6 * demands` 微小破平项；全量 120 例重放共 `24,397` 次中程状态中仅 **`1` 次**（`heldout-200-08`）发生选择分歧，对应均长 `20.6081`、降幅 **`7.9628%`**（`[6.88%, 8.98%]`，同为 `94/120` 胜）。两口径均证实在仓库出发步反转排序是收益的核心因果来源。

## 定义或方法步骤

1. 显式判别 `current_node == depot` 与 `current_node != depot` 两个阶段。
2. 仓库出发步禁止直接套用中程净节约 / 径向惩罚公式，应依据剩余车次规模或远端外扫目标选择种子客户。
3. 中程步保留局部几何与容量权衡，不在已验证规则（如 `V0`、`s2_r5_spiral`）中混入未标定尺度的绝对需求/带宽常项（见 `H-001`）。

## 适用条件、假设与限制

- 对满足三角不等式的欧氏标准 CVRP 构造策略普遍成立；当全解并行合并或局部搜索接管后（如 `cw_relocate_2opt`），出发步顺序不再是决定瓶颈。

## 来源及支持的具体结论

- 分析脚本与对照重放：`experiments/cvrp_midterm/analysis/boundary_analysis.py`、`experiments/cvrp_midterm/analysis/eval_s2_holdout.py`、`frontend/h003_preview/build_data.py`。
- `P0-120` 与 `Final-Accept-120` 工作台同协议绑定见 `attributes.evidence_bindings`。

## 代码和评测关联

- 严格反事实与历史对照重放脚本：`frontend/h003_preview/build_data.py`（产出 `frontend/h003_preview/data.js`）。
- 历史分析与盲测基线脚本：`experiments/cvrp_midterm/analysis/boundary_analysis.py`、`experiments/cvrp_midterm/analysis/eval_s2_holdout.py`。

## 未确认项与冲突证据

- 最优出发策略仍与剩余总需求车数比 `rem_routes = sum(q)/rest_capacity` 相关：末期残余很少时近邻紧凑种子可能优于纯外围种子。
- 本卡片针对顺次构造接口 `select_next_node` 验证；在大型 Set X（`n=500..1000`）上多阶段并行搜索显著更优。
"""
    _upsert("evidence-cvrp-depot-start-phase-h003", h3_meta, h3_md)

    # ------------------------------------------------------------------
    # B. CREATE NEW COMPREHENSIVE STANDARD CVRP CARDS (15 cards)
    # ------------------------------------------------------------------

    # N1) Petal clustering & set partitioning
    _upsert(
        "method-cvrp-petal-cluster-construct",
        {
            "type": "method",
            "title": "CVRP Petal cluster-first route-second and set partitioning heuristic",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "petal", "sweep", "cluster-first", "set-partitioning", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Extends polar-angle Sweep by enumerating feasible contiguous angular petals and solving a set-partitioning dynamic program or IP over petals to form complete CVRP routes.",
            "attributes": {
                "knowledge_tier": "literature_abstract",
                "problem_variant": "standard_cvrp",
                "paradigm": "cluster_first",
                "complexity_class": "O(n^2)",
                "interface": "solve_cvrp",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["central_depot", "planar_2d", "clustered_sectors"],
                    "weak_on": ["eccentric_depot", "overlapping_radial_rings"],
                    "scale_notes": "比单次 Sweep 消除起始极角切口偏置，在中心仓库平面算例上常显著优于 Sweep，仍需要后接路间局部搜索消除扇区边界锯齿。",
                },
                "interface_blueprint": {
                    "skeleton_role": "按极角排列客户序列；枚举全部需求不超过容量 Q 的连续极角片段作为候选花瓣（1-petal / 2-petal），用快速 TSP/2-opt 估算每瓣代价，再用最短路 DP 或集合划分选择不重叠花瓣覆盖全部客户",
                    "evolvable_hook": "petal_cost_estimator(petal_nodes, dmat, demands, Q) 与 petal_candidate_filter(angles, radii)",
                    "state_maintained": ["angular_order", "candidate_petals", "petal_costs", "dp_partition_table"],
                    "invariants_and_constraints": ["所选花瓣构成客户 1..n 的精确划分", "每片花瓣总需求 <= Q", "花瓣内部路径起止于仓库 0"],
                    "typical_pitfalls": ["枚举全部花瓣时若对每瓣做高耗时 TSP 会超预算", "偏心仓库时仅按极角划分会导致跨环长边"],
                },
                "math_formulation": [
                    {
                        "expr": "min sum_{p in P} c_p x_p   s.t.  sum_{p ni i} x_p = 1 (forall i=1..n),  sum_{i in p} q_i <= Q",
                        "variables": {"P": "由连续极角片段生成的候选花瓣集合", "c_p": "花瓣 p 的闭环路径长度", "x_p": "二进制选取变量"},
                        "preconditions": "二维平面客户坐标；当仅允许连续单扇区花瓣时可用环上 O(n*K_max) 最短路 DP 精确求解",
                    }
                ],
                "artifact_refs": [],
                "evidence_bindings": [],
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-lit-cvrp-clustered-gillett-miller-sweep"], "sources": ["src-foster-ryan-1976-petal"]},
            "source_refs": ["src-foster-ryan-1976-petal"],
            "evidence_refs": ["literature:10.1057/jors.1976.63"],
            "code_refs": [],
        },
        """# CVRP Petal cluster-first route-second and set partitioning heuristic

花瓣算法（Petal / 2-Petal）是 Gillett–Miller 极角扫描（Sweep）的自然推广：不再只做单次贪心扇区切分，而是生成大量可行极角花瓣并利用最短路 DP 或集合划分选出全局最优组合。

## 定义或方法步骤

1. 以仓库为原点计算所有客户极角 $\\theta_i = \\operatorname{atan2}(y_i - y_0, x_i - x_0)$ 并按极角排序形成环序列 $\\pi = (\\pi_1, \\dots, \\pi_n)$。
2. 对每个起点 $a$ 与连续长度 $L$，只要 $\\sum_{t=a}^{a+L-1} q_{\\pi_t} \\le Q$，生成候选花瓣 $p = [\\pi_a, \\dots, \\pi_{a+L-1}]$，用快速构造 + 2-opt 计算闭环代价 $c_p$。
3. 在环序列上构造有向无环图（边 $a \\to a+L$ 权重为 $c_p$），枚举起始切口运行最短路 DP（或求解集合划分整数规划）选出最小总代价的不重叠花瓣集合。
4. 将选中花瓣对应的路线合并为完整 CVRP 解，可选叠加路间 `relocate / 2-opt*` 消除扇区边界效应。

## 适用条件、假设与限制

- 依赖二维平面坐标，适用于中心仓库、空间聚类或扇形分布标准 CVRP。
- 无法映射到 `select_next_node`，属于 `cluster_first` / `solve_cvrp` 范式。

## 来源及支持的具体结论

- Foster & Ryan (1976), *Operational Research Quarterly* 27(2): 367–384（`src-foster-ryan-1976-petal`）。
- 相比单次 Sweep，Petal 显著降低切口敏感性并直接受益于花瓣内 2-opt 精度。

## 代码和评测关联

- 关联 Sweep 文献卡：`method-lit-cvrp-clustered-gillett-miller-sweep`；本地尚未将该算法纳入 7 条基准参照，保留为里程碑二动态接口候选骨架。

## 未确认项与冲突证据

- 尚未在本仓库 7 个 CVRP 套件上直接测算 1-Petal / 2-Petal 实测曲线，待里程碑二计划期骨架验证。
""",
    )

    # N2) Cheapest & Regret-k Insertion for Standard CVRP
    _upsert(
        "method-cvrp-cheapest-regret-insertion",
        {
            "type": "method",
            "title": "Standard CVRP cheapest detour and Regret-k route insertion",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "insertion", "cheapest-insertion", "regret-k", "regret-2", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Time-window-free standard CVRP route insertion comparing minimum-detour cheapest insertion and Regret-k (k=2,3) lookahead insertion across parallel routes, explicitly distinguished from Solomon VRPTW insertion.",
            "attributes": {
                "knowledge_tier": "local_implementation",
                "problem_variant": "standard_cvrp",
                "paradigm": "insertion",
                "complexity_class": "O(n^2 log n)",
                "interface": "solve_cvrp",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["tight_capacity", "bimodal_demands", "lns_repair_operator", "clustered"],
                    "weak_on": ["very_large_n_without_candidate_list"],
                    "scale_notes": "Regret-2 / Regret-3 插入在紧容量与双峰需求下显著避免将重货或偏远客户推迟到最后单独开车的尾部灾难，同时也是 LNS/ALNS 的核心修复算子。",
                },
                "interface_blueprint": {
                    "skeleton_role": "维护当前多条路径集合与剩余容量；每轮对所有未插入客户计算在全部可行路径各位置的最小插入增量 Delta_1(u) 及次优路径增量 Delta_2(u)，按最小 Delta_1（Cheapest）或最大 Regret_k = sum_{m=2..k}(Delta_m - Delta_1) 选择下一个插入客户与位置",
                    "evolvable_hook": "insertion_priority(u, best_route_deltas, demand_u, route_loads, d_depot_u) -> float",
                    "state_maintained": ["routes", "route_loads", "unrouted_customers", "best_insertion_cache"],
                    "invariants_and_constraints": ["仅在 route_load[r] + q_u <= Q 的路径中计算可行插入", "若某客户在所有现有路径均超容，则允许新开单客户路径 [0, u, 0]（插入代价 2*d(0,u)）", "增量更新仅需重算刚被修改那条路径的插入代价"],
                    "typical_pitfalls": ["未考虑开新路径 [0, u, 0] 导致紧容量实例提前卡死", "朴素 O(n^3) 每步全量重算在大 n 下超时，须增量维护每条路径的最优插槽"],
                },
                "math_formulation": [
                    {
                        "expr": "Delta(u; r, p) = d(r_{p-1}, u) + d(u, r_p) - d(r_{p-1}, r_p)",
                        "variables": {"u": "待插入客户", "r": "目标路径", "p": "插入位置索引"},
                        "preconditions": "无时间窗标准 CVRP；满足容量约束 load(r) + q_u <= Q",
                    },
                    {
                        "expr": "Regret_k(u) = sum_{m=2}^{k} (Delta_{(m)}(u) - Delta_{(1)}(u))",
                        "variables": {"Delta_{(m)}(u)": "客户 u 在第 m 好可行路径上的最小插入增量"},
                        "preconditions": "优先插入 Regret_k(u) 最大的客户（若仅有一条可行路径则赋予大惩罚值立即插入）",
                    },
                ],
                "artifact_refs": [],
                "evidence_bindings": [],
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": [
                    "method-lit-vrptw-solomon-i1-i2-insertion",
                    "method-lit-cvrp-minveh-solomon-insertion-minimise-vehicles",
                    "method-cvrp-lns-shaw-regret",
                ],
                "sources": ["src-ropke-pisinger-2006-alns"],
            },
            "source_refs": ["src-ropke-pisinger-2006-alns"],
            "evidence_refs": ["literature:10.1287/trsc.1050.0135"],
            "code_refs": [],
        },
        """# Standard CVRP cheapest detour and Regret-k route insertion

标准无时间窗 CVRP 下的最小绕行插入（Cheapest Insertion）与后悔值插入（Regret-$k$ Insertion），明确区别于面向 VRPTW 的 Solomon I1/I2 插入卡片。

## 定义或方法步骤

1. **初始化种子路径**：选取 $K_0$ 个远端或高需求种子客户初始化若干条路径 $[0, s_r, 0]$，或从空路径集起步（允许动态新开路径 $[0, u, 0]$，增量代价 $2 d(0, u)$）。
2. **可行插槽增量计算**：对每个未插入客户 $u$ 与每条满足 $\\text{load}(r) + q_u \\le Q$ 的路径 $r$，计算最优插槽增量 $\\Delta^*(u, r) = \\min_p [d(r_{p-1}, u) + d(u, r_p) - d(r_{p-1}, r_p)]$。
3. **选择准则**：
   - **Cheapest Insertion**：选取 $\\arg\\min_u \\Delta_{(1)}(u)$；
   - **Regret-$k$ Insertion**（常用 $k=2$ 或 $k=3$）：将每个客户在各可行路径上的最优增量升序排列为 $\\Delta_{(1)}(u) \\le \\Delta_{(2)}(u) \\le \\dots$，优先插入 $\\operatorname{Regret}_k(u) = \\sum_{m=2}^k (\\Delta_{(m)}(u) - \\Delta_{(1)}(u))$ 最大的客户，以最小 $\\Delta_{(1)}(u)$ 破平。
4. 将选中客户插入最优位置并更新该路径负载与插入缓存，重复直至全部客户插入完毕。

## 适用条件、假设与限制

- 严格适用于标准无时间窗 CVRP（无需到达时刻或等待时间约束）；当从 Solomon I1/I2 迁移时，时间窗推迟权重置零即退化为此类纯距离+容量插入。
- 无法映射至 `select_next_node`（每次在任意已有路径中间插入），属于 `solve_cvrp` 全解构造及 LNS 修复范式。

## 来源及支持的具体结论

- Ropke & Pisinger (2006), *Transportation Science* 40(4): 455–472（`src-ropke-pisinger-2006-alns`）系统证明了 Regret-$k$ 插入作为构造与 LNS 修复算子在紧密约束下的稳定性。

## 代码和评测关联

- 与 VRPTW 变体卡 `method-lit-vrptw-solomon-i1-i2-insertion`、`method-lit-cvrp-minveh-solomon-insertion-minimise-vehicles` 显式区分；与 `method-cvrp-lns-shaw-regret` 互为修复算子关联。

## 未确认项与冲突证据

- 朴素实现的 Regret-$k$ 在 $n=1000$ 规模下需配合增量缓存或候选路径剪枝才能满足 500 ms 预算；待里程碑二全解骨架基准化。
""",
    )

    # N3) Intra-route 2-opt (VERIFIED EXPERIMENT with cw_2opt!)
    _upsert(
        "method-cvrp-intra-2opt",
        {
            "type": "method",
            "title": "Standard CVRP intra-route 2-opt edge reversal (cw_2opt)",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "2-opt", "2opt", "local-search", "intra-route", "cw-2opt", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Deterministic O(1)-delta intra-route 2-opt edge reversal applied per CVRP route (tested as cw_2opt on top of parallel Clarke-Wright across all 7 Milestone-1 suites).",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "local_search",
                "complexity_class": "O(k*n^2)",
                "interface": "solve_cvrp",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["all_euclidean_cvrp", "removing_route_crossings", "fast_post_processing"],
                    "weak_on": ["inter_route_load_rebalancing", "reducing_vehicle_count"],
                    "scale_notes": "对每条子路径长度 m 仅需 O(m^2) 且 O(1) 增量判断，不改变路径需求负载（天然保持容量可行）；在全部 7 个套件上以极低额外耗时稳定缩短 CW 路程。",
                },
                "interface_blueprint": {
                    "skeleton_role": "接收初始可行路径集合（如并行 CW），对每条路径 [0, c_1..c_m, 0] 循环扫描子段反转 (i, j) 直至无严格改进移动或到达时间/轮次预算",
                    "evolvable_hook": "select_2opt_move(route, dmat, candidate_pairs, deltas) 或与扰动结合的接受策略",
                    "state_maintained": ["routes", "passes_used", "deadline_clock"],
                    "invariants_and_constraints": ["反转单个闭环子路径内部片段不改变客户集合与路线总需求，容量可行性恒保持", "对称距离矩阵下 delta = d(a,c)+d(b,d)-d(a,b)-d(c,d) 为精确 O(1) 代价差"],
                    "typical_pitfalls": ["在非对称距离矩阵中反转整段会导致段内方向代价变化（此时 O(1) 差值公式失效）", "内层重算整条路径代价会退化为 O(m^3)"],
                },
                "math_formulation": [
                    {
                        "expr": "Delta_2opt(i, j) = d(r_{i-1}, r_j) + d(r_i, r_{j+1}) - d(r_{i-1}, r_i) - d(r_j, r_{j+1}) < -eps",
                        "variables": {"r_i..r_j": "被反转的客户子段", "r_{i-1}, r_{j+1}": "断边外侧端点（边界处为仓库 0）"},
                        "preconditions": "对称距离矩阵；单条容量可行路径内部改进",
                    }
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": WORKBENCH_COMMIT_PIN, "path": "agent_skill_loop/cvrp_workbench/solvers.py", "sha256": solvers_sha},
                ],
                "evidence_bindings": _collect_bindings(summary, "cw_2opt", core_suites),
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-lit-cvrp-construct-clarke-wright-savings-merge", "method-cvrp-inter-relocate"], "sources": ["src-croes-1958-2opt", "src-cvrp-workbench-20261121"]},
            "source_refs": ["src-croes-1958-2opt", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["literature:10.1287/opre.6.6.791", "report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
            "code_refs": [],
        },
        f"""# Standard CVRP intra-route 2-opt edge reversal (cw_2opt)

标准 CVRP 路内 `2-opt` 局部搜索（与并行 Clarke–Wright 组合为工作台参照 `cw_2opt`），通过反转单条路径内部连续子段消除路径自交与折返。

## 定义或方法步骤

1. 从任意容量可行完整解（本工作台参照为并行 `cw_parallel_merge`）出发，逐条处理长度 $m \\ge 2$ 的子路径 $r = [c_1, \\dots, c_m]$（首尾隐式连接仓库 `0`）。
2. 枚举断边索引 $0 \\le i < j < m$，令 $a = r_{{i-1}}$（$i=0$ 时为 `0`）、$b = r_i$、$c = r_j$、$d = r_{{j+1}}$（$j=m-1$ 时为 `0`），以 $O(1)$ 计算精确增量 $\\Delta = d(a, c) + d(b, d) - d(a, b) - d(c, d)$。
3. 若 $\\Delta < -10^{{-9}}$，立即原地反转切片 `r[i:j+1]`（First-Improvement），并继续扫描直至整轮无严格改进或达到显式时间/轮次预算。
4. 由于不跨路径移动客户，路线负载与车数保持不变，始终 100% 满足容量约束。

## 适用条件、假设与限制

- 要求距离矩阵对称（`euc_2d_float` 或 `euc_2d_nint`）；仅优化单条路径内部顺序，无法改善跨路径客户分配或缩减车辆数。
- 对并行 CW 初始解的二次精修开销极低（由于单条路径客户数 $m \\ll n$，总代价远小于全图 TSP 2-opt）。

## 来源及支持的具体结论

- 文献来源：`src-croes-1958-2opt`（Croes 1958）。
- 本仓库全解评测证据（`cw_2opt`, `src-cvrp-workbench-20261121`, 预算 `standard_500ms`）：

{_fmt_suite_table(summary, "cw_2opt", core_suites)}

## 代码和评测关联

- 实现源码：`agent_skill_loop/cvrp_workbench/solvers.py`（`_two_opt_single_route`, `solve_cw_2opt`）。
- 逐实例成绩与可对比路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- 单纯路内 2-opt 在路径边界交错严重时改善有限，需与路间 `relocate / swap / 2-opt*` 联合使用（见 `method-cvrp-inter-relocate`）。
""",
    )

    # N4) Intra-route Or-opt
    _upsert(
        "method-cvrp-intra-or-opt",
        {
            "type": "method",
            "title": "Standard CVRP intra-route Or-opt contiguous segment relocation",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "or-opt", "oropt", "local-search", "intra-route", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Relocates contiguous chains of length L in {1, 2, 3} to a better edge position within the same CVRP route using O(1) delta evaluation.",
            "attributes": {
                "knowledge_tier": "local_implementation",
                "problem_variant": "standard_cvrp",
                "paradigm": "local_search",
                "complexity_class": "O(k*n^2)",
                "interface": "local_move_operator",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["post_2opt_refinement", "clustered_subchains", "all_euclidean_cvrp"],
                    "weak_on": ["inter_route_rebalancing"],
                    "scale_notes": "是 3-opt 的高效受限子集（仅 O(m^2) 而非 O(m^3)），常与 2-opt 联合构成路内完全局部最优检查。",
                },
                "interface_blueprint": {
                    "skeleton_role": "对每条路径及段长 L in {1,2,3}，枚举连续段 (i..i+L-1) 抽出并插入同路径其余边 (k, k+1)（正向或反向），O(1) 计算 3 条旧边换 3 条新边的差值",
                    "evolvable_hook": "or_opt_priority(seg_len, delta, route_len) 或邻域切换顺序",
                    "state_maintained": ["routes", "segment_length_L"],
                    "invariants_and_constraints": ["插入目标边不得与抽出段内部重叠", "路内 Or-opt 不改变路径总需求，容量恒可行"],
                    "typical_pitfalls": ["目标索引 k 落在抽出段内部造成节点丢失或重复", "忽略 L=1 即等价于路内单点 relocate"],
                },
                "math_formulation": [
                    {
                        "expr": "Delta_OrOpt = [d(a, d) - d(a, b) - d(c, d)] + [d(u, b) + d(c, v) - d(u, v)]",
                        "variables": {"[b..c]": "长度为 L in {1,2,3} 的连续段", "a, d": "段原前后邻接节点", "(u, v)": "目标插入边"},
                        "preconditions": "单条路径内部移动；对称距离下可额外测试反转段 [c..b] 插入 (u,v)",
                    }
                ],
                "artifact_refs": [],
                "evidence_bindings": [],
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-cvrp-intra-2opt", "method-cvrp-vns"], "sources": ["src-or-1976-or-opt"]},
            "source_refs": ["src-or-1976-or-opt"],
            "evidence_refs": ["gap:standard-cvrp-or-opt-benchmark-pending-milestone2"],
            "code_refs": [],
        },
        """# Standard CVRP intra-route Or-opt contiguous segment relocation

标准 CVRP 路内 `Or-opt` 算子将单条路径中长度为 $L \\in \\{1, 2, 3\\}$ 的连续客户段整体平移至同一路径的另一条边之间，可视为 `3-opt` 的 $O(m^2)$ 高效子集。

## 定义或方法步骤

1. 对单条路径 $r = [0, c_1, \\dots, c_m, 0]$，依次扫描段长 $L \\in \\{1, 2, 3\\}$ 与起始下标 $i$，取出子段 $S = [b, \\dots, c]$（前驱 $a$，后继 $d$）。
2. 计算抽出增量 $\\Delta_{\\text{rem}} = d(a, d) - d(a, b) - d(c, d)$。
3. 枚举移除 $S$ 后剩余路径上的所有边 $(u, v)$，计算正向插入增量 $d(u, b) + d(c, v) - d(u, v)$（及可选反向插入 $d(u, c) + d(b, v) - d(u, v)$）。
4. 若总增量 $\\Delta < -10^{-9}$，执行搬移并继续迭代直至到达路内 Or-opt 局部最优或耗尽预算。

## 适用条件、假设与限制

- 不改变路径客户组成与总需求，天然保持 CVRP 容量约束；与 `2-opt` 交替使用可消除绝大部分路内次优折线。
- 属于局部改进算子（`local_move_operator`），需挂载在全解 `solve_cvrp` 或 RVND/VNS 框架下。

## 来源及支持的具体结论

- Or (1976)（`src-or-1976-or-opt`）；在 VRP 经典 RVND 架构（如 HGS / Vidal 等）中作为路内标准邻域与 2-opt 并列使用。

## 代码和评测关联

- 对应 TSP 侧既有条目：`method-tsp-or-opt-2`；标准 CVRP 全解工作台已将 `2-opt` 与 `relocate` 纳入首批 7 条基线，Or-opt 计划在里程碑二 RVND 骨架中统一评测。

## 未确认项与冲突证据

- 本里程碑尚未在 7 个 CVRP 套件上单独记录 `cw_or_opt` 消融表，已以 `gap:` 明确标注。
""",
    )

    # N5) Inter-route Relocate (VERIFIED EXPERIMENT with cw_relocate_2opt!)
    _upsert(
        "method-cvrp-inter-relocate",
        {
            "type": "method",
            "title": "Standard CVRP inter-route 1-0 relocate + intra-route 2-opt (cw_relocate_2opt)",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "relocate", "relocation", "local-search", "inter-route", "cw-relocate-2opt", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Budgeted inter-route 1-0 customer relocation with capacity-feasibility guards alternating with intra-route 2-opt (tested as cw_relocate_2opt across all 7 Milestone-1 suites).",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "local_search",
                "complexity_class": "O(k*n^2)",
                "interface": "solve_cvrp",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["all_euclidean_cvrp", "cvrplib_abpx", "eohs_cvrp", "vehicle_count_reduction", "heterogeneous_regimes"],
                    "weak_on": ["very_large_n_600_plus_under_tight_500ms_budget"],
                    "scale_notes": "7 条标准参照中质量最高；不仅显著缩短总路程，而且能清空单客户短路径以减少车辆数。在 n <= 200 套件上 500 ms 预算内几乎 100% 收敛至局部最优；在 Set X n > 500 大例上按时间预算截断并返回当前最优可行解。",
                },
                "interface_blueprint": {
                    "skeleton_role": "在并行 CW + 2-opt 初始解上循环扫描全部客户 u 的抽出代价与全部容量可行目标路径/插槽的插入代价（含同路径与跨路径），应用严格改进移位后对受影响路径增量执行 2-opt，并删除空路径",
                    "evolvable_hook": "relocate_move_score(delta, load_src, load_dst, cap, empties_route) 与候选邻域裁剪",
                    "state_maintained": ["routes: list[list[int]]", "loads: list[float]", "deadline_clock"],
                    "invariants_and_constraints": ["跨路径移位必须先检 loads[dst] + q_u <= Q + 1e-12", "若源路径移空则从路径池删除，减少车辆数", "任意时刻受预算截断均可返回当前可行解"],
                    "typical_pitfalls": ["同路径 relocate 时未修正移除位置导致的插入索引偏移 (+1/-1)", "缺少显式时间预算导致 n=1000 算例全量扫描超时"],
                },
                "math_formulation": [
                    {
                        "expr": "Delta_reloc(u: r_a -> r_b@p) = [d(a-, a+) - d(a-, u) - d(u, a+)] + [d(b-, u) + d(u, b+) - d(b-, b+)]",
                        "variables": {"u": "被搬移客户", "a-, a+": "u 在源路径 r_a 中的前后节点", "b-, b+": "目标路径 r_b 插槽 p 的前后节点"},
                        "preconditions": "若 r_a != r_b，须满足 load(r_b) + q_u <= Q",
                    }
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": WORKBENCH_COMMIT_PIN, "path": "agent_skill_loop/cvrp_workbench/solvers.py", "sha256": solvers_sha},
                ],
                "evidence_bindings": _collect_bindings(summary, "cw_relocate_2opt", core_suites),
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-lit-cvrp-construct-clarke-wright-savings-merge", "method-cvrp-intra-2opt", "method-cvrp-inter-swap"], "sources": ["src-cvrp-workbench-20261121"]},
            "source_refs": ["src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:docs/cvrp-kb-benchmark-frontend-final-plan.md"],
            "code_refs": [],
        },
        f"""# Standard CVRP inter-route 1-0 relocate + intra-route 2-opt (cw_relocate_2opt)

标准 CVRP 路间 `1-0 Relocate`（单客户跨路径/同路径重插入）与路内 `2-opt` 交替局部搜索（工作台参照 `cw_relocate_2opt`），是本里程碑 7 条参照算法中质量最强的全解参照。

## 定义或方法步骤

1. 以并行 Clarke–Wright（`cw_parallel_merge`）构造初始可行解，并先对每条路径执行一次路内 `2-opt`。
2. 外层局部搜索循环中，遍历每条路径 $r_a$ 上的每个客户 $u$：
   - 计算从 $r_a$ 抽出 $u$ 的 $O(1)$ 代价差 $\\Delta_{{\\text{{rem}}}} = d(a^-, a^+) - d(a^-, u) - d(u, a^+)$；
   - 扫描全部路径 $r_b$（若 $r_b \\ne r_a$ 则先检查容量不变量 $\\text{{load}}(r_b) + q_u \\le Q$）及其全部插槽 $p$，以 $O(1)$ 计算插入代价差 $\\Delta_{{\\text{{ins}}}} = d(b^-, u) + d(u, b^+) - d(b^-, b^+)$；
   - 选取使总差值 $\\Delta = \\Delta_{{\\text{{rem}}}} + \\Delta_{{\\text{{ins}}}} < -10^{{-9}}$ 最小的改进移动（Best-Improvement per node）。
3. 应用移位并更新 `loads[r_a]`、`loads[r_b]`；仅对发生变动的 $r_a, r_b$ 立即运行轻量路内 `2-opt`；若 $r_a$ 变空则将其移除（自动减少车队规模）。
4. 达到固定时间预算（`500 ms`）或外层轮次上限（`80` 轮）时安全返回当前最优可行解，并记录 `budget_exhausted` 标志。

## 适用条件、假设与限制

- 适用于全部对称标准 CVRP（`euc_2d_float` 与 `euc_2d_nint`）；属于 Anytime 局部搜索，预算耗尽时仍保证 100% 合法可行解。
- 当 $n > 500$（如 CVRPLib Set X 大例）且时间预算为 500 ms 时，全量 $O(n^2)$ 移位扫描可能触发预算截断，此时需配合粒度邻域裁剪（见 `method-lit-cvrp-local-granular-tabu-search`）。

## 来源及支持的具体结论

- 本仓库统一测时与独立校验结果（`cw_relocate_2opt`, `src-cvrp-workbench-20261121`, 预算 `standard_500ms`）：

{_fmt_suite_table(summary, "cw_relocate_2opt", core_suites)}

## 代码和评测关联

- 实现源码：`agent_skill_loop/cvrp_workbench/solvers.py:solve_cw_relocate_2opt`。
- 逐实例记录与可查看路线：`results/per_instance_records.json`、`routes/*.json`。

## 未确认项与冲突证据

- 1-0 Relocate 在紧容量满载路径之间可能被容量约束阻断，需与 1-1 `swap` 及 `2-opt*` 联合打破满载僵局（见 `method-cvrp-inter-swap`、`method-cvrp-inter-2opt-star`、`method-cvrp-vns`）。
""",
    )

    # N6) Inter-route 1-1 Swap
    _upsert(
        "method-cvrp-inter-swap",
        {
            "type": "method",
            "title": "Standard CVRP inter-route 1-1 swap (customer exchange)",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "swap", "exchange", "local-search", "inter-route", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Exchanges one customer from route A with one customer from route B whenever both post-swap loads respect capacity Q and total distance strictly decreases.",
            "attributes": {
                "knowledge_tier": "local_implementation",
                "problem_variant": "standard_cvrp",
                "paradigm": "local_search",
                "complexity_class": "O(k*n^2)",
                "interface": "local_move_operator",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["tight_capacity", "near_full_routes", "bimodal_demands"],
                    "weak_on": ["reducing_route_count_directly"],
                    "scale_notes": "当两条路径均接近满载导致 1-0 Relocate 无法单向迁入时，1-1 Swap 仅要求净负载差 |q_u - q_v| 满足余量，是紧容量工况下不可或缺的互补邻域。",
                },
                "interface_blueprint": {
                    "skeleton_role": "枚举不同路径对 (r_a, r_b) 上的客户对 (u, v)，先以 O(1) 校验双向容量不等式，再以 O(1) 计算 4 边替换增量",
                    "evolvable_hook": "swap_candidate_priority(delta, load_imbalance_change, dist_uv)",
                    "state_maintained": ["routes", "loads"],
                    "invariants_and_constraints": ["load(r_a) - q_u + q_v <= Q 且 load(r_b) - q_v + q_u <= Q", "仅交换不同路径节点（同路径 swap 可额外处理相邻节点边界）"],
                    "typical_pitfalls": ["同路径相邻节点 swap 时直接套用 4 边独立公式会重复计算中间边 (u,v)"],
                },
                "math_formulation": [
                    {
                        "expr": "Delta_swap = [d(a-,v)+d(v,a+)-d(a-,u)-d(u,a+)] + [d(b-,u)+d(u,b+)-d(b-,v)-d(v,b+)]",
                        "variables": {"u in r_a, v in r_b": "两条不同路径上的待交换客户", "a-/a+, b-/b+": "各自前后邻接节点"},
                        "preconditions": "r_a != r_b，且 load(r_a)-q_u+q_v <= Q、load(r_b)-q_v+q_u <= Q",
                    }
                ],
                "artifact_refs": [],
                "evidence_bindings": [],
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-cvrp-inter-relocate", "method-cvrp-vns"], "sources": ["src-mladenovic-hansen-1997-vns"]},
            "source_refs": ["src-mladenovic-hansen-1997-vns"],
            "evidence_refs": ["gap:standard-cvrp-swap-standalone-benchmark-pending-milestone2"],
            "code_refs": [],
        },
        """# Standard CVRP inter-route 1-1 swap (customer exchange)

标准 CVRP 路间 `1-1 Swap` 算子交换两条不同路径中的一对客户 $(u, v)$，专门解决紧容量满载路径间 `1-0 Relocate` 被单向容量卡死的问题。

## 定义或方法步骤

1. 遍历全部无序路径对 $r_a < r_b$ 与客户对 $u \\in r_a, v \\in r_b$。
2. 以 $O(1)$ 校验双向容量可行性：$\\text{load}(r_a) - q_u + q_v \\le Q$ 且 $\\text{load}(r_b) - q_v + q_u \\le Q$。
3. 以 $O(1)$ 计算 4 边替换差值 $\\Delta = [d(a^-, v) + d(v, a^+) - d(a^-, u) - d(u, a^+)] + [d(b^-, u) + d(u, b^+) - d(b^-, v) - d(v, b^+)]$。
4. 若 $\\Delta < -10^{-9}$，执行交换并同步更新 `loads[r_a]` 与 `loads[r_b]`，随后可触发轻量路内 `2-opt`。

## 适用条件、假设与限制

- 在 `tight_capacity` 与 `bimodal_demands`（如 `hetero-288` 紧容量工况及 CVRPLib 满载实例）中与 `1-0 Relocate` 高度互补。
- 单独使用无法减少路径数，需与 `relocate` / `2-opt*` 联合编排。

## 来源及支持的具体结论

- 经典 VRP 复合局部搜索基础算子（与 RVND / VNS 结合见 `src-mladenovic-hansen-1997-vns`、`method-cvrp-vns`）。

## 代码和评测关联

- 关联已验证参照：`method-cvrp-inter-relocate`（`cw_relocate_2opt`）、`method-cvrp-vns`。

## 未确认项与冲突证据

- 尚未单独发布 `cw_swap` 消融记录，计划随里程碑二 RVND 邻域组合统一基准化。
""",
    )

    # N7) Inter-route 2-opt*
    _upsert(
        "method-cvrp-inter-2opt-star",
        {
            "type": "method",
            "title": "Standard CVRP inter-route 2-opt* (tail exchange)",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "2-opt*", "2opt-star", "2optstar", "local-search", "inter-route", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Breaks one edge in each of two CVRP routes and cross-reconnects their tails (normal or reversed) when prefix+suffix loads satisfy capacity Q.",
            "attributes": {
                "knowledge_tier": "local_implementation",
                "problem_variant": "standard_cvrp",
                "paradigm": "local_search",
                "complexity_class": "O(k*n^2)",
                "interface": "local_move_operator",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["crossing_routes", "clustered_spatial", "medium_to_large_routes"],
                    "weak_on": ["extremely_short_routes_len_1_or_2"],
                    "scale_notes": "单次 O(1) 校验（借助每条路径预计算的前缀需求数组）即可整体交换两条相交路径的尾部，比逐点 relocate 更直接解开双路径交叉。",
                },
                "interface_blueprint": {
                    "skeleton_role": "为每条路径维护前缀和需求数组 pref_load；对任意两条不同路径 (r_a, r_b) 枚举断点 (i, j)，O(1) 判断顺接 (head_a + tail_b, head_b + tail_a) 与反接 (head_a + rev(head_b), rev(tail_a) + tail_b) 的容量与路程增量",
                    "evolvable_hook": "two_opt_star_priority(delta, orientation, load_balance)",
                    "state_maintained": ["routes", "prefix_loads", "total_loads"],
                    "invariants_and_constraints": ["顺接容量：pref_a[i] + (tot_b - pref_b[j]) <= Q 且 pref_b[j] + (tot_a - pref_a[i]) <= Q", "反接容量：pref_a[i] + pref_b[j] <= Q 且 (tot_a - pref_a[i]) + (tot_b - pref_b[j]) <= Q", "若产生空路径则直接移除实现车数缩减"],
                    "typical_pitfalls": ["遗漏对称 CVRP 下的反接方向（头接反转头 + 尾接反转尾），丢失一半可行解", "修改路径后未刷新 prefix_loads 导致容量越界"],
                },
                "math_formulation": [
                    {
                        "expr": "Delta_direct = d(a_i, b_{j+1}) + d(b_j, a_{i+1}) - d(a_i, a_{i+1}) - d(b_j, b_{j+1})",
                        "variables": {"(a_i, a_{i+1})": "路径 A 断开的边", "(b_j, b_{j+1})": "路径 B 断开的边"},
                        "preconditions": "顺接重连：pref_load(A,i) + suff_load(B,j+1) <= Q 且 pref_load(B,j) + suff_load(A,i+1) <= Q",
                    },
                    {
                        "expr": "Delta_rev = d(a_i, b_j) + d(a_{i+1}, b_{j+1}) - d(a_i, a_{i+1}) - d(b_j, b_{j+1})",
                        "variables": {"a_i, b_j": "两路径前半段末尾", "a_{i+1}, b_{j+1}": "两路径后半段起点"},
                        "preconditions": "对称距离下反接重连：pref_load(A,i) + pref_load(B,j) <= Q 且 suff_load(A,i+1) + suff_load(B,j+1) <= Q",
                    },
                ],
                "artifact_refs": [],
                "evidence_bindings": [],
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-cvrp-intra-2opt", "method-cvrp-inter-relocate", "method-cvrp-vns"], "sources": ["src-potvin-rousseau-1995-2opt-star"]},
            "source_refs": ["src-potvin-rousseau-1995-2opt-star"],
            "evidence_refs": ["literature:10.1057/jors.1995.204"],
            "code_refs": [],
        },
        """# Standard CVRP inter-route 2-opt* (tail exchange)

标准 CVRP 路间 `2-opt*` 算子（Potvin & Rousseau 1995）分别断开两条不同路径上的一条边并交叉重连两段尾部，能够以单步大结构移动彻底解开两条路径之间的空间交叉。

## 定义或方法步骤

1. 为每条路径预计算前缀需求累加数组 `pref_load[r][i]`，使任意切点的前半段与后半段负载均可 $O(1)$ 查询。
2. 对不同路径对 $(r_a, r_b)$ 与边对 $(a_i, a_{i+1}) \\in r_a$、$(b_j, b_{j+1}) \\in r_b$，同时检验两种合法重连方式：
   - **顺接尾部交换**：新路径为 `[0..a_i, b_{j+1}..0]` 与 `[0..b_j, a_{i+1}..0]`；
   - **对称反接重连**：新路径为 `[0..a_i, b_j..b_1, 0]` 与 `[0, a_m..a_{i+1}, b_{j+1}..0]`。
3. 两种方式均先用前缀数组在 $O(1)$ 内判定容量不变量 $\\le Q$，再以 $O(1)$ 比较 2 边替换差值 $\\Delta < -10^{-9}$。
4. 接受改进后重构两条路径并刷新前缀需求数组；若其中一条新路径退化为空 `[0, 0]`，自动删除空路径（等价于两路径可行合并）。

## 适用条件、假设与限制

- 顺接方式适用于有向与无向 VRP；反接方式要求距离矩阵对称（标准欧氏 CVRP 均满足）。
- 原论文针对 VRPTW，但应用于无时间窗标准 CVRP 时可直接省去时间窗推迟判定，仅保留 $O(1)$ 前缀/后缀容量校验。

## 来源及支持的具体结论

- Potvin & Rousseau (1995), *JORS* 46(12): 1433–1446（`src-potvin-rousseau-1995-2opt-star`）。

## 代码和评测关联

- 与路内 `method-cvrp-intra-2opt`、路间 `method-cvrp-inter-relocate` 构成标准 CVRP 经典三邻域核心；纳入 `method-cvrp-vns` 邻域清单。

## 未确认项与冲突证据

- 独立 `cw_2opt_star` 基准记录计划在里程碑二复合局部搜索骨架中补测。
""",
    )

    # N8) Standard CVRP VNS / RVND
    _upsert(
        "method-cvrp-vns",
        {
            "type": "method",
            "title": "Standard CVRP Variable Neighborhood Search (VNS / RVND)",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "vns", "rvnd", "vnd", "metaheuristic", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Standard CVRP General VNS / Randomized Variable Neighborhood Descent combining shaking perturbations with deterministic descent over {2-opt, Or-opt, relocate, swap, 2-opt*}, distinct from the DARP VNS entry.",
            "attributes": {
                "knowledge_tier": "local_implementation",
                "problem_variant": "standard_cvrp",
                "paradigm": "metaheuristic",
                "complexity_class": "O(k*n^2)",
                "interface": "solve_cvrp",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["cvrplib_abpx", "heterogeneous_regimes", "multi_second_budget", "escaping_local_optima"],
                    "weak_on": ["sub_10ms_ultra_fast_budget"],
                    "scale_notes": "在单次 RVND 陷入复合局部最优后通过可控强度扰动（k-step shake: double-bridge / random cross-exchange）跳出局部极值，是超越单一局部搜索上限的核心元启发式骨架。",
                },
                "interface_blueprint": {
                    "skeleton_role": "外层 VNS 循环维护全局最优解 x* 与扰动强度 k=1..k_max；内层 RVND 随机打乱邻域序列 N={2-opt, Or-opt, relocate, swap, 2-opt*} 直至全部邻域均无改进；若新解严格更优则更新 x* 并重置 k=1，否则增大扰动强度 k+=1",
                    "evolvable_hook": "neighborhood_schedule(k, stagnation, instance_features) 与 shaking_operator(routes, k, capacity)",
                    "state_maintained": ["best_routes", "incumbent_routes", "neighborhood_order", "shake_level_k", "time_budget_left"],
                    "invariants_and_constraints": ["扰动算子必须输出容量可行解或立即经修复恢复可行", "每次内层 RVND 结束时必须验证客户覆盖与容量不变量", "严格遵守显式时间预算以便公平跨算法比较"],
                    "typical_pitfalls": ["将 DARP 的 VNS 文献卡误认为标准 CVRP 实现", "扰动强度过大退化为随机重启，过小则反复落回同一吸引盆"],
                },
                "math_formulation": [
                    {
                        "expr": "x' = Shake_k(x*),   x'' = RVND(x', {N_1..N_5});   accept x* <- x'' if f(x'') < f(x*)",
                        "variables": {"x*": "当前全局最优 CVRP 路径集", "Shake_k": "第 k 档扰动算子", "N_1..N_5": "路内/路间复合局部搜索邻域族"},
                        "preconditions": "标准无时间窗 CVRP；所有邻域均满足精确容量可行检查",
                    }
                ],
                "artifact_refs": [],
                "evidence_bindings": [],
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": [
                    "method-cvrp-intra-2opt",
                    "method-cvrp-intra-or-opt",
                    "method-cvrp-inter-relocate",
                    "method-cvrp-inter-swap",
                    "method-cvrp-inter-2opt-star",
                    "method-lit-darp-iterated-vns-for-dial-a-ride",
                ],
                "sources": ["src-mladenovic-hansen-1997-vns"],
            },
            "source_refs": ["src-mladenovic-hansen-1997-vns"],
            "evidence_refs": ["literature:10.1016/S0305-0548(97)00031-2"],
            "code_refs": [],
        },
        """# Standard CVRP Variable Neighborhood Search (VNS / RVND)

面向**标准无时间窗 CVRP** 的变邻域搜索（VNS / GVNS）与随机变邻域下降（RVND）元启发式卡片，明确区分于历史文献库中面向拨号乘车问题的 `method-lit-darp-iterated-vns-for-dial-a-ride`。

## 定义或方法步骤

1. **初始解构造**：用并行 Clarke–Wright（`cw_parallel_merge`）或 Regret 插入生成初始可行解 $x^*$，设扰动阶数 $k = 1$。
2. **扰动阶段（Shaking）**：在当前最优解 $x^*$ 上应用强度为 $k$ 的可行扰动（如随机跨路径片段交换 CROSS-exchange 或多步可行移位）得到 $x'$。
3. **随机变邻域下降（RVND）**：将标准 CVRP 五大核心邻域 $\\{\\text{2-opt}, \\text{Or-opt}, \\text{relocate}, \\text{swap}, \\text{2-opt}^*\\}$ 随机排序依次下降；每当任一邻域找到严格改进即更新当前解并重新激活邻域列表，直至全部邻域均无改进得到局部最优解 $x''$。
4. **接受与邻域切换**：若 $f(x'') < f(x^*)$，则 $x^* \\leftarrow x''$ 并重置 $k = 1$；否则 $k \\leftarrow (k \\bmod k_{\\max}) + 1$，循环直至耗尽时间预算。

## 适用条件、假设与限制

- 适用于标准容量约束 CVRP，适合 500 ms 至数十秒级预算；对毫秒级极短预算，单轮 `cw_relocate_2opt` 已占主体收益。
- 属于全解元启发式（`solve_cvrp`），不兼容 `select_next_node`。

## 来源及支持的具体结论

- Mladenović & Hansen (1997)（`src-mladenovic-hansen-1997-vns`）；RVND 复合邻域设计为现代高性能 CVRP 求解器（如 ILS-SP / HGS）的核心组件。

## 代码和评测关联

- 关联子邻域卡：`method-cvrp-intra-2opt`、`method-cvrp-intra-or-opt`、`method-cvrp-inter-relocate`、`method-cvrp-inter-swap`、`method-cvrp-inter-2opt-star`。
- 明确区分变体卡：`method-lit-darp-iterated-vns-for-dial-a-ride`（`problem_variant="darp"`）。

## 未确认项与冲突证据

- 完整 VNS/RVND 全解求解器将在里程碑二计划期动态接口阶段作为元启发式骨架接入基准对比。
""",
    )

    # N9) Standard CVRP LNS / Shaw-Regret Ruin-and-Recreate
    _upsert(
        "method-cvrp-lns-shaw-regret",
        {
            "type": "method",
            "title": "Standard CVRP Large Neighborhood Search (LNS / Shaw-Regret Ruin-and-Recreate)",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "lns", "alns", "ruin-and-recreate", "shaw-removal", "regret", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Ruin-and-recreate metaheuristic for standard CVRP pairing Shaw relatedness/worst/random destroy operators with cheapest and Regret-k repair under explicit time budgets.",
            "attributes": {
                "knowledge_tier": "local_implementation",
                "problem_variant": "standard_cvrp",
                "paradigm": "ruin_and_recreate",
                "complexity_class": "O(k*n^2)",
                "interface": "solve_cvrp",
                "eoh_map": {"status": "not_mappable", "adapter_kind": "full_route_skeleton", "entrypoint": "solve_cvrp"},
                "applicable_regimes": {
                    "strong_on": ["cvrplib_set_x", "large_n_200_to_1000", "tight_capacity", "escaping_deep_local_optima"],
                    "weak_on": ["sub_20ms_budget"],
                    "scale_notes": "每次破坏 10%-25% 相关客户并用 Regret-k 整体重插，能够一次性跨越局部搜索需要几十步才能完成的路径重组，在 Set X 大规模异构算例上优势显著。",
                },
                "interface_blueprint": {
                    "skeleton_role": "外层循环维护全局最优与当前解；每轮执行 Destroy(移除 q 个客户) -> Repair(Cheapest / Regret-k 重插) -> 可选轻量局部搜索 -> SA / Record-to-Record 接受准则",
                    "evolvable_hook": "destroy_relatedness(i, j, routes, dmat, demands) 与 repair_priority(u, insertion_costs) 及自适应算子权重更新",
                    "state_maintained": ["best_routes", "current_routes", "operator_weights", "temperature_or_rtr_threshold"],
                    "invariants_and_constraints": ["Destroy 移除客户数 q 满足 1 <= q < n", "Repair 阶段允许新开路径保证 100% 恢复可行解", "所有候选解须在输出前通过独立全解校验器"],
                    "typical_pitfalls": ["移除比例过高导致单轮重插耗时爆炸", "Shaw 相关性缺少随机化指数 p 导致反复拆同一簇陷入循环"],
                },
                "math_formulation": [
                    {
                        "expr": "R_Shaw(i, j) = phi_d * (d(i,j)/d_max) + phi_q * (|q_i - q_j|/q_max) + phi_r * 1[route(i) != route(j)]",
                        "variables": {"R_Shaw(i,j)": "客户 i 与 j 的相关性（越小越相关）", "phi_d, phi_q, phi_r": "空间/需求/同路径权重"},
                        "preconditions": "无时间窗标准 CVRP（去掉时间窗项）；按 u^p 幂律随机偏向选择相关性最小的待移除客户",
                    }
                ],
                "artifact_refs": [],
                "evidence_bindings": [],
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-cvrp-cheapest-regret-insertion", "method-cvrp-vns"], "sources": ["src-shaw-1998-lns", "src-ropke-pisinger-2006-alns"]},
            "source_refs": ["src-shaw-1998-lns", "src-ropke-pisinger-2006-alns"],
            "evidence_refs": ["literature:10.1007/3-540-49481-2_30", "literature:10.1287/trsc.1050.0135"],
            "code_refs": [],
        },
        """# Standard CVRP Large Neighborhood Search (LNS / Shaw-Regret Ruin-and-Recreate)

面向标准 CVRP 的破坏重建大邻域搜索（LNS / ALNS），以 Shaw 相关性破坏与 Regret-$k$ 修复为核心，是突破局部搜索邻域深度瓶颈的主要范式之一。

## 定义或方法步骤

1. **初始解**：采用并行 Clarke–Wright + 2-opt（`cw_2opt`）生成快速高质量初始可行解。
2. **破坏（Destroy）**：按设定规模 $q \\in [\\min(4, 0.1n), \\min(40, 0.25n)]$ 从当前解移除客户，常见算子包括：
   - **Shaw Relatedness Removal**：按空间距离、需求相近度与路径归属计算相关性 $R(i, j)$，围绕种子客户移除成片关联客户；
   - **Worst Removal**：优先移除抽出节省距离最大的异常绕行客户；
   - **Random / String Removal**：随机拆解若干客户或整段相邻子链以保持多样性。
3. **重建（Repair）**：调用 Cheapest Insertion 或 Regret-$k$（$k=2, 3$）将全部被移除客户重新插回可行路径（必要时新开路径保证可行），并对变动路径执行快速 `2-opt`。
4. **接受与自适应更新**：采用 Record-to-Record Travel 或模拟退火接受准则；若为 ALNS，则按分段得分轮盘赌更新破坏/修复算子权重。

## 适用条件、假设与限制

- 适用于标准 CVRP 全尺度（尤以 CVRPLib Set X `n=100..1000` 和紧容量实例为强项）。
- 无法映射至 `select_next_node`；天然契合里程碑二“计划期接口设计”中进化破坏相关性与修复评分 Hook 的范式。

## 来源及支持的具体结论

- Shaw (1998)（`src-shaw-1998-lns`）；Ropke & Pisinger (2006)（`src-ropke-pisinger-2006-alns`）。

## 代码和评测关联

- 关联修复算子卡：`method-cvrp-cheapest-regret-insertion`；关联局部搜索卡：`method-cvrp-intra-2opt`、`method-cvrp-inter-relocate`。

## 未确认项与冲突证据

- 尚未纳入里程碑一首批 7 条基线（首批聚焦 4 逐点 + 1 并行合并 + 2 局部搜索），将在里程碑二接口进化实验中作为高上限范式落地评测。
""",
    )

    # N10) Stage-2 R7 (s2_r7_iso)
    _upsert(
        "method-cvrp-s2-r7-iso",
        {
            "type": "method",
            "title": "CVRP AST-safe isolation urgency with angular coherence and continuous early return (R7 / s2_r7_iso)",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "r7", "s2-r7-iso", "isolation", "early-return", "select_next_node", "scale-invariant", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Stage-2 Round-7 autonomous math constructive rule combining AST-safe nearest-unvisited isolation urgency (-0.24*d_nn), elongation rho, Law-of-Cosines cos(theta_0), two-phase depot start, and continuous early return; strongest pointwise rule on clustered regimes.",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "sequential_construct",
                "complexity_class": "O(n^2)",
                "interface": "select_next_node",
                "eoh_map": {"status": "possible", "adapter_kind": "direct_entrypoint", "entrypoint": "select_next_node"},
                "applicable_regimes": {
                    "strong_on": ["clustered", "hetero_288_clustered_top_winner", "n_50_to_200", "scale_invariance_1e-3_to_1e3"],
                    "weak_on": ["vs_parallel_merge_and_local_search", "extra_O(n^2)_submatrix_per_step_at_large_n"],
                    "scale_notes": "在 hetero-288 聚类子集赢得最多逐实例胜场（与 R5 形成主要互补对）；注意单步内需构造可行子矩阵求最近未访问邻距 d_nn，大 n 时求解耗时略高于 R5。",
                },
                "interface_blueprint": {
                    "skeleton_role": "单车顺序构造骨架（允许合法主动早返仓 return 0），严格通过 AST 白名单校验",
                    "evolvable_hook": "select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int",
                    "state_maintained": ["current_node", "rest_capacity", "unvisited_nodes"],
                    "invariants_and_constraints": ["使用 np.where(np.eye(n) > 0.5, np.inf, sub) 绕过被禁的 np.fill_diagonal", "所有距离项经 scale = max(d_cur) 归一化保持 0.00% 缩放极差"],
                    "typical_pitfalls": ["源码中 mid-route 处 pressure 被硬编码为 0.0（H-009 诊断发现），意外关闭了内旋衰减，但仍凭借孤立紧迫项取得强势聚类成绩"],
                },
                "math_formulation": [
                    {
                        "expr": "d_nn(j) = min_{k in F, k != j} d(j, k) / max(d_cur);   score = (d_cur - alpha*d_dep)/scale + 0.35*rho - 0.105*fill - 0.22*cos_t - 0.24*d_nn",
                        "variables": {"d_nn(j)": "候选 j 到其余可行未访问客户的归一化最近邻距（孤立度）", "rho": "三角伸长比 d(i,j)/(d(0,i)+d(0,j))"},
                        "preconditions": "中程步 current_node != depot；使用 AST 允许的 np.where + np.eye 屏蔽对角线",
                    }
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/selection_s2/rules_s2/s2_r7_iso.py", "sha256": r7_sha},
                ],
                "evidence_bindings": _collect_bindings(summary, "s2_r7_iso", core_suites + ["shared_diagnostic_6"]),
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": ["method-cvrp-s2-r5-spiral"],
                "sources": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md"],
            "code_refs": [],
        },
        f"""# CVRP AST-safe isolation urgency with angular coherence and continuous early return (R7 / s2_r7_iso)

`s2_r7_iso`（`s2_autonomous_math_r8` 第 7 轮 `candidate_2`，`H-008` 产出的 AST 自恢复代表规则）在两阶段出发步、伸长比 $\\rho$ 与余弦角相干的基础上，引入**孤立紧迫度项** $-0.24 \\cdot d_{{\\text{{nn}}}}$ 与无硬门槛连续自适应早返仓。

## 定义或方法步骤

1. **AST 安全最近邻孤立度**：对可行候选子矩阵 `sub = distance_matrix[nodes][:, nodes]`，利用白名单允许的 `np.where(np.eye(n) > 0.5, np.inf, sub)` 屏蔽对角线，计算归一化孤立度 `d_nn = np.min(masked, axis=1) / scale`（优先顺路服务孤立点，避免最后形成单点专车）。
2. **两阶段仓库出发步**：`rem_routes = sum(dem) / rest_capacity > 7.0` 时执行外向重远优先并偏爱孤立点；后期转为紧凑径向收尾。
3. **中程综合打分**：`score = (d_cur - alpha*d_dep)/scale + 0.35*rho - 0.105*fill - 0.22*cos_theta - 0.24*d_nn`。
4. **无硬门槛连续早返**：移除 R5 的 `best_dem > 0.55*rest_capacity` 硬门控，当 `1 - rho_best < tau` 且 `d_cur >= d_dep * (1 - tau) * 1.05` 时主动返回仓库 `0`。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node`；严格 0.00% 坐标缩放极差。

## 适用条件、假设与限制

- 在聚类空间工况（`clustered`）与 `shared_diagnostic_6`（`10.2595`）上表现尤为突出，是方向二候选池中与 `R5` 形成互补的核心成员。
- 由于每步构造 $|F| \\times |F|$ 子矩阵求 `d_nn`，大 $n$（如 `n=200` 及 CVRPLib Set X）下求解耗时高于 `R5`。

## 来源及支持的具体结论

- 统一工作台多套件复算结果（`s2_r7_iso`, `src-cvrp-workbench-20261121`, 预算 `standard_500ms`）：

{_fmt_suite_table(summary, "s2_r7_iso", core_suites + ["shared_diagnostic_6"])}

## 代码和评测关联

- 导出规则源码：`experiments/cvrp_midterm/selection_s2/rules_s2/s2_r7_iso.py`（`sha256: {r7_sha}`）。
- 关联发现：`evidence-cvrp-stage2-math-discoveries-h004-h009`、`evidence-cvrp-selection-complementarity-h010`。

## 未确认项与冲突证据

- 源码审计（`H-009`）发现中程分支中 `pressure = 0.0` 被意外写死，关闭了 `alpha` 的随容衰减；说明 R7 的优异表现主要归功于孤立紧迫度与连续早返仓，而非内旋衰减。
""",
    )

    # N11) Frozen C Rule Card
    c_stress_rows = [r for r in stress.get("records", []) if r.get("algorithm_id") == "c"]
    c_max_drift = max((float(r["scale_drift_pct"]) for r in c_stress_rows if r.get("scale_drift_pct") is not None), default=0.0)
    _upsert(
        "method-cvrp-frozen-c-near-tie",
        {
            "type": "method",
            "title": "Frozen PoC rule C: linear radial score with absolute near-tie capacity band",
            "category": "method",
            "problem_family": "cvrp",
            "tags": ["cvrp", "frozen-c", "h-001", "scale-collapse", "near-tie", "select_next_node", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Frozen PoC constructive rule C (10.9197 on shared_diagnostic_6 at nominal scale s=1) whose mixed-unit near-tie gate band=1e-3*(span+1.0) triggers an O(1/s^2) capacity-fit payload causing +207% collapse at coordinate scale s=1e-3.",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "sequential_construct",
                "complexity_class": "O(n^2)",
                "interface": "select_next_node",
                "eoh_map": {"status": "possible", "adapter_kind": "direct_entrypoint", "entrypoint": "select_next_node"},
                "applicable_regimes": {
                    "strong_on": ["nominal_unit_square_n50_dev_only"],
                    "weak_on": ["rescaled_coordinates_1e-3", "large_n_100_200", "eccentric_depot"],
                    "scale_notes": "标称单位正方形 n=50 共享 6 例为 10.9197，但因出发步耦合 (alpha=0.6<1) 在 P0-120 退化至 22.55，且在 s=1e-3 坐标缩放下崩溃 +207%（dev24 压力抽检最大漂移见 evidence_bindings）。",
                },
                "interface_blueprint": {
                    "skeleton_role": "单车顺序构造 select_next_node（作为早期 PoC 冻结基线与尺度崩溃诊断靶标）",
                    "evolvable_hook": "select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int",
                    "state_maintained": ["current_node", "rest_capacity", "unvisited_nodes"],
                    "invariants_and_constraints": ["严格禁止在未无量纲化的情况下混合绝对常量 1.0 与坐标距离 d_cur"],
                    "typical_pitfalls": ["band = 1e-3*(span + 1.0) 混合量纲，cap_term = 0.01*|rest_cap - dem|/d_cur 按 O(1/s^2) 爆炸"],
                },
                "math_formulation": [
                    {
                        "expr": "base = d(i,j) - 0.6*d(0,j);  band = 1e-3*(span + 1.0);  cap_term = 0.01 * |rest_cap - q_j| / max(d(i,j), 1e-9)",
                        "variables": {"span": "max(base) - min(base)", "band": "混合量纲近并列门控带宽", "cap_term": "非无量纲容量匹配项"},
                        "preconditions": "仅在 s ~ 1 单位正方形上偶然工作；当坐标缩放 s -> 0 时 cap_term/base ~ O(1/s^2) 接管决策",
                    }
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py", "sha256": c_sha},
                ],
                "evidence_bindings": [
                    *_collect_bindings(summary, "c", ["shared_diagnostic_6", "cvrp_dev_hetero_24", "cvrp_hist_p0_120", "cvrp_hist_hetero_288", "cvrp_final_accept_120"]),
                    {
                        "suite_id": "cvrp_dev_hetero_24",
                        "run_id": "cvrp_workbench_v2_scale_stress_1e-3",
                        "algorithm_id": "c",
                        "metric": "max_scale_drift_pct_at_1e-3",
                        "value": round(c_max_drift, 4),
                        "comparison_mode": "local_recomputed",
                        "reference_note": f"4 例 1e-3 坐标缩放压力抽检最大相对漂移 {c_max_drift:.2f}%（R5 / R7 / CW 为 0.00%）",
                        "artifact_path": "results/scale_stress_records.json",
                    },
                ],
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-cvrp-s2-r5-spiral"], "sources": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"]},
            "source_refs": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md"],
            "code_refs": [],
        },
        f"""# Frozen PoC rule C: linear radial score with absolute near-tie capacity band

前期泛化 PoC 冻结规则 `C`（`reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py`），在共享 6 例标称尺度取得 `10.9197`，是本课题揭示 **H-001 串联尺度崩溃机理** 与 **H-003 仓库出发耦合退化** 的核心解剖样本。

## 定义或方法步骤

1. 计算线性径向基分 `base = d(i, j) - 0.6 * d(0, j)` 与当前极差 `span = max(base) - min(base)`。
2. 构造混合量纲近并列带宽 `band = 1e-3 * (span + 1.0)`，标记满足 `base <= min(base) + band` 的候选集合。
3. 当 `current_node != depot` 且近并列候选数 $\\ge 2$ 时，在门控内叠加非无量纲容量匹配项 `cap_term = 0.01 * |rest_capacity - dem| / max(d_cur, 1e-9)` 与 `-1e-6 * dem`。
4. 否则直接最小化 `base - 1e-6 * dem`。

## EoH 适配

- ProblemSpec：`cvrp_construct`，入口 `select_next_node`（保留为反例与历史回归基线，严禁在无量纲修复前作为跨尺度种子）。

## 适用条件、假设与限制

- 严重违反坐标缩放等变性：在 `cvrp_dev_hetero_24` 的 `1e-3` 缩放压力抽检中最大归一化路程漂移达 **{c_max_drift:.2f}%**（共享 6 例 4 尺度极差达 `206.99%`）。
- 仓库出发步 `alpha = 0.6 < 1` 强制由内向外（inside-out），在大规模 `n=100/200` 上严重落后。

## 来源及支持的具体结论

- 机制证据卡片：`evidence-cvrp-scale-collapse-h001`、`evidence-cvrp-depot-start-phase-h003`。
- 统一工作台复算结果：

{_fmt_suite_table(summary, "c", ["shared_diagnostic_6", "cvrp_dev_hetero_24", "cvrp_hist_p0_120", "cvrp_hist_hetero_288", "cvrp_final_accept_120"])}

## 代码和评测关联

- 只读冻结源码：`reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py`（`sha256: {c_sha}`）。
- 尺度压力测试原始数据：`results/scale_stress_records.json`、`experiments/cvrp_midterm/analysis/scale_term_audit.json`。

## 未确认项与冲突证据

- 仅将 `band` 改为相对带宽可压低尺度极差至 `0.40%`，但标称尺度路程反而升高 `+1.92%`，证明门控与载荷须同时重设而非机械去常量。
""",
    )

    # N12) Evidence H-001: Frozen C Series Scale-Collapse Observation
    _upsert(
        "evidence-cvrp-scale-collapse-h001",
        {
            "type": "evidence",
            "title": "CVRP Frozen C series gate x O(1/s^2) payload scale-collapse mechanism (H-001)",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["cvrp", "h-001", "frozen-c", "scale-collapse", "scaling", "dimensionless", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Proves Frozen C's +207% collapse under s=1e-3 coordinate scaling is a series gate-x-payload mechanism: mixed-unit band=1e-3*(span+1.0) opens the gate (1.7% -> 84.3%) while cap_term/base explodes as O(1/s^2) (log-log slope -1.994).",
            "attributes": {
                "knowledge_tier": "math_observation",
                "problem_variant": "standard_cvrp",
                "paradigm": "math_mechanism",
                "complexity_class": "O(1)",
                "interface": "select_next_node",
                "applicable_regimes": {
                    "strong_on": ["diagnosing_unit_leakage", "scale_invariance_auditing", "cvrp_dev_hetero_24_stress"],
                    "weak_on": ["rules_already_dimensionless"],
                    "scale_notes": "对任何将未归一化需求/常数项直接加到坐标距离上的启发式公式均具普适诊断意义；直接确立了本课题全部后续规则 0.00% 坐标缩放极差的硬性设计规范。",
                },
                "math_formulation": [
                    {
                        "expr": "band(s) / base(s) = 1e-3 * (span_1 + 1/s) / base_1  ~ O(1) + O(1/s)",
                        "variables": {"s": "统一坐标缩放因子", "span_1": "标称尺度极差"},
                        "preconditions": "坐标整体乘以常数 s > 0 而需求与容量保持不变",
                    },
                    {
                        "expr": "cap_term(s) / base(s) = [0.01 * |rest_cap - q_j| / (s * d_1)] / (s * base_1) ~ O(1 / s^2)",
                        "variables": {"cap_term(s)": "门控内容量匹配载荷", "s": "坐标缩放因子"},
                        "preconditions": "门控触发（mask.sum() >= 2 and current_node != depot）时实测 4 尺度对数斜率 = -1.994",
                    },
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/analysis/scale_term_audit.py", "sha256": _sha256_file_lf(REPO / "experiments/cvrp_midterm/analysis/scale_term_audit.py")},
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py", "sha256": c_sha},
                ],
                "evidence_bindings": [
                    {
                        "suite_id": "shared_diagnostic_6",
                        "run_id": "h001_scale_term_audit",
                        "algorithm_id": "c",
                        "metric": "scale_spread_pct_4scales",
                        "value": 206.99,
                        "comparison_mode": "local_recomputed",
                        "reference_note": "C_full s=1: 10.9197 -> s=1e-3: 33.5221 (+206.99%); C_no_cap spread=0.18%; C_rel_band spread=0.40%",
                        "artifact_path": "experiments/cvrp_midterm/analysis/scale_term_audit.json",
                    },
                    {
                        "suite_id": "cvrp_dev_hetero_24",
                        "run_id": "cvrp_workbench_v2_scale_stress_1e-3",
                        "algorithm_id": "c",
                        "metric": "max_scale_drift_pct_at_1e-3",
                        "value": round(c_max_drift, 4),
                        "comparison_mode": "local_recomputed",
                        "reference_note": f"4 例 1e-3 压力抽检：Frozen C 最大漂移 {c_max_drift:.2f}%，R5/R7/CW 漂移 0.00%",
                        "artifact_path": "results/scale_stress_records.json",
                    },
                ],
            },
            "relations": {"problems": ["problem-cvrp"], "methods": ["method-cvrp-frozen-c-near-tie", "method-cvrp-s2-r5-spiral"], "sources": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"]},
            "source_refs": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md"],
            "code_refs": [],
        },
        f"""# CVRP Frozen C series gate x O(1/s^2) payload scale-collapse mechanism (H-001)

`H-001` 揭示了 `Frozen C` 在坐标缩放下的串联崩溃机理：**绝对常量近并列带宽是开关（Gate），非无量纲 $O(1/s^2)$ 容量项是破坏载荷（Payload）**。

## 定义或方法步骤

1. 在 4 组坐标尺度 $s \\in \\{{1, 10^{{-2}}, 10^{{-3}}, 10^3\\}}$ 上对共享 6 例全部 300 个决策步精确复现 `C.py:35` 门控条件（`mask.sum() >= 2 and current_node != depot`）。
2. 量测门控触发率与各项对基分 `base` 的量纲标度指数：
   - 门控触发率随缩放由 `1.7% (s=1) -> 67.7% (s=0.01) -> 84.3% (s=0.001) -> 0.7% (s=1000)`；
   - 触发步上 `cap_term / base` 对 $s$ 的 4 点对数斜率为 **`-1.994`（理论 $-2$，即 $O(1/s^2)$）**；
   - `-1e-6 * dem / base` 对数斜率为 **`-0.979`（理论 $-1$，即 $O(1/s)$）**；
   - `band / base` 混合斜率为 **`-0.542`**。
3. 执行三项直接消融（共享 6 例 4 尺度极差）：
   - `C_full`：`206.99%`（`10.9197 -> 33.5221`）；
   - `C_no_cap`（仅移除 `cap_term`）：`0.18%`（完全消除崩溃）；
   - `C_rel_band`（仅将 `band` 改为相对宽度）：`0.40%`（但标称尺度升高 `+1.92%` 至 `11.1297`）；
   - `C_no_dem`（仅移除 `-1e-6*dem`）：仍为 `205.89%`。

## 适用条件、假设与限制

- 适用于欧氏 CVRP 规则的量纲一致性审计；在 `cvrp_dev_hetero_24` 新增的 4 例 `1e-3` 坐标缩放压力抽检中已作为常驻自动化防退化检测。

## 来源及支持的具体结论

- `experiments/cvrp_midterm/analysis/scale_term_audit.json` 与 `experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md` §3.1。
- 本工作台 `cvrp_dev_hetero_24` `1e-3` 压力抽检（`results/scale_stress_records.json`）：`Frozen C` 最大漂移 **{c_max_drift:.2f}%**，而严格无量纲的 `nn`、`savings_pointwise`、`s2_r5_spiral`、`s2_r7_iso`、`cw_parallel_merge`、`cw_2opt`、`cw_relocate_2opt` 全部保持 **`0.00%`** 零漂移。

## 代码和评测关联

- 诊断脚本：`experiments/cvrp_midterm/analysis/scale_term_audit.py`、`experiments/cvrp_midterm/analysis/band_hypothesis.py`。
- 关联规则卡：`method-cvrp-frozen-c-near-tie`、`method-cvrp-s2-r5-spiral`。

## 未确认项与冲突证据

- 绝对常量门控仅当被演化搜索放在单位正方形上时才被隐蔽掩盖，一旦迁移至 CVRPLib（坐标范围 `0..100` 或 `0..1000`）即会因门控关闭或载荷失衡而失效。
""",
    )

    # N13) Evidence H-004..H-009 Stage-2 Math Discoveries
    _upsert(
        "evidence-cvrp-stage2-math-discoveries-h004-h009",
        {
            "type": "evidence",
            "title": "Stage-2 autonomous math discoveries synthesis: early return, rho, rem_routes, cos(theta_0), inward spiral, and isolation urgency (H-004 to H-009)",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["cvrp", "h-004", "h-005", "h-006", "h-007", "h-008", "h-009", "early-return", "spiral", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Tracks the six verified Stage-2 mathematical mechanisms discovered across Rounds 1-7: voluntary early return (sigma < tau), elongation ratio rho, two-phase rem_routes start, Law-of-Cosines cos(theta_0), state-only spiral alpha_eff, and AST-safe isolation urgency d_nn.",
            "attributes": {
                "knowledge_tier": "math_observation",
                "problem_variant": "standard_cvrp",
                "paradigm": "math_mechanism",
                "complexity_class": "O(n^2)",
                "interface": "select_next_node",
                "applicable_regimes": {
                    "strong_on": ["sequential_construct", "multi_scale_n50_n100_n200", "scale_invariance"],
                    "weak_on": ["single_run_search_variance_not_yet_multi_seed"],
                    "scale_notes": "各机理均在 ana72 上通过离线消融检验后注入下一轮进化，最终在零泄露 P0-120 与全新隔离的 final_accept_120 上持续验证。",
                },
                "math_formulation": [
                    {
                        "expr": "sigma(i,j) = 1 - rho(i,j) = (d(0,i) + d(0,j) - d(i,j)) / (d(0,i) + d(0,j)) < tau(pressure) => return 0",
                        "variables": {"sigma(i,j)": "无量纲归一化节约率（0 表示跨仓库直连，1 表示零绕行共线）", "tau(pressure)": "随容量压力递增的早返阈值"},
                        "preconditions": "H-004 / H-005：current_node != depot，利用 evaluator.py 合法早返动作避免跨仓库长距离桥接",
                    },
                    {
                        "expr": "alpha_eff = alpha_0 - alpha_1 * min(1, mean(q_F) / rest_cap)",
                        "variables": {"alpha_eff": "纯状态内旋权重（同步对所有候选统一，避免 H-004a 反重货偏置）"},
                        "preconditions": "H-007：车辆满载初期大 alpha 外扫，近满载时降 alpha 沿回仓走廊收割客户",
                    },
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/ledger/hypotheses.jsonl", "sha256": _sha256_file_lf(REPO / "experiments/cvrp_midterm/ledger/hypotheses.jsonl")},
                ],
                "evidence_bindings": [
                    *_collect_bindings(summary, "s2_r5_spiral", ["cvrp_hist_p0_120", "cvrp_final_accept_120"]),
                    *_collect_bindings(summary, "s2_r7_iso", ["cvrp_hist_p0_120", "cvrp_final_accept_120"]),
                ],
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": ["method-cvrp-s2-r5-spiral", "method-cvrp-s2-r7-iso"],
                "sources": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md"],
            "code_refs": [],
        },
        """# Stage-2 autonomous math discoveries synthesis (H-004 to H-009)

汇总第二阶段 8 轮自主数学分析（`s2_autonomous_math_r8`）中提出、消融并验证的六项递进数学机理（`H-004`–`H-009`）。

## 定义或方法步骤

1. **`H-004`（无量纲主动早返仓）**：当最佳候选的归一化节约率 $\\sigma(i,j) = 1 - \\rho(i,j) < \\tau$ 时主动返回 `0`，避免跨仓库无效桥接，并校准 $\\beta_{\\text{fill}} \\in [0.05, 0.18]$ 防止容量项压过几何项。
2. **`H-005`（三角伸长比 $\\rho$ 与自适应早返）**：将线性的 `(d_cur - alpha*d_dep)/scale` 与无量纲伸长比 $\\rho(i,j) = d(i,j)/(d(0,i)+d(0,j))$ 融合，实测 `ana72` 降至 `18.296`。
3. **`H-006`（两阶段剩余车队出发 `rem_routes` + 余弦角花瓣相干 $\\cos\\theta_0$）**：通过 `rem_routes = sum(q)/rest_cap` 在外围清扫与核区收尾间平滑切换，叠加余弦定理角相干抑制跨扇区跳跃，`ana72` 进一步降至 `17.927`（R4 在 `P0-120` 达 `19.8100`）。
4. **`H-007`（纯状态内旋 $\\alpha_{\\text{eff}}(\\text{pressure})$）**：与被证伪的逐候选末端惩罚 `H-004a` 相反，使用同步对所有候选统一的车辆压力 `pressure = min(1, mean(q_F)/rest_cap)` 驱动 $\\alpha_{\\text{eff}} = \\alpha_0 - \\alpha_1 \\cdot \\text{pressure}$，消除反重货偏置并产出最优规则 `R5`（`P0-120 = 19.6092`）。
5. **`H-008`（AST 安全孤立紧迫度 $-w_{\\text{iso}} d_{\\text{nn}}$ + 无硬门槛早返）**：以 `np.where(np.eye(n)>0.5, np.inf, sub)` 修复 R6 的 `fill_diagonal` 拒绝，产出在聚类工况胜场最高的 `R7`（`s2_r7_iso`）。
6. **`H-009`（实现缺陷审计与后期边际递减）**：定位 R7 源码中 `pressure = 0.0` 硬编码及候选 1/5 `sum(dem)` 饱和缺陷，透明记录 R8 后期边际递减。

## 适用条件、假设与限制

- 多组件在最终规则 `R5 / R7` 中协同作用，目前由逐轮单步离线消融证据支撑，尚未做全 $2^5$ 子集全因子拆解。
- 来源于单次配对搜索（48 EoH 请求/臂，实验臂 Token 多约 35% 且单列外部分析成本）。

## 来源及支持的具体结论

- 完整假设账本：`experiments/cvrp_midterm/ledger/hypotheses.jsonl`（条目 `H-004` 至 `H-009`）。
- 盲测与全新独立验收集数据：`experiments/cvrp_midterm/analysis/s2_holdout_eval.json`、`results/summary.json`。

## 代码和评测关联

- 关联规则卡：`method-cvrp-s2-r5-spiral`、`method-cvrp-s2-r7-iso`；关联证伪反例卡：`evidence-cvrp-antipattern-falsified-hypotheses`。

## 未确认项与冲突证据

- 多随机种子独立搜索的方差尚未统计，计划在里程碑三无人值守 Research Agent 中补齐多 seed 对照。
""",
    )

    # N14) Evidence H-010: Direction 2 Complementarity & OOF Selection
    sel_h288_p2 = (selection.get("analyses") or {}).get("hetero_288__pointwise_plus_s2") or {}
    sel_h288_mp7 = (selection.get("analyses") or {}).get("hetero_288__multiparadigm_7") or {}
    sel_fin_p2 = (selection.get("analyses") or {}).get("final_accept_120__pointwise_plus_s2_frozen") or {}
    sel_fin_mp7 = (selection.get("analyses") or {}).get("final_accept_120__multiparadigm_7_frozen") or {}

    def _sel_line(ana: Mapping[str, Any], proto: str, sel_id: str) -> str:
        m = (((ana.get("protocols") or {}).get(proto) or {}).get("selectors") or {}).get(sel_id)
        if not m:
            return "—"
        lo, hi = m["gain_ci95"]
        return (
            f"gain={m['gain_vs_sbs']*100:+.2f}% [{lo*100:+.2f}%, {hi*100:+.2f}%], p={m['p_boot_one_sided']:.4f}, "
            f"feat={m['mean_feat_ms']:.3f} + infer={m['mean_infer_ms']:.3f} + solve={m['mean_solve_ms']:.3f} = {m['mean_total_ms']:.3f} ms"
        )

    h10_bindings: list[dict[str, Any]] = []
    for key_name, ana, proto, sel_id in (
        ("hetero_288_p2_cv12_rf", sel_h288_p2, "cv12", "rf_reg"),
        ("hetero_288_p2_loro48_rf", sel_h288_p2, "loro48", "rf_reg"),
        ("hetero_288_p2_loso3_rf", sel_h288_p2, "loso3", "rf_reg"),
        ("hetero_288_mp7_cv12_rf", sel_h288_mp7, "cv12", "rf_reg"),
        ("final_accept_120_p2_rf", sel_fin_p2, "frozen_transfer", "rf_reg"),
        ("final_accept_120_mp7_rf", sel_fin_mp7, "frozen_transfer", "rf_reg"),
    ):
        m = (((ana.get("protocols") or {}).get(proto) or {}).get("selectors") or {}).get(sel_id)
        if m:
            h10_bindings.append({
                "suite_id": ana["suite_id"],
                "run_id": f"{ana['portfolio_id']}__{proto}",
                "algorithm_id": sel_id,
                "metric": "gain_vs_sbs",
                "value": m["gain_vs_sbs"],
                "comparison_mode": "local_recomputed",
                "reference_note": _sel_line(ana, proto, sel_id),
                "artifact_path": "results/selection_records.json",
            })

    _upsert(
        "evidence-cvrp-selection-complementarity-h010",
        {
            "type": "evidence",
            "title": "CVRP multi-scale complementarity, out-of-fold selection, and frozen transfer boundaries (H-010)",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["cvrp", "h-010", "selector", "portfolio", "vbs", "sbs", "cv12", "loro48", "loso3", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Quantifies SBS vs Oracle (VBS) complementarity contraction with scale, separated selector timing (feat + infer + solve), positive/negative OOF results across cv12/loro48/loso3 on hetero-288, and frozen cross-suite transfer from select-64 to isolated final-accept-120.",
            "attributes": {
                "knowledge_tier": "verified_experiment",
                "problem_variant": "standard_cvrp",
                "paradigm": "selector_portfolio",
                "complexity_class": "empirical",
                "interface": "select_algorithm",
                "applicable_regimes": {
                    "strong_on": ["within_distribution_cv12_small_n50", "heterogeneous_pointwise_pools"],
                    "weak_on": ["leave_one_scale_out_loso3", "dominated_single_paradigm_large_n200", "ultra_tight_runtime_overhead"],
                    "scale_notes": "在所测逐点池中互补间隙随规模显著收窄（n=50 -> n=100 -> n=200）；在含局部搜索的多范式 7 池中 cw_relocate_2opt 几乎全面占优，互补性转为质量-耗时 Pareto 权衡。",
                },
                "math_formulation": [
                    {
                        "expr": "y_{i,k} = (c_{i,k} - min_m c_{i,m}) / min_m c_{i,m};   T_total(i) = T_feat(i) + T_infer(i) + T_solve(i, pi(i))",
                        "variables": {"y_{i,k}": "严格在训练集内计算的尺度无关相对遗憾回归目标", "T_feat, T_infer, T_solve": "分离测量的特征提取、单实例推理与所选算法求解耗时"},
                        "preconditions": "固定单一最佳 SBS 不支付 T_feat 与 T_infer；禁止混用不同计时边界",
                    }
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": WORKBENCH_COMMIT_PIN, "path": "agent_skill_loop/cvrp_workbench/selection.py", "sha256": selection_sha},
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/selection_s2/select_s2.py", "sha256": _sha256_file_lf(REPO / "experiments/cvrp_midterm/selection_s2/select_s2.py")},
                ],
                "evidence_bindings": h10_bindings,
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": ["method-cvrp-s2-r5-spiral", "method-cvrp-s2-r7-iso", "method-cvrp-inter-relocate"],
                "sources": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md"],
            "code_refs": [],
        },
        f"""# CVRP multi-scale complementarity, out-of-fold selection, and frozen transfer boundaries (H-010)

`H-010` 完整记录方向二在历史多因子回归集 `cvrp_hist_hetero_288`（`cv12 / loro48 / loso3` 三协议）以及全新冻结迁移（`cvrp_select_multiscale_64 -> cvrp_final_accept_120`）上的互补性、折外质量收益、分离计时开销及负向边界。

## 定义或方法步骤

1. 提取 12 维尺度无关实例特征（`extract_instance_features`），记录每例特征耗时 `feat_ms`。
2. 仅在训练折内部计算无量纲相对遗憾目标 $y_{{i,k}} = (c_{{i,k}} - \\min_m c_{{i,m}})/\\min_m c_{{i,m}}$，训练 `stump_1d / knn5 / ridge / pairwise_cs / pairwise_plain / rf_reg / rf_pairwise_cs` 与折内 `fixed_best_sbs`。
3. 严格分离计时：`fixed_best_sbs` 仅计 `solve_ms`（`feat_ms = 0, infer_ms = 0`）；特征选择器分别计量 `feat_ms + infer_ms + solve_ms = total_ms`。
4. 同步落盘每个测试实例的 `selected_algorithm / oracle_algorithm / regret_rel / is_mistake_vs_oracle` 以供前端页面 4 下钻至页面 3 核查失误代价。

## 适用条件、假设与限制

- `cvrp_hist_hetero_288` 已在中期实验中暴露用于特征与模型开发，明确标为历史回归集；真正独立的部署泛化能力以 `cvrp_select_multiscale_64 -> cvrp_final_accept_120` 冻结迁移结果为准。
- 严格保留全部正负结果：在同分布 `cv12` 上可见显著正收益，但在跨工况 `loro48` 与跨规模 `loso3` 上收益收窄甚至转负。

## 来源及支持的具体结论

- **`cvrp_hist_hetero_288`（`pointwise_plus_s2` 12 规则池，统一分离测时）**：
  - 全局 SBS = `{sel_h288_p2.get('global_sbs_algorithm')}`（总长 `{sel_h288_p2.get('global_sbs_total')}` vs Oracle VBS `{sel_h288_p2.get('global_vbs_total')}`，互补间隙 `{(sel_h288_p2.get('global_sbs_gap_to_vbs') or 0)*100:.2f}%`）
  - `cv12 / rf_reg`：{_sel_line(sel_h288_p2, 'cv12', 'rf_reg')}
  - `loro48 / rf_reg`：{_sel_line(sel_h288_p2, 'loro48', 'rf_reg')}
  - `loso3 / rf_reg`：{_sel_line(sel_h288_p2, 'loso3', 'rf_reg')}
- **全新独立冻结迁移（`cvrp_select_multiscale_64 -> cvrp_final_accept_120`）**：
  - `pointwise_plus_s2_frozen / rf_reg`：{_sel_line(sel_fin_p2, 'frozen_transfer', 'rf_reg')}
  - `multiparadigm_7_frozen / rf_reg`：{_sel_line(sel_fin_mp7, 'frozen_transfer', 'rf_reg')}

## 代码和评测关联

- 选择流水线：`agent_skill_loop/cvrp_workbench/selection.py`、`experiments/cvrp_midterm/selection_s2/select_s2.py`。
- 逐实例决策与失误表：`results/selection_records.json`。

## 未确认项与冲突证据

- 当候选池仅包含单范式顺序规则时，互补间隙在 `n=200` 收窄至不足 0.5%；要在更大规模建立可观的跨实例互补空间，需引入里程碑二的多范式全解候选池（并在统一时间预算下联合权衡质量与耗时）。
""",
    )

    # N15) Failure & Falsification Antipattern Card
    _upsert(
        "evidence-cvrp-antipattern-falsified-hypotheses",
        {
            "type": "evidence",
            "title": "CVRP falsified hypotheses & engineering antipatterns (H-004a, H-008a, dev4 overfitting R3, AST traps)",
            "category": "evidence",
            "problem_family": "cvrp",
            "tags": ["cvrp", "antipattern", "falsified", "h-004a", "h-008a", "overfitting", "ast-whitelist", "standard-cvrp"],
            "status": "reviewed",
            "summary": "Documents four verified failure/falsification cases in CVRP heuristic search: terminal-stop +d_dep anti-heavy bias (H-004a), discrete exact-fit bin-packing detours (H-008a), dev4 single-scale selection overfitting (auto_dev1_r3), and hidden AST whitelist rejections (fill_diagonal/ix_/count_nonzero).",
            "attributes": {
                "knowledge_tier": "failure_antipattern",
                "problem_variant": "standard_cvrp",
                "paradigm": "math_mechanism",
                "complexity_class": "empirical",
                "interface": "select_next_node",
                "applicable_regimes": {
                    "strong_on": ["guarding_autonomous_search_against_known_dead_ends"],
                    "weak_on": [],
                    "scale_notes": "挂接在关联构造规则与实验工况下，防止未来 Research Agent 重复踩入已证伪方向。",
                },
                "math_formulation": [
                    {
                        "expr": "H-004a antipattern: +w_ret * d(0,j) when (rest_cap - q_j < min_other_q)  => selectively penalizes heavy q_j",
                        "variables": {"w_ret": "尾站回程惩罚权重", "min_other_q": "其余未访问客户最小需求"},
                        "preconditions": "在 dev4 (-0.038 -> +0.023) 与 ana72 (18.67 -> 19.52) 均单调恶化，已证伪放弃",
                    },
                    {
                        "expr": "H-008a antipattern: -w_bp * 1[rest_cap == q_j] + w_bp * 1[0 < rest_cap - q_j < min_q] => spatial detour > packing savings",
                        "variables": {"w_bp": "离散满载/残容惩罚权重"},
                        "preconditions": "在 ana72 上随 w_bp in {0.05, 0.12, 0.25} 单调恶化（17.877 -> 18.102），已证伪放弃",
                    },
                ],
                "artifact_refs": [
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/selection_s2/rules_s2/s2_r3_rho.py", "sha256": alg_by_id["s2_r3_rho"]["code_sha256"]},
                    {"kind": "repo_code", "commit": MIDTERM_COMMIT_PIN, "path": "experiments/cvrp_midterm/ledger/hypotheses.jsonl", "sha256": _sha256_file_lf(REPO / "experiments/cvrp_midterm/ledger/hypotheses.jsonl")},
                ],
                "evidence_bindings": _collect_bindings(summary, "s2_r3_rho", ["shared_diagnostic_6", "cvrp_hist_p0_120", "cvrp_hist_hetero_288"]),
            },
            "relations": {
                "problems": ["problem-cvrp"],
                "methods": ["method-cvrp-s2-r5-spiral", "method-cvrp-s2-r7-iso"],
                "sources": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            },
            "source_refs": ["src-cvrp-midterm-20261121", "src-cvrp-workbench-20261121"],
            "evidence_refs": ["report:experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md"],
            "code_refs": [],
        },
        f"""# CVRP falsified hypotheses & engineering antipatterns (H-004a, H-008a, R3 overfitting, AST traps)

归档中期研究与审计过程中经实测证伪或暴露的四类典型失败案例，作为未来自主 Research Agent 的反模式护栏。

## 定义或方法步骤

1. **`H-004a` 尾站 `+d_dep` 符号翻转偏置（已证伪）**：试图在 `rest_cap - q_j < min_other_q` 时将 `-alpha*d(0,j)` 翻转为 `+w_ret*d(0,j)` 以压缩尾程回仓距离；但该条件仅在重货客户上触发，产生反重货偏置，导致 `ana72` 由 `18.6728` 恶化至 `19.5211`。正确替代方案为纯状态内旋 `H-007` + 主动早返 `H-004`。
2. **`H-008a` 离散恰好满载/残容惩罚（已证伪）**：在已有平滑填充项与早返仓的基础上叠加离散 `rem==0` 奖励与 `0 < rem < min_q` 惩罚，诱发远距离空间绕行去凑整装满，在 `ana72` 上随权重 `{0.05, 0.12, 0.25}` 单调恶化（`17.877 -> 17.940 -> 17.991 -> 18.102`）。
3. **极小单规模开发集选优过拟合（`auto_dev1_r3` / `s2_r3_rho`）**：仅凭 4 例 `n=50` `dev4` 排名第一（`-0.1576`）但漏写仓库出发分支的 `R3`，在独立多规模 `P0-120` 上均值反退化至 `21.1411`（落后配对对照 `-2.51%`，仅 `45/120` 胜），证明必须使用独立多规模选优集（如本里程碑 `cvrp_select_multiscale_64`）。
4. **AST 沙箱白名单隐蔽禁调陷阱**：`agent_skill_loop/evaluator.py` 禁止调用 `np.fill_diagonal`、`np.ix_`、`np.count_nonzero`、`np.searchsorted`，在 `b4_finding_only` 造成 2 个候选被官方拒绝，在 `S2` R6 导致整轮 `0/5` 有效；须改用 `np.where(np.eye(n) > 0.5, np.inf, sub)`、`mat[nodes][:, nodes]`、`int(np.sum(mask))` 等白名单安全写法。

## 适用条件、假设与限制

- 适用于 `cvrp_construct` 演化搜索与自动化假设提出阶段；在跨入全解 `solve_cvrp` 骨架后仍应保留多规模独立选优集与显式白名单注入机制。

## 来源及支持的具体结论

- 假设账本：`experiments/cvrp_midterm/ledger/hypotheses.jsonl`（`H-004a`、`H-008a`、`H-005`、`H-009`）；审计复验：`experiments/cvrp_midterm/analysis/audit_reverification_p0.json`。
- `s2_r3_rho` 统一工作台复算数据：

{_fmt_suite_table(summary, "s2_r3_rho", ["shared_diagnostic_6", "cvrp_hist_p0_120", "cvrp_hist_hetero_288"])}

## 代码和评测关联

- 反例源码：`experiments/cvrp_midterm/selection_s2/rules_s2/s2_r3_rho.py`；白名单定义：`agent_skill_loop/evaluator.py:_NUMPY_ATTRIBUTES`。

## 未确认项与冲突证据

- 离散满载奖励在极窄容量（例如一车仅装 2-3 件大货的退化装箱型 CVRP）下的边界效应未做专项测试；在标准 `q ~ 1..9, Q in {28, 40, 45}` 工况下已充分证伪。
""",
    )

    from sync_top_venue_kb import sync_top_venue_kb
    tv_res = sync_top_venue_kb(workspace, bundle_dir, upgraded=upgraded, created=created)

    return {
        "ok": True,
        "workspace": str(workspace),
        "added_sources": added_sources + tv_res["added_top_venue_sources"],
        "upgraded_count": len(upgraded),
        "created_count": len(created),
        "upgraded_ids": sorted(upgraded),
        "created_ids": sorted(created),
        "total_entries": len(list(entries_dir.glob("*.json"))),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    res = sync_kb(args.workspace, args.bundle_dir)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
