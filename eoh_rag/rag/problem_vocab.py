"""
模块：problem_vocab（问题专属词汇表）
功能：为不同的组合优化问题提供一套受控的启发式特征词汇，供卡片合成与 RAG 提示词生成使用。
职责：管理各问题（在线装箱、TSP、CVRP）的“特征动作（DO）”与“适用场景（WHEN）”文本，
      使描述性语言与对应问题的领域术语一致，避免各问题的表述互相串味。
接口：get_feature_vocab(problem: str) -> tuple[dict[str, str], dict[str, str]]
      按问题名返回 (feature_do, feature_when) 两个词典。
输入：调用时传入的问题标识字符串，如 "bp_online"、"tsp_construct"、"cvrp_construct"。
输出：两个字符串到字符串的映射：键是特征名，值是该特征的自然语言解释。
示例：
    do, when = get_feature_vocab("bp_online")
    print(do["best_fit"])   # 输出该特征对应的动作说明
"""

from __future__ import annotations


# BP Online（在线装箱）—— 装箱问题相关术语
# 下面两个字典用同一套“特征名”作为键：
#   *_DO   描述“该特征让启发式做什么动作”
#   *_WHEN 描述“该特征在什么情况下适用”


# BP Online — bin packing terminology
# BP_FEATURE_DO：装箱问题中每个特征“要做的动作”说明（键=特征名，值=动作描述）
BP_FEATURE_DO: dict[str, str] = {
    "residual": "prefer bins with small positive residual after placing item",
    "tight_fit": "reward close fit (residual near zero) without overflow",
    "utilization": "prefer bins with high current utilization (filled fraction)",
    "harmonic": "group items by size class relative to bin capacity, handle differently",
    "gap_penalty": "penalize unusable leftover capacity (residual too small for future items)",
    "fragmentation": "avoid creating many partially-filled bins; consolidate",
    "best_fit": "select the bin where item fits most tightly (minimum residual)",
    "worst_fit": "select largest residual bin to keep options open for later items",
    "adaptive": "switch strategy based on item-to-capacity ratio (small/medium/large)",
    "exponential": "use exp() to amplify preference for near-full bins",
    "polynomial": "use polynomial penalty on residual gaps",
    "saturation": "bonus for bins approaching full capacity",
    "threshold": "items above/below a size threshold get different bin assignment logic",
    "balance": "keep bin utilizations roughly equal to maximize future flexibility",
    "same_size_reservation": "reserve bins for same-size items to avoid fragmentation across mixed bins",
    "item_scaled_residual": "scale residual penalty by item size to handle heterogeneous arrivals",
    "reusable_slack": "prefer bins whose leftover can still fit common item sizes",
    "dead_gap_avoidance": "strongly penalize residual too small for any likely future item",
    "awkward_gap_penalty": "penalize bins left in a state where only rare item sizes can fill them",
}

# BP_FEATURE_WHEN：装箱问题中每个特征“适用于什么场景”的说明（键与 BP_FEATURE_DO 一一对应）
BP_FEATURE_WHEN: dict[str, str] = {
    "residual": "need to minimize wasted bin capacity",
    "tight_fit": "items vary in size and exact fit prevents fragmentation",
    "utilization": "objective is to minimize total bins used",
    "harmonic": "item sizes span a wide range relative to bin capacity",
    "gap_penalty": "best-fit alone leaves many tiny unusable gaps",
    "fragmentation": "many bins are partially filled with no room for common item sizes",
    "best_fit": "items arrive online and greedy tight-packing is effective",
    "worst_fit": "item sizes are unpredictable and keeping large residuals helps future placement",
    "adaptive": "item-to-bin ratio varies significantly across arrivals",
    "exponential": "linear scoring doesn't sufficiently penalize fragmented bins",
    "polynomial": "need smooth but strong penalty for medium-sized gaps",
    "saturation": "bins near capacity should be preferred to close them out",
    "threshold": "binary classification of items into size classes improves scoring",
    "balance": "many similar-sized items benefit from even distribution",
    "same_size_reservation": "arrivals contain many items of the same size that pack perfectly together",
    "item_scaled_residual": "item sizes vary widely and fixed residual scoring misweights large items",
    "reusable_slack": "leftover capacity that can't fit any future item is wasted space",
    "dead_gap_avoidance": "historical data shows small-gap bins never get filled",
    "awkward_gap_penalty": "residual is large enough to count but too odd-shaped for common item sizes",
}

# TSP Construct — traveling salesman terminology
# TSP_FEATURE_DO：旅行商问题（逐步构造路径）中每个特征的动作说明
TSP_FEATURE_DO: dict[str, str] = {
    "destination": "minimize d(current,u) + alpha*d(u,dest), increasing alpha as fewer nodes remain",
    "normalize": "normalize forward and backward distances to [0,1] before combining",
    "adaptive_weights": "use remaining_ratio to dynamically adjust forward vs backward weights",
    "regret": "maximize regret = second_best - best and prefer high regret candidates",
    "farthest": "visit distant nodes early to avoid costly late-stage connections",
    "nearest": "greedily select closest unvisited node for immediate cost reduction",
    "lookahead": "consider 2-step lookahead; penalize choices that strand distant nodes",
    "projection": "simulate greedy chain from candidate to destination for full tour estimate",
    "two_opt": "after construction, apply 2-opt local search to improve solution",
    "centroid": "prefer nodes near the centroid of remaining unvisited set for compact tours",
    "cluster": "identify spatial clusters; visit them contiguously",
}

# CVRP Construct — capacitated vehicle routing terminology
# CVRP_FEATURE_DO：带容量约束的车辆路径问题（逐步构造）中每个特征的动作说明
CVRP_FEATURE_DO: dict[str, str] = {
    "far_first": "from depot, select farthest customer to seed distant route clusters",
    "regret": "compare cost of serving now vs from depot later; prefer high regret",
    "savings": "merge routes using Clarke-Wright savings criterion",
    "capacity": "check remaining vehicle capacity before selecting next customer",
    "urgency": "prioritize customers far from depot (harder to serve in separate routes)",
    "nearest": "greedily select closest feasible customer",
    "sweep": "order customers by angle from depot; build routes by angular sweep",
    "depot_distance": "use distance-to-depot as proxy for urgency (far = high priority)",
    "remaining_aware": "adapt strategy as remaining capacity decreases",
    "cluster": "group nearby customers into same route",
}


def get_feature_vocab(problem: str) -> tuple[dict[str, str], dict[str, str]]:
    """按问题名返回该问题的特征词汇表。

    参数：
        problem：问题标识字符串，支持 "bp_online"、"tsp_construct"、"cvrp_construct"。

    返回：
        一个二元组 (feature_do, feature_when)：
        - feature_do：特征名到“动作说明”的映射；
        - feature_when：特征名到“适用场景”的映射。
        目前仅装箱问题提供 when 词典，其余问题的 when 为空字典；
        遇到无法识别的问题名时，两个词典都返回空字典。
    """
    # 逐个匹配已支持的问题名，返回对应的词典组合
    if problem == "bp_online":
        return BP_FEATURE_DO, BP_FEATURE_WHEN
    elif problem == "tsp_construct":
        return TSP_FEATURE_DO, {}
    elif problem == "cvrp_construct":
        return CVRP_FEATURE_DO, {}
    # 未识别的问题名：返回一对空字典
    return {}, {}
