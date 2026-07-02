"""
模块：behavior_plot（在线装箱启发式打分行为可视化）
功能：把一个演化得到的在线装箱（Online Bin Packing）打分函数画成曲线，直观展示它随箱子剩余空间变化的行为。
职责：定义打分函数 score，并在不同物品体积下绘制「打分值 vs 归一化剩余空间」曲线，同时导出若干关键点的观测数值。
接口：
    - score(item, bins)：给定物品体积与各箱子当前容量，返回每个箱子的打分（数值越高越应优先放入）。
    - plot_behavior()：绘制多子图曲线并保存图片，同时把关键观测点写成 JSON。
输入：无外部参数；直接以脚本方式运行即可（内部使用固定的物品体积列表与剩余空间采样区间）。
输出：
    - evidence/bp_interpretability/behavior_plot.png（可视化图片）
    - evidence/bp_interpretability/behavior_observations.json（关键点打分观测）
示例：
    python behavior_plot.py
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path


def score(item, bins):
    """计算把一个物品放入各个箱子时的打分（分数越高越优先选择该箱子）。

    参数：
        item：待放入物品的体积（标量）。
        bins：各箱子当前的剩余容量（可为标量或 numpy 数组），逐元素计算。
    返回：
        与 bins 形状一致的打分，等于「利用率奖励」减去「剩余空间惩罚」。

    打分由两部分组成：
        - utilization：利用率奖励，物品占放入后所需空间的比例越大、越接近「刚好装满」，奖励越高。
        - penalty：当放入后剩余空间落在 (0, 2×item) 这一段「尴尬区间」时施加的惩罚，
          用于避免留下过小、难以再利用的碎片空间。
    """
    # residual：放入该物品后箱子会剩下的空间
    residual = bins - item
    # 利用率奖励：item 占「剩余 + 物品」的比例越大，指数值越高（1e-9 防止分母为 0）
    utilization = np.exp(item / (residual + item + 1e-9))
    # 仅在剩余空间处于 (0, 2×item) 的尴尬区间时施加惩罚，其余情况惩罚为 0
    penalty = np.where((residual > 0) & (residual < 2 * item), (residual - item) ** 2 / (item + 1e-9), 0)
    return utilization - penalty


def plot_behavior():
    """绘制打分函数在多种物品体积下的行为曲线，并导出关键观测点。

    对每个物品体积，扫描不同的箱子剩余空间，画出「打分值 vs 剩余空间/物品体积」曲线，
    并标注 residual=0、residual=item、residual=2×item 三条参考线以及惩罚区间。
    最终保存整幅图片，并把若干代表性物品体积在关键点上的打分写入 JSON，便于量化对比。
    """
    # 2 行 3 列共 6 个子图，每个子图对应一个物品体积
    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    item_sizes = [5, 10, 20, 40, 60, 80]

    for ax, item_size in zip(axes.flat, item_sizes):
        # 取放入物品后剩余空间从约 0 到 100 的 500 个采样点
        residuals = np.linspace(0.1, 100, 500)
        bins = residuals + item_size  # 箱子当前容量 = 放入后的剩余空间 + 物品体积

        scores = score(item_size, bins)

        # 横轴按物品体积归一化，使不同物品体积的曲线可横向对比
        x = residuals / item_size

        ax.plot(x, scores, 'b-', linewidth=2)
        ax.axvline(x=0, color='red', linestyle='--', alpha=0.5, label='residual=0')
        ax.axvline(x=1, color='green', linestyle='--', alpha=0.7, label='residual=item')
        ax.axvline(x=2, color='orange', linestyle='--', alpha=0.7, label='residual=2×item')

        # 用浅色阴影标出惩罚区间（归一化后为 0 到 2）
        ax.axvspan(0, 2, alpha=0.1, color='red', label='penalty zone')

        ax.set_title(f'item={item_size}', fontsize=12)
        ax.set_xlabel('residual / item')
        ax.set_ylabel('score')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

    plt.suptitle('BP Online Evolved Heuristic: Item-Scaled Residual Shaping\nscore = exp(item/(residual+item)) - penalty(residual ∈ [0,2×item])',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()

    # 保存整幅图片到证据目录
    out = Path('evidence/bp_interpretability/behavior_plot.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f'Saved: {out}')

    # 另外采集关键点的打分数值，形成可量化的观测记录
    observations = []
    for item_size in [10, 20, 40]:
        # 在四个代表性剩余空间上取打分值
        r0 = score(item_size, np.array([item_size + 0.1]))[0]  # 剩余空间≈0（几乎正好装满）
        r_item = score(item_size, np.array([2 * item_size]))[0]  # 剩余空间=物品体积
        r_2item = score(item_size, np.array([3 * item_size]))[0]  # 剩余空间=2×物品体积
        r_large = score(item_size, np.array([item_size + 50]))[0]  # 剩余空间较大
        observations.append({
            'item': item_size,
            'score_at_tight_fit': round(float(r0), 4),
            'score_at_residual_eq_item': round(float(r_item), 4),
            'score_at_residual_eq_2item': round(float(r_2item), 4),
            'score_at_large_residual': round(float(r_large), 4),
        })
        print(f'item={item_size}: tight={r0:.3f}, r=item:{r_item:.3f}, r=2item:{r_2item:.3f}, large:{r_large:.3f}')

    # 把观测记录写成 JSON 文件
    import json
    Path('evidence/bp_interpretability/behavior_observations.json').write_text(
        json.dumps(observations, indent=2))


if __name__ == '__main__':
    plot_behavior()
