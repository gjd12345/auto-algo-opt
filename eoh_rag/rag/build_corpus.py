from __future__ import annotations

import re
from pathlib import Path

from .schemas import CorpusItem, load_corpus, save_corpus

# failure_case 语料由 curated 的 failure_cases 模块提供。
# build_failure_cases 在此重新导出，方便调用方从 build_corpus 统一引入。
from .failure_cases import build_failure_cases  # noqa: F401  (re-export)


CORPUS_FILES = {
    "code_example": "code_examples.jsonl",
    "algorithm_card": "algorithm_cards.jsonl",
    "api_constraint": "api_constraints.jsonl",
    "failure_case": "failure_cases.jsonl",
}

VRP_LITERATURE_IDS = {"nearest_insertion", "farthest_insertion", "solomon_i1", "regret2_insertion", "cw_savings"}
OBP_LITERATURE_IDS = {
    "obp_first_fit",
    "obp_best_fit",
    "obp_worst_fit",
    "obp_harmonic",
    "obp_funsearch_residual_poly",
    "obp_eoh_util_sqrt_exp",
}
TSP_LITERATURE_IDS = {
    "tsp_nearest_neighbor",
    "tsp_nearest_insertion",
    "tsp_farthest_insertion",
    "tsp_regret_insertion",
    "tsp_two_opt_awareness",
}
CVRP_LITERATURE_IDS = {
    "cvrp_nearest_capacity",
    "cvrp_savings",
    "cvrp_sweep",
    "cvrp_regret_insertion",
    "cvrp_far_first",
}
LITERATURE_IDS = VRP_LITERATURE_IDS | OBP_LITERATURE_IDS | TSP_LITERATURE_IDS | CVRP_LITERATURE_IDS


def _is_history_card(item: CorpusItem) -> bool:
    """Check if a card was synthesized from best code (not hand-curated)."""
    return item.kind == "algorithm_card" and item.id.startswith("history_")

_STANDARD_INSERTSHIPS_CONSTRAINTS = [
    "Never skip orders unless no feasible assignment exists.",
    "Rollback tentative insertions when a candidate route fails.",
    "Call RenewnTotalCost before returning Dispatch.",
    "Avoid negative, suspiciously low, timeout, and missing-result candidates.",
]


def default_corpus_dir(project_root: str | Path) -> Path:
    return (Path(project_root) / "eoh_rag_workspace" / "rag" / "corpus").resolve()


def resolve_corpus_dir(project_root: str | Path, corpus_dir: str | Path | None) -> Path:
    root = Path(project_root).resolve()
    allowed_dir = default_corpus_dir(root)
    if not corpus_dir:
        candidate = allowed_dir
    else:
        raw = Path(corpus_dir)
        if raw.is_absolute():
            candidate = raw.resolve()
        else:
            root_relative = (root / raw).resolve()
            try:
                root_relative.relative_to(allowed_dir)
                candidate = root_relative
            except ValueError:
                candidate = (allowed_dir / raw).resolve()

    try:
        candidate.relative_to(allowed_dir)
    except ValueError:
        raise ValueError("RAG corpus directory must stay under eoh_rag_workspace/rag/corpus")
    return candidate


def _title_from_id(item_id: str) -> str:
    return item_id.replace("_", " ").replace("-", " ").title()


def _tags_from_name(name: str) -> list[str]:
    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", name)]
    tags = ["insertships"]
    for token in tokens:
        if token not in tags:
            tags.append(token)
    return tags


def build_code_examples(project_root: str | Path) -> list[CorpusItem]:
    """InsertShips code examples are curated externally, not built here; returns []."""
    return []


def build_algorithm_cards(project_root: str | Path) -> list[CorpusItem]:
    """Algorithm cards are curated manually; SA seed content lives in api_constraint. Returns []."""
    return []


def filter_corpus_by_mode(corpus: list[CorpusItem], mode: str) -> list[CorpusItem]:
    normalized = mode.strip().lower() if mode else "mixed"
    if normalized == "mixed":
        return list(corpus)
    if normalized == "history":
        return [item for item in corpus if item.id not in LITERATURE_IDS]
    if normalized == "literature":
        return [item for item in corpus if item.id in LITERATURE_IDS or item.kind in {"api_constraint", "failure_case"}]
    raise ValueError("RAG mode must be one of: history, literature, mixed")


def build_api_constraints(project_root: str | Path) -> list[CorpusItem]:
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
    target_dir = resolve_corpus_dir(project_root, corpus_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    algorithm_path = target_dir / CORPUS_FILES["algorithm_card"]
    curated_algorithm_cards: list[CorpusItem] = []
    if algorithm_path.exists():
        # Preserve both curated literature cards AND history-derived cards (from best-code feedback loop).
        existing_algorithm_cards = [
            item for item in load_corpus(algorithm_path)
            if item.id in LITERATURE_IDS or _is_history_card(item)
        ]
        curated_algorithm_cards = existing_algorithm_cards
        lit_count = len({item.id for item in curated_algorithm_cards})
        if lit_count < len(LITERATURE_IDS):
            print("Warning: algorithm_cards.jsonl has fewer than expected curated literature cards.")
    else:
        print("Warning: algorithm_cards.jsonl missing; writing empty curated algorithm card corpus.")

    grouped = {
        "code_example": build_code_examples(project_root),
        "algorithm_card": curated_algorithm_cards,
        "api_constraint": build_api_constraints(project_root),
        "failure_case": build_failure_cases(project_root),
    }

    written: list[Path] = []
    for kind, filename in CORPUS_FILES.items():
        path = target_dir / filename
        if kind != "algorithm_card" or not algorithm_path.exists():
            save_corpus(grouped[kind], path)
        written.append(path)
    return written


def load_all_corpora(project_root: str | Path, corpus_dir: str | Path | None = None) -> list[CorpusItem]:
    target_dir = resolve_corpus_dir(project_root, corpus_dir)
    expected = [target_dir / filename for filename in CORPUS_FILES.values()]
    if any(not path.exists() for path in expected):
        build_all_corpora(project_root, target_dir)

    items: list[CorpusItem] = []
    for path in expected:
        items.extend(load_corpus(path))
    return items
