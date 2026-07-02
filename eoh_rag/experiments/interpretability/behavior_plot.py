"""Behavior plot: visualize score function across different item sizes.

Plots score vs (residual/item) to reveal the item-scaled residual shaping behavior.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path


def score(item, bins):
    residual = bins - item
    utilization = np.exp(item / (residual + item + 1e-9))
    penalty = np.where((residual > 0) & (residual < 2 * item), (residual - item) ** 2 / (item + 1e-9), 0)
    return utilization - penalty


def plot_behavior():
    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    item_sizes = [5, 10, 20, 40, 60, 80]

    for ax, item_size in zip(axes.flat, item_sizes):
        # bins with residual from 0 to 100 (after placing item)
        residuals = np.linspace(0.1, 100, 500)
        bins = residuals + item_size  # bins = residual + item

        scores = score(item_size, bins)

        # Normalize x-axis by item size
        x = residuals / item_size

        ax.plot(x, scores, 'b-', linewidth=2)
        ax.axvline(x=0, color='red', linestyle='--', alpha=0.5, label='residual=0')
        ax.axvline(x=1, color='green', linestyle='--', alpha=0.7, label='residual=item')
        ax.axvline(x=2, color='orange', linestyle='--', alpha=0.7, label='residual=2×item')

        # Mark penalty region
        ax.axvspan(0, 2, alpha=0.1, color='red', label='penalty zone')

        ax.set_title(f'item={item_size}', fontsize=12)
        ax.set_xlabel('residual / item')
        ax.set_ylabel('score')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)

    plt.suptitle('BP Online Evolved Heuristic: Item-Scaled Residual Shaping\nscore = exp(item/(residual+item)) - penalty(residual ∈ [0,2×item])',
                 fontsize=13, fontweight='bold')
    plt.tight_layout()

    out = Path('evidence/bp_interpretability/behavior_plot.png')
    plt.savefig(out, dpi=150, bbox_inches='tight')
    print(f'Saved: {out}')

    # Also save key observations
    observations = []
    for item_size in [10, 20, 40]:
        # Find score at key points
        r0 = score(item_size, np.array([item_size + 0.1]))[0]  # residual≈0 (tight fit)
        r_item = score(item_size, np.array([2 * item_size]))[0]  # residual=item
        r_2item = score(item_size, np.array([3 * item_size]))[0]  # residual=2*item
        r_large = score(item_size, np.array([item_size + 50]))[0]  # large residual
        observations.append({
            'item': item_size,
            'score_at_tight_fit': round(float(r0), 4),
            'score_at_residual_eq_item': round(float(r_item), 4),
            'score_at_residual_eq_2item': round(float(r_2item), 4),
            'score_at_large_residual': round(float(r_large), 4),
        })
        print(f'item={item_size}: tight={r0:.3f}, r=item:{r_item:.3f}, r=2item:{r_2item:.3f}, large:{r_large:.3f}')

    import json
    Path('evidence/bp_interpretability/behavior_observations.json').write_text(
        json.dumps(observations, indent=2))


if __name__ == '__main__':
    plot_behavior()
