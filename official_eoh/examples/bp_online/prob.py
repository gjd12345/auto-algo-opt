# Copyright (c) 2026 Fei Liu. MIT License.
# Project: https://github.com/FeiLiu36/EoH
# Citation: Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu,
#           Qingfu Zhang, Evolution of Heuristics: Towards Efficient Automatic Algorithm Design
#           Using Large Language Model, Forty-first International Conference on Machine Learning
#           (ICML), 2024.

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'eoh', 'src'))

from eoh import BaseProblem
from get_instance import GetData


class BPONLINE(BaseProblem):
    template_program = '''
def score(item: int, bins: np.ndarray) -> np.ndarray:
    """Score each bin for assigning the current item. Higher score = preferred bin.

    Args:
        item: size of the current item to assign
        bins: remaining capacities of feasible bins (all >= item size)
    Returns:
        scores: priority scores for each bin
    """
    return bins
'''
    task_description = (
        "Design a novel score function that scores a set of bins to assign an item. "
        "In each step, the item will be assigned to the bin with the maximum score. "
        "The final goal is to minimize the number of used bins."
    )

    def __init__(self, capacity: int = 100, timeout: int = 40, n_processes: int = 1):
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.instances, self.lb = GetData().get_instances(capacity)

    def get_valid_bin_indices(self, item: float, bins: np.ndarray) -> np.ndarray:
        return np.nonzero((bins - item) >= 0)[0]

    def online_binpack(self, items: tuple, bins: np.ndarray, score_func):
        packing = [[] for _ in bins]
        for item in items:
            valid = self.get_valid_bin_indices(item, bins)
            priorities = score_func(item, bins[valid])
            best = valid[np.argmax(priorities)]
            bins[best] -= item
            packing[best].append(item)
        return packing, bins

    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        fitness_per_dataset = []
        for name, dataset in self.instances.items():
            num_bins_list = []
            for _, instance in dataset.items():
                capacity = instance['capacity']
                items = np.array(instance['items'])
                bins = np.array([capacity] * instance['num_items'])
                _, bins_packed = self.online_binpack(items, bins, callable_func)
                num_bins_list.append(-(bins_packed != capacity).sum())
            avg = -np.mean(num_bins_list)
            fitness_per_dataset.append((avg - self.lb[name]) / self.lb[name])
        return float(np.mean(fitness_per_dataset))


class BPONLINEBroad(BPONLINE):
    """广训练池 + held-out 报告版 BP 评测器(opt-in)。

    用 n_train 个变化 Weibull 实例作适应度(对齐 EoH-S 128 实例),held-out pkl 只报告不进适应度。
    manifest 设 broad_training:true 启用;缺省 false 时 BPONLINE 旧 5 实例不受影响。
    预留 n_train/held_out_set 字段供 TSP/CVRP 复用(决策 aa)。
    """
    def __init__(self, capacity: int = 100, timeout: int = 40, n_processes: int = 1,
                 n_train: int = 128, held_out_set: list | None = None,
                 training_profile: str = "single_5k"):
        super(BPONLINE, self).__init__(timeout=timeout, n_processes=n_processes)
        self.training_profile = training_profile
        self.instances, self.lb = self._gen_broad_instances(capacity, n_train, training_profile)
        self.held_out_data = self._load_held_out(held_out_set)
        self.held_out_report = {}     # 由 run 结束后读取
        # held-out 只用于最终报告；演化阶段若逐候选重复计算，会显著放大耗时且不参与适应度。
        self.report_held_out = False

    @staticmethod
    def _gen_broad_instances(capacity: int, n_train: int, training_profile: str = "single_5k"):
        """生成冻结训练实例；多尺度版本与 128×5k 保持相同总物品量。"""
        if training_profile == "balanced_1k_5k_10k":
            instances = {}
            lower_bounds = {}
            # 40×(1k+5k+10k)=64 万，与旧 128×5k 的评测量一致；三个尺度分别计分后等权平均。
            for scale_index, item_count in enumerate((1000, 5000, 10000)):
                dataset_name = f"broad_train_{item_count}"
                dataset = {}
                lower_bound_sum = 0.0
                for instance_index in range(40):
                    rng = np.random.default_rng(21000 + scale_index * 1000 + instance_index)
                    items = np.clip(
                        np.round(rng.weibull(3.0, item_count) * 45.0).astype(int),
                        1,
                        capacity,
                    )
                    dataset[str(instance_index)] = {
                        "items": items.tolist(),
                        "capacity": capacity,
                        "num_items": item_count,
                    }
                    lower_bound_sum += np.ceil(items.sum() / capacity)
                instances[dataset_name] = dataset
                lower_bounds[dataset_name] = round(lower_bound_sum / len(dataset), 4)
            return instances, lower_bounds
        if training_profile != "single_5k":
            raise ValueError(f"unknown BP training profile: {training_profile}")

        # 保留旧数据的 seed、数量和字段，默认配置的历史结果可逐字重放。
        instances = {"broad_train": {}}
        lb_sum = 0.0
        k, lam = 3.0, 45.0
        for i in range(n_train):
            rng = np.random.default_rng(7000 + i)
            items = np.clip(np.round(rng.weibull(k, 5000) * lam).astype(int), 1, capacity)
            instances["broad_train"][str(i)] = {
                "items": items.tolist(), "capacity": capacity, "num_items": 5000
            }
            lb_sum += np.ceil(items.sum() / capacity)
        return instances, {"broad_train": round(lb_sum / n_train, 4)}

    @staticmethod
    def _load_held_out(held_out_set: list | None) -> list:
        if not held_out_set:
            return []
        import pickle
        data = []
        for path in held_out_set:
            fn = str(path)
            if not os.path.exists(fn):
                continue
            try:
                raw = pickle.load(open(fn, "rb"))
                insts = []
                for v in raw.values():
                    if isinstance(v, dict):
                        for vv in v.values():
                            if isinstance(vv, dict) and "items" in vv:
                                insts.append(np.array(vv["items"], dtype=np.float64))
                    elif isinstance(v, list) and v and isinstance(v[0], (list, tuple, np.ndarray)):
                        for inst in v:
                            insts.append(np.array(inst, dtype=np.float64))
                data.append({"path": fn, "instances": insts})
            except Exception as exc:
                print(f"[BPONLINEBroad] held-out 加载失败 {fn}: {exc}")
        return data

    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        fitness = super().evaluate_program(program_str, callable_func)
        if not self.report_held_out:
            return fitness

        self.held_out_report = {}
        for entry in self.held_out_data:
            items_list = entry["instances"]
            if not items_list:
                continue
            try:
                cap = 100
                used_list = []
                lb_list = []
                for items in items_list:
                    bins = np.array([cap] * len(items), dtype=float)
                    _, bins_packed = self.online_binpack(items, bins, callable_func)
                    used_list.append(-(bins_packed != cap).sum())
                    lb_list.append(np.ceil(np.sum(items) / cap))
                mean_used = -np.mean(used_list)
                mean_lb = np.mean(lb_list)
                self.held_out_report[entry["path"]] = round((mean_used - mean_lb) / mean_lb * 100, 3)
            except Exception as exc:
                self.held_out_report[entry["path"]] = f"error: {exc}"
        return fitness
