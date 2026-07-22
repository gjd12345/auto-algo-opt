# Copyright (c) 2026 Fei Liu. MIT License.
# Project: https://github.com/FeiLiu36/EoH
# Citation: Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu,
#           Qingfu Zhang, Evolution of Heuristics: Towards Efficient Automatic Algorithm Design
#           Using Large Language Model, Forty-first International Conference on Machine Learning
#           (ICML), 2024.

import sys
import os
import re
import hashlib
import json
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
                 robust_feedback: bool = False, confirmation_feedback: bool = False,
                 held_out_profile: str = ""):
        super(BPONLINE, self).__init__(timeout=timeout, n_processes=n_processes)
        self.training_profile = training_profile
        self.structured_feedback = structured_feedback
        self.robust_feedback = robust_feedback
        self.confirmation_feedback = confirmation_feedback
        self.held_out_profile = held_out_profile
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
        if training_profile == "dual_env_1k_5k_10k":
            instances = {}
            lower_bounds = {}
            # 搜索批保持原 Weibull 分布；确认批预注册为均匀分布与宽尾 Weibull 的等量混合。
            # 这里不读取 HiFo，避免把已经查看过的 held-out 反向变成训练反馈。
            for scale_index, item_count in enumerate((1000, 5000, 10000)):
                for batch_name, seed_start in (("search", 91000), ("confirm", 101000)):
                    dataset_name = f"broad_{batch_name}_{item_count}"
                    dataset = {}
                    lower_bound_sum = 0.0
                    for instance_index in range(20):
                        rng = np.random.default_rng(
                            seed_start + scale_index * 1000 + instance_index
                        )
                        if batch_name == "search":
                            items = np.clip(
                                np.round(rng.weibull(3.0, item_count) * 45.0).astype(int),
                                1,
                                capacity,
                            )
                        elif instance_index < 10:
                            items = rng.integers(1, capacity + 1, size=item_count)
                        else:
                            items = np.clip(
                                np.round(rng.weibull(1.5, item_count) * 35.0).astype(int),
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
        if training_profile == "fme_dev_distributions_v1":
            instances = {}
            lower_bounds = {}
            # 三个开发分布各 4 个冻结反例候选，共 12 个；两实验臂共享完全相同的实例。
            # 规模保持较小，让额外预算用于算法创造，而不是重复消耗在大规模评测上。
            distribution_specs = {
                "uniform": (61000, 1, capacity),
                "small_item_dense": (62000, 1, max(2, int(capacity * 0.35))),
                "large_item_dense": (63000, max(1, int(capacity * 0.55)), capacity),
            }
            for distribution, (seed_start, lower, upper) in distribution_specs.items():
                dataset_name = f"fme_dev_{distribution}"
                dataset = {}
                lower_bound_sum = 0.0
                for instance_index in range(4):
                    rng = np.random.default_rng(seed_start + instance_index)
                    items = rng.integers(lower, upper + 1, size=2048)
                    dataset[str(instance_index)] = {
                        "items": items.tolist(),
                        "capacity": capacity,
                        "num_items": len(items),
                    }
                    lower_bound_sum += np.ceil(items.sum() / capacity)
                instances[dataset_name] = dataset
                lower_bounds[dataset_name] = round(
                    lower_bound_sum / len(dataset), 4
                )
            return instances, lower_bounds
        if training_profile == "fme_dev_order_regime_feedback_v1":
            return BPONLINEBroad._gen_order_regime_feedback_instances(capacity)
        if training_profile == "fme_dev_distribution_order_v2":
            instances = {}
            lower_bounds = {}
            # v2 使用全新的开发 seed，并对同一多重集构造两种顺序。交替大小顺序是
            # 通用在线装箱压力测试，不复用首轮已查看 held-out 的升序/降序坐标。
            distribution_specs = {
                "uniform": (81000, 1, capacity),
                "small_item_dense": (82000, 1, max(2, int(capacity * 0.35))),
                "large_item_dense": (83000, max(1, int(capacity * 0.55)), capacity),
            }
            for distribution, (seed_start, lower, upper) in distribution_specs.items():
                dataset_name = f"fme_dev_v2_{distribution}"
                dataset = {}
                lower_bound_sum = 0.0
                for multiset_index in range(2):
                    rng = np.random.default_rng(seed_start + multiset_index)
                    random_order = rng.integers(lower, upper + 1, size=2048)
                    ordered = np.sort(random_order)
                    midpoint = len(ordered) // 2
                    alternating_extremes = np.column_stack(
                        (ordered[midpoint:][::-1], ordered[:midpoint])
                    ).reshape(-1)
                    for order_variant, items in (
                        ("random", random_order),
                        ("alternating_extremes", alternating_extremes),
                    ):
                        instance_id = f"{multiset_index}-{order_variant}"
                        dataset[instance_id] = {
                            "items": items.tolist(),
                            "capacity": capacity,
                            "num_items": len(items),
                            "multiset_id": str(multiset_index),
                            "order_variant": order_variant,
                        }
                        lower_bound_sum += np.ceil(items.sum() / capacity)
                instances[dataset_name] = dataset
                lower_bounds[dataset_name] = round(
                    lower_bound_sum / len(dataset), 4
                )
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
    def _gen_order_regime_feedback_instances(capacity: int):
        """生成独立的顺序区间开发集，不复用 v1/v2 的开发或 held-out 坐标。"""
        small_item_upper = capacity // 3
        if small_item_upper < 1:
            raise ValueError("order-regime profile requires capacity of at least 3")

        instances = {}
        lower_bounds = {}
        regime_specs = {
            "small_dominant": (84000, "small"),
            "mixed": (85000, "mixed"),
            "large_dominant": (86000, "large"),
        }
        for regime_id, (seed_start, sampler_kind) in regime_specs.items():
            dataset_name = f"fme_dev_order_regime_v1_{regime_id}"
            dataset = {}
            lower_bound_sum = 0.0
            for multiset_index in range(2):
                rng = np.random.default_rng(seed_start + multiset_index)
                if sampler_kind == "small":
                    sampled_multiset = rng.integers(
                        1, small_item_upper + 1, size=2048
                    )
                elif sampler_kind == "mixed":
                    small_items = rng.integers(
                        1, small_item_upper + 1, size=1024
                    )
                    large_items = rng.integers(
                        small_item_upper + 1, capacity + 1, size=1024
                    )
                    sampled_multiset = np.concatenate((small_items, large_items))
                else:
                    sampled_multiset = rng.integers(
                        small_item_upper + 1, capacity + 1, size=2048
                    )

                # 先冻结同一多重集，再由两个排列共享它；这使顺序而非样本组成成为
                # 唯一的比较变量，也避免复用已消费的升序/降序 held-out 坐标。
                random_order = rng.permutation(sampled_multiset)
                ordered_multiset = np.sort(sampled_multiset)
                midpoint = len(ordered_multiset) // 2
                alternating_extremes = np.column_stack(
                    (ordered_multiset[midpoint:][::-1], ordered_multiset[:midpoint])
                ).reshape(-1)
                large_item_count = int(
                    np.count_nonzero(sampled_multiset * 3 > capacity)
                )
                large_item_fraction = large_item_count / len(sampled_multiset)
                multiset_hash = hashlib.sha256(
                    json.dumps(
                        {
                            "capacity": capacity,
                            "sorted_items": ordered_multiset.tolist(),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                for order_variant, items in (
                    ("random", random_order),
                    ("alternating_extremes", alternating_extremes),
                ):
                    order_payload = {
                        "capacity": capacity,
                        "items": items.tolist(),
                    }
                    order_hash = hashlib.sha256(
                        json.dumps(
                            order_payload, sort_keys=True, separators=(",", ":")
                        ).encode("utf-8")
                    ).hexdigest()
                    instance_hash = hashlib.sha256(
                        json.dumps(
                            {
                                "problem": "bp_online",
                                "capacity": capacity,
                                "regime_id": regime_id,
                                "multiset_id": str(multiset_index),
                                "order_variant": order_variant,
                                "items": items.tolist(),
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest()
                    instance_id = f"{multiset_index}-{order_variant}"
                    dataset[instance_id] = {
                        "items": items.tolist(),
                        "capacity": capacity,
                        "num_items": len(items),
                        "regime_id": regime_id,
                        "multiset_id": str(multiset_index),
                        "order_variant": order_variant,
                        "large_item_count": large_item_count,
                        "large_item_fraction": large_item_fraction,
                        "multiset_hash": multiset_hash,
                        "order_hash": order_hash,
                        "instance_hash": instance_hash,
                    }
                    lower_bound_sum += np.ceil(items.sum() / capacity)
            instances[dataset_name] = dataset
            lower_bounds[dataset_name] = round(
                lower_bound_sum / len(dataset), 4
            )
        return instances, lower_bounds

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

    @staticmethod
    def _gen_fme_held_out(
        capacity: int = 100, profile: str = "fme_unseen_v1"
    ) -> list:
        """候选冻结后才生成的预注册 held-out 分布，不参与进化反馈。"""
        if profile == "fme_unseen_v2":
            return BPONLINEBroad._gen_fme_held_out_v2(capacity)
        if profile != "fme_unseen_v1":
            raise ValueError(f"unknown FME held-out profile: {profile}")

        suites = []

        mixture_instances = []
        for instance_index in range(8):
            rng = np.random.default_rng(71000 + instance_index)
            small = rng.integers(1, 36, size=2048)
            large = rng.integers(55, capacity + 1, size=2048)
            items = np.concatenate([small, large])
            rng.shuffle(items)
            mixture_instances.append(items)
        suites.append(
            {
                "path": "runtime://fme-heldout/v1/unseen_mixture",
                "instances": mixture_instances,
            }
        )

        scale_instances = []
        for instance_index in range(6):
            rng = np.random.default_rng(72000 + instance_index)
            scale_instances.append(
                rng.integers(1, capacity + 1, size=8192).astype(np.float64)
            )
        suites.append(
            {
                "path": "runtime://fme-heldout/v1/unseen_scale",
                "instances": scale_instances,
            }
        )

        order_instances = []
        for instance_index in range(3):
            rng = np.random.default_rng(73000 + instance_index)
            base = rng.integers(1, capacity + 1, size=4096).astype(np.float64)
            order_instances.extend([np.sort(base), np.sort(base)[::-1].copy()])
        suites.append(
            {
                "path": "runtime://fme-heldout/v1/order_perturbation",
                "instances": order_instances,
            }
        )
        return suites

    @staticmethod
    def _gen_fme_held_out_v2(capacity: int = 100) -> list:
        """生成与 v1、开发 v2 均不重合的二阶段确认套件。"""
        suites = []

        trimodal_instances = []
        for instance_index in range(6):
            rng = np.random.default_rng(91000 + instance_index)
            small = rng.integers(1, 26, size=2048)
            medium = rng.integers(35, 66, size=2048)
            large = rng.integers(75, capacity + 1, size=2048)
            items = np.concatenate([small, medium, large])
            rng.shuffle(items)
            trimodal_instances.append(items.astype(np.float64))
        suites.append(
            {
                "path": "runtime://fme-heldout/v2/unseen_trimodal",
                "instances": trimodal_instances,
            }
        )

        scale_instances = []
        for instance_index in range(4):
            rng = np.random.default_rng(92000 + instance_index)
            scale_instances.append(
                rng.integers(1, capacity + 1, size=12288).astype(np.float64)
            )
        suites.append(
            {
                "path": "runtime://fme-heldout/v2/unseen_scale_12k",
                "instances": scale_instances,
            }
        )

        random_order_instances = []
        quantile_block_instances = []
        for instance_index in range(4):
            rng = np.random.default_rng(93000 + instance_index)
            random_order = rng.integers(1, capacity + 1, size=4096)
            ordered = np.sort(random_order)
            blocks = np.split(ordered, 16)
            block_order = rng.permutation(len(blocks))
            quantile_block_order = np.concatenate(
                [blocks[index] for index in block_order]
            )
            random_order_instances.append(random_order.astype(np.float64))
            quantile_block_instances.append(
                quantile_block_order.astype(np.float64)
            )
        suites.extend(
            [
                {
                    "path": "runtime://fme-heldout/v2/order_random",
                    "instances": random_order_instances,
                },
                {
                    "path": "runtime://fme-heldout/v2/order_quantile_blocks",
                    "instances": quantile_block_instances,
                },
            ]
        )
        return suites

    def evaluate_program(self, program_str: str, callable_func) -> float | dict | None:
        if self.confirmation_feedback:
            fitness, scale_feedback = self._evaluate_with_confirmation_feedback(callable_func)
            evaluation_result = {"objective": fitness, "feedback": scale_feedback}
        elif self.structured_feedback:
            candidate_id = None
            if self.training_profile == "fme_dev_order_regime_feedback_v1":
                candidate_id = hashlib.sha256(
                    program_str.encode("utf-8")
                ).hexdigest()
            fitness, scale_feedback = self._evaluate_with_scale_feedback(
                callable_func, candidate_id=candidate_id
            )
            evaluation_result = {"objective": fitness, "feedback": scale_feedback}
        else:
            fitness = super().evaluate_program(program_str, callable_func)
            evaluation_result = fitness
        if not self.report_held_out:
            return evaluation_result

        if self.held_out_profile in {"fme_unseen_v1", "fme_unseen_v2"} and not self.held_out_data:
            # 延迟生成确保正式候选冻结前，进化进程既不计算也不读取 held-out。
            self.held_out_data = self._gen_fme_held_out(
                profile=self.held_out_profile
            )
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
                aggregate_gap = round((mean_used - mean_lb) / mean_lb * 100, 6)
                if self.held_out_profile in {"fme_unseen_v1", "fme_unseen_v2"}:
                    instance_gap_pct = [
                        round((used - lower_bound) / lower_bound * 100.0, 6)
                        for used, lower_bound in zip(
                            [-value for value in used_list], lb_list
                        )
                    ]
                    self.held_out_report[entry["path"]] = {
                        "mean_gap_pct": aggregate_gap,
                        "instance_gap_pct": instance_gap_pct,
                        "instance_count": len(instance_gap_pct),
                    }
                else:
                    self.held_out_report[entry["path"]] = round(aggregate_gap, 3)
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

    def _evaluate_with_scale_feedback(self, callable_func, candidate_id: str | None = None):
        """返回聚合目标和各尺度 gap，供 scale_aware 提示定位最差尺度。"""
        if self.training_profile == "fme_dev_order_regime_feedback_v1":
            if not candidate_id:
                raise ValueError("order-regime feedback requires a candidate code hash")
            return self._evaluate_with_order_regime_feedback(
                callable_func, candidate_id
            )
        if self.training_profile in {
            "fme_dev_distributions_v1",
            "fme_dev_distribution_order_v2",
        }:
            return self._evaluate_with_fme_feedback(callable_func)
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

    def _evaluate_with_order_regime_feedback(self, callable_func, candidate_id: str):
        """把隔离开发实例转为轻量观察，再委托深 Module 编译反馈。"""
        from eoh_rag.fme.order_regime_feedback import (
            DEVELOPMENT_SUITE,
            OrderPairObservation,
            OrderRegimeFeedbackAdapter,
        )

        observations = []
        objective_gaps = []
        for dataset in self.instances.values():
            for instance in dataset.values():
                capacity = int(instance["capacity"])
                items = np.array(instance["items"])
                bins = np.array([capacity] * instance["num_items"])
                _, bins_packed = self.online_binpack(items, bins, callable_func)
                used_bins = int((bins_packed != capacity).sum())
                lower_bound = float(np.ceil(np.sum(items) / capacity))
                gap = (used_bins - lower_bound) / lower_bound
                objective_gaps.append(float(gap))
                observations.append(
                    OrderPairObservation(
                        candidate_id=candidate_id,
                        development_suite=DEVELOPMENT_SUITE,
                        regime_id=str(instance["regime_id"]),
                        multiset_id=str(instance["multiset_id"]),
                        order_variant=str(instance["order_variant"]),
                        capacity=capacity,
                        item_count=int(instance["num_items"]),
                        large_item_count=int(instance["large_item_count"]),
                        large_item_fraction=float(instance["large_item_fraction"]),
                        multiset_hash=str(instance["multiset_hash"]),
                        order_hash=str(instance["order_hash"]),
                        instance_hash=str(instance["instance_hash"]),
                        relative_gap_pct=float(gap * 100.0),
                        valid=True,
                    )
                )
        summary = OrderRegimeFeedbackAdapter().compile(observations)
        # 标量适应度仍是全部 12 个开发实例的均值；新的信息只进入反馈字段，
        # 不会改变候选函数可见输入或既有 FME v2 的目标定义。
        return float(np.mean(objective_gaps)), summary.to_feedback()

    def _evaluate_with_fme_feedback(self, callable_func):
        """在冻结开发反例上形成行为画像，不读取 confirmation 或 held-out。"""
        order_sensitive_profile = (
            self.training_profile == "fme_dev_distribution_order_v2"
        )
        distribution_gaps = {}
        order_variant_gaps = {}
        order_pair_gaps = {}
        distinguishing_counterexamples = []
        counterexample_gap_pct = {}
        counterexample_artifacts = {}
        all_dataset_gaps = []
        for dataset_name, dataset in self.instances.items():
            prefix = "fme_dev_v2_" if order_sensitive_profile else "fme_dev_"
            distribution = dataset_name.removeprefix(prefix)
            instance_gaps = []
            for instance_id, instance in dataset.items():
                capacity = instance["capacity"]
                items = np.array(instance["items"])
                bins = np.array([capacity] * instance["num_items"])
                _, bins_packed = self.online_binpack(items, bins, callable_func)
                used_bins = int((bins_packed != capacity).sum())
                lower_bound = float(np.ceil(np.sum(items) / capacity))
                gap = (used_bins - lower_bound) / lower_bound
                instance_gaps.append((instance_id, float(gap)))
                counterexample_prefix = (
                    "bp-dev-v2" if order_sensitive_profile else "bp-dev"
                )
                counterexample_id = (
                    f"{counterexample_prefix}-{distribution}-{instance_id}"
                )
                order_variant = instance.get("order_variant")
                multiset_id = instance.get("multiset_id")
                if order_sensitive_profile:
                    pair_key = f"{distribution}:{multiset_id}"
                    order_pair_gaps.setdefault(pair_key, {})[
                        str(order_variant)
                    ] = float(gap)
                    order_variant_gaps.setdefault(str(order_variant), []).append(
                        float(gap)
                    )
                instance_payload = {
                    "problem": "bp_online",
                    "distribution": distribution,
                    "capacity": capacity,
                    "items": instance["items"],
                }
                if order_sensitive_profile:
                    instance_payload.update(
                        {
                            "multiset_id": multiset_id,
                            "order_variant": order_variant,
                        }
                    )
                instance_hash = hashlib.sha256(
                    json.dumps(
                        instance_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                counterexample_gap_pct[counterexample_id] = round(gap * 100.0, 6)
                counterexample_artifacts[counterexample_id] = {
                    "source_distribution": distribution,
                    "feature_region": (
                        f"{distribution}:order={order_variant}:n{instance['num_items']}:c{capacity}"
                        if order_sensitive_profile
                        else f"{distribution}:n{instance['num_items']}:c{capacity}"
                    ),
                    "instance_hash": instance_hash,
                    "instance_ref": f"runtime://fme/bp/{counterexample_id}",
                    "generation_method": (
                        "frozen_distribution_order_pair_sampler_v2"
                        if order_sensitive_profile
                        else "frozen_distribution_sampler_v1"
                    ),
                }
            mean_gap = float(np.mean([gap for _, gap in instance_gaps]))
            distribution_gaps[distribution] = round(mean_gap * 100.0, 6)
            all_dataset_gaps.append(mean_gap)
            worst_instance_id, _ = max(instance_gaps, key=lambda item: item[1])
            distinguishing_counterexamples.append(
                f"{'bp-dev-v2' if order_sensitive_profile else 'bp-dev'}-{distribution}-{worst_instance_id}"
            )

        worst_distribution = max(distribution_gaps, key=distribution_gaps.get)
        profile_payload = {
            "problem": "bp_online",
            "per_distribution_relative_gap": distribution_gaps,
            "feature_sensitivity": max(distribution_gaps.values())
            - min(distribution_gaps.values()),
            "distinguishing_counterexample_ids": distinguishing_counterexamples,
        }
        if order_sensitive_profile:
            per_order_variant_relative_gap = {
                order_variant: round(float(np.mean(gaps)) * 100.0, 6)
                for order_variant, gaps in order_variant_gaps.items()
            }
            pair_order_sensitivity_pct = {
                pair_key: round(
                    (max(gaps.values()) - min(gaps.values())) * 100.0, 6
                )
                for pair_key, gaps in order_pair_gaps.items()
            }
            order_sensitivity_pct = max(pair_order_sensitivity_pct.values())
            profile_payload.update(
                {
                    "per_order_variant_relative_gap": per_order_variant_relative_gap,
                    "pair_order_sensitivity_pct": pair_order_sensitivity_pct,
                    "order_sensitivity_pct": order_sensitivity_pct,
                }
            )
        behavior_profile_hash = hashlib.sha256(
            json.dumps(
                profile_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        feedback = {
            "scale_gap_pct": distribution_gaps,
            "per_distribution_relative_gap": distribution_gaps,
            "worst_scale": worst_distribution,
            "worst_distribution": worst_distribution,
            "worst_gap_pct": distribution_gaps[worst_distribution],
            "feature_sensitivity": profile_payload["feature_sensitivity"],
            "distinguishing_counterexample_ids": distinguishing_counterexamples,
            "counterexample_gap_pct": counterexample_gap_pct,
            "counterexample_artifacts": counterexample_artifacts,
            "behavior_profile_hash": behavior_profile_hash,
            "visible_scope": "dev_only",
        }
        if order_sensitive_profile:
            feedback.update(
                {
                    "per_order_variant_relative_gap": profile_payload[
                        "per_order_variant_relative_gap"
                    ],
                    "pair_order_sensitivity_pct": profile_payload[
                        "pair_order_sensitivity_pct"
                    ],
                    "order_sensitivity_pct": profile_payload[
                        "order_sensitivity_pct"
                    ],
                    "behavior_profile_version": "bp_fme_distribution_order_v2",
                    "development_suite": "fme_development_distribution_order_v2",
                }
            )
        # 两臂共享同一标量适应度；FME 的差异只来自结构化证据与动作选择。
        return float(np.mean(all_dataset_gaps)), feedback
