"""
模块：baselines —— problem 目标值基线常量
功能：集中维护 problem → baseline 映射表，供 evaluator / card_synthesis
      / 报告脚本共用。任何"评价 obj 是否好"的判断都必须走这里。
职责：只维护 problem → baseline 映射表，以及一个统一的 get_baseline() 查询函数。
不负责：
  - 计算 objective（那是 Evaluator/official_eoh_run 的事）
  - 提升阈值（target_improvement 归 evaluator）
主要调用方：evaluator.py，rag.card_synthesis，报告/分析脚本。

接口：
    PROBLEM_BASELINES: dict[str, float]  # minimize 语义
    def get_baseline(problem: str) -> float | None

输入：problem 名称
输出：float baseline（越小越好）或 None（未知 problem 请显式处理）

示例：
    from eoh_rag.experiments.baselines import PROBLEM_BASELINES, get_baseline
    baseline = get_baseline("bp_online")   # -> 0.0398
    baseline = get_baseline("unknown")     # -> None
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 官方 EoH baseline —— 冻结常量，已核对 evidence
# ---------------------------------------------------------------------------
#   bp_online       0.0398   Online Bin Packing (Weibull, 1k items)
#   tsp_construct   6.560    TSP construct heuristic (n=100)
#   cvrp_construct  13.519   CVRP construct heuristic (n=200)
# ---------------------------------------------------------------------------
PROBLEM_BASELINES: dict[str, float] = {
    "bp_online": 0.0398,
    "tsp_construct": 6.560,
    "cvrp_construct": 13.519,
}


def get_baseline(problem: str) -> float | None:
    """返回 problem 的 baseline；未知 problem 返回 None。"""
    return PROBLEM_BASELINES.get(problem)


__all__ = ["PROBLEM_BASELINES", "get_baseline"]
