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

class CVRPCONSTBroad(CVRPCONST):
    """CVRP 广训练池 + held-out 评测器。
    
    用 n_train 个变化实例作适应度(对齐 EoH-S 256 实例设计),held-out 只报告不进适应度。
    """
    def __init__(self, n_customers: int = 50, capacity: int = 40, timeout: int = 40,
                 n_processes: int = 1, n_train: int = 128, held_out_set: list | None = None):
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.problem_size = n_customers + 1
        self.capacity = capacity
        self.n_train = n_train
        self.held_out_data = held_out_set or []
        self.held_out_report = {}
        self.instance_data = self._gen_broad_instances(n_train, n_customers, capacity)

    @staticmethod
    def _gen_broad_instances(n: int, n_cust: int, cap: int):
        """生成 n 个 CVRP 训练实例(随机坐标+需求)。"""
        data = []
        for i in range(n):
            rng = np.random.default_rng(11000 + i)
            coords = rng.uniform(0, 100, (n_cust + 1, 2))
            demands = np.zeros(n_cust + 1, dtype=int)
            demands[1:] = rng.integers(1, max(2, cap // 10), n_cust)
            data.append((coords, demands))
        return data

    def _tour_cost(self, coords, route):
        return sum(np.linalg.norm(np.array(coords[r]) - np.array(coords[s]))
                   for r, s in zip(route, route[1:]))

    def _route_construct(self, heuristic, dist, demands, cap):
        n = self.problem_size
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

    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        costs = []
        for coords, demands in self.instance_data:
            dist = np.array([[np.linalg.norm(coords[i] - coords[j]) for j in range(self.problem_size)]
                              for i in range(self.problem_size)])
            route = self._route_construct(callable_func, dist, demands, self.capacity)
            if route is None: return None
            costs.append(self._tour_cost(coords, route))
        fitness = float(np.mean(costs))
        self.held_out_report = {}
        for entry in self.held_out_data:
            try:
                result = evaluate_cvrp(callable_func, load_cvrp(entry))
            except Exception as exc:
                result = {"instance": Path(entry).stem, "feasible": False, "capacity_valid": False, "coverage_valid": False, "error_type": type(exc).__name__, "error": str(exc)}
            self.held_out_report[Path(entry).stem] = result
        return fitness
