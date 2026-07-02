"""
模块：registry（规格注册表）
功能：集中登记框架支持的「优化目标」与「优化问题」两类静态规格，供运行器按名字查询。
职责：
    - 维护 TARGET_SPECS：待进化的目标函数规格（函数签名、约束提示、抽取/替换正则、护栏检查等），
      每一项描述一个待 LLM 演化的启发式函数（如 InsertShips / Optimization / SelectItems /
      SplitOrders / ScoreBin）。
    - 维护 PROBLEM_SPECS：每个优化问题的运行规格（源码文件、可执行文件、优化方向、基准数据、指标）。
    - 提供按名字取规格的两个查询函数。
接口：
    - TARGET_SPECS: dict[str, TargetSpec]
    - PROBLEM_SPECS: dict[str, ProblemSpec]
    - get_target_spec(name: str) -> TargetSpec
    - get_problem_spec(name: str) -> ProblemSpec
输入：无外部文件或环境变量；仅依赖同包内的 ProblemSpec 与 TargetSpec 数据类。
输出：TargetSpec / ProblemSpec 实例（找不到时抛出 ValueError）。
示例：
    spec = get_target_spec("InsertShips")
    problem = get_problem_spec("vrp_insertships")
"""
from __future__ import annotations

from .problem_spec import ProblemSpec
from .target_spec import TargetSpec


# 目标规格表：键为目标名，值为对应的 TargetSpec。
# 每个 TargetSpec 描述一个待进化的启发式函数——包括函数签名、写给 LLM 的约束提示、
# 从生成代码中抽取该函数的正则（extract_regex）、把新实现回填到源码的替换模板
# （replace_regex_template）、RAG 的 API 使用上下文，以及生成结果需通过的护栏检查项。


TARGET_SPECS: dict[str, TargetSpec] = {
    # InsertShips：在既有派车方案上把新订单逐一插入路线的目标函数。
    # 采用「试插-撤销」策略评估每次插入的代价增量，且不得跳过任何订单。
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
    # Optimization：在已有派车方案上做温度感知的局部优化（类模拟退火）。
    # 在车辆间移动船次或调整路线，失败的移动需回滚，且订单集合必须保持不变。
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
        seed_path="go_solver/main.go:455",
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
    # SelectItems：0/1 背包问题的选择函数。返回与物品数等长的布尔数组，
    # 在总重量不超过容量的前提下最大化总价值。
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
    # SplitOrders：把大订单按车辆容量拆分成子订单。
    # 需精确保留每个原始订单的体积，且每个子订单体积不超过所选车辆容量。
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
    # ScoreBin：在线装箱问题的打分函数。为每个候选箱子返回一个有限分值，
    # 可行箱子中分值最高者胜出，目标是尽量减少使用的箱子数。
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


# 问题规格表：键为问题名，值为对应的 ProblemSpec。
# 每个 ProblemSpec 描述一个优化问题的运行环境——包括实现语言、参与编译的源码文件、
# 生成的可执行文件名、目标是最大化还是最小化、评测所用的基准数据集，以及默认关注的指标。
PROBLEM_SPECS: dict[str, ProblemSpec] = {
    # vrp_insertships：带容量与时间窗的车辆路径问题（对应 InsertShips 目标），
    # 使用 Solomon 基准数据集，目标为最小化。
    "vrp_insertships": ProblemSpec(
        name="vrp_insertships",
        language="go",
        source_files=["go_solver/main.go", "go_solver/routing.go"],
        main_binary="mainbin_sa.exe",
        objective_direction="minimize",
        benchmark_data=[
            {"source_dir": "go_solver/solomon_benchmark_d50", "instances": ["rc101.json", "rc102.json", "rc103.json"]},
            {"source_dir": "go_solver/solomon_benchmark_d75", "instances": ["rc101.json", "rc102.json", "rc103.json"]},
        ],
        default_metrics={"primary": "best_EOH_J", "secondary": "valid_candidates"},
    ),
    # knapsack：0/1 背包问题（对应 SelectItems 目标），目标为最大化总价值。
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
    # mixer_split：搅拌车订单拆分问题（对应 SplitOrders 目标），目标为最小化。
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
    # bin_packing_online：在线装箱问题（对应 ScoreBin 目标），
    # 以「与下界的差距」为主要指标，目标为最小化。
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
    """按名字取出目标规格。

    参数 name：目标名（如 "InsertShips"、"ScoreBin"），须为 TARGET_SPECS 的键。
    返回：对应的 TargetSpec。
    找不到时抛出 ValueError。
    """
    try:
        return TARGET_SPECS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown target spec: {name}") from exc


def get_problem_spec(name: str) -> ProblemSpec:
    """按名字取出问题规格。

    参数 name：问题名（如 "vrp_insertships"、"bin_packing_online"），须为 PROBLEM_SPECS 的键。
    返回：对应的 ProblemSpec。
    找不到时抛出 ValueError。
    """
    try:
        return PROBLEM_SPECS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown problem spec: {name}") from exc
