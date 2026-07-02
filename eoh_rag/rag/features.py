from __future__ import annotations

import re

from .schemas import CorpusItem


_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
_CODE_FEATURE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*")
STRATEGY_FEATURES = frozenset({
    "adaptive_weights", "best_fit", "capacity", "centrality", "cluster",
    "depot", "destination", "detour", "distance", "farthest", "first_fit",
    "harmonic", "lookahead", "nearest", "normalize", "penalty", "regret",
    "remaining_aware", "residual", "savings", "sweep", "tightness",
    "two_opt", "utilization", "worst_fit",
})
LEGACY_OBSERVED_FEATURES = frozenset({
    "angle", "balance", "clustering", "cost_delta", "diffusion", "exp",
    "feasibility", "forward_score", "greedy", "insertion", "isolation",
    "local_search", "merge", "polynomial", "progress", "route_consolidation",
    "select_next", "smooth_route", "sqrt", "threshold", "two_hop",
    "weighted_score",
})
WEAK_CONTEXT_TOKENS = frozenset({
    "alpha", "beta", "demand", "feasible", "future", "gamma", "return",
})
FEATURE_ALIASES = {
    "2opt": "two_opt",
    "bestfit": "best_fit",
    "clarke_wright": "savings",
    "clustering": "cluster",
    "far_first": "farthest",
    "firstfit": "first_fit",
    "look_ahead": "lookahead",
    "pair_savings": "savings",
    "regret2": "regret",
    "worstfit": "worst_fit",
}
FEATURE_PATTERNS: dict[str, tuple[str, ...]] = {
    "adaptive_weights": ("adaptive_weight", "dynamic_weight", "remaining_ratio"),
    "best_fit": ("best_fit", "bestfit"),
    "capacity": (
        "capacity_aware", "capacity_check", "capacity_penalty", "capacity_slack",
        "capacity_utilization", "remaining_vehicle_capacity", "rest_capacity",
    ),
    "centrality": ("centrality", "closeness_centrality", "minimum_spanning_tree", "mst"),
    "cluster": ("cluster", "clustering", "centroid", "kmeans", "k_means"),
    "depot": ("depot_distance", "distance_from_depot", "distance_to_depot", "from_depot"),
    "destination": (
        "backward_distance", "bwd_distance", "dist_to_dest",
        "distance_to_destination", "destination_penalty", "return_distance",
    ),
    "detour": ("detour", "delta_distance", "insertion_cost"),
    "distance": ("distance_heuristic", "distance_penalty", "distance_score", "farthest_distance", "nearest_distance"),
    "farthest": ("farthest", "far_first", "distant", "max_dist"),
    "first_fit": ("first_fit", "firstfit"),
    "harmonic": ("harmonic", "size_class"),
    "lookahead": ("lookahead", "look_ahead", "two_step"),
    "nearest": ("nearest", "closest", "argmin", "min_dist", "minimum_distance"),
    "normalize": ("normalize", "normalization", "range_fwd"),
    "penalty": ("penalty", "penalize", "penalized"),
    "regret": ("regret", "regret2", "second_best"),
    "remaining_aware": ("remaining_aware", "remaining_ratio", "n_rem", "n_unvisited"),
    "residual": ("residual", "remaining_capacity", "capacity_slack", "slack"),
    "savings": ("saving", "savings", "clarke_wright", "pair_savings"),
    "sweep": ("sweep", "polar_angle", "angular_sector"),
    "tightness": ("tightness", "tight_fit"),
    "two_opt": ("two_opt", "2opt"),
    "utilization": ("utilization", "fill_ratio"),
    "worst_fit": ("worst_fit", "worstfit"),
}
_CODE_STOPWORDS = frozenset({
    # Go keywords
    "func", "return", "var", "int", "float64", "float32", "bool", "string",
    "nil", "len", "append", "make", "range", "for", "if", "else",
    "true", "false", "err", "error", "fmt", "math", "sort",
    "package", "import", "main", "type", "struct", "interface",
    "break", "continue", "switch", "case", "default", "defer", "go",
    "chan", "map", "select", "fallthrough", "goto", "const",
    # Python keywords/builtins
    "def", "self", "none", "class", "lambda", "yield", "pass",
    "try", "except", "finally", "raise", "with", "print",
    "numpy", "array", "list", "dict", "tuple", "set", "float",
    # Common API/interface variables (not strategy features)
    "item", "items", "bins", "remaining", "capacity",
    "current", "node", "scores", "score", "result",
    "destination", "unvisited", "visited", "nodes",
    "distance", "matrix", "demands", "depot",
    "rest", "index", "value", "values", "total",
    "obj", "args", "kwargs", "data", "output", "input",
})


def _split_identifier(token: str) -> list[str]:
    """Split camelCase, snake_case, and kebab-case into parts."""
    token = _CAMEL_SPLIT_RE.sub(r"\1_\2", token)
    token = token.replace("-", "_")
    return [part.lower() for part in token.split("_") if part]


def extract_identifier_tokens(code: str | None) -> set[str]:
    """Extract identifier tokens with the legacy stopword behavior."""
    if not code:
        return set()
    tokens = _CODE_FEATURE_RE.findall(code)
    features: set[str] = set()
    for token in tokens:
        for part in _split_identifier(token):
            if len(part) >= 3 and part not in _CODE_STOPWORDS:
                features.add(part)
    return features


def extract_code_features(code: str | None) -> set[str]:
    """Backward-compatible name for identifier-token extraction."""
    return extract_identifier_tokens(code)


def _normalized_text(value: str) -> str:
    normalized = _CAMEL_SPLIT_RE.sub(r"\1_\2", value)
    normalized = re.sub(r"[-\s]+", "_", normalized.lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def normalize_strategy_feature(token: str | None) -> str | None:
    """Normalize an explicit feature/tag to a canonical strategy feature."""
    if not token:
        return None
    normalized = _normalized_text(str(token))
    canonical = FEATURE_ALIASES.get(normalized, normalized)
    return canonical if canonical in STRATEGY_FEATURES else None


def _contains_pattern(normalized_code: str, pattern: str) -> bool:
    normalized_pattern = _normalized_text(pattern)
    return re.search(
        rf"(?<![a-z0-9]){re.escape(normalized_pattern)}(?![a-z0-9])",
        normalized_code,
    ) is not None


def extract_strategy_features(code: str | None) -> set[str]:
    """Map code to canonical features using strong, bounded patterns only."""
    if not code:
        return set()
    normalized_code = _normalized_text(code)
    return {
        feature
        for feature, patterns in FEATURE_PATTERNS.items()
        if any(_contains_pattern(normalized_code, pattern) for pattern in patterns)
    }


def extract_card_features(item: CorpusItem) -> set[str]:
    """Extract canonical features from card tags, then descriptive text."""
    tag_features = {
        canonical
        for tag in item.tags
        if (canonical := normalize_strategy_feature(tag)) is not None
    }
    if tag_features:
        return tag_features
    return extract_strategy_features("\n".join((item.id, item.title, item.summary)))


def load_population_features(
    population: list[dict],
    top_fraction: float = 1.0,
    diversity_mode: str = "all",
) -> set[str]:
    """Extract strategy features from valid individuals in a population.

    Only considers individuals with objective != None.
    top_fraction limits to the best N% by objective (lower is better).

    diversity_mode:
      "all" — extract features from top_fraction individuals (default)
      "elite_only" — equivalent to top_fraction=0.25
      "diversity" — return features of best individual only (for complementary card selection)
    """
    valid = [
        individual for individual in population
        if isinstance(individual, dict)
        and individual.get("objective") is not None
        and individual.get("code")
    ]
    if not valid:
        return set()
    valid.sort(key=lambda item: item["objective"])

    if diversity_mode == "elite_only":
        top_fraction = 0.25
    elif diversity_mode == "diversity":
        # Only the single best individual's features
        return extract_strategy_features(valid[0]["code"])

    count = max(1, int(len(valid) * top_fraction))
    features: set[str] = set()
    for individual in valid[:count]:
        features |= extract_strategy_features(individual["code"])
    return features
