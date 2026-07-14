"""EOH 问题：在安全局部搜索原语上自动生成 TSP 控制器。"""

from __future__ import annotations

import sys
from pathlib import Path


# 通过仓库相对布局定位框架包，避免把本机绝对路径写进正式运行逻辑。
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

EOH_SRC = REPO_ROOT / "official_eoh" / "eoh" / "src"
if str(EOH_SRC) not in sys.path:
    sys.path.insert(0, str(EOH_SRC))

from eoh import BaseProblem  # noqa: E402
from eoh_rag.search_control.tsp_controller import (  # noqa: E402
    MAX_TOTAL_BUDGET,
    build_controller_suite,
    evaluate_controller,
)


class TSPSEARCHCONTROLLER(BaseProblem):
    """只进化调度策略，底层搜索实现保持冻结。"""

    template_program = '''
def build_search_plan(problem_size: int, total_budget: int) -> list:
    """Return [(primitive, budget, minimum_relative_gain), ...]."""
    return [("two_opt", 20, 0.0), ("relocate", 10, 0.0), ("three_opt", 4, 0.0)]
'''
    task_description = (
        "Design a size-aware controller for TSP local search. Return a non-empty list with at most five "
        "(primitive, budget, minimum_relative_gain) tuples. Primitive must be one of 'two_opt', "
        "'relocate', 'or_opt_2', or 'three_opt'. Budget must be an integer from 1 to 24. The weighted "
        "total uses costs 1, 2, 3, and 5 respectively and must not exceed total_budget. "
        "minimum_relative_gain must be between 0 and 0.05 and stops later steps when the current step "
        "improves less than that value. Focus on route quality while avoiding wasteful steps."
    )

    def __init__(self, timeout: int = 120, n_processes: int = 1):
        super().__init__(timeout=timeout, n_processes=n_processes)
        self.dev_suite = build_controller_suite("synthetic_dev_v1")
        self.confirm_suite = build_controller_suite("synthetic_confirm_v1")
        self.report_held_out = False
        self.held_out_report: dict = {}

    def evaluate_program(self, program_str: str, callable_func) -> float | None:
        del program_str
        suite = self.confirm_suite if self.report_held_out else self.dev_suite
        summary = evaluate_controller(callable_func, suite)
        if self.report_held_out:
            # held-out 只在最终候选冻结后由 runner 开启，不参与进化反馈。
            self.held_out_report = {
                "suite": "synthetic_confirm_v1",
                "controller_confirm_objective": summary["objective"],
                "controller_confirm_mean_normalized_cost": summary["mean_normalized_cost"],
                "controller_confirm_mean_improvement_pct": summary["mean_improvement_pct"],
                "controller_confirm_valid_instances": summary["valid_instances"],
                "controller_confirm_instance_count": summary["instance_count"],
                "instance_results": summary["instance_results"],
            }
        return float(summary["objective"])
