"""
模块：strategy_feature_inventory（策略特征清单生成器）
功能：扫描 RAG 相关源码与语料库，汇总出组合优化启发式所用的“策略特征”词表及其分类，生成一份确定性的清单（Markdown + JSON）。
职责：
  - 静态解析若干 Python 源文件（features / card_synthesis / reranker / controller），提取其中的特征常量、别名、停用词等定义；
  - 遍历语料库 jsonl 行，统计每个标签在全量语料与历史卡片中的出现次数及来源；
  - 把所有词条按“规范策略特征 / 历史观察到的特征 / 弱上下文词 / 元数据标签”四类归类，并附上别名、风险提示与出现证据；
  - 渲染为人类可读的 Markdown 表格，同时导出结构化 JSON。
接口：
  - build_inventory(repo_root: Path) -> dict：核心逻辑，返回完整清单字典；
  - render_markdown(inventory: dict) -> str：把清单字典渲染成 Markdown 文本；
  - main() -> None：命令行入口，解析参数并写出两份产物文件。
输入：
  - 命令行参数 --repo-root（仓库根目录，默认脚本上一级目录）、--markdown-output、--json-output；
  - 依赖仓库内文件：eoh_rag/rag/features.py、card_synthesis.py、reranker.py、tocc/controller.py，以及 eoh_rag_workspace/rag/corpus/*.jsonl。
输出：
  - docs/strategy_feature_inventory.md（Markdown 清单）；
  - docs/strategy_feature_inventory.json（结构化清单）。
说明：本脚本仅用 ``ast`` 读取源码、用 ``json`` 读取语料库，不导入任何运行时模块，也不写回运行时/语料库文件；对同样的输入总是产生同样的输出。
示例：
  python scripts/strategy_feature_inventory.py --repo-root .
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# 规范策略特征词表：这些词被视为“正统”的策略特征，允许参与检索时的重叠计算（overlap）。
CANONICAL_CANDIDATES = frozenset({
    "adaptive_weights", "best_fit", "capacity", "centrality", "cluster",
    "depot", "destination", "detour", "distance", "farthest", "first_fit",
    "harmonic", "lookahead", "nearest", "normalize", "penalty", "regret",
    "remaining_aware", "residual", "savings", "sweep", "tightness",
    "two_opt", "utilization", "worst_fit",
})

# 历史上在语料/代码中观察到、但未纳入规范词表的特征词：仍可追溯，默认不参与重叠计算。
LEGACY_OBSERVED = frozenset({
    "angle", "balance", "clustering", "cost-delta", "diffusion", "exp",
    "feasibility", "forward_score", "greedy", "insertion", "isolation",
    "local-search", "merge", "polynomial", "progress", "route-consolidation",
    "select-next", "smooth-route", "sqrt", "threshold", "two_hop",
    "weighted-score",
})

# 弱上下文词：单独出现时区分度很低（如 alpha/beta/demand 等），只允许出现在复合模式里，不能单独触发特征。
WEAK_CONTEXT_TOKENS = frozenset({
    "alpha", "beta", "demand", "feasible", "future", "gamma", "return",
})

# 特征别名映射：把各种写法（连字符、无分隔、缩写等）统一归并到规范词表中的标准名。
# 键是别名，值是它对应的规范特征名。
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

# 各规范特征的风险提示：说明该特征在匹配时容易踩的坑（多为与弱上下文词或 API 变量名混淆），供清单展示。
FEATURE_RISKS = {
    "adaptive_weights": ["alpha/beta/gamma are weak tokens and must not trigger alone"],
    "capacity": ["feasible/demand are weak tokens; capacity is also an API variable"],
    "depot": ["depot is commonly an API/interface token"],
    "destination": ["return is a weak token and causes broad false positives"],
    "distance": ["distance and distance_matrix are commonly API/interface tokens"],
    "lookahead": ["future is a weak token and must not trigger alone"],
}


def _literal_assignment(path: Path, name: str) -> Any:
    """从指定 Python 源文件中，静态读取某个模块级赋值的字面量取值。

    只做 AST 解析、不执行源码，因此不会触发任何副作用或导入。

    参数：
        path：待解析的 Python 源文件路径。
        name：要查找的模块级变量名。
    返回：
        该变量的字面量取值。若右值是 ``frozenset(...)`` / ``set(...)`` /
        ``tuple(...)`` / ``list(...)`` 这类单参数容器构造调用，则先取出内部字面量，
        再用对应容器类型包装后返回；否则直接按字面量求值返回。
    异常：
        在文件中找不到该赋值时抛出 ValueError。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        value = None
        targets: list[ast.expr] = []
        # 普通赋值（a = ...）与带类型注解的赋值（a: T = ...）分别取出赋值目标与右值。
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None:
            continue
        # 命中目标变量名后，判断右值形态并求值。
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            # 右值是单参数的容器构造调用：先对内部参数求字面量，再套上对应容器类型。
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
            # 其他情况直接按纯字面量求值（如 dict、list 字面量等）。
            return ast.literal_eval(value)
    raise ValueError(f"Assignment {name!r} not found in {path}")


def _optional_literal_assignment(path: Path, name: str) -> Any | None:
    """`_literal_assignment` 的“宽容版”：找不到该赋值时返回 None 而不是抛异常。

    用于那些可能存在、也可能不存在的可选定义。
    """
    try:
        return _literal_assignment(path, name)
    except ValueError:
        return None


def _load_corpus_tags(corpus_dir: Path) -> tuple[Counter[str], Counter[str], dict[str, set[str]]]:
    """遍历语料库目录下所有 jsonl 文件，统计标签出现情况。

    参数：
        corpus_dir：语料库目录，其中每个 ``*.jsonl`` 文件的每一行是一条 JSON 记录。
    返回：
        三元组 (all_tags, history_tags, observed_in)：
          - all_tags：每个标签在全部语料中的出现次数；
          - history_tags：仅统计 id 以 ``history_`` 开头的历史卡片中的标签次数；
          - observed_in：每个标签出现过的来源集合（如 ``corpus:<文件名>``、``history_card_tags``）。
    异常：
        某一行不是 JSON 对象时抛出 ValueError。
    """
    all_tags: Counter[str] = Counter()
    history_tags: Counter[str] = Counter()
    observed_in: dict[str, set[str]] = defaultdict(set)
    for path in sorted(corpus_dir.glob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue  # 跳过空行
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Corpus row must be an object at {path}:{line_no}")
            # id 以 history_ 开头的记录属于“历史卡片”，其标签需要单独计数。
            is_history = str(payload.get("id", "")).startswith("history_")
            for raw_tag in payload.get("tags", []):
                tag = str(raw_tag).lower()  # 标签统一转小写，避免大小写导致重复计数
                all_tags[tag] += 1
                observed_in[tag].add(f"corpus:{path.name}")
                if is_history:
                    history_tags[tag] += 1
                    observed_in[tag].add("history_card_tags")
    return all_tags, history_tags, observed_in


def build_inventory(repo_root: Path) -> dict[str, Any]:
    """构建完整的策略特征清单。

    从仓库源码中静态读取特征相关定义（停用词、模式、代码特征族等），
    结合语料库标签统计，把所有词条归类并整理成可导出的字典结构。

    参数：
        repo_root：仓库根目录，用于拼出各源文件与语料库的路径。
    返回：
        一个字典，包含 schema 版本、数据来源、各模块提取行为说明、别名表、
        模式表、停用词、逐条特征证据（features）以及已知风险等字段。
    """
    # 各来源文件与语料目录的路径（相对仓库根目录）。
    features_path = repo_root / "eoh_rag/rag/features.py"
    synthesis_path = repo_root / "eoh_rag/rag/card_synthesis.py"
    reranker_path = repo_root / "eoh_rag/rag/reranker.py"
    controller_path = repo_root / "eoh_rag/tocc/controller.py"
    corpus_dir = repo_root / "eoh_rag_workspace/rag/corpus"

    # 代码停用词：这些标识符在特征提取时会被忽略。
    code_stopwords = set(_literal_assignment(features_path, "_CODE_STOPWORDS"))
    # 特征模式与代码特征族既可能定义在 card_synthesis 里，也可能定义在 features 里；
    # 下面优先取 card_synthesis 中的定义，缺失时回退到 features，并记录实际来源，供清单标注。
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
    # 记录“模式”和“代码特征族”这两项定义的真实出处，写入证据。
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
    # reranker 的特征停用词是可选的，缺失时按空集合处理。
    reranker_stopwords = set(
        _optional_literal_assignment(reranker_path, "_FEATURE_STOPWORDS") or set()
    )
    all_tags, history_tags, observed_in = _load_corpus_tags(corpus_dir)

    # 把源码中出现的各类词条也登记进 observed_in，标注其来源。
    for name in synthesis_patterns:
        observed_in[name].add(pattern_source)
    for name in code_family:
        observed_in[name].add(family_source)
    for name in code_stopwords:
        observed_in[name].add("features._CODE_STOPWORDS")
    for name in reranker_stopwords:
        observed_in[name].add("reranker._FEATURE_STOPWORDS")

    # 汇总所有待归类词条：语料/代码中观察到的、加上四类静态词表与别名键的并集。
    terms = (
        set(observed_in)
        | set(CANONICAL_CANDIDATES)
        | set(LEGACY_OBSERVED)
        | set(WEAK_CONTEXT_TOKENS)
        | set(FEATURE_ALIASES)
    )
    feature_rows = []
    for name in sorted(terms):  # 按名称排序，保证输出稳定可复现
        canonical_target = FEATURE_ALIASES.get(name)  # 若该词是别名，取其规范目标名
        # 按优先级判定分类：规范特征 > 弱上下文词 > 历史观察/别名 > 其余元数据标签。
        if name in CANONICAL_CANDIDATES:
            classification = "canonical_strategy_feature"
        elif name in WEAK_CONTEXT_TOKENS:
            classification = "weak_context_token"
        elif name in LEGACY_OBSERVED or canonical_target:
            classification = "legacy_observed_feature"
        else:
            classification = "metadata_tag"
        patterns = list(synthesis_patterns.get(name, []))
        # 为每个词条汇总一行完整证据：分类、是否参与重叠、出现来源、别名、计数、风险等。
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

    # 组装并返回最终清单：包含来源、各模块提取行为说明、别名/模式/停用词、逐条特征证据与已知风险。
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
    """把 build_inventory 产出的清单字典渲染成 Markdown 文本。

    参数：
        inventory：build_inventory 返回的清单字典。
    返回：
        一段 Markdown 字符串，依次包含：各提取器说明、四类分类清单、
        逐条特征证据表格、以及已知风险列表。
    """
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
    # 按四种分类分别列出对应的特征名。
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
        # 表格单元内用 <br> 拼接多值，空值以 "-" 占位；计数列格式为“语料数/历史数”。
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
    """命令行入口：解析参数、构建清单，并写出 Markdown 与 JSON 两份产物。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    # 未显式指定输出路径时，默认写到仓库 docs/ 目录下。
    markdown_path = args.markdown_output or repo_root / "docs/strategy_feature_inventory.md"
    json_path = args.json_output or repo_root / "docs/strategy_feature_inventory.json"
    inventory = build_inventory(repo_root)
    markdown_path.write_text(render_markdown(inventory), encoding="utf-8")
    # JSON 以 sort_keys 排序输出，保证结果稳定；ensure_ascii=False 便于中文可读。
    json_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
