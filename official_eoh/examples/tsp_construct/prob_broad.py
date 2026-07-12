#!/usr/bin/env python3
"""A3: TSP held-out 评测器(与 A1 BPONLINEBroad 同构,复用 n_train/held_out_set 字段)。"""
import sys
import importlib.util
from pathlib import Path

import numpy as np

EXAMPLE_DIR = Path(__file__).resolve().parent
OFFICIAL_EOH_ROOT = EXAMPLE_DIR.parents[1]
# 按当前文件定位 vendored EoH，避免依赖开发机路径或启动命令所在目录。
sys.path.insert(0, str(OFFICIAL_EOH_ROOT / "eoh" / "src"))
sys.path.insert(0, str(EXAMPLE_DIR))
sys.path.insert(0, str(EXAMPLE_DIR.parent))
from core_benchmarks import evaluate_tsp, load_tsp

_BASE_SPEC = importlib.util.spec_from_file_location("_tsp_construct_base_prob", EXAMPLE_DIR / "prob.py")
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise ImportError("cannot load TSP base problem")
_BASE_MODULE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_BASE_MODULE)
TSPCONST = _BASE_MODULE.TSPCONST

class TSPCONSTBroad(TSPCONST):
    """TSP 广训练池 + held-out 报告版评测器(opt-in,与 A1 同构)。
    
    用默认 n=50(等缺省构造)的训练实例族作适应度(规模可配),held-out 实例只报告不进适应度。
    manifest 设 broad_training:true 启用;缺省 false 时原 TSPCONST 不受影响。
    """
    def __init__(self, problem_size: int = 50, timeout: int = 40, n_processes: int = 1,
                 n_train: int = 128, held_out_set: list | None = None):
        super().__init__(timeout=timeout, n_processes=n_processes)  # BaseProblem,非 TSPCONST
        self.problem_size = problem_size
        self.neighbor_size = min(50, problem_size)
        self.n_train = n_train
        self.held_out_data = held_out_set or []
        self.held_out_report = {}
        # held-out 不参与适应度，只在最终最佳候选确定后计算，避免每个候选重复跑大型基准。
        self.report_held_out = False
        self.instance_data = self._gen_broad_instances(n_train, problem_size)
    
    @staticmethod
    def _gen_broad_instances(n: int, size: int):
        """生成 n 个随机 TSP 实例(同分布不同 seed)。"""
        data = []
        for i in range(n):
            rng = np.random.default_rng(9000 + i)
            coords = rng.uniform(0, 1000, (size, 2))
            dist = np.array([[np.linalg.norm(coords[a]-coords[b]) for b in range(size)] for a in range(size)])
            neigh = np.argsort(dist, axis=1)
            data.append((coords.tolist(), dist.tolist(), neigh.tolist()))
        return data  # [(coords, dist_matrix, neigh_matrix), ...]
    
    def _tour_cost(self, coords, route):
        cost = sum(np.linalg.norm(np.array(coords[r])-np.array(coords[s])) for r,s in zip(route, route[1:]))
        cost += np.linalg.norm(np.array(coords[route[-1]]) - np.array(coords[route[0]]))
        return cost
    
    def _eval_candidate(self, heuristic, coords, dist, neigh, neighbor_size=50):
        n = len(coords)
        route = [0]; current = 0
        for i in range(1, n-1):
            near = neigh[current][1:]
            unvisited = np.array([u for u in near if u not in route])
            unvisited = unvisited[:min(neighbor_size, len(unvisited))]
            if len(unvisited) == 0:
                unvisited = np.array([u for u in range(n) if u not in route])
            try:
                nxt = heuristic(current, 0, unvisited, np.array(dist))
            except Exception:
                nxt = unvisited[0]
            if nxt in route:
                return None
            route.append(nxt); current = nxt
        remaining = [u for u in range(n) if u not in route]
        if remaining: route.append(remaining[0])
        if len(route) != n: return None
        return self._tour_cost(coords, route)
    
    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        costs = []
        for coords, dist, neigh in self.instance_data:
            v = self._eval_candidate(callable_func, coords, dist, neigh)
            if v is None: return None
            costs.append(v)
        fitness = float(np.mean(costs))
        if not self.report_held_out:
            return fitness

        # held-out 报告(只记录,不进适应度)
        self.held_out_report = {}
        for entry in self.held_out_data:
            try:
                result = evaluate_tsp(callable_func, load_tsp(entry))
            except Exception as exc:
                result = {"instance": Path(entry).stem, "feasible": False, "error_type": type(exc).__name__, "error": str(exc)}
            self.held_out_report[Path(entry).stem] = result
        return fitness
