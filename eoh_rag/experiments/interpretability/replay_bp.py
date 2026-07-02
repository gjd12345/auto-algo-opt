"""
模块：replay_bp（在线装箱最优代码复现验证）
功能：把演化得到的最优打分函数重跑一遍，验证它报告的目标值是真实可信的，而不是钻了评测器的空子。
职责：编译打分函数、模拟在线装箱过程、生成 Weibull 分布的物品序列、跨多个随机种子统计目标值分布与异常计数。
接口：
  - make_score_fn() -> 打分函数：编译内置的最优打分代码并返回可调用对象。
  - simulate_bp_online(score_fn, items, capacity=100) -> dict：跑一趟在线装箱，返回目标值与统计信息。
  - generate_weibull_items(n=5000, shape=3.0, scale=45.0, capacity=100, seed=42) -> list：生成一批物品尺寸。
  - run_replay(n_seeds=20) -> dict：用多个种子重跑并汇总统计结果。
输入：无外部文件依赖；仅依赖 numpy；随机性由传入的 seed 控制。
输出：控制台打印目标值均值/范围/异常计数；并把完整汇总写入 evidence/bp_interpretability/replay_results.json。
示例：
  python replay_bp.py            # 用 20 个种子复现并保存结果
"""

import json
import numpy as np
from pathlib import Path


# 待验证的最优打分函数源码（字符串形式），运行时会被 exec 编译成真正的函数。
# 打分逻辑：对每个候选箱子，用"放入后的空间利用率"减去"剩余空间过大时的惩罚"作为分数，分数越高越优先放入。
#   - residual：放入该物品后箱子的剩余容量
#   - utilization：利用率项，剩余越小、越贴合，分数越高
#   - penalty：当剩余容量落在 (0, 2*item) 区间时施加的惩罚，避免留下不上不下的碎片空间
BEST_CODE = """
def score(item: int, bins: np.ndarray) -> np.ndarray:
    residual = bins - item
    utilization = np.exp(item / (residual + item + 1e-9))
    penalty = np.where((residual > 0) & (residual < 2 * item), (residual - item) ** 2 / (item + 1e-9), 0)
    return utilization - penalty
"""


def make_score_fn():
    """编译内置的最优打分代码并返回可调用的打分函数。

    做法是用一个仅暴露 numpy 的命名空间执行 BEST_CODE，再取出其中定义的 score。
    返回值：签名为 score(item, bins) 的函数，给每个候选箱子打分。
    """
    ns = {"np": np}  # 受控命名空间，只把 numpy 注入进去
    exec(BEST_CODE, ns)  # 执行源码字符串，score 会被定义到 ns 里
    return ns["score"]


def simulate_bp_online(score_fn, items, capacity=100):
    """用给定的打分函数模拟一趟在线装箱，并统计结果质量。

    在线装箱：物品逐个到达，只能立即决定放进哪个已开的箱子或新开一个箱子，不能回头调整。
    关键参数：
      - score_fn：打分函数，对当前物品给每个可行箱子打分，取分数最高者放入。
      - items：物品尺寸序列。
      - capacity：单个箱子的容量。
    返回值：dict，包含目标值 objective（waste_ratio，浪费率，越小越好）、
    使用箱数 bins_used，以及 NaN/Inf/溢出等异常计数，用于检查是否钻了评测器空子。
    """
    bins = []  # 每个元素记录一个已开箱子的剩余容量
    invalid_placements = 0
    overflow_count = 0
    nan_count = 0
    inf_count = 0

    for item in items:
        if not bins:
            # 还没有任何箱子时，直接开一个新箱子放入
            bins.append(capacity - item)
            continue

        bins_arr = np.array(bins, dtype=np.float64)
        feasible_mask = bins_arr >= item  # 剩余容量放得下当前物品的箱子
        feasible_indices = np.where(feasible_mask)[0]

        if len(feasible_indices) == 0:
            # 没有任何已开箱子放得下，只能新开一个
            bins.append(capacity - item)
            continue

        feasible_bins = bins_arr[feasible_indices]
        scores = score_fn(item, feasible_bins)  # 只给可行箱子打分

        # 健壮性检查：打分函数可能返回 NaN/Inf，替换成极端有限值以免 argmax 出错
        if np.any(np.isnan(scores)):
            nan_count += 1
            scores = np.nan_to_num(scores, nan=-1e18)
        if np.any(np.isinf(scores)):
            inf_count += 1
            scores = np.nan_to_num(scores, posinf=1e18, neginf=-1e18)

        best_idx = feasible_indices[np.argmax(scores)]  # 选分数最高的可行箱子
        bins[best_idx] -= item  # 放入后更新该箱子剩余容量

        if bins[best_idx] < 0:
            # 剩余容量变为负数说明超出容量，记为非法放置（正常逻辑不应发生）
            overflow_count += 1
            invalid_placements += 1

    # 浪费率 = 总空余容量 / 总容量；用到的箱子越少、越装满，浪费率越低
    total_capacity = len(bins) * capacity
    total_items = sum(items)
    waste = total_capacity - total_items
    waste_ratio = waste / total_capacity if total_capacity > 0 else 0

    return {
        "objective": round(waste_ratio, 8),
        "bins_used": len(bins),
        "total_items_placed": len(items),
        "waste_ratio": waste_ratio,
        "invalid_placements": invalid_placements,
        "overflow_count": overflow_count,
        "nan_count": nan_count,
        "inf_count": inf_count,
    }


def generate_weibull_items(n=5000, shape=3.0, scale=45.0, capacity=100, seed=42):
    """按 Weibull 分布生成一批物品尺寸，作为标准装箱基准的输入。

    关键参数：n 物品数量；shape/scale 是 Weibull 分布的形状与尺度参数；
    capacity 用于把尺寸上限截断到容量；seed 控制随机性以便复现。
    返回值：整数尺寸列表，每个尺寸落在 [1, capacity] 区间。
    """
    rng = np.random.default_rng(seed)
    raw = rng.weibull(shape, size=n) * scale
    # 取整并裁剪到 [1, capacity]，保证尺寸合法（至少为 1，不超过箱容）
    items = np.clip(np.round(raw).astype(int), 1, capacity)
    return items.tolist()


def run_replay(n_seeds=20):
    """在多个随机种子上重复复现，汇总目标值分布与异常计数。

    对 0..n_seeds-1 每个种子各生成一批物品并模拟一趟装箱，收集所有目标值后
    计算均值/标准差/最值/中位数，同时累加各类异常计数。
    返回值：dict 汇总结果，含逐种子的完整明细 all_results。
    """
    score_fn = make_score_fn()
    results = []

    for seed in range(n_seeds):
        # 每个种子对应一批不同的物品序列，逐个模拟
        items = generate_weibull_items(seed=seed)
        result = simulate_bp_online(score_fn, items)
        result["seed"] = seed
        results.append(result)

    objectives = [r["objective"] for r in results]  # 各种子的目标值（浪费率）
    summary = {
        "n_seeds": n_seeds,
        "mean_objective": round(np.mean(objectives), 8),
        "std_objective": round(np.std(objectives), 8),
        "min_objective": round(np.min(objectives), 8),
        "max_objective": round(np.max(objectives), 8),
        "median_objective": round(np.median(objectives), 8),
        # 跨全部种子累计的异常计数，全为 0 才说明结果干净可信
        "total_invalid_placements": sum(r["invalid_placements"] for r in results),
        "total_overflow_count": sum(r["overflow_count"] for r in results),
        "total_nan_count": sum(r["nan_count"] for r in results),
        "total_inf_count": sum(r["inf_count"] for r in results),
        "all_results": results,
    }
    return summary


# 直接运行本脚本时：跑 20 个种子的复现，打印统计摘要，并把完整结果落盘为 JSON
if __name__ == "__main__":
    summary = run_replay(n_seeds=20)
    print(f"Mean: {summary['mean_objective']:.6f} ± {summary['std_objective']:.6f}")
    print(f"Range: [{summary['min_objective']:.6f}, {summary['max_objective']:.6f}]")
    print(f"Invalid: {summary['total_invalid_placements']}, Overflow: {summary['total_overflow_count']}")
    print(f"NaN: {summary['total_nan_count']}, Inf: {summary['total_inf_count']}")

    out = Path("evidence/bp_interpretability/replay_results.json")
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved to {out}")
