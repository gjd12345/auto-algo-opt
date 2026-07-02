"""
模块：failure_cases —— 主线 RAG failure_case 语料（curated）
功能：提供 BP/TSP/CVRP 通用的"无效候选/失败模式"卡片，注入 RAG prompt 作为反面约束。
职责：定义 3 张 failure_case 卡（内容为 curated 静态文本，描述当前通用规则）。
不负责：
  - 运行时候选分类（由候选校验逻辑负责，与本模块无关）
  - 语料落盘/加载（由 build_corpus 负责，本模块只产出 CorpusItem）
主要调用方：eoh_rag.rag.build_corpus.build_failure_cases（re-export）→ build_all_corpora。

接口：
    def build_failure_cases(project_root=None) -> list[CorpusItem]

输入：project_root（为对齐 builder 统一调用签名而保留，实际忽略——内容是 curated 静态文本）
输出：list[CorpusItem]，kind 均为 "failure_case"，source_path="curated"，content 非空

示例：
    from eoh_rag.rag.failure_cases import build_failure_cases
    cards = build_failure_cases()          # 3 张 curated failure_case 卡
"""

from __future__ import annotations

from pathlib import Path

from .schemas import CorpusItem


# ---------------------------------------------------------------------------
# curated failure-case 内容 —— 覆盖当前三个官方问题（BP/TSP/CVRP）的通用无效模式
# ---------------------------------------------------------------------------

_SUSPICIOUS_LOW = """A suspiciously low objective usually means the candidate is invalid, not excellent.
Common causes: skipped items/orders, broken cost accumulation, a penalty/sentinel
objective (e.g. 1e9) misread as a good score, or incomplete evaluation.
Validate before trusting — recompute the full objective over all inputs.
- BP Online: ScoreBin must return finite scores for every bin; a near-zero
  objective from returning identical or degenerate scores is invalid.
- TSP / CVRP: every node/customer must be visited exactly once; a low tour cost
  produced by skipping nodes is invalid."""

_NEGATIVE_OR_MISSING = """Negative costs, missing return values, or a missing required function are invalid
candidate outcomes — never treat them as feasible.
- Missing code or a missing target function (ScoreBin / select_next_node / ...) is
  an immediate invalid.
- Negative, NaN, or inf objective is an artifact, not an improvement.
- TSP / CVRP: the heuristic must return a valid, in-range node/customer index.
- Return a complete result object; do not emit partial results."""

_TIMEOUT_OR_UNBOUNDED = """A timeout means unbounded or super-linear computation, not merely a hard instance.
Expensive exhaustive search times out on dense or large instances.
- Bound candidate scans; avoid nested loops over all nodes and unbounded while loops.
- Prefer O(n log n) / O(n) scoring; add safe fallback logic when a step is costly.
- A candidate that cannot finish within the eval timeout is invalid regardless of
  its partial objective."""


def build_failure_cases(project_root: str | Path | None = None) -> list[CorpusItem]:
    """返回 3 张 curated failure_case 卡（内容为当前通用规则）。

    project_root 仅为对齐 builder 统一调用签名而保留，本函数不读取任何文件。
    """
    return [
        CorpusItem(
            id="suspicious_low_objective",
            kind="failure_case",
            title="Suspiciously low objective",
            tags=["all", "suspicious-low", "guard", "objective"],
            source_path="curated",
            summary="Very low objective values can indicate skipped items, broken costs, or incomplete evaluation.",
            constraints=[
                "Do not treat suspicious-low objective values as valid.",
                "Recompute the full objective over all inputs before trusting it.",
            ],
            content=_SUSPICIOUS_LOW,
        ),
        CorpusItem(
            id="negative_or_missing_result",
            kind="failure_case",
            title="Negative cost or missing result",
            tags=["all", "negative", "missing-result", "guard"],
            source_path="curated",
            summary="Negative costs, missing results, or missing functions are invalid candidate outcomes.",
            constraints=[
                "Return a complete result object.",
                "Do not allow negative / NaN / inf objective artifacts.",
            ],
            content=_NEGATIVE_OR_MISSING,
        ),
        CorpusItem(
            id="timeout_or_unbounded_search",
            kind="failure_case",
            title="Timeout or unbounded search",
            tags=["all", "timeout", "guard", "fallback"],
            source_path="curated",
            summary="Expensive exhaustive search can time out on dense or large instances.",
            constraints=[
                "Bound candidate scans; avoid nested loops over all nodes.",
                "Use bounded attempts and safe fallback logic.",
            ],
            content=_TIMEOUT_OR_UNBOUNDED,
        ),
    ]


__all__ = ["build_failure_cases"]
