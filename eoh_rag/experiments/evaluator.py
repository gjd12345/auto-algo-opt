"""
模块：evaluator —— 单次 run 结果的确定性评价器
功能：给一次 run 的 objective 打分，得到 {improvement, passed, decision} 三元组。
      是"是否值得存 card / 是否要 archive / 是否 escalate"这些决策的唯一入口。
职责：
  - 计算 improvement = (baseline - objective) / |baseline|
  - 判断是否达到 target_improvement 门槛（默认 0.05 = +5%）
  - 输出决策 archive / continue / adjust / escalate（详见 EVALUATOR_SPEC.md）
不负责：
  - 从磁盘读 run 结果（那是 batch_runner / RunTracker 的事）
  - 触发 archive/escalate 的副作用（由调用方按 decision 做）

主要调用方：batch_runner 的 hooks、rag.card_synthesis、report 脚本。

接口：
    def evaluate_run(
        problem: str,
        objective: float,
        baseline: float | None = None,
        target_improvement: float = 0.05,
    ) -> dict

输入：problem, objective (最小化)；可选覆盖 baseline / target_improvement。
输出：dict = {
    "problem": str,
    "objective": float,
    "baseline": float | None,
    "improvement": float,      # (baseline - obj) / |baseline|；无 baseline 时为 0.0
    "target": float,           # target_improvement
    "passed": bool,            # improvement >= target
    "decision": str,           # archive / continue / adjust / escalate
    "reason": str,             # 人类可读原因
}

示例：
    from eoh_rag.experiments.evaluator import evaluate_run
    r = evaluate_run("bp_online", 0.00674)
    # r["improvement"] ≈ 0.831, passed=True, decision="archive"
"""

from __future__ import annotations

from typing import Any

from eoh_rag.experiments.baselines import get_baseline


def evaluate_run(
    problem: str,
    objective: float,
    baseline: float | None = None,
    target_improvement: float = 0.05,
) -> dict[str, Any]:
    """给一次 run 结果打分并给出决策。见模块头。"""
    if baseline is None:
        baseline = get_baseline(problem)

    if baseline is None:
        return {
            "problem": problem,
            "objective": objective,
            "baseline": None,
            "improvement": 0.0,
            "target": target_improvement,
            "passed": False,
            "decision": "escalate",
            "reason": f"unknown baseline for problem={problem!r}; refuse to evaluate",
        }

    if objective is None or _is_bad_float(objective):
        return {
            "problem": problem,
            "objective": objective,
            "baseline": baseline,
            "improvement": 0.0,
            "target": target_improvement,
            "passed": False,
            "decision": "adjust",
            "reason": "objective missing or non-finite; likely evaluation failure",
        }

    improvement = (baseline - objective) / abs(baseline)
    passed = improvement >= target_improvement

    if passed:
        decision = "archive"
        reason = (
            f"improvement={improvement:.3f} >= target={target_improvement:.3f}; "
            f"eligible for archive/card"
        )
    elif improvement > 0:
        decision = "continue"
        reason = (
            f"improvement={improvement:.3f} > 0 but < target={target_improvement:.3f}; "
            f"keep evolving"
        )
    elif improvement == 0:
        decision = "continue"
        reason = "no change vs baseline; keep evolving"
    else:
        decision = "adjust"
        reason = (
            f"regressed: improvement={improvement:.3f} < 0 (obj={objective} vs "
            f"baseline={baseline}); tweak seed / operators"
        )

    return {
        "problem": problem,
        "objective": objective,
        "baseline": baseline,
        "improvement": improvement,
        "target": target_improvement,
        "passed": passed,
        "decision": decision,
        "reason": reason,
    }


def _is_bad_float(x: Any) -> bool:
    """objective 是 NaN/inf 时也视为失败。"""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return True
    return f != f or f == float("inf") or f == float("-inf")


__all__ = ["evaluate_run"]
