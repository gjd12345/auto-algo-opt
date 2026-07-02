"""
模块：build_corpus（RAG 语料构建）
功能：为启发式演化框架构建并加载 RAG 检索语料，为大模型改写算法代码时提供参考知识。
职责：
    - 定义四类语料文件（代码示例、算法卡片、API 约束、失败案例）与其磁盘文件名的映射。
    - 维护各优化问题（VRP、在线装箱 OBP、TSP、CVRP）的“文献来源”语料 id 集合。
    - 生成 curated（人工整理）的 API 约束语料，覆盖 InsertShips、优化、背包、混合拆单、
      在线装箱、TSP、CVRP 等问题的 Go / Python 接口调用规范。
    - 按检索模式（history / literature / mixed）过滤语料。
    - 把各类语料落盘到语料目录，并支持从磁盘统一加载全部语料。
接口：
    - default_corpus_dir(project_root) -> Path：返回默认语料目录。
    - resolve_corpus_dir(project_root, corpus_dir) -> Path：解析并校验语料目录（限制在允许范围内）。
    - build_api_constraints(project_root) -> list[CorpusItem]：构建 API 约束语料。
    - build_all_corpora(project_root, corpus_dir=None) -> list[Path]：构建全部语料并落盘。
    - load_all_corpora(project_root, corpus_dir=None) -> list[CorpusItem]：加载全部语料（缺失则先构建）。
    - filter_corpus_by_mode(corpus, mode) -> list[CorpusItem]：按检索模式过滤语料。
输入：
    - project_root：项目根目录（用于定位 eoh_rag_workspace/rag/corpus 语料目录）。
    - corpus_dir：可选的语料目录，需落在允许范围内。
输出：
    - 语料 jsonl 文件（code_examples / algorithm_cards / api_constraints / failure_cases）。
    - CorpusItem 列表（供检索模块使用）。
示例：
    >>> paths = build_all_corpora("/path/to/project")   # 构建全部语料并返回落盘路径
    >>> items = load_all_corpora("/path/to/project")     # 加载全部语料条目
"""

from __future__ import annotations

import re
from pathlib import Path

from .schemas import CorpusItem, load_corpus, save_corpus

# failure_case 语料由 curated 的 failure_cases 模块提供。
# build_failure_cases 在此重新导出，方便调用方从 build_corpus 统一引入。
from .failure_cases import build_failure_cases  # noqa: F401  (re-export)


# 四类语料的种类名 -> 落盘文件名映射。构建与加载语料时按此映射逐一处理。
CORPUS_FILES = {
    "code_example": "code_examples.jsonl",
    "algorithm_card": "algorithm_cards.jsonl",
    "api_constraint": "api_constraints.jsonl",
    "failure_case": "failure_cases.jsonl",
}

# 以下集合列出各优化问题“来自文献”的算法卡片 id（相对于历史合成卡片）。
# 检索模式为 literature 时只保留这些 id 的算法卡片；为 history 时会剔除这些 id。
# VRP（车辆路径）相关文献算法 id。
VRP_LITERATURE_IDS = {"nearest_insertion", "farthest_insertion", "solomon_i1", "regret2_insertion", "cw_savings"}
# OBP（在线装箱）相关文献算法 id。
OBP_LITERATURE_IDS = {
    "obp_first_fit",
    "obp_best_fit",
    "obp_worst_fit",
    "obp_harmonic",
    "obp_funsearch_residual_poly",
    "obp_eoh_util_sqrt_exp",
}
# TSP（旅行商）相关文献算法 id。
TSP_LITERATURE_IDS = {
    "tsp_nearest_neighbor",
    "tsp_nearest_insertion",
    "tsp_farthest_insertion",
    "tsp_regret_insertion",
    "tsp_two_opt_awareness",
}
# CVRP（带容量车辆路径）相关文献算法 id。
CVRP_LITERATURE_IDS = {
    "cvrp_nearest_capacity",
    "cvrp_savings",
    "cvrp_sweep",
    "cvrp_regret_insertion",
    "cvrp_far_first",
}
# 汇总全部文献算法 id，供按模式过滤语料时统一判断。
LITERATURE_IDS = VRP_LITERATURE_IDS | OBP_LITERATURE_IDS | TSP_LITERATURE_IDS | CVRP_LITERATURE_IDS


def _is_history_card(item: CorpusItem) -> bool:
    """判断某语料条目是否为“历史合成”的算法卡片。

    历史合成卡片由框架从演化过程中的最优代码自动生成（id 以 ``history_`` 开头），
    而非人工整理的文献卡片。

    参数：
        item：待判断的语料条目。
    返回：
        当且仅当该条目是种类为 ``algorithm_card`` 且 id 以 ``history_`` 开头时返回 True。
    """
    return item.kind == "algorithm_card" and item.id.startswith("history_")

# InsertShips 问题的标准约束条目：这些是大模型改写代码时必须遵守的关键安全规则。
_STANDARD_INSERTSHIPS_CONSTRAINTS = [
    "Never skip orders unless no feasible assignment exists.",
    "Rollback tentative insertions when a candidate route fails.",
    "Call RenewnTotalCost before returning Dispatch.",
    "Avoid negative, suspiciously low, timeout, and missing-result candidates.",
]


def default_corpus_dir(project_root: str | Path) -> Path:
    """返回默认语料目录的绝对路径：``<project_root>/eoh_rag_workspace/rag/corpus``。"""
    return (Path(project_root) / "eoh_rag_workspace" / "rag" / "corpus").resolve()


def resolve_corpus_dir(project_root: str | Path, corpus_dir: str | Path | None) -> Path:
    """解析并校验语料目录，确保它落在允许的根目录之内。

    参数：
        project_root：项目根目录。
        corpus_dir：期望的语料目录，可为绝对路径、相对路径或 None（使用默认目录）。
    返回：
        校验通过的语料目录绝对路径。
    异常：
        当最终路径不在 ``eoh_rag_workspace/rag/corpus`` 之下时抛出 ValueError。
    """
    root = Path(project_root).resolve()
    allowed_dir = default_corpus_dir(root)
    if not corpus_dir:
        # 未指定目录时，直接使用默认语料目录。
        candidate = allowed_dir
    else:
        raw = Path(corpus_dir)
        if raw.is_absolute():
            # 绝对路径直接解析。
            candidate = raw.resolve()
        else:
            # 相对路径：先尝试相对项目根目录解析，若已落在允许目录内则采用；
            # 否则退回为相对允许目录解析。
            root_relative = (root / raw).resolve()
            try:
                root_relative.relative_to(allowed_dir)
                candidate = root_relative
            except ValueError:
                candidate = (allowed_dir / raw).resolve()

    # 最终统一校验：候选目录必须位于允许目录之下，防止写到范围之外。
    try:
        candidate.relative_to(allowed_dir)
    except ValueError:
        raise ValueError("RAG corpus directory must stay under eoh_rag_workspace/rag/corpus")
    return candidate


def _title_from_id(item_id: str) -> str:
    """由语料 id 生成可读标题：把下划线/连字符换成空格并首字母大写。"""
    return item_id.replace("_", " ").replace("-", " ").title()


def _tags_from_name(name: str) -> list[str]:
    """由名称提取标签列表：首个标签固定为 ``insertships``，其后追加名称中去重的小写词元。"""
    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", name)]
    tags = ["insertships"]
    for token in tokens:
        if token not in tags:
            tags.append(token)
    return tags


def build_code_examples(project_root: str | Path) -> list[CorpusItem]:
    """构建代码示例语料。InsertShips 的代码示例由外部人工整理，这里不生成，返回空列表。"""
    return []


def build_algorithm_cards(project_root: str | Path) -> list[CorpusItem]:
    """构建算法卡片语料。算法卡片为人工整理，SA（模拟退火）种子内容归于 api_constraint，这里返回空列表。"""
    return []


def filter_corpus_by_mode(corpus: list[CorpusItem], mode: str) -> list[CorpusItem]:
    """按检索模式过滤语料。

    参数：
        corpus：全部语料条目列表。
        mode：检索模式，取值 ``history`` / ``literature`` / ``mixed``（大小写与空白不敏感，空值按 ``mixed`` 处理）。
    返回：
        - mixed：返回全部语料的副本。
        - history：剔除全部文献算法卡片（id 属于 LITERATURE_IDS 的条目）。
        - literature：仅保留文献算法卡片，以及所有 api_constraint 与 failure_case 条目。
    异常：
        模式不在三者之列时抛出 ValueError。
    """
    normalized = mode.strip().lower() if mode else "mixed"
    if normalized == "mixed":
        return list(corpus)
    if normalized == "history":
        return [item for item in corpus if item.id not in LITERATURE_IDS]
    if normalized == "literature":
        return [item for item in corpus if item.id in LITERATURE_IDS or item.kind in {"api_constraint", "failure_case"}]
    raise ValueError("RAG mode must be one of: history, literature, mixed")


def build_api_constraints(project_root: str | Path) -> list[CorpusItem]:
    """构建各优化问题的 API 约束语料（人工整理）。

    每个条目描述一个问题接口的“安全调用规范”，包括必须遵守的硬约束（constraints）
    与详细规则说明（content），用于在大模型改写算法代码时约束其输出的正确性与安全性。
    覆盖问题：InsertShips 插入、路径优化、0/1 背包、混合拆单、在线装箱、TSP 构造、CVRP 构造。

    参数：
        project_root：项目根目录（用于路径解析，各条目内容本身为静态文本）。
    返回：
        CorpusItem 列表，每项 kind 均为 ``api_constraint``。
    """
    root = Path(project_root).resolve()
    return [
        CorpusItem(
            id="insertships_api_skeleton",
            kind="api_constraint",
            title="InsertShips Go API skeleton",
            tags=["insertships", "api", "safety"],
            source_path="curated",
            summary="Safe Go API call sequence: save state, trial insert, record delta, rollback, commit best, RenewnTotalCost.",
            constraints=[
                "Every order MUST be inserted; fallback to new Assign if no existing Assign works.",
                "RenewnTotalCost() exactly once before return.",
            ],
            content=(
                "API: insertships_skeleton\n"
                "Rules:\n"
                "- Save Assign state before trial AddShip.\n"
                "- If AddShip succeeds: GenRoute, record cost_delta, then RemoveShip+GenRoute to undo.\n"
                "- Commit: re-apply best (Assign, position) once. GenRoute after final insert.\n"
                "- Every order needs a fallback insertion path.\n"
                "- Call RenewnTotalCost exactly once before return."
            ),
        ),
        CorpusItem(
            id="optimization_api_skeleton",
            kind="api_constraint",
            title="Optimization Go API skeleton",
            tags=["optimization", "api", "safety"],
            source_path="curated",
            summary="SA-style route improvement: move orders between vehicles, preserve dispatch integrity.",
            constraints=[
                "Never lose or duplicate orders during vehicle-to-vehicle moves.",
                "RenewnTotalCost() exactly once before return.",
            ],
            content=(
                "API: optimization_skeleton\n"
                "Rules:\n"
                "- Use dispatch.Assigns[].RemoveShip/AddShip/GenRoute to move orders between vehicles.\n"
                "- Use dispatch.RenewnTotalCost() before return.\n"
                "- Temperature parameter controls acceptance of worse moves (SA).\n"
                "- Return the modified dispatch. Never create new Assign objects from scratch."
            ),
        ),
        CorpusItem(
            id="knapsack_api_skeleton",
            kind="api_constraint",
            title="Knapsack SelectItems Go API skeleton",
            tags=["knapsack", "api", "safety"],
            source_path="curated",
            summary="0/1 knapsack: return boolean array, respect capacity, maximize value.",
            constraints=[
                "Return len(items) booleans.",
                "Total selected weight must NOT exceed capacity.",
            ],
            content=(
                "API: knapsack_selectitems_skeleton\n"
                "Rules:\n"
                "- func SelectItems(items []Item, capacity int) []bool\n"
                "- Return a boolean slice of length len(items).\n"
                "- selected weight := sum(items[i].Weight for i where result[i] is true).\n"
                "- selected must be <= capacity.\n"
                "- Maximize total value := sum(items[i].Value for i where result[i] is true)."
            ),
        ),
        CorpusItem(
            id="mixer_split_api_skeleton",
            kind="api_constraint",
            title="Mixer SplitOrders Go API skeleton",
            tags=["mixer", "splitorders", "api", "safety"],
            source_path="curated",
            summary="Concrete mixer order splitting: preserve volume, obey vehicle capacity, return valid suborders.",
            constraints=[
                "Preserve each original order volume exactly.",
                "Every suborder volume must be positive and <= chosen vehicle capacity.",
            ],
            content=(
                "API: mixer_split_skeleton\n"
                "Rules:\n"
                "- func SplitOrders(orders []Order, vehicles []Vehicle, workHours float64) []SubOrder\n"
                "- Return []SubOrder.\n"
                "- Preserve each original order volume exactly.\n"
                "- Every suborder volume must be <= chosen vehicle capacity.\n"
                "- Use fallback splitting by largest available vehicle.\n"
                "- Never invent unknown order IDs."
            ),
        ),
        CorpusItem(
            id="obp_api_skeleton",
            kind="api_constraint",
            title="Online Bin Packing ScoreBin API skeleton",
            tags=["obp", "binpacking", "scorebin", "api", "safety"],
            source_path="curated",
            summary="Online bin packing: score feasible bins, return finite scores, minimize used bins.",
            constraints=[
                "Return exactly len(remaining) finite scores.",
                "The evaluator opens a new bin when no existing bin is feasible.",
            ],
            content=(
                "API: obp_scorebin_skeleton\n"
                "Rules:\n"
                "- func ScoreBin(item int, remaining []int, capacity int) []float64\n"
                "- remaining contains only feasible bins.\n"
                "- Return len(remaining) finite scores; highest score wins.\n"
                "- Do not read files, env, network, or use randomness.\n"
                "- Prefer fewer used bins and low gap to lower bound."
            ),
        ),
        CorpusItem(
            id="tsp_construct_api_skeleton",
            kind="api_constraint",
            title="Official TSP Construct select_next_node API skeleton",
            tags=["tsp", "construct", "api", "safety"],
            source_path="curated",
            summary="TSP construct: return one unvisited node id from select_next_node.",
            constraints=[
                "Return exactly one int from unvisited_nodes.",
                "Never return a visited node, destination_node, or a new array.",
            ],
            content=(
                "API: tsp_select_next_node\n"
                "Rules:\n"
                "- def select_next_node(current_node, destination_node, unvisited_nodes, distance_matrix) -> int\n"
                "- Return one int contained in unvisited_nodes.\n"
                "- Use distance_matrix[current_node][unvisited_nodes] for distances.\n"
                "- Do not mutate unvisited_nodes or distance_matrix.\n"
                "- Keep computation bounded and deterministic."
            ),
        ),
        CorpusItem(
            id="cvrp_construct_api_skeleton",
            kind="api_constraint",
            title="Official CVRP Construct select_next_node API skeleton",
            tags=["cvrp", "construct", "api", "safety"],
            source_path="curated",
            summary="CVRP construct: return one feasible customer, or depot only to end a route.",
            constraints=[
                "Return one int from unvisited_nodes, or depot only for voluntary return.",
                "Respect rest_capacity; unvisited_nodes is already capacity-feasible.",
            ],
            content=(
                "API: cvrp_select_next_node\n"
                "Rules:\n"
                "- def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int\n"
                "- Return one int from unvisited_nodes, or depot to close route.\n"
                "- Use demands and rest_capacity for capacity-aware choices.\n"
                "- Do not mutate arrays.\n"
                "- Keep deterministic and bounded."
            ),
        ),
    ]


def build_all_corpora(project_root: str | Path, corpus_dir: str | Path | None = None) -> list[Path]:
    """构建全部四类语料并落盘，返回写入（或应存在）的文件路径列表。

    行为要点：
        - 算法卡片文件若已存在，则保留其中的文献卡片与历史合成卡片，且不覆盖该文件
          （避免丢失已有的人工整理与历史反馈内容）；文件不存在时写入空的算法卡片语料。
        - 代码示例、API 约束、失败案例三类语料每次都重新生成并写入。

    参数：
        project_root：项目根目录。
        corpus_dir：可选的语料目录，需落在允许范围内。
    返回：
        四个语料文件的路径列表（顺序与 CORPUS_FILES 一致）。
    """
    target_dir = resolve_corpus_dir(project_root, corpus_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    algorithm_path = target_dir / CORPUS_FILES["algorithm_card"]
    curated_algorithm_cards: list[CorpusItem] = []
    if algorithm_path.exists():
        # 算法卡片文件已存在：同时保留文献卡片与历史合成卡片（来自最优代码反馈闭环），其余丢弃。
        existing_algorithm_cards = [
            item for item in load_corpus(algorithm_path)
            if item.id in LITERATURE_IDS or _is_history_card(item)
        ]
        curated_algorithm_cards = existing_algorithm_cards
        # 统计现有文献卡片的去重数量，若少于预期集合则给出提醒。
        lit_count = len({item.id for item in curated_algorithm_cards})
        if lit_count < len(LITERATURE_IDS):
            print("Warning: algorithm_cards.jsonl has fewer than expected curated literature cards.")
    else:
        print("Warning: algorithm_cards.jsonl missing; writing empty curated algorithm card corpus.")

    # 按种类聚合各自的语料条目，供后续统一落盘。
    grouped = {
        "code_example": build_code_examples(project_root),
        "algorithm_card": curated_algorithm_cards,
        "api_constraint": build_api_constraints(project_root),
        "failure_case": build_failure_cases(project_root),
    }

    written: list[Path] = []
    for kind, filename in CORPUS_FILES.items():
        path = target_dir / filename
        # 算法卡片文件已存在时不覆盖，仅记录路径；其余种类正常写盘。
        if kind != "algorithm_card" or not algorithm_path.exists():
            save_corpus(grouped[kind], path)
        written.append(path)
    return written


def load_all_corpora(project_root: str | Path, corpus_dir: str | Path | None = None) -> list[CorpusItem]:
    """加载全部语料条目；若任一语料文件缺失，则先构建再加载。

    参数：
        project_root：项目根目录。
        corpus_dir：可选的语料目录，需落在允许范围内。
    返回：
        合并四类语料文件后的 CorpusItem 列表。
    """
    target_dir = resolve_corpus_dir(project_root, corpus_dir)
    expected = [target_dir / filename for filename in CORPUS_FILES.values()]
    # 只要有任一预期文件不存在，就整体重建，保证四类语料齐备。
    if any(not path.exists() for path in expected):
        build_all_corpora(project_root, target_dir)

    items: list[CorpusItem] = []
    for path in expected:
        items.extend(load_corpus(path))
    return items
