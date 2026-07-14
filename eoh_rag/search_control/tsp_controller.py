"""让 EOH 在固定安全原语上进化 TSP 搜索控制器。"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Callable, Sequence

import numpy as np


# 这些原语已经在前序独立实验中验证。这里复用实现而不复制算法代码，避免
# 控制器评测与教师上界使用两套语义不同的局部搜索。
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_ROOT = _REPO_ROOT / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

import evaluate_tsp_nearest_two_opt as nearest_two_opt  # noqa: E402
import evaluate_tsp_or_opt_2_vnd as segment_relocation  # noqa: E402
import evaluate_tsp_relocation_vnd as node_relocation  # noqa: E402
import evaluate_tsp_restricted_three_opt as restricted_three_opt  # noqa: E402
import intervene_tsp_edge_variability as route_metrics  # noqa: E402


ALLOWED_PRIMITIVES = (
    "two_opt",
    "relocate",
    "or_opt_2",
    "three_opt",
)

# 不同邻域一次搜索的计算量差异较大。用固定权重约束总预算，避免控制器通过
# 堆叠昂贵 3-opt 获得不公平的评测优势。
PRIMITIVE_BUDGET_WEIGHTS = {
    "two_opt": 1,
    "relocate": 2,
    "or_opt_2": 3,
    "three_opt": 5,
}
MAX_TOTAL_BUDGET = 60
MAX_PLAN_STEPS = 5
MAX_STEP_BUDGET = 24
MAX_STOP_THRESHOLD = 0.05
PLAN_COST_PENALTY = 0.0001


@dataclass(frozen=True)
class SearchStep:
    """一项已经通过白名单和预算校验的搜索动作。"""

    primitive: str
    budget: int
    minimum_relative_gain: float


@dataclass(frozen=True)
class ControllerInstance:
    """控制器评测所需的冻结 TSP 实例与初始路线。"""

    name: str
    distances: np.ndarray
    neighbors: np.ndarray
    initial_route: np.ndarray


def _is_int(value: object) -> bool:
    return isinstance(value, (int, np.integer)) and not isinstance(value, bool)


def validate_search_plan(
    raw_plan: object,
    total_budget: int,
    budget_policy: str = "strict",
) -> list[SearchStep]:
    """校验候选控制器输出，并按冻结策略处理加权总预算。

    ``strict`` 保留 proxy v1 的合同：总预算超限时整份计划无效。
    ``clip`` 用于独立的 proxy v2：保留合法前缀，超限步骤截到剩余预算后停止。
    未知原语、字段类型错误和单步越界在两种策略下都不会被修复。
    """

    if not _is_int(total_budget) or not 1 <= int(total_budget) <= MAX_TOTAL_BUDGET:
        raise ValueError("total_budget 超出控制器允许范围")
    if not isinstance(raw_plan, (list, tuple)) or not raw_plan:
        raise ValueError("搜索计划必须是非空列表")
    if len(raw_plan) > MAX_PLAN_STEPS:
        raise ValueError("搜索计划步骤过多")
    if budget_policy not in {"strict", "clip"}:
        raise ValueError(f"未知预算策略：{budget_policy!r}")

    steps: list[SearchStep] = []
    weighted_budget = 0
    for index, raw_step in enumerate(raw_plan):
        if not isinstance(raw_step, (list, tuple)) or len(raw_step) != 3:
            raise ValueError(f"第 {index + 1} 步必须包含原语、预算和停止阈值")
        primitive, budget, threshold = raw_step
        if primitive not in ALLOWED_PRIMITIVES:
            raise ValueError(f"未知搜索原语：{primitive!r}")
        if not _is_int(budget) or not 1 <= int(budget) <= MAX_STEP_BUDGET:
            raise ValueError(f"第 {index + 1} 步预算越界")
        if isinstance(threshold, bool) or not isinstance(
            threshold, (int, float, np.integer, np.floating)
        ):
            raise ValueError(f"第 {index + 1} 步停止阈值必须是数值")
        threshold_value = float(threshold)
        if not math.isfinite(threshold_value) or not 0.0 <= threshold_value <= MAX_STOP_THRESHOLD:
            raise ValueError(f"第 {index + 1} 步停止阈值越界")

        budget_value = int(budget)
        primitive_name = str(primitive)
        step_weight = PRIMITIVE_BUDGET_WEIGHTS[primitive_name]
        requested_cost = step_weight * budget_value
        if weighted_budget + requested_cost > int(total_budget):
            if budget_policy == "strict":
                raise ValueError("搜索计划超过加权总预算")

            # v2 只修复总预算溢出：保留原顺序和合法前缀，把当前步骤截到剩余预算后停止。
            # 这样不会替候选重新排序，也不会让后续低成本步骤绕过前面的超限选择。
            affordable_budget = (int(total_budget) - weighted_budget) // step_weight
            if affordable_budget >= 1:
                steps.append(
                    SearchStep(primitive_name, affordable_budget, threshold_value)
                )
            break

        weighted_budget += requested_cost
        steps.append(SearchStep(primitive_name, budget_value, threshold_value))
    return steps


def _generate_coordinates(node_count: int, seed: int, distribution: str) -> np.ndarray:
    """生成固定分布的开发实例；seed 和分布均由协议冻结。"""

    rng = np.random.default_rng(seed)
    if distribution == "uniform":
        coordinates = rng.random((node_count, 2))
    elif distribution == "clustered":
        centers = rng.random((4, 2))
        assignments = rng.integers(0, len(centers), size=node_count)
        coordinates = np.clip(
            centers[assignments] + rng.normal(0.0, 0.055, (node_count, 2)),
            0.0,
            1.0,
        )
    elif distribution == "ring":
        angles = np.linspace(0.0, 2.0 * np.pi, node_count, endpoint=False)
        angles += rng.normal(0.0, 0.035, node_count)
        radius = 0.40 + rng.normal(0.0, 0.045, node_count)
        coordinates = np.column_stack(
            (0.5 + radius * np.cos(angles), 0.5 + radius * np.sin(angles))
        )
    else:
        raise ValueError(f"未知实例分布：{distribution}")

    # 历史评测采用 TSPLIB EUC_2D 整数距离；0～1 坐标会在取整后坍缩为大量
    # 0 距离。统一放大到 0～1000，保留几何结构并与真实实例的距离语义一致。
    return coordinates * 1000.0


def _nearest_neighbor_route(distances: np.ndarray) -> np.ndarray:
    """构造固定起点路线，让控制器只负责后处理顺序而不混入构造差异。"""

    node_count = len(distances)
    route = np.empty(node_count, dtype=np.int64)
    route[0] = 0
    unvisited = np.ones(node_count, dtype=bool)
    unvisited[0] = False
    current = 0
    for position in range(1, node_count):
        candidates = np.flatnonzero(unvisited)
        # 距离并列时 np.argmin 保留节点编号更小者，保证跨平台重放稳定。
        next_node = int(candidates[int(np.argmin(distances[current, candidates]))])
        route[position] = next_node
        unvisited[next_node] = False
        current = next_node
    return route


_SUITE_SPECS = {
    "synthetic_dev_v1": (
        (64, 1101, "uniform"),
        (80, 1102, "clustered"),
        (96, 1103, "ring"),
        (112, 1104, "uniform"),
        (128, 1105, "clustered"),
        (144, 1106, "ring"),
    ),
    "synthetic_confirm_v1": (
        (72, 2101, "clustered"),
        (88, 2102, "ring"),
        (104, 2103, "uniform"),
        (120, 2104, "clustered"),
        (136, 2105, "ring"),
        (152, 2106, "uniform"),
    ),
    # v2 在每个规模上同时覆盖三种分布，避免控制器把“节点数”误当成“分布类型”。
    "synthetic_dev_v2": (
        (64, 3101, "uniform"),
        (64, 3102, "clustered"),
        (64, 3103, "ring"),
        (96, 3104, "uniform"),
        (96, 3105, "clustered"),
        (96, 3106, "ring"),
        (128, 3107, "uniform"),
        (128, 3108, "clustered"),
        (128, 3109, "ring"),
        (160, 3110, "uniform"),
        (160, 3111, "clustered"),
        (160, 3112, "ring"),
    ),
    "synthetic_confirm_v2": (
        (72, 4101, "uniform"),
        (72, 4102, "clustered"),
        (72, 4103, "ring"),
        (104, 4104, "uniform"),
        (104, 4105, "clustered"),
        (104, 4106, "ring"),
        (136, 4107, "uniform"),
        (136, 4108, "clustered"),
        (136, 4109, "ring"),
        (168, 4110, "uniform"),
        (168, 4111, "clustered"),
        (168, 4112, "ring"),
    ),
    "synthetic_confirm_v3": (
        (80, 5101, "uniform"),
        (80, 5102, "clustered"),
        (80, 5103, "ring"),
        (112, 5104, "uniform"),
        (112, 5105, "clustered"),
        (112, 5106, "ring"),
        (144, 5107, "uniform"),
        (144, 5108, "clustered"),
        (144, 5109, "ring"),
        (176, 5110, "uniform"),
        (176, 5111, "clustered"),
        (176, 5112, "ring"),
    ),
}

AVAILABLE_CONTROLLER_SUITES = tuple(_SUITE_SPECS)


def build_controller_suite(suite_name: str) -> tuple[ControllerInstance, ...]:
    """按冻结规格构建实例、距离矩阵、近邻表和相同的初始路线。"""

    if suite_name not in _SUITE_SPECS:
        raise ValueError(f"未知控制器评测集：{suite_name}")
    instances = []
    for node_count, seed, distribution in _SUITE_SPECS[suite_name]:
        coordinates = _generate_coordinates(node_count, seed, distribution)
        distances = route_metrics.build_distance_matrix(coordinates)
        neighbors = nearest_two_opt.build_nearest_neighbors(
            distances,
            neighbor_count=min(12, node_count - 1),
            block_size=64,
        )
        instances.append(
            ControllerInstance(
                name=f"{distribution}_n{node_count}_s{seed}",
                distances=distances,
                neighbors=neighbors,
                initial_route=_nearest_neighbor_route(distances),
            )
        )
    return tuple(instances)


def _apply_repeated_move(
    route: np.ndarray,
    budget: int,
    move: Callable[[np.ndarray], tuple[np.ndarray, bool]],
) -> tuple[np.ndarray, int]:
    accepted = 0
    for _ in range(budget):
        moved, improved = move(route)
        if not improved:
            break
        route = moved
        accepted += 1
    return route, accepted


def _apply_step(
    route: np.ndarray,
    instance: ControllerInstance,
    step: SearchStep,
) -> tuple[np.ndarray, int]:
    """把一个已校验动作映射到冻结实现，候选代码不能替换底层原语。"""

    if step.primitive == "two_opt":
        return nearest_two_opt.nearest_two_opt(
            route,
            instance.distances,
            instance.neighbors,
            step.budget,
        )
    if step.primitive == "relocate":
        return _apply_repeated_move(
            route,
            step.budget,
            lambda current: node_relocation.best_relocation(
                current, instance.distances, instance.neighbors
            ),
        )
    if step.primitive == "or_opt_2":
        return _apply_repeated_move(
            route,
            step.budget,
            lambda current: segment_relocation.best_segment_relocation(
                current, instance.distances, instance.neighbors, segment_length=2
            ),
        )

    accepted = 0
    for _ in range(step.budget):
        moved, improved, _ = restricted_three_opt.best_restricted_three_opt(
            route,
            instance.distances,
            instance.neighbors,
            candidate_neighbor_count=min(8, instance.neighbors.shape[1]),
        )
        if not improved:
            break
        route = moved
        accepted += 1
    return route, accepted


def _evaluate_instance(
    plan_function: Callable[[int, int], object],
    instance: ControllerInstance,
    budget_policy: str,
) -> dict[str, Any]:
    raw_plan = plan_function(len(instance.initial_route), MAX_TOTAL_BUDGET)
    steps = validate_search_plan(raw_plan, MAX_TOTAL_BUDGET, budget_policy)
    route = instance.initial_route.copy()
    initial_cost = route_metrics.route_cost(route, instance.distances)
    executed_budget = 0
    step_results = []

    for step in steps:
        before_cost = route_metrics.route_cost(route, instance.distances)
        route, accepted = _apply_step(route, instance, step)
        after_cost = route_metrics.route_cost(route, instance.distances)
        relative_gain = (before_cost - after_cost) / before_cost
        executed_budget += PRIMITIVE_BUDGET_WEIGHTS[step.primitive] * step.budget
        step_results.append(
            {
                "primitive": step.primitive,
                "budget": step.budget,
                "accepted": accepted,
                "relative_gain": relative_gain,
            }
        )
        # 阈值只决定是否继续后续步骤，当前步骤仍完整执行，避免结果依赖中途观测顺序。
        if relative_gain + 1e-12 < step.minimum_relative_gain:
            break

    if len(np.unique(route)) != len(route):
        raise ValueError("搜索原语产生了重复节点")
    final_cost = route_metrics.route_cost(route, instance.distances)
    return {
        "instance": instance.name,
        "node_count": len(route),
        "initial_cost": initial_cost,
        "final_cost": final_cost,
        "normalized_cost": final_cost / initial_cost,
        "improvement_pct": (initial_cost - final_cost) / initial_cost * 100.0,
        "executed_weighted_budget": executed_budget,
        "steps": step_results,
    }


def evaluate_controller(
    plan_function: Callable[[int, int], object],
    suite: Sequence[ControllerInstance],
    budget_policy: str = "strict",
) -> dict[str, Any]:
    """评测一个控制器；目标以路线质量为主，只加极小的确定性预算惩罚。"""

    results = [
        _evaluate_instance(plan_function, instance, budget_policy) for instance in suite
    ]
    mean_normalized_cost = fmean(item["normalized_cost"] for item in results)
    mean_budget_ratio = fmean(
        item["executed_weighted_budget"] / MAX_TOTAL_BUDGET for item in results
    )
    objective = mean_normalized_cost + PLAN_COST_PENALTY * mean_budget_ratio
    return {
        "objective": objective,
        "mean_normalized_cost": mean_normalized_cost,
        "mean_improvement_pct": fmean(item["improvement_pct"] for item in results),
        "mean_budget_ratio": mean_budget_ratio,
        "valid_instances": len(results),
        "instance_count": len(suite),
        "instance_results": results,
    }
