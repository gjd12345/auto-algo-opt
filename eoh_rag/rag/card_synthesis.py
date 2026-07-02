"""Best-code → Card feedback loop.

Extracts strategy features from evolutionary best code, synthesizes
Skill Cards, and appends them to the RAG corpus so future runs can
retrieve evolved strategies.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .features import (
    extract_strategy_features as _extract_canonical_strategy_features,
    normalize_strategy_feature,
)
from .problem_vocab import get_feature_vocab
from .schemas import CorpusItem, load_corpus, save_corpus

# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def extract_strategy_features(code: str | None) -> set[str]:
    """Backward-compatible wrapper for canonical feature extraction."""
    return _extract_canonical_strategy_features(code)


def get_code_family(code: str | None) -> set[str]:
    """Backward-compatible wrapper returning canonical strategy features."""
    return _extract_canonical_strategy_features(code)


# ---------------------------------------------------------------------------
# Card synthesis
# ---------------------------------------------------------------------------

# Human-readable descriptions per feature, used to build Skill Card content.
_FEATURE_DO: dict[str, str] = {
    "destination": "minimize d(current,u) + alpha*d(u,dest), increasing alpha as fewer nodes remain",
    "normalize": "normalize forward and backward distances to [0,1] before combining",
    "adaptive_weights": "use remaining_ratio to dynamically adjust forward vs backward weights",
    "regret": "maximize regret = second_best - best and prefer high regret candidates",
    "farthest": "maximize depot/current distance early to seed distant clusters",
    "cluster": "identify unvisited node clusters; visit distant clusters before nearby ones",
    "centrality": "prefer nodes with high closeness centrality or high MST edge weight",
    "penalty": "penalize candidates very close to destination unless few nodes remain",
    "lookahead": "consider 2-step lookahead; penalize choices that strand distant nodes",
    "savings": "compute savings S(i,j) = d(ref,i)+d(ref,j)-d(i,j); merge by highest savings",
    "nearest": "select the unvisited node with minimum distance from current node",
    "capacity": "filter to feasible candidates that fit remaining vehicle capacity",
    "forward_score": "weight the direct distance from current node to candidate",
    "remaining_aware": "adapt strategy based on how many nodes remain",
    "diffusion": "propagate influence scores through nearby nodes for diversified selection",
    "threshold": "filter candidates whose score exceeds a dynamic threshold",
}

_FEATURE_WHEN: dict[str, str] = {
    "destination": "the tour must return to a destination/depot and the last edge is costly",
    "normalize": "forward and backward distances are on different scales",
    "adaptive_weights": "early tour steps should favor exploration, late steps should favor return",
    "regret": "several candidates compete and one may become costly later",
    "farthest": "distant clusters may be left until too late",
    "cluster": "unvisited nodes form spatial clusters",
    "centrality": "some nodes are more central and should be visited strategically",
    "penalty": "premature return to destination wastes tour length",
    "lookahead": "greedy choices can strand distant nodes",
    "savings": "merging separate trips can reduce total distance",
    "nearest": "a simple greedy baseline is needed",
    "capacity": "vehicle capacity constrains which customers can be served",
    "forward_score": "direct connection cost is the primary selection signal",
    "remaining_aware": "strategy should adapt as the tour progresses",
    "diffusion": "pure greedy gets stuck in local patterns",
    "threshold": "too many candidates need filtering before scoring",
}

# Problem-specific API constraints (reused from build_corpus patterns).
_PROBLEM_CONSTRAINTS: dict[str, list[str]] = {
    "tsp_construct": [
        "Return exactly one int from unvisited_nodes.",
        "Never return a visited node or destination_node.",
        "Do not mutate unvisited_nodes or distance_matrix.",
        "Keep computation bounded and deterministic.",
    ],
    "cvrp_construct": [
        "Return one int from unvisited_nodes, or depot only when intentionally ending the route.",
        "Never return an infeasible node (demand > rest_capacity).",
        "Do not mutate unvisited_nodes, demands, or distance_matrix.",
    ],
}


def _feature_hash(features: set[str], max_features: int = 3) -> str:
    """Short hash from top feature names for unique card IDs."""
    sorted_features = sorted(features)
    key = "_".join(sorted_features[:max_features])
    # Add short hash to avoid collisions when feature sets overlap
    short = hashlib.md5("_".join(sorted_features).encode()).hexdigest()[:6]
    return f"{key}_{short}"


_CARD_FEATURE_PRIORITY: list[str] = [
    "regret",
    "farthest",
    "savings",
    "cluster",
    "centrality",
    "destination",
    "capacity",
    "normalize",
    "adaptive_weights",
    "lookahead",
    "remaining_aware",
    "nearest",
    "forward_score",
    "penalty",
]


def _select_card_features(features: set[str], max_features: int = 3) -> set[str]:
    """Keep a history card as a small operator, not a full-code summary."""
    selected = [feature for feature in _CARD_FEATURE_PRIORITY if feature in features]
    selected.extend(feature for feature in sorted(features) if feature not in selected)
    return set(selected[:max_features])


def _build_title(problem: str, features: set[str]) -> str:
    """Generate a human-readable card title."""
    prefix = problem.split("_")[0].upper()  # TSP, CVRP, etc.
    # Pick the 2-3 most distinctive features
    priority = ["regret", "farthest", "destination", "normalize", "adaptive_weights",
                "cluster", "centrality", "savings", "penalty", "lookahead"]
    selected = [f for f in priority if f in features][:3]
    if not selected:
        selected = sorted(features)[:2]
    label = " ".join(w.replace("_", " ").title() for w in selected)
    return f"{prefix} {label} Evolved Card"


def _build_summary(problem: str, features: set[str]) -> str:
    """Generate a one-line summary for retrieval scoring."""
    prefix = problem.split("_")[0].upper()
    priority = ["regret", "farthest", "destination", "normalize", "adaptive_weights",
                "cluster", "centrality", "savings"]
    selected = [f for f in priority if f in features][:3]
    if not selected:
        selected = sorted(features)[:2]
    strategy_desc = " + ".join(selected)
    return f"{prefix} construction heuristic evolved from best code: {strategy_desc}."


# ---------------------------------------------------------------------------
# Code snippet extraction
# ---------------------------------------------------------------------------

_SCORING_KEYWORDS = frozenset([
    "score", "scores", "weight", "weights", "cost", "costs",
    "regret", "metric", "priority", "distance", "dist",
    "penalty", "rank", "value", "argmin", "argmax",
])

_DANGEROUS_PATTERNS = re.compile(
    r"(?:import\s|from\s.*import|open\(|os\.|subprocess\.|"
    r"sys\.|print\(|logging\.|sleep\(|random\.|"
    r"requests\.|urllib\.|http\.|socket\.)",
    re.MULTILINE
)

_MAX_SNIPPET_LINES = 15
_MAX_SNIPPET_CHARS = 700


def _is_dangerous_line(line: str) -> bool:
    return bool(_DANGEROUS_PATTERNS.search(line))


def _nesting_depth(code: str) -> int:
    """Estimate max indentation nesting depth."""
    max_depth = 0
    for line in code.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        depth = indent // 4
        max_depth = max(max_depth, depth)
    return max_depth


def _extract_scoring_core_ast(code: str) -> str | None:
    """Try AST-based extraction: find return stmt, trace back assignments."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    func_bodies = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_bodies.append(node)

    if not func_bodies:
        return None

    target_func = func_bodies[0]
    lines = code.splitlines()

    returns = [n for n in ast.walk(target_func) if isinstance(n, ast.Return)]
    if not returns:
        return None

    last_return = None
    for node in ast.walk(target_func):
        if isinstance(node, ast.Return):
            last_return = node

    if last_return is None:
        return None

    end_line = last_return.lineno
    start_line = max(1, end_line - _MAX_SNIPPET_LINES + 1)

    func_start = target_func.lineno
    start_line = max(start_line, func_start + 1)

    snippet_lines = lines[start_line - 1:end_line]
    snippet_lines = [l for l in snippet_lines if not _is_dangerous_line(l)]

    if len(snippet_lines) > _MAX_SNIPPET_LINES:
        snippet_lines = snippet_lines[-_MAX_SNIPPET_LINES:]

    return "\n".join(snippet_lines).strip() if snippet_lines else None


def _extract_scoring_core_keyword(code: str) -> str | None:
    """Fallback: find lines with scoring keywords, expand window."""
    lines = code.splitlines()
    score_lines = []

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in _SCORING_KEYWORDS):
            if not _is_dangerous_line(line):
                score_lines.append(i)

    if not score_lines:
        return None

    center = score_lines[len(score_lines) // 2]
    half_window = _MAX_SNIPPET_LINES // 2

    start = max(0, center - half_window)
    end = min(len(lines), center + half_window + 1)

    snippet_lines = [l for l in lines[start:end] if not _is_dangerous_line(l)]
    if len(snippet_lines) > _MAX_SNIPPET_LINES:
        snippet_lines = snippet_lines[:_MAX_SNIPPET_LINES]

    return "\n".join(snippet_lines).strip() if snippet_lines else None


def _extract_scoring_core(code: str | None, max_lines: int = _MAX_SNIPPET_LINES) -> str | None:
    """Extract scoring/selection core from heuristic code.

    Returns None if no meaningful snippet can be extracted.
    """
    if not code or not code.strip():
        return None

    snippet = _extract_scoring_core_ast(code)
    if not snippet:
        snippet = _extract_scoring_core_keyword(code)

    if not snippet:
        return None

    if _nesting_depth(snippet) > 3:
        return None

    if "while True" in snippet or "while 1" in snippet:
        return None

    lines = snippet.splitlines()[:max_lines]
    result = "\n".join(lines)

    if len(result) > _MAX_SNIPPET_CHARS:
        result = result[:_MAX_SNIPPET_CHARS].rsplit("\n", 1)[0]

    return result.strip() if result.strip() else None


def _build_formula_summary(features: set[str]) -> str:
    """One-line formula summary from detected features."""
    parts = []
    if "regret" in features:
        parts.append("regret = second_best - best")
    if "adaptive_weights" in features:
        parts.append("alpha = remaining_ratio")
    if "destination" in features:
        parts.append("score includes d(node, dest)")
    if "normalize" in features:
        parts.append("distances normalized to [0,1]")
    if "savings" in features:
        parts.append("savings = d(ref,i)+d(ref,j)-d(i,j)")
    if "farthest" in features:
        parts.append("prefer distant nodes early")
    if "cluster" in features:
        parts.append("cluster-aware selection")
    if not parts:
        parts.append("composite scoring from detected features")
    return "; ".join(parts[:3])


def _build_content(problem: str, features: set[str], code: str | None = None) -> str:
    """Generate Skill Card content (When/Do/Fallback/Safety + Formula + Code)."""
    prefix = problem.split("_")[0].upper()

    # 使用 problem-specific 词表，防止 TSP/CVRP 语言泄漏到 BP card
    prob_do, prob_when = get_feature_vocab(problem)
    feature_do = prob_do if prob_do else _FEATURE_DO
    feature_when = prob_when if prob_when else _FEATURE_WHEN

    # When: combine relevant conditions
    when_parts = []
    for f in sorted(features):
        if f in feature_when:
            when_parts.append(feature_when[f])
    when = "; ".join(when_parts[:3]) if when_parts else f"constructing a {prefix} solution step by step."

    # Do: combine algorithmic steps
    do_parts = []
    for f in sorted(features):
        if f in feature_do:
            do_parts.append(feature_do[f])
    do = ". ".join(do_parts[:4]) if do_parts else "apply the evolved scoring formula from best code."

    content = (
        f"Skill: {prefix.lower()}_evolved_{'_'.join(sorted(features)[:3])}\n"
        f"When: {when}\n"
        f"Do: {do}\n"
        f"Fallback: nearest neighbor if scores tie or few nodes remain.\n"
        f"Safety: return one valid node; do not mutate inputs; keep computation bounded."
    )

    # Append structured sections for enhanced retrieval
    feature_tags = ", ".join(sorted(features))
    content += f"\n\nFeature tags: {feature_tags}"

    formula = _build_formula_summary(features)
    content += f"\nFormula summary: {formula}"

    snippet = _extract_scoring_core(code) if code else None
    if snippet:
        content += f"\n\nCode pattern:\n```python\n{snippet}\n```"
    else:
        content += "\n\nCode pattern: -"

    return content


def synthesize_card(
    problem: str,
    code: str,
    features: set[str] | None = None,
    run_info: dict[str, Any] | None = None,
) -> CorpusItem:
    """Synthesize a Skill Card from best code and its detected features.

    Parameters
    ----------
    problem : str
        Problem identifier (e.g. ``"tsp_construct"``).
    code : str
        The best code from an evolutionary run.
    features : set[str] | None
        Pre-extracted features; if ``None``, extracted from *code*.
    run_info : dict | None
        Optional metadata (``run_dir``, ``objective``, ``generation``).
    """
    if features is None:
        features = extract_strategy_features(code)
    else:
        features = {
            canonical
            for feature in features
            if (canonical := normalize_strategy_feature(feature)) is not None
        }
    if not features:
        raise ValueError("No strategy features detected in code; cannot synthesize card.")
    card_features = _select_card_features(features)

    run_info = run_info or {}
    feature_hash = _feature_hash(card_features)
    card_id = f"history_{problem}_{feature_hash}"
    source_path = str(run_info.get("run_dir", "auto_synthesized"))

    return CorpusItem(
        id=card_id,
        kind="algorithm_card",
        title=_build_title(problem, card_features),
        tags=[problem.split("_")[0], "construct", "evolved"] + sorted(card_features),
        source_path=source_path,
        summary=_build_summary(problem, card_features),
        constraints=_PROBLEM_CONSTRAINTS.get(problem, []),
        content=_build_content(problem, card_features, code=code),
    )


# ---------------------------------------------------------------------------
# Corpus persistence
# ---------------------------------------------------------------------------

def append_card_to_corpus(card: CorpusItem, corpus_dir: str | Path) -> bool:
    """Append *card* to ``algorithm_cards.jsonl`` if not already present.

    Returns ``True`` if the card was written, ``False`` if it was a duplicate.
    """
    corpus_path = Path(corpus_dir) / "algorithm_cards.jsonl"
    existing = load_corpus(corpus_path) if corpus_path.exists() else []
    existing_ids = {item.id for item in existing}
    if card.id in existing_ids:
        return False
    existing.append(card)
    save_corpus(existing, corpus_path)
    return True
