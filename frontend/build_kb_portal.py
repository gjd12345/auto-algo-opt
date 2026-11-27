"""Build offline, jargon-free Academic Knowledge Exhibition Portal (index.html + portal_data.js).

Reads an immutable knowledge release strictly read-only, scrubs internal
milestone/wave/arm/hypothesis identifiers into clear academic terminology,
and emits a standalone zero-CDN HTML portal compatible with ``file://``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

PORTAL_SRC_DIR = Path(__file__).resolve().parent / "kb_portal"
H003_DATA_JS_PATH = Path(__file__).resolve().parent / "h003_preview" / "data.js"
DEFAULT_RELEASE_DIR = Path("knowledge_store/releases/20261127-main-co-workbench-m6-final")
DEFAULT_OUTPUT_DIR = Path("outputs/kb_portal")

JS_BUNDLE_FILES: tuple[str, ...] = (
    "renderers.js",
    "microlabs.js",
    "graph_view.js",
    "app.js",
)

# Curated academic Chinese titles for representative & M6/mechanism entries (zero internal jargon)
CURATED_DISPLAY_TITLES: dict[str, str] = {
    "evidence-m6-wave1-clean-audit-20261127": "严格截止时间审计与无竞争单核计时规范",
    "evidence-m6-wave2-b1-decoupled-pareto-20261127": "停滞重启与风险上界自适应早停解耦及帕累托前沿",
    "evidence-m6-wave2-c2-multiscale-430-20261127": "多尺度几何–规模联合探针与 430 题全通实证",
    "evidence-m6-wave3-c1-exact-k-contract-20261127": "车队规模感知契约与指定车数硬约束求解跃升",
    "evidence-m6-wave4-b2-clean-sandbox-20261127": "零绕过数值沙箱诊断与自修复消融实证",
    "evidence-m6-wave4-b3-clean-memory-kb-20261127": "统一基准知识库与跨尺度门控跨运行记忆迁移",
    "theory-m6-waves1to4-unified-framework-20261127": "截止可观测性、组合可行域与记忆迁移统一理论框架",
    "evidence-cvrp-antipattern-falsified-hypotheses": "已证伪启发式假设与算法设计常见反模式警示",
    "evidence-cvrp-depot-start-phase-h003": "仓库出发步径向排序相变与反事实因果替换实证",
    "evidence-cvrp-scale-collapse-h001": "绝对带宽门控与二次载荷敏感导致的坐标缩尺崩溃机理",
    "evidence-cvrp-selection-complementarity-h010": "多尺度互补构造、折外选择边界与迁移局限分析",
    "evidence-cvrp-stage2-math-discoveries-h004-h009": "径向内旋、负荷率与容量自适应主动早返核心数学规律汇编",
    "evidence-obp-hardcoded-capacity-antipattern": "跨问题反面教材：硬编码容量常数导致的混合单位尺度崩溃",
    "method-cvrp-i605-tworegime-savings": "两段容量切换节约值与主动早返构造规则",
    "method-cvrp-m2-l2a-generalized-savings": "全局仓距尺度归一化广义并行路径合并规则",
    "method-cvrp-m2-l2b-dynamic-state-merge": "动态路线负荷状态反馈并行合并与候选刷新机制",
    "method-cvrp-m3-ruin-recreate-l3": "基于节点破坏评分与后悔值重插的大规模破坏修复框架",
    "method-cvrp-s2-r4-cos": "两阶段径向出发与余弦角相干互补构造规则",
    "method-cvrp-s2-r5-spiral": "纯状态无量纲内旋角相干与容量自适应早返规则",
    "method-cvrp-s2-r7-iso": "孤立客户紧迫度与连续主动早返构造规则",
    "method-obp-i605-exp-deadzone": "在线装箱指数级剩余利用率与死区二次惩罚规则",
    "method-research-agent-m3-autonomous-loop": "带持久预算状态机与跨尺度验证的自主算法研究框架",
    "method-cvrp-cheapest-regret-insertion": "标准车辆路径问题最小插入增量与 Regret-k 后悔值构造",
    "framework-search-control-rag": "搜索过程控制与结构化知识检索增强框架",
    "evidence-cvrp-m2-cross-paradigm-blind120-and-selection": "跨范式路径合并与盲测 120 题独立选择归因实证",
    "evidence-cvrp-m2-diagnostic-planning-and-budget-adaptation": "求解期诊断规划与严格预算自适应调控实证",
    "evidence-cvrp-m2-perpair-scale-normalization-antipattern": "反模式警示：单对局部尺度归一化引发的多尺度失真",
    "evidence-cvrp-m3-blind120-and-direction2": "盲测 120 题验证与求解期算子选择稳定性评估",
    "evidence-cvrp-m3-external-eohs256-cvrplib-abp74-x100": "跨开源基准集（256 题与官方 174 题）泛化评测证据",
    "evidence-cvrp-m3-four-arm-multiseed-500ms-25ms": "500 ms 与 25 ms 双时限下四臂多种子对照实证",
    "evidence-m4-shapley-hrk-invariance-closure-20261124": "特征归因与尺度不变性完整统计检验归档",
    "evidence-m5-21run-trajectory-control-closure-20261125": "二十一组长轨迹控制与全局早停对比实证",
    "evidence-m5-s1-sandbox-causal-ablation-20261125": "数值沙箱辅助分析因果消融基准对照",
    "evidence-m5-s2-multiscale-dual-timing-ablation-20261125": "多尺度联合泛化与双时限约束对照实证",
    "evidence-m35-pure-kb-memory-retest-20261125": "纯知识库检索对比跨运行记忆回放复测证据",
    "evidence-m31-cross-problem-tsp-obp-bpp-20261124": "跨问题族（旅行商与装箱问题）统一评测实证",
    "evidence-m32-scaling-latency-cliff-20261124": "大规模算例计算延迟悬崖与超限机理剖面分析",
    "evidence-milestone15-historical-reproduction": "经典文献基准独立复现与可验证基线标定",
}

_JARGON_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"2026\d{4}-main-[a-z0-9-]+", re.I), "统一基准知识库发布版"),
    (re.compile(r"cvrp_m[23]_blind_120", re.I), "120题独立盲测集"),
    (re.compile(r"cvrp_final_accept_120", re.I), "120题终极盲测集"),
    (re.compile(r"cvrp_dev_hetero_24", re.I), "24题多样几何开发集"),
    (re.compile(r"cvrp_select_multiscale_64", re.I), "64题多尺度筛选集"),
    (re.compile(r"\bMilestone\s*\d+(?:\.\d+)?\b", re.I), "系统性受控验证阶段"),
    (re.compile(r"里程碑\s*[一二三四五六\d]+(?:\.\d+)?(?:阶段\s*[0-9A-Za-z.]*)?"), "受控实证阶段"),
    (re.compile(r"\bmilestone\d+(?:_[a-z0-9_]+)?\b", re.I), "受控实验阶段"),
    (re.compile(r"milestone_?\d+(?:\.\d+)?", re.I), "historical_audit"),
    (re.compile(r"\bWave\s*[1-4]\b", re.I), "专题验证批次"),
    (re.compile(r"\bWaves\s*1[–-]4\b", re.I), "全阶段受控实验"),
    (re.compile(r"\bM[1-6](?:\.\d+)?\b", re.I), "核心研究阶段"),
    (re.compile(r"\bm[1-6](?=[-_\s]|$)"), "基准阶段"),
    (re.compile(r"\bonline_writeback\b", re.I), "在线即时写回策略"),
    (re.compile(r"\bfull_closed_loop\b", re.I), "闭环记忆读写策略"),
    (re.compile(r"\barm[0-3]\b", re.I), "对照实验组"),
    (re.compile(r"\barm_b3_0_base_kb_only\b"), "统一基准知识库基线组"),
    (re.compile(r"\barm_b3_1_online_writeback\b"), "在线即时写回组"),
    (re.compile(r"\barm_b3_2_offline_l3_c2_gated\b"), "离线跨尺度门控精炼只读组"),
    (re.compile(r"\barm_b3_3_full_closed_loop_c2_gated\b"), "门控完整闭环记忆组"),
    (re.compile(r"\barm_b2_0_free_tool\b"), "自由工具基线组"),
    (re.compile(r"\barm_b2_1_slice_only\b"), "结构化信息直供对照组"),
    (re.compile(r"\barm_b2_2_sandbox_only\b"), "数值沙箱诊断强制门控组"),
    (re.compile(r"\bs2_r5_spiral\b", re.I), "内旋主动早返规则"),
    (re.compile(r"\bs2_r7_iso\b", re.I), "孤立紧迫早返规则"),
    (re.compile(r"\bs2_r4_cos\b", re.I), "余弦角相干互补规则"),
    (re.compile(r"\bS2-R[457]\b", re.I), "高阶状态构造规则"),
    (re.compile(r"\bH-00[1-9]\b|\bH-010\b|\bH-004a\b|\bH-008a\b"), "关键机制发现"),
    (re.compile(r"</?(?:i|em|b|strong|sup|sub)>", re.I), ""),
    (re.compile(r"island605[a-z0-9_/-]*", re.I), "多岛演化历史实验集"),
    (re.compile(r"\bY_[01]{2}\b"), "对照实验配置"),
    (re.compile(r"\bC[12]\b"), "专项治理策略"),
    (re.compile(r"\bB[123]\b"), "专项消融"),
    (re.compile(r"\bA[1-4]\b"), "基线审计项"),
    (re.compile(r"\bL2[ab]?\b"), "并行路径合并层"),
    (re.compile(r"\bL3\b"), "离线破坏修复精炼层"),
    (re.compile(r"\bR[3457]\b"), "代表构造策略"),
]


def scrub_internal_jargon(text: str) -> str:
    """Replace internal milestone, wave, arm, and hypothesis tokens with clean academic terms."""
    out = str(text or "")
    for pat, repl in _JARGON_REPLACEMENTS:
        out = pat.sub(repl, out)
    # Collapse accidental doubled spaces created after replacements
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_h003_preview() -> dict[str, Any] | None:
    if not H003_DATA_JS_PATH.is_file():
        return None
    raw = H003_DATA_JS_PATH.read_text(encoding="utf-8")
    if "=" not in raw:
        return None
    body = raw.split("=", 1)[1].strip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def _safe_js_json(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        raw.replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _clean_markdown_body(raw_md: str) -> str:
    lines = []
    for line in str(raw_md or "").splitlines():
        # Strip raw repository relative report paths listed as bare bullet items
        if re.match(r"^\s*-\s*`(experiments|tools|agent_skill_loop|benchmarks)/[^`]+`\s*$", line):
            continue
        lines.append(scrub_internal_jargon(line))
    return "\n".join(lines).strip()


def build_kb_portal(*, release_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Build a standalone, jargon-free academic portal from an immutable release."""
    release_dir = release_dir.resolve()
    output_dir = output_dir.resolve()
    entries_dir = release_dir / "entries"
    if not entries_dir.is_dir():
        raise FileNotFoundError(f"Release entries directory not found: {entries_dir}")

    sources_doc = _load_json(release_dir / "sources.json")
    manifest_doc = _load_json(release_dir / "manifest.json")

    raw_entries: list[dict[str, Any]] = []
    entry_ids: set[str] = set()
    for jp in sorted(entries_dir.glob("*.json")):
        d = _load_json(jp)
        eid = str(d.get("id") or jp.stem)
        entry_ids.add(eid)
        md_path = jp.with_suffix(".md")
        raw_md = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
        d["_raw_body"] = raw_md
        raw_entries.append(d)

    entries_out: list[dict[str, Any]] = []
    for d in raw_entries:
        eid = str(d.get("id") or "")
        attrs = d.get("attributes") if isinstance(d.get("attributes"), dict) else {}
        rels = d.get("relations") if isinstance(d.get("relations"), dict) else {}

        display_title = CURATED_DISPLAY_TITLES.get(eid) or scrub_internal_jargon(str(d.get("title") or eid))
        clean_summary = scrub_internal_jargon(str(d.get("summary") or ""))
        clean_body = _clean_markdown_body(d.get("_raw_body") or "")

        related_ids: list[str] = []
        for bucket in ("methods", "problems", "implementations"):
            for target in rels.get(bucket) or []:
                tid = str(target)
                if tid in entry_ids and tid != eid and tid not in related_ids:
                    related_ids.append(tid)

        # Clean blueprint / math formulations if present
        bp = attrs.get("interface_blueprint")
        if isinstance(bp, dict):
            bp_clean = {
                "skeleton_role": scrub_internal_jargon(str(bp.get("skeleton_role") or "")),
                "evolvable_hook": str(bp.get("evolvable_hook") or ""),
                "invariants_and_constraints": [scrub_internal_jargon(str(x)) for x in (bp.get("invariants_and_constraints") or [])],
                "typical_pitfalls": [scrub_internal_jargon(str(x)) for x in (bp.get("typical_pitfalls") or [])],
            }
        else:
            bp_clean = None

        math_form = attrs.get("math_formulation") if isinstance(attrs.get("math_formulation"), list) else []

        search_text = " ".join([
            display_title,
            clean_summary,
            str(d.get("problem_family") or ""),
            str(d.get("type") or ""),
            " ".join(str(t) for t in (d.get("tags") or [])),
            clean_body[:600],
        ]).lower()

        entries_out.append({
            "id": eid,
            "type": str(d.get("type") or "method"),
            "problem_family": str(d.get("problem_family") or "unknown"),
            "knowledge_tier": attrs.get("knowledge_tier") or "",
            "paradigm": attrs.get("paradigm") or "",
            "display_title": display_title,
            "clean_summary": clean_summary,
            "clean_body": clean_body,
            "interface_blueprint": bp_clean,
            "math_formulation": math_form,
            "source_refs": [str(s) for s in (d.get("source_refs") or [])],
            "related_entry_ids": related_ids[:10],
            "relations_count": len(related_ids),
            "featured": eid in CURATED_DISPLAY_TITLES,
            "search_text": search_text,
        })

    sources_out: list[dict[str, Any]] = []
    for s in sources_doc.get("sources") or []:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        sources_out.append({
            "id": str(s["id"]),
            "display_title": scrub_internal_jargon(str(s.get("title") or "")),
            "authors": [scrub_internal_jargon(str(a)) for a in (s.get("authors") or [])],
            "year": s.get("year"),
            "venue": scrub_internal_jargon(str(s.get("venue") or "")),
            "doi": s.get("doi"),
        })

    portal_payload = {
        "schema_version": "kb-exhibition-portal/v1",
        "release_id": str(manifest_doc.get("release_id") or release_dir.name),
        "counts": {
            "entries": len(entries_out),
            "sources": len(sources_out),
        },
        "entries": entries_out,
        "sources": sources_out,
        "h003_preview": _load_h003_preview(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "portal_data.js"
    data_path.write_text(
        f"window.__KB_PORTAL_DATA__={_safe_js_json(portal_payload)};\n",
        encoding="utf-8",
        newline="\n",
    )

    css_text = (PORTAL_SRC_DIR / "styles.css").read_text(encoding="utf-8")
    js_blocks = "\n\n".join(
        f"/* === {name} === */\n" + (PORTAL_SRC_DIR / name).read_text(encoding="utf-8")
        for name in JS_BUNDLE_FILES
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>组合优化学术知识展馆 · 结构化机理与实证白皮书</title>
<style>
{css_text}
</style>
</head>
<body>
<div id="portal-app">
  <div style="padding:48px;text-align:center;color:#78716c;">正在加载组合优化学术知识展馆……</div>
</div>
<div id="drawer-backdrop" class="drawer-backdrop hidden">
  <aside id="drawer-panel" class="drawer-panel" role="dialog" aria-label="知识条目详情"></aside>
</div>
<div id="present-overlay" class="present-overlay hidden" role="dialog" aria-label="答辩演示模式"></div>
<script src="./portal_data.js"></script>
<script>
{js_blocks}
</script>
</body>
</html>
"""
    index_path = output_dir / "index.html"
    index_path.write_text(html, encoding="utf-8", newline="\n")

    return {
        "ok": True,
        "release_dir": str(release_dir),
        "output_dir": str(output_dir),
        "index_html": str(index_path),
        "portal_data_js": str(data_path),
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "entries_embedded": len(entries_out),
        "sources_embedded": len(sources_out),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    res = build_kb_portal(release_dir=args.release, output_dir=args.output_dir)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
