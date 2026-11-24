"""The online bin-packing priority interface."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

import numpy as np

from agent_skill_loop.cvrp_workbench.tsp_obp import run_obp_online_arrivals

from .contracts import HookSpec
from .packing_adapters import OBP_PROTOCOL_ID, checked_packing_scores
from .templates import TemplateSpec, compute_template_source_sha256, register_template

OBP_TEMPLATE_ID = "obp_online_priority"
OBP_BEST_FIT_HOOK_CODE = """def priority(current_item, feasible_remaining_capacities):
    return -feasible_remaining_capacities
"""
OBP_FIRST_FIT_HOOK_CODE = """def priority(current_item, feasible_remaining_capacities):
    return -np.arange(len(feasible_remaining_capacities))
"""


def run_obp_online_priority_v1(
    items: Iterable[float],
    capacity: float,
    priority: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
) -> tuple[list[int] | None, dict[str, Any]]:
    if postprocess_mode != "none":
        raise ValueError("unsupported_postprocess_mode")

    def score(item: float, spaces: np.ndarray) -> np.ndarray:
        return checked_packing_scores(priority(item, spaces), len(spaces))

    return run_obp_online_arrivals(
        items, capacity, score, solve_deadline_ms=time_budget_ms, capture_trace=capture_merge_sequence,
    )


_HOOK_SPEC = HookSpec("priority", ("current_item", "feasible_remaining_capacities"),
                      output_shape_arg="feasible_remaining_capacities")
register_template(TemplateSpec(
    template_id=OBP_TEMPLATE_ID,
    template_version="v1",
    problem_family="obp",
    paradigm="sequential_construct",
    hook_name=_HOOK_SPEC.name,
    hook_signature=_HOOK_SPEC.signature,
    allowed_postprocess_modes=frozenset({"none"}),
    runner=run_obp_online_priority_v1,
    default_task_description=(
        "Score the read-only array of feasible remaining capacities for the current arriving item. "
        "Return one finite priority per bin in opening order. The highest score wins and ties favor "
        "the earliest opened bin. When no bin fits, the runner opens one without calling the hook. "
        "Previous assignments are final."
    ),
    default_template_program=OBP_BEST_FIT_HOOK_CODE,
    default_baseline_hook_code=OBP_BEST_FIT_HOOK_CODE,
    template_source_sha256=compute_template_source_sha256(
        run_obp_online_priority_v1, run_obp_online_arrivals, checked_packing_scores,
    ),
    protocol_id=OBP_PROTOCOL_ID,
    hook_specs=(_HOOK_SPEC,),
))
