# Copyright (c) 2026 Fei Liu. MIT License.
# Project: https://github.com/FeiLiu36/EoH
# Citation: Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu,
#           Qingfu Zhang, Evolution of Heuristics: Towards Efficient Automatic Algorithm Design
#           Using Large Language Model, Forty-first International Conference on Machine Learning
#           (ICML), 2024.

import sys
import os
import re
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
                 training_profile: str = "single_5k", structured_feedback: bool = False,
                 robust_feedback: bool = False, confirmation_feedback: bool = False):
        super(BPONLINE, self).__init__(timeout=timeout, n_processes=n_processes)
        self.training_profile = training_profile
        self.structured_feedback = structured_feedback
        self.robust_feedback = robust_feedback
        self.confirmation_feedback = confirmation_feedback
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
        if training_profile == "robust_folds_1k_5k_10k":
            balanced, _ = BPONLINEBroad._gen_broad_instances(
                capacity, n_train, "balanced_1k_5k_10k"
            )
            instances = {}
            lower_bounds = {}
            # 复用完全相同的 120 个实例，只拆成四折；避免把增加数据量误当成稳健反馈效果。
            for dataset_name, dataset in balanced.items():
                for fold_index in range(4):
                    fold_name = f"{dataset_name}_fold{fold_index}"
                    fold_items = list(dataset.items())[fold_index * 10:(fold_index + 1) * 10]
                    instances[fold_name] = dict(fold_items)
                    lower_bounds[fold_name] = round(
                        np.mean(
                            [
                                np.ceil(np.sum(instance["items"]) / capacity)
                                for _, instance in fold_items
                            ]
                        ),
                        4,
                    )
            return instances, lower_bounds
        if training_profile == "dual_batch_1k_5k_10k":
            instances = {}
            lower_bounds = {}
            # 搜索和开发确认各占一半预算；确认批参与选择，因此不是最终 held-out。
            for scale_index, item_count in enumerate((1000, 5000, 10000)):
                for batch_name, seed_start in (("search", 41000), ("confirm", 51000)):
                    dataset_name = f"broad_{batch_name}_{item_count}"
                    dataset = {}
                    lower_bound_sum = 0.0
                    for instance_index in range(20):
                        rng = np.random.default_rng(
                            seed_start + scale_index * 1000 + instance_index
                        )
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

    def evaluate_program(self, program_str: str, callable_func) -> float | dict | None:
        if self.confirmation_feedback:
            fitness, scale_feedback = self._evaluate_with_confirmation_feedback(callable_func)
            evaluation_result = {"objective": fitness, "feedback": scale_feedback}
        elif self.structured_feedback:
            fitness, scale_feedback = self._evaluate_with_scale_feedback(callable_func)
            evaluation_result = {"objective": fitness, "feedback": scale_feedback}
        else:
            fitness = super().evaluate_program(program_str, callable_func)
            evaluation_result = fitness
        if not self.report_held_out:
            return evaluation_result

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
        return evaluation_result

    def _evaluate_dataset_gap(self, name, dataset, callable_func):
        """计算一个冻结数据集的 gap，供多种反馈合同复用。"""
        used_bins = []
        for instance in dataset.values():
            capacity = instance["capacity"]
            items = np.array(instance["items"])
            bins = np.array([capacity] * instance["num_items"])
            _, bins_packed = self.online_binpack(items, bins, callable_func)
            used_bins.append((bins_packed != capacity).sum())
        return float((np.mean(used_bins) - self.lb[name]) / self.lb[name])

    def _evaluate_with_confirmation_feedback(self, callable_func):
        """搜索批负责排序，独立开发确认批负责判断候选是否能进入种群。"""
        gaps = {"search": {}, "confirm": {}}
        for name, dataset in self.instances.items():
            match = re.search(r"broad_(search|confirm)_(\d+)", name)
            if not match:
                raise ValueError(f"invalid dual-batch dataset name: {name}")
            batch_name, scale = match.groups()
            gaps[batch_name][scale] = self._evaluate_dataset_gap(name, dataset, callable_func)
        search_scale = {
            scale: round(gap * 100.0, 6) for scale, gap in gaps["search"].items()
        }
        confirm_scale = {
            scale: round(gap * 100.0, 6) for scale, gap in gaps["confirm"].items()
        }
        search_objective = float(np.mean(list(gaps["search"].values())))
        confirm_objective = float(np.mean(list(gaps["confirm"].values())))
        worst_scale = max(search_scale, key=search_scale.get)
        feedback = {
            "scale_gap_pct": search_scale,
            "confirm_scale_gap_pct": confirm_scale,
            "worst_scale": worst_scale,
            "worst_gap_pct": search_scale[worst_scale],
            "confirm_objective": confirm_objective,
            "search_confirm_gap": confirm_objective - search_objective,
        }
        return search_objective, feedback

    def _evaluate_with_scale_feedback(self, callable_func):
        """返回聚合目标和各尺度 gap，供 scale_aware 提示定位最差尺度。"""
        fitness_per_dataset = []
        gap_by_scale = {}
        for name, dataset in self.instances.items():
            gap = self._evaluate_dataset_gap(name, dataset, callable_func)
            fitness_per_dataset.append(float(gap))
            match = re.search(r"broad_train_(\d+)", name)
            scale = match.group(1) if match else name.rsplit("_", 1)[-1]
            gap_by_scale.setdefault(scale, []).append(float(gap * 100.0))
        scale_gap_pct = {
            scale: round(float(np.mean(gaps)), 6) for scale, gaps in gap_by_scale.items()
        }
        scale_std_pct = {
            scale: round(float(np.std(gaps)), 6) for scale, gaps in gap_by_scale.items()
        }
        worst_scale = max(scale_gap_pct, key=scale_gap_pct.get)
        feedback = {
            "scale_gap_pct": scale_gap_pct,
            "worst_scale": worst_scale,
            "worst_gap_pct": scale_gap_pct[worst_scale],
        }
        mean_objective = float(np.mean(fitness_per_dataset))
        if self.robust_feedback:
            # 波动惩罚让只在个别固定折上获益的候选不易进入种群；权重在实验前固定为 0.5。
            variation_penalty = 0.5 * float(np.mean(list(scale_std_pct.values()))) / 100.0
            feedback.update(
                {
                    "scale_std_pct": scale_std_pct,
                    "scale_fold_gap_pct": {
                        scale: [round(gap, 6) for gap in gaps]
                        for scale, gaps in gap_by_scale.items()
                    },
                    "mean_objective": mean_objective,
                    "variation_penalty": variation_penalty,
                }
            )
            return mean_objective + variation_penalty, feedback
        return mean_objective, feedback
