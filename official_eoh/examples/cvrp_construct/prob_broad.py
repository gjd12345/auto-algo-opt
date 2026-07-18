#!/usr/bin/env python3
"""
A4: CVRP 广训练池 + held-out 报告评测器(复用 A1/A3 模式,opt-in)。

manifest 设 broad_training:true 启用;缺省 false 时原 CVRPCONST 不受影响。
预留 n_train/held_out_set 字段复用(决策 aa)。
"""
from __future__ import annotations
import sys
import importlib.util
from pathlib import Path

import numpy as np

EXAMPLE_DIR = Path(__file__).resolve().parent
OFFICIAL_EOH_ROOT = EXAMPLE_DIR.parents[1]
# 与 TSP evaluator 使用相同的文件定位规则，确保从任意工作目录导入均一致。
sys.path.insert(0, str(OFFICIAL_EOH_ROOT / "eoh" / "src"))
sys.path.insert(0, str(EXAMPLE_DIR))
sys.path.insert(0, str(EXAMPLE_DIR.parent))

from core_benchmarks import evaluate_cvrp, load_cvrp

_BASE_SPEC = importlib.util.spec_from_file_location("_cvrp_construct_base_prob", EXAMPLE_DIR / "prob.py")
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise ImportError("cannot load CVRP base problem")
_BASE_MODULE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_BASE_MODULE)
CVRPCONST = _BASE_MODULE.CVRPCONST

# 选择器与广训练评测器共享同一环境定义，避免节点数、容量或几何分布各自复制后漂移。
CVRP_MULTI_ENVIRONMENT_SPECS = (
    {"name": "uniform_50", "geometry": "uniform_square", "n_customers": 50, "capacity": 40, "demand_max": 3},
    {"name": "clustered_100", "geometry": "clustered", "n_customers": 100, "capacity": 60, "demand_max": 6},
    {"name": "rectangular_200", "geometry": "rectangular", "n_customers": 200, "capacity": 80, "demand_max": 8},
)

class CVRPCONSTBroad(CVRPCONST):
    """CVRP 广训练池 + held-out 评测器。
    
    用 n_train 个变化实例作适应度(对齐 EoH-S 256 实例设计),held-out 只报告不进适应度。
    """
    def __init__(self, n_customers: int = 50, capacity: int = 40, timeout: int = 40,
                 n_processes: int = 1, n_train: int = 128, held_out_set: list | None = None,
                 confirmation_feedback: bool = False, n_confirm: int | None = None,
                 training_profile: str = "uniform_50"):
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.problem_size = n_customers + 1
        self.capacity = capacity
        self.n_train = n_train
        self.training_profile = training_profile
        self.confirmation_feedback = confirmation_feedback
        self.held_out_data = held_out_set or []
        self.held_out_report = {}
        # held-out 只在最终报告阶段执行，避免在 128 实例训练评估后重复增加额外开销。
        self.report_held_out = False
        self.instance_data = self._gen_profile_instances(
            n_train, n_customers, capacity, training_profile, seed_start=11000
        )
        # 独立确认批只控制进化接纳；最终基准实例仍保持报告用途，不参与候选选择。
        confirm_size = n_train if n_confirm is None else max(1, int(n_confirm))
        self.confirmation_data = (
            self._gen_profile_instances(
                confirm_size, n_customers, capacity, training_profile, seed_start=21000
            )
            if confirmation_feedback else []
        )

    @staticmethod
    def _generate_instance(spec: dict, seed: int) -> dict:
        """生成一个带环境标签的实例，供搜索批和确认批复用同一合同。"""
        rng = np.random.default_rng(seed)
        n_customers = int(spec["n_customers"])
        geometry = spec["geometry"]
        if geometry == "uniform_square":
            coords = rng.uniform(0, 100, (n_customers + 1, 2))
        elif geometry == "clustered":
            centers = rng.uniform(15, 85, (4, 2))
            assignments = rng.integers(0, len(centers), n_customers + 1)
            coords = centers[assignments] + rng.normal(0, 8, (n_customers + 1, 2))
            coords = np.clip(coords, 0, 100)
            coords[0] = np.array([50.0, 50.0])
        elif geometry == "rectangular":
            coords = np.column_stack(
                (rng.uniform(0, 300, n_customers + 1), rng.uniform(0, 50, n_customers + 1))
            )
        else:
            raise ValueError(f"unknown CVRP geometry: {geometry}")
        demands = np.zeros(n_customers + 1, dtype=int)
        demands[1:] = rng.integers(1, int(spec["demand_max"]) + 1, n_customers)
        return {
            "environment": spec["name"],
            "coords": coords,
            "demands": demands,
            "capacity": int(spec["capacity"]),
        }

    @classmethod
    def _gen_profile_instances(
        cls, n: int, n_cust: int, cap: int, training_profile: str, seed_start: int
    ) -> list[dict]:
        """按 profile 生成等权环境；多环境总预算尽量均分，避免大规模环境支配数量。"""
        if training_profile == "uniform_50":
            specs = [{
                "name": "uniform_50",
                "geometry": "uniform_square",
                "n_customers": n_cust,
                "capacity": cap,
                "demand_max": max(1, cap // 10 - 1),
            }]
        elif training_profile == "multi_env_50_100_200":
            specs = list(CVRP_MULTI_ENVIRONMENT_SPECS)
        else:
            raise ValueError(f"unknown CVRP training profile: {training_profile}")

        if n < len(specs):
            raise ValueError(
                f"n_train={n} cannot cover all {len(specs)} CVRP environments"
            )
        counts = [n // len(specs)] * len(specs)
        for index in range(n % len(specs)):
            counts[index] += 1
        data = []
        for environment_index, (spec, count) in enumerate(zip(specs, counts)):
            environment_seed = seed_start + environment_index * 1000
            data.extend(cls._generate_instance(spec, environment_seed + i) for i in range(count))
        return data

    def _tour_cost(self, coords, route):
        return sum(np.linalg.norm(np.array(coords[r]) - np.array(coords[s]))
                   for r, s in zip(route, route[1:]))

    def _route_construct(self, heuristic, dist, demands, cap):
        n = len(demands)
        route = [0]; load = 0; cur = 0
        unvisited = set(range(1, n))
        all_cust = np.arange(1, n)
        feasible = all_cust.copy()
        steps = 0; max_steps = n * n
        while unvisited and steps < max_steps:
            steps += 1
            try:
                nxt = heuristic(cur, 0, feasible, float(cap - load), demands.copy(), dist.copy())
            except Exception:
                nxt = 0
            if nxt == 0:
                route.append(0); load = 0; cur = 0
            else:
                route.append(int(nxt)); load += int(demands[int(nxt)]); cur = int(nxt)
                unvisited.discard(int(nxt))
            feasible = np.array([u for u in all_cust if u in unvisited and load + demands[u] <= cap])
            if unvisited and len(feasible) == 0:
                route.append(0); load = 0; cur = 0
                feasible = np.array(list(unvisited))
        if unvisited: return None
        if route[-1] != 0: route.append(0)
        if len(set(route)) != n: return None
        return route

    def _evaluate_instances(self, callable_func, instance_data) -> tuple[float, dict] | None:
        """多环境按环境等权；每客户成本避免 200 节点环境仅因数值大而支配目标。"""
        environment_costs: dict[str, list[float]] = {}
        normalize_per_customer = self.training_profile == "multi_env_50_100_200"
        for entry in instance_data:
            coords = entry["coords"]
            demands = entry["demands"]
            delta = coords[:, None, :] - coords[None, :, :]
            dist = np.sqrt(np.sum(delta * delta, axis=2))
            route = self._route_construct(callable_func, dist, demands, entry["capacity"])
            if route is None: return None
            cost = self._tour_cost(coords, route)
            if normalize_per_customer:
                cost /= max(1, len(coords) - 1)
            environment_costs.setdefault(entry["environment"], []).append(cost)
        environment_means = {
            name: float(np.mean(costs)) for name, costs in environment_costs.items()
        }
        return float(np.mean(list(environment_means.values()))), environment_means

    def evaluate_program(self, program_str: str, callable_func) -> float | dict | None:
        search_result = self._evaluate_instances(callable_func, self.instance_data)
        if search_result is None:
            return None
        fitness, search_environments = search_result

        evaluation_result: float | dict = fitness
        if self.confirmation_feedback:
            confirm_result = self._evaluate_instances(callable_func, self.confirmation_data)
            if confirm_result is None:
                return None
            confirm_objective, confirm_environments = confirm_result
            evaluation_result = {
                "objective": fitness,
                "feedback": {
                    "confirm_objective": confirm_objective,
                    "search_confirm_gap": confirm_objective - fitness,
                    "search_environment_objectives": search_environments,
                    "confirm_environment_objectives": confirm_environments,
                },
            }

        if not self.report_held_out:
            return evaluation_result

        self.held_out_report = {}
        for entry in self.held_out_data:
            try:
                result = evaluate_cvrp(callable_func, load_cvrp(entry))
            except Exception as exc:
                result = {"instance": Path(entry).stem, "feasible": False, "capacity_valid": False, "coverage_valid": False, "error_type": type(exc).__name__, "error": str(exc)}
            self.held_out_report[Path(entry).stem] = result
        return evaluation_result
