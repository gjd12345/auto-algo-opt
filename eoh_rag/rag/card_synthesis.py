"""
模块：card_synthesis（最优代码 → 技能卡片 反馈闭环）
功能：把进化过程中得到的最优启发式代码，提炼成一张可检索的“技能卡片”（Skill Card），
      并写回 RAG 语料库，让后续的运行可以检索并复用这些已经进化出来的策略。
职责：
      - 从代码中抽取策略特征（如 regret、savings、cluster 等关键词/模式）；
      - 依据特征拼装卡片的标题、摘要、正文（When/Do/Fallback/Safety + 公式 + 代码片段）；
      - 安全地截取代码中的“打分/选择核心”片段，过滤危险语句；
      - 把生成的卡片去重后追加进语料文件 algorithm_cards.jsonl。
接口：
      - extract_strategy_features(code) / get_code_family(code)：抽取策略特征集合；
      - synthesize_card(problem, code, features=None, run_info=None) -> CorpusItem：合成一张卡片；
      - append_card_to_corpus(card, corpus_dir) -> bool：把卡片追加进语料库（重复返回 False）。
输入：
      - problem：问题标识（如 "tsp_construct"、"cvrp_construct"）；
      - code：某次进化跑出的最优启发式源码字符串；
      - corpus_dir：语料库目录（其下有 algorithm_cards.jsonl）。
输出：
      - CorpusItem 对象（一张技能卡片），以及写入语料库的布尔结果。
示例：
      card = synthesize_card("tsp_construct", best_code)
      append_card_to_corpus(card, "path/to/corpus")
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

# features 模块提供“规范化”的特征抽取与特征名归一，这里作为底层实现复用
from .features import (
    extract_strategy_features as _extract_canonical_strategy_features,
    normalize_strategy_feature,
)
# 按问题（TSP/CVRP/BP 等）取对应的特征词表，避免跨问题的措辞泄漏
from .problem_vocab import get_feature_vocab
# 语料库的数据结构与读写工具
from .schemas import CorpusItem, load_corpus, save_corpus

# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def extract_strategy_features(code: str | None) -> set[str]:
    """抽取代码中的策略特征集合，直接复用底层规范化实现。"""
    return _extract_canonical_strategy_features(code)


def get_code_family(code: str | None) -> set[str]:
    """返回代码所属的“策略家族”特征集合，与 extract_strategy_features 等价。"""
    return _extract_canonical_strategy_features(code)


# ---------------------------------------------------------------------------
# Card synthesis
# ---------------------------------------------------------------------------

# 每个特征对应的“做什么（Do）”人类可读描述，用于拼装卡片正文中的操作步骤。
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

# 每个特征对应的“什么时候用（When）”人类可读描述，用于拼装卡片正文中的适用条件。
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

# 各问题特有的 API 约束（写入卡片的 constraints 字段，提醒生成的代码必须遵守的规则）。
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
    """由排名靠前的特征名生成一段短哈希，用于拼出唯一的卡片 ID。

    先取排序后的前若干个特征名拼成可读前缀，再补一段基于全部特征的 md5 短哈希，
    避免不同特征集合在只看前几个名字时发生 ID 冲突。
    """
    sorted_features = sorted(features)
    key = "_".join(sorted_features[:max_features])
    # 附加短哈希，防止特征集合部分重叠时 ID 撞车
    short = hashlib.md5("_".join(sorted_features).encode()).hexdigest()[:6]
    return f"{key}_{short}"


# 卡片特征的展示优先级：越靠前越“有辨识度”，用于挑选进标题/摘要的代表特征。
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
    """挑选出少量最具代表性的特征，让卡片保持“小算子”粒度而非整份代码摘要。

    先按优先级列表挑，再用剩余特征按字母序补足，最多保留 max_features 个。
    """
    selected = [feature for feature in _CARD_FEATURE_PRIORITY if feature in features]
    selected.extend(feature for feature in sorted(features) if feature not in selected)
    return set(selected[:max_features])


def _build_title(problem: str, features: set[str]) -> str:
    """根据问题前缀和代表特征生成一个人类可读的卡片标题。"""
    prefix = problem.split("_")[0].upper()  # TSP、CVRP 等
    # 选出 2-3 个最有辨识度的特征
    priority = ["regret", "farthest", "destination", "normalize", "adaptive_weights",
                "cluster", "centrality", "savings", "penalty", "lookahead"]
    selected = [f for f in priority if f in features][:3]
    if not selected:
        selected = sorted(features)[:2]
    label = " ".join(w.replace("_", " ").title() for w in selected)
    return f"{prefix} {label} Evolved Card"


def _build_summary(problem: str, features: set[str]) -> str:
    """生成一行摘要，供检索阶段做相关性打分使用。"""
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

# 打分相关的关键词：包含这些词的代码行更可能是“打分/选择核心”，用于关键词兜底提取。
_SCORING_KEYWORDS = frozenset([
    "score", "scores", "weight", "weights", "cost", "costs",
    "regret", "metric", "priority", "distance", "dist",
    "penalty", "rank", "value", "argmin", "argmax",
])

# 危险代码模式：涉及导入、文件/系统/网络访问、打印、随机、睡眠等的行会被过滤掉，
# 保证写进卡片的代码片段只展示纯粹的打分逻辑，既安全又干净。
_DANGEROUS_PATTERNS = re.compile(
    r"(?:import\s|from\s.*import|open\(|os\.|subprocess\.|"
    r"sys\.|print\(|logging\.|sleep\(|random\.|"
    r"requests\.|urllib\.|http\.|socket\.)",
    re.MULTILINE
)

_MAX_SNIPPET_LINES = 15   # 代码片段最多保留的行数
_MAX_SNIPPET_CHARS = 700  # 代码片段最多保留的字符数


def _is_dangerous_line(line: str) -> bool:
    """判断某一行代码是否命中危险模式（需要被过滤）。"""
    return bool(_DANGEROUS_PATTERNS.search(line))


def _nesting_depth(code: str) -> int:
    """估算代码的最大缩进嵌套层数（按 4 空格一层计算）。"""
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
    """基于 AST 的提取：定位函数的 return 语句，向前回溯一段作为打分核心片段。

    解析失败、没有函数或没有 return 时返回 None；同时会过滤危险行并限制行数。
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    # 收集所有函数定义，取第一个作为目标函数
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

    # 找到最后一个 return 语句，作为片段的结束点
    last_return = None
    for node in ast.walk(target_func):
        if isinstance(node, ast.Return):
            last_return = node

    if last_return is None:
        return None

    # 以最后一个 return 为结束行，向前取若干行；起点不早于函数体首行
    end_line = last_return.lineno
    start_line = max(1, end_line - _MAX_SNIPPET_LINES + 1)

    func_start = target_func.lineno
    start_line = max(start_line, func_start + 1)

    snippet_lines = lines[start_line - 1:end_line]
    snippet_lines = [l for l in snippet_lines if not _is_dangerous_line(l)]

    # 过滤后若仍超长，只保留末尾若干行（离 return 更近、更贴近打分结论）
    if len(snippet_lines) > _MAX_SNIPPET_LINES:
        snippet_lines = snippet_lines[-_MAX_SNIPPET_LINES:]

    return "\n".join(snippet_lines).strip() if snippet_lines else None


def _extract_scoring_core_keyword(code: str) -> str | None:
    """兜底提取：找出含打分关键词的行，以其中位行为中心取一个上下文窗口。"""
    lines = code.splitlines()
    score_lines = []

    # 记录所有命中打分关键词且非危险的行号
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in _SCORING_KEYWORDS):
            if not _is_dangerous_line(line):
                score_lines.append(i)

    if not score_lines:
        return None

    # 以命中行的中位数为窗口中心，上下各取半个窗口
    center = score_lines[len(score_lines) // 2]
    half_window = _MAX_SNIPPET_LINES // 2

    start = max(0, center - half_window)
    end = min(len(lines), center + half_window + 1)

    snippet_lines = [l for l in lines[start:end] if not _is_dangerous_line(l)]
    if len(snippet_lines) > _MAX_SNIPPET_LINES:
        snippet_lines = snippet_lines[:_MAX_SNIPPET_LINES]

    return "\n".join(snippet_lines).strip() if snippet_lines else None


def _extract_scoring_core(code: str | None, max_lines: int = _MAX_SNIPPET_LINES) -> str | None:
    """从启发式代码中提取“打分/选择核心”片段，供卡片展示。

    先尝试基于 AST 的提取，失败则退回关键词提取；若嵌套过深、含死循环，
    或最终无法得到有意义的片段，则返回 None。
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
    """把检测到的特征翻译成一行公式摘要（最多 3 条），便于人快速理解卡片打分逻辑。"""
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
    """拼装技能卡片正文：When/Do/Fallback/Safety 四段 + 公式摘要 + 代码片段。

    会依据问题选用对应词表来描述 When/Do，避免不同问题（如 TSP/CVRP/BP）的措辞相互串味。
    """
    prefix = problem.split("_")[0].upper()

    # 使用 problem-specific 词表，防止 TSP/CVRP 语言泄漏到 BP card
    prob_do, prob_when = get_feature_vocab(problem)
    feature_do = prob_do if prob_do else _FEATURE_DO
    feature_when = prob_when if prob_when else _FEATURE_WHEN

    # When：拼接相关的适用条件（最多 3 条）
    when_parts = []
    for f in sorted(features):
        if f in feature_when:
            when_parts.append(feature_when[f])
    when = "; ".join(when_parts[:3]) if when_parts else f"constructing a {prefix} solution step by step."

    # Do：拼接相关的操作步骤（最多 4 条）
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

    # 追加结构化字段（特征标签、公式摘要、代码片段），提升检索命中效果
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
    """由最优代码及其检测到的特征合成一张技能卡片（CorpusItem）。

    参数
    ----------
    problem : str
        问题标识（例如 ``"tsp_construct"``）。
    code : str
        某次进化跑出的最优启发式代码。
    features : set[str] | None
        预先抽取好的特征；为 ``None`` 时会从 *code* 中现场抽取。
    run_info : dict | None
        可选的元数据（``run_dir``、``objective``、``generation`` 等）。

    返回：一个 CorpusItem 卡片对象；若代码里检测不到任何策略特征则抛出 ValueError。
    """
    if features is None:
        features = extract_strategy_features(code)
    else:
        # 外部传入的特征先做归一化，丢弃无法归一的项
        features = {
            canonical
            for feature in features
            if (canonical := normalize_strategy_feature(feature)) is not None
        }
    if not features:
        raise ValueError("No strategy features detected in code; cannot synthesize card.")
    card_features = _select_card_features(features)

    run_info = run_info or {}
    # 由代表特征生成稳定的卡片 ID，并记录来源目录
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
    """把 *card* 追加进 ``algorithm_cards.jsonl``（若尚未存在）。

    写入成功返回 ``True``；若 ID 已存在（重复卡片）则不写入并返回 ``False``。
    """
    corpus_path = Path(corpus_dir) / "algorithm_cards.jsonl"
    existing = load_corpus(corpus_path) if corpus_path.exists() else []
    existing_ids = {item.id for item in existing}
    if card.id in existing_ids:
        return False  # 已有同 ID 卡片，视为重复，跳过写入
    existing.append(card)
    save_corpus(existing, corpus_path)
    return True
