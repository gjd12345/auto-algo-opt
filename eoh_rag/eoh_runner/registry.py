from __future__ import annotations

from .problem_spec import ProblemSpec
from .target_spec import TargetSpec


TARGET_SPECS: dict[str, TargetSpec] = {
    "InsertShips": TargetSpec(
        name="InsertShips",
        function_name="InsertShips",
        signature="func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch",
        inputs=["dispatch", "oris", "dess", "total_ship"],
        outputs=["Dispatch"],
        prompt_constraints=(
            "Use trial-undo insertion: AddShip, GenRoute, record cost delta, RemoveShip, "
            "GenRoute. Never skip orders. Call RenewnTotalCost before return."
        ),
        extract_regex=(
            r"func\s+InsertShips\s*\(\s*dispatch\s+Dispatch\s*,\s*oris\s*,\s*dess\s*\[\]Station\s*,"
            r"\s*total_ship\s+int\s*\)\s*Dispatch\s*\{[\s\S]*?\n\}"
        ),
        replace_regex_template=(
            r"func InsertShips\(dispatch Dispatch, oris, dess \[\]Station, total_ship int\) "
            r"Dispatch \{\s*\n%s\n\}"
        ),
        seed_path=None,
        rag_api_context=(
            "Save Assign state -> trial AddShip -> GenRoute -> record delta -> RemoveShip undo -> "
            "commit best -> RenewnTotalCost."
        ),
        guard_checks=["no_skipped_orders", "renew_cost_before_return", "dispatch_integrity"],
    ),
    "Optimization": TargetSpec(
        name="Optimization",
        function_name="Optimization",
        signature="func Optimization(dispatch Dispatch, temperature float64) Dispatch",
        inputs=["dispatch", "temperature"],
        outputs=["Dispatch"],
        prompt_constraints=(
            "Move ships between vehicles or adjust routes using temperature-aware acceptance. "
            "Preserve every order exactly once. Call RenewnTotalCost before return."
        ),
        extract_regex=r"func\s+Optimization\s*\(\s*dispatch\s+Dispatch\s*,\s*temperature\s+float64\s*\)\s*Dispatch\s*\{[\s\S]*?\n\}",
        replace_regex_template=r"func Optimization\(dispatch Dispatch, temperature float64\) Dispatch \{\s*\n%s\n\}",
        seed_path="main.go:455",
        rag_api_context=(
            "Use dispatch.Assigns[].RemoveShip/AddShip/GenRoute and dispatch.RenewnTotalCost. "
            "Rollback failed moves and preserve the ship-id multiset."
        ),
        guard_checks=[
            "optimization_order_multiset_preserved",
            "no_duplicated_ship_id",
            "no_missing_ship_id",
            "no_negative_NaN_cost",
            "renew_cost_before_return",
        ],
    ),
    "SelectItems": TargetSpec(
        name="SelectItems",
        function_name="SelectItems",
        signature="func SelectItems(items []Item, capacity int) []bool",
        inputs=["items", "capacity"],
        outputs=["[]bool"],
        prompt_constraints=(
            "Return exactly len(items) booleans. true means selected. Total selected weight must "
            "not exceed capacity. Maximize total value."
        ),
        extract_regex=r"func\s+SelectItems\s*\(\s*items\s+\[\]Item\s*,\s*capacity\s+int\s*\)\s*\[\]bool\s*\{[\s\S]*?\n\}",
        replace_regex_template=r"func SelectItems\(items \[\]Item, capacity int\) \[\]bool \{\s*\n%s\n\}",
        seed_path="eoh_rag_workspace/problems/knapsack/knapsack_solver.go",
        rag_api_context=(
            "func SelectItems(items []Item, capacity int) []bool. Return len(items) booleans. "
            "Keep total selected weight <= capacity. Maximize total value."
        ),
        guard_checks=["knapsack_capacity_not_exceeded", "return_array_correct_length"],
    ),
    "SplitOrders": TargetSpec(
        name="SplitOrders",
        function_name="SplitOrders",
        signature="func SplitOrders(orders []Order, vehicles []Vehicle, workHours float64) []SubOrder",
        inputs=["orders", "vehicles", "workHours"],
        outputs=["[]SubOrder"],
        prompt_constraints=(
            "Return suborders that preserve every original order volume. Each suborder volume must be "
            "<= its vehicle capacity. Never invent order IDs."
        ),
        extract_regex=(
            r"func\s+SplitOrders\s*\(\s*orders\s+\[\]Order\s*,\s*vehicles\s+\[\]Vehicle\s*,"
            r"\s*workHours\s+float64\s*\)\s*\[\]SubOrder\s*\{[\s\S]*?\n\}"
        ),
        replace_regex_template=(
            r"func SplitOrders\(orders \[\]Order, vehicles \[\]Vehicle, workHours float64\) "
            r"\[\]SubOrder \{\s*\n%s\n\}"
        ),
        seed_path="eoh_rag_workspace/problems/mixer_split/mixer_split_solver.go",
        rag_api_context=(
            "Return []SubOrder. Preserve each original order volume exactly. Each suborder volume "
            "must be <= chosen vehicle capacity. Use largest-capacity fallback splitting."
        ),
        guard_checks=[
            "mixer_order_volume_preserved",
            "mixer_suborder_capacity_not_exceeded",
            "mixer_known_order_ids_only",
        ],
    ),
    "ScoreBin": TargetSpec(
        name="ScoreBin",
        function_name="ScoreBin",
        signature="func ScoreBin(item int, remaining []int, capacity int) []float64",
        inputs=["item", "remaining", "capacity"],
        outputs=["[]float64"],
        prompt_constraints=(
            "Return exactly len(remaining) finite scores. Higher score wins among feasible bins. "
            "Minimize used bins and gap to the lower bound."
        ),
        extract_regex=r"func\s+ScoreBin\s*\(\s*item\s+int\s*,\s*remaining\s+\[\]int\s*,\s*capacity\s+int\s*\)\s*\[\]float64\s*\{[\s\S]*?\n\}",
        replace_regex_template=r"func ScoreBin\(item int, remaining \[\]int, capacity int\) \[\]float64 \{\s*\n%s\n\}",
        seed_path="eoh_rag_workspace/problems/bin_packing_online/bin_packing_solver.go",
        rag_api_context="Score feasible bins only. Return len(remaining) finite scores. Highest score is selected.",
        guard_checks=["obp_score_length", "obp_finite_scores", "obp_no_secret_io"],
    ),
}


PROBLEM_SPECS: dict[str, ProblemSpec] = {
    "vrp_insertships": ProblemSpec(
        name="vrp_insertships",
        language="go",
        source_files=["main.go", "routing.go"],
        main_binary="mainbin_sa.exe",
        objective_direction="minimize",
        benchmark_data=[
            {"source_dir": "solomon_benchmark_d50", "instances": ["rc101.json", "rc102.json", "rc103.json"]},
            {"source_dir": "solomon_benchmark_d75", "instances": ["rc101.json", "rc102.json", "rc103.json"]},
        ],
        default_metrics={"primary": "best_EOH_J", "secondary": "valid_candidates"},
    ),
    "knapsack": ProblemSpec(
        name="knapsack",
        language="go",
        source_files=["eoh_rag_workspace/problems/knapsack/knapsack_solver.go"],
        main_binary="knapsack_solver",
        objective_direction="maximize",
        benchmark_data=[
            {"path": "eoh_rag_workspace/problems/knapsack/testdata/testdata_01.json", "label": "n20"},
        ],
        default_metrics={"primary": "value", "secondary": "valid_rate"},
    ),
    "mixer_split": ProblemSpec(
        name="mixer_split",
        language="go",
        source_files=["eoh_rag_workspace/problems/mixer_split/mixer_split_solver.go"],
        main_binary="mixer_split_solver",
        objective_direction="minimize",
        benchmark_data=[
            {"path": "eoh_rag_workspace/problems/mixer_split/testdata/testdata_01.json", "label": "mixer_day_01"},
        ],
        default_metrics={"primary": "final_cost", "secondary": "valid_rate"},
    ),
    "bin_packing_online": ProblemSpec(
        name="bin_packing_online",
        language="go",
        source_files=["eoh_rag_workspace/problems/bin_packing_online/bin_packing_solver.go"],
        main_binary="bin_packing_solver",
        objective_direction="minimize",
        benchmark_data=[
            {"path": "eoh_rag_workspace/problems/bin_packing_online/testdata/obp_5x60_c100.json", "label": "obp_5x60_c100"},
        ],
        default_metrics={"primary": "gap_to_lb", "secondary": "valid_rate"},
    ),
}


def get_target_spec(name: str) -> TargetSpec:
    try:
        return TARGET_SPECS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown target spec: {name}") from exc


def get_problem_spec(name: str) -> ProblemSpec:
    try:
        return PROBLEM_SPECS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown problem spec: {name}") from exc
