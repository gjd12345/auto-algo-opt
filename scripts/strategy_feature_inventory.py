"""Generate a deterministic inventory of strategy-feature definitions and tags.

The script parses Python source with ``ast`` and corpus rows with ``json``. It
does not import runtime modules or modify runtime/corpus files.
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CANONICAL_CANDIDATES = frozenset({
    "adaptive_weights", "best_fit", "capacity", "centrality", "cluster",
    "depot", "destination", "detour", "distance", "farthest", "first_fit",
    "harmonic", "lookahead", "nearest", "normalize", "penalty", "regret",
    "remaining_aware", "residual", "savings", "sweep", "tightness",
    "two_opt", "utilization", "worst_fit",
})

LEGACY_OBSERVED = frozenset({
    "angle", "balance", "clustering", "cost-delta", "diffusion", "exp",
    "feasibility", "forward_score", "greedy", "insertion", "isolation",
    "local-search", "merge", "polynomial", "progress", "route-consolidation",
    "select-next", "smooth-route", "sqrt", "threshold", "two_hop",
    "weighted-score",
})

WEAK_CONTEXT_TOKENS = frozenset({
    "alpha", "beta", "demand", "feasible", "future", "gamma", "return",
})

FEATURE_ALIASES = {
    "2opt": "two_opt",
    "best-fit": "best_fit",
    "bestfit": "best_fit",
    "clarke-wright": "savings",
    "clustering": "cluster",
    "far_first": "farthest",
    "first-fit": "first_fit",
    "firstfit": "first_fit",
    "look_ahead": "lookahead",
    "pair-savings": "savings",
    "regret2": "regret",
    "remaining_capacity": "residual",
    "residual-capacity": "residual",
    "rest_capacity": "capacity",
    "return-distance": "destination",
    "second_best": "regret",
    "size-class": "harmonic",
    "worst-fit": "worst_fit",
    "worstfit": "worst_fit",
}

FEATURE_RISKS = {
    "adaptive_weights": ["alpha/beta/gamma are weak tokens and must not trigger alone"],
    "capacity": ["feasible/demand are weak tokens; capacity is also an API variable"],
    "depot": ["depot is commonly an API/interface token"],
    "destination": ["return is a weak token and causes broad false positives"],
    "distance": ["distance and distance_matrix are commonly API/interface tokens"],
    "lookahead": ["future is a weak token and must not trigger alone"],
}


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        value = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in {"frozenset", "set", "tuple", "list"}
                and len(value.args) == 1
                and not value.keywords
            ):
                literal = ast.literal_eval(value.args[0])
                constructors = {
                    "frozenset": frozenset,
                    "set": set,
                    "tuple": tuple,
                    "list": list,
                }
                return constructors[value.func.id](literal)
            return ast.literal_eval(value)
    raise ValueError(f"Assignment {name!r} not found in {path}")


def _optional_literal_assignment(path: Path, name: str) -> Any | None:
    try:
        return _literal_assignment(path, name)
    except ValueError:
        return None


def _load_corpus_tags(corpus_dir: Path) -> tuple[Counter[str], Counter[str], dict[str, set[str]]]:
    all_tags: Counter[str] = Counter()
    history_tags: Counter[str] = Counter()
    observed_in: dict[str, set[str]] = defaultdict(set)
    for path in sorted(corpus_dir.glob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Corpus row must be an object at {path}:{line_no}")
            is_history = str(payload.get("id", "")).startswith("history_")
            for raw_tag in payload.get("tags", []):
                tag = str(raw_tag).lower()
                all_tags[tag] += 1
                observed_in[tag].add(f"corpus:{path.name}")
                if is_history:
                    history_tags[tag] += 1
                    observed_in[tag].add("history_card_tags")
    return all_tags, history_tags, observed_in


def build_inventory(repo_root: Path) -> dict[str, Any]:
    features_path = repo_root / "eoh_rag/rag/features.py"
    synthesis_path = repo_root / "eoh_rag/rag/card_synthesis.py"
    reranker_path = repo_root / "eoh_rag/rag/reranker.py"
    controller_path = repo_root / "eoh_rag/tocc/controller.py"
    corpus_dir = repo_root / "eoh_rag_workspace/rag/corpus"

    code_stopwords = set(_literal_assignment(features_path, "_CODE_STOPWORDS"))
    legacy_patterns = _optional_literal_assignment(synthesis_path, "FEATURE_PATTERNS")
    legacy_code_family = _optional_literal_assignment(synthesis_path, "_CODE_FAMILY_FEATURES")
    synthesis_patterns = dict(
        legacy_patterns
        if legacy_patterns is not None
        else _literal_assignment(features_path, "FEATURE_PATTERNS")
    )
    code_family = set(
        legacy_code_family
        if legacy_code_family is not None
        else _literal_assignment(features_path, "STRATEGY_FEATURES")
    )
    pattern_source = (
        "card_synthesis.FEATURE_PATTERNS"
        if legacy_patterns is not None
        else "features.FEATURE_PATTERNS"
    )
    family_source = (
        "card_synthesis._CODE_FAMILY_FEATURES"
        if legacy_code_family is not None
        else "features.STRATEGY_FEATURES"
    )
    reranker_stopwords = set(
        _optional_literal_assignment(reranker_path, "_FEATURE_STOPWORDS") or set()
    )
    all_tags, history_tags, observed_in = _load_corpus_tags(corpus_dir)

    for name in synthesis_patterns:
        observed_in[name].add(pattern_source)
    for name in code_family:
        observed_in[name].add(family_source)
    for name in code_stopwords:
        observed_in[name].add("features._CODE_STOPWORDS")
    for name in reranker_stopwords:
        observed_in[name].add("reranker._FEATURE_STOPWORDS")

    terms = (
        set(observed_in)
        | set(CANONICAL_CANDIDATES)
        | set(LEGACY_OBSERVED)
        | set(WEAK_CONTEXT_TOKENS)
        | set(FEATURE_ALIASES)
    )
    feature_rows = []
    for name in sorted(terms):
        canonical_target = FEATURE_ALIASES.get(name)
        if name in CANONICAL_CANDIDATES:
            classification = "canonical_strategy_feature"
        elif name in WEAK_CONTEXT_TOKENS:
            classification = "weak_context_token"
        elif name in LEGACY_OBSERVED or canonical_target:
            classification = "legacy_observed_feature"
        else:
            classification = "metadata_tag"
        patterns = list(synthesis_patterns.get(name, []))
        feature_rows.append({
            "name": name,
            "classification": classification,
            "canonical_target": canonical_target,
            "overlap_enabled": name in CANONICAL_CANDIDATES,
            "observed_in": sorted(observed_in.get(name, set())),
            "aliases": sorted(alias for alias, target in FEATURE_ALIASES.items() if target == name),
            "patterns": patterns,
            "in_code_stopwords": name in code_stopwords,
            "in_reranker_stopwords": name in reranker_stopwords,
            "corpus_tag_count": all_tags[name],
            "history_tag_count": history_tags[name],
            "risk_notes": FEATURE_RISKS.get(name, []),
        })

    return {
        "schema_version": 1,
        "sources": [
            "eoh_rag/rag/features.py",
            "eoh_rag/rag/card_synthesis.py",
            "eoh_rag/rag/reranker.py",
            "eoh_rag/tocc/controller.py",
            "eoh_rag_workspace/rag/corpus/*.jsonl",
        ],
        "module_extractors": [
            {
                "module": "eoh_rag/rag/features.py",
                "behavior": (
                    "identifier extraction remains compatible; canonical taxonomy uses aliases and bounded strong patterns; "
                    "population unions canonical features from valid individuals"
                ),
            },
            {
                "module": "eoh_rag/rag/card_synthesis.py",
                "behavior": "delegates strategy extraction and code-family compatibility wrappers to rag.features",
            },
            {
                "module": "eoh_rag/rag/reranker.py",
                "behavior": "delegates card tags and id/title/summary fallback to rag.features.extract_card_features",
            },
            {
                "module": "eoh_rag/tocc/controller.py",
                "behavior": "delegates code-family extraction directly to rag.features.extract_strategy_features",
            },
        ],
        "aliases": dict(sorted(FEATURE_ALIASES.items())),
        "patterns": {key: value for key, value in sorted(synthesis_patterns.items())},
        "stopwords": {
            "code": sorted(code_stopwords),
            "reranker": sorted(reranker_stopwords),
        },
        "features": feature_rows,
        "risks": [
            "substring matching has no token boundaries",
            "return -> destination and feasible -> capacity are broad false-positive paths",
            "distance/capacity/destination/depot are code stopwords but also strategy candidates",
            "reranker currently treats arbitrary non-stopword tags as overlap features",
        ],
    }


def render_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Strategy Feature Inventory",
        "",
        "This file is generated by `scripts/strategy_feature_inventory.py`.",
        "It records current behavior and proposed classifications; it does not change runtime behavior.",
        "",
        "## Current Extractors",
        "",
    ]
    for item in inventory["module_extractors"]:
        lines.append(f"- `{item['module']}`: {item['behavior']}")
    lines.extend(["", "## Classification", ""])
    for classification in (
        "canonical_strategy_feature",
        "legacy_observed_feature",
        "weak_context_token",
        "metadata_tag",
    ):
        names = [row["name"] for row in inventory["features"] if row["classification"] == classification]
        lines.append(f"- **{classification}**: {', '.join(f'`{name}`' for name in names) or '-'}")
    lines.extend([
        "",
        "Canonical features are overlap candidates. Legacy observed features remain traceable but default to overlap disabled.",
        "Weak context tokens must only participate in compound patterns.",
        "",
        "## Feature Evidence",
        "",
        "| Name | Class | Canonical target | Overlap | Observed in | Corpus/history count | Risks |",
        "|---|---|---|---:|---|---:|---|",
    ])
    for row in inventory["features"]:
        observed = "<br>".join(row["observed_in"]) or "-"
        risks = "<br>".join(row["risk_notes"]) or "-"
        target = row["canonical_target"] or "-"
        counts = f"{row['corpus_tag_count']}/{row['history_tag_count']}"
        lines.append(
            f"| `{row['name']}` | {row['classification']} | `{target}` | "
            f"{'yes' if row['overlap_enabled'] else 'no'} | {observed} | {counts} | {risks} |"
        )
    lines.extend(["", "## Known Risks", ""])
    lines.extend(f"- {risk}" for risk in inventory["risks"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    markdown_path = args.markdown_output or repo_root / "docs/strategy_feature_inventory.md"
    json_path = args.json_output or repo_root / "docs/strategy_feature_inventory.json"
    inventory = build_inventory(repo_root)
    markdown_path.write_text(render_markdown(inventory), encoding="utf-8")
    json_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
