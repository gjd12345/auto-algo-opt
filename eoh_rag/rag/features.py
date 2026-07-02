"""
模块：features（策略特征抽取）
功能：把启发式算法的源代码或文字描述，映射为一组标准化的“策略特征”标签，用于 RAG 检索与算法演化时判断某段代码用到了哪些优化思路。
职责：维护一套规范特征词表（如 best_fit / nearest / regret / two_opt 等）、别名映射与匹配模式；提供从代码标识符、卡片标签、群体个体中提取特征的工具函数。
接口：
  - extract_identifier_tokens(code) / extract_code_features(code)：抽取代码里的标识符词元（含停用词过滤）。
  - normalize_strategy_feature(token)：把单个标签/词归一化到规范特征名，命中不了则返回 None。
  - extract_strategy_features(code)：用严格的边界模式，把代码映射为规范特征集合。
  - extract_card_features(item)：优先用卡片标签，其次用标题/摘要文本抽取特征。
  - load_population_features(population, top_fraction, diversity_mode)：从演化群体的有效个体中汇总策略特征。
输入：待分析的代码字符串、CorpusItem 语料卡片对象、或算法演化群体（list[dict]，每个个体含 objective 与 code 字段）。
输出：字符串集合 set[str]，元素均为 STRATEGY_FEATURES 中的规范特征名。
示例：
  >>> extract_strategy_features("score = best_fit(bin) - nearest_distance(node)")
  {'best_fit', 'nearest', 'distance'}
"""
from __future__ import annotations

import re

from .schemas import CorpusItem


# 在 camelCase 的“小写/数字 + 大写”交界处切分，例如 bestFit -> best_Fit
_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
# 匹配一个合法的代码标识符（字母开头，可含数字，可用下划线连接多段）
_CODE_FEATURE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*")
# 规范策略特征词表：所有对外输出的特征名都必须落在这个集合内
STRATEGY_FEATURES = frozenset({
    "adaptive_weights", "best_fit", "capacity", "centrality", "cluster",
    "depot", "destination", "detour", "distance", "farthest", "first_fit",
    "harmonic", "lookahead", "nearest", "normalize", "penalty", "regret",
    "remaining_aware", "residual", "savings", "sweep", "tightness",
    "two_opt", "utilization", "worst_fit",
})
# 曾在语料中出现、但未纳入规范词表的观测特征词，仅作参考记录，不参与最终输出
LEGACY_OBSERVED_FEATURES = frozenset({
    "angle", "balance", "clustering", "cost_delta", "diffusion", "exp",
    "feasibility", "forward_score", "greedy", "insertion", "isolation",
    "local_search", "merge", "polynomial", "progress", "route_consolidation",
    "select_next", "smooth_route", "sqrt", "threshold", "two_hop",
    "weighted_score",
})
# 语义偏弱的上下文词元（如数学符号、通用变量），出现时不足以判定为某种策略
WEAK_CONTEXT_TOKENS = frozenset({
    "alpha", "beta", "demand", "feasible", "future", "gamma", "return",
})
# 特征别名映射：把常见的等价写法归一化到规范特征名（键为归一化后的写法）
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
# 特征匹配模式表：规范特征名 -> 一组代码中可能出现的关键片段；命中任一片段即认定用到该特征
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
# 代码停用词：语言关键字、内置类型、以及通用接口变量名，抽取标识符时需要过滤掉，
# 因为它们不代表任何具体的优化策略
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
    """把标识符按 camelCase、snake_case、kebab-case 切分成若干小写片段。"""
    token = _CAMEL_SPLIT_RE.sub(r"\1_\2", token)  # 驼峰交界处插入下划线
    token = token.replace("-", "_")  # 短横线统一替换为下划线
    return [part.lower() for part in token.split("_") if part]  # 按下划线切分并转小写


def extract_identifier_tokens(code: str | None) -> set[str]:
    """从代码中抽取标识符词元集合。

    先用正则找出所有标识符，再逐个拆成小写片段；只保留长度 >= 3
    且不在停用词表中的片段。code 为空时返回空集合。
    """
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
    """抽取代码标识符词元的别名入口，直接转发给 extract_identifier_tokens。"""
    return extract_identifier_tokens(code)


def _normalized_text(value: str) -> str:
    # 归一化文本：驼峰拆分、转小写、把连字符/空白折叠成单个下划线，并去掉首尾多余下划线
    normalized = _CAMEL_SPLIT_RE.sub(r"\1_\2", value)
    normalized = re.sub(r"[-\s]+", "_", normalized.lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def normalize_strategy_feature(token: str | None) -> str | None:
    """把一个明确的标签/特征词归一化到规范策略特征名。

    先做文本归一化，再查别名映射；若最终结果落在 STRATEGY_FEATURES 中
    则返回该规范名，否则返回 None（表示未识别为已知策略）。
    """
    if not token:
        return None
    normalized = _normalized_text(str(token))
    canonical = FEATURE_ALIASES.get(normalized, normalized)
    return canonical if canonical in STRATEGY_FEATURES else None


def _contains_pattern(normalized_code: str, pattern: str) -> bool:
    # 判断归一化后的代码中是否“整词”出现某个模式片段：
    # 用前后不接字母/数字的边界断言，避免误匹配到更长单词的一部分
    normalized_pattern = _normalized_text(pattern)
    return re.search(
        rf"(?<![a-z0-9]){re.escape(normalized_pattern)}(?![a-z0-9])",
        normalized_code,
    ) is not None


def extract_strategy_features(code: str | None) -> set[str]:
    """把代码映射为规范策略特征集合。

    仅采用 FEATURE_PATTERNS 中带边界约束的强匹配模式：某特征只要命中
    其任意一个关键片段即被收录。code 为空时返回空集合。
    """
    if not code:
        return set()
    normalized_code = _normalized_text(code)
    return {
        feature
        for feature, patterns in FEATURE_PATTERNS.items()
        if any(_contains_pattern(normalized_code, pattern) for pattern in patterns)
    }


def extract_card_features(item: CorpusItem) -> set[str]:
    """从语料卡片中抽取规范策略特征。

    优先把卡片标签逐个归一化为规范特征；只要标签能得到任一特征，就直接返回。
    否则退回到用卡片的 id、标题、摘要拼接文本，走强模式抽取。
    """
    # 第一优先级：直接从标签归一化得到规范特征
    tag_features = {
        canonical
        for tag in item.tags
        if (canonical := normalize_strategy_feature(tag)) is not None
    }
    if tag_features:
        return tag_features
    # 标签没有可用特征时，改用描述性文本兜底抽取
    return extract_strategy_features("\n".join((item.id, item.title, item.summary)))


def load_population_features(
    population: list[dict],
    top_fraction: float = 1.0,
    diversity_mode: str = "all",
) -> set[str]:
    """从演化群体的有效个体中汇总策略特征。

    只统计 objective 不为 None 且含有 code 的个体；objective 越小越好。
    top_fraction 用于限定只取按目标值排序后最优的前 N% 个体。

    diversity_mode（多样性模式）：
      "all"        —— 对前 top_fraction 的个体统一抽取特征（默认）
      "elite_only" —— 等价于把 top_fraction 强制设为 0.25
      "diversity"  —— 只返回最优个体的特征（用于挑选互补卡片）
    """
    # 过滤出格式合法、目标值存在且带代码的个体
    valid = [
        individual for individual in population
        if isinstance(individual, dict)
        and individual.get("objective") is not None
        and individual.get("code")
    ]
    if not valid:
        return set()
    valid.sort(key=lambda item: item["objective"])  # 按目标值升序排序（越小越优）

    if diversity_mode == "elite_only":
        top_fraction = 0.25  # 精英模式：只看最优的 25%
    elif diversity_mode == "diversity":
        # 多样性模式：只取排序后第一名（最优个体）的特征
        return extract_strategy_features(valid[0]["code"])

    # 计算参与统计的个体数量（至少 1 个），并对其特征取并集
    count = max(1, int(len(valid) * top_fraction))
    features: set[str] = set()
    for individual in valid[:count]:
        features |= extract_strategy_features(individual["code"])
    return features
