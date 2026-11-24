"""The offline bin-packing ranking and repacking interface."""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from agent_skill_loop.problems.bpp_offline import pack_item_order

from .contracts import HookSpec
from .packing_adapters import BPP_PROTOCOL_ID, checked_packing_scores
from .templates import TemplateSpec, compute_template_source_sha256, register_template

BPP_TEMPLATE_ID = "bpp_offline_reorder_repack"
BPP_FFD_HOOK_CODE = """def rank_items(item_sizes, capacity):
    return item_sizes
"""


def run_bpp_offline_reorder_repack_v1(
    items: Sequence[float],
    capacity: float,
    rank_items: Callable[..., Any],
    *,
    postprocess_mode: str = "none",
    time_budget_ms: float | None = 500.0,
    template_options: Mapping[str, Any] | None = None,
    capture_merge_sequence: bool = False,
) -> tuple[list[list[int]] | None, dict[str, Any]]:
    if postprocess_mode not in {"none", "repack"}:
        raise ValueError("unsupported_postprocess_mode")
    started = time.perf_counter()
    deadline = math.inf if time_budget_ms is None else started + time_budget_ms / 1000.0
    item_sizes = np.frombuffer(np.asarray(items, dtype=np.float64).tobytes(), dtype=np.float64)
    meta: dict[str, Any] = {"hook_call_count": 0}
    order = None
    initial_bins = None
    bins = None
    if time.perf_counter() < deadline:
        hook_started = time.perf_counter()
        priorities = checked_packing_scores(rank_items(item_sizes, capacity), len(items))
        meta.update(hook_call_count=1, hook_ms=(time.perf_counter() - hook_started) * 1000.0)
        if time.perf_counter() < deadline:
            order = sorted(range(len(items)), key=priorities.__getitem__, reverse=True)
            initial_bins = pack_item_order(items, capacity, order, deadline=deadline)
            bins = initial_bins
            if initial_bins is not None and postprocess_mode == "repack":
                repack_started = time.perf_counter()
                repacked = pack_item_order(items, capacity, order, best_fit=True, deadline=deadline)
                meta["postprocess_ms"] = (time.perf_counter() - repack_started) * 1000.0
                if repacked is not None and len(repacked) < len(initial_bins):
                    bins = repacked

    exhausted = time.perf_counter() >= deadline
    meta.update(budget_exhausted=exhausted, stop_reason="solve_deadline" if exhausted else "completed")
    if capture_merge_sequence:
        meta.update(first_order=order, pre_repack_bins=initial_bins)
    return bins, meta


_HOOK_SPEC = HookSpec("rank_items", ("item_sizes", "capacity"), output_shape_arg="item_sizes")
register_template(TemplateSpec(
    template_id=BPP_TEMPLATE_ID,
    template_version="v1",
    problem_family="bpp",
    paradigm="reorder_repack",
    hook_name=_HOOK_SPEC.name,
    hook_signature=_HOOK_SPEC.signature,
    allowed_postprocess_modes=frozenset({"none", "repack"}),
    runner=run_bpp_offline_reorder_repack_v1,
    default_task_description=(
        "Rank the full read-only item size array using the bin capacity. Return one finite priority "
        "per original item. The runner packs items by decreasing priority, breaking ties by original "
        "index. Repacking mode tries best fit in the same order and keeps an improvement when available."
    ),
    default_template_program=BPP_FFD_HOOK_CODE,
    default_baseline_hook_code=BPP_FFD_HOOK_CODE,
    template_source_sha256=compute_template_source_sha256(
        run_bpp_offline_reorder_repack_v1, pack_item_order, checked_packing_scores,
    ),
    protocol_id=BPP_PROTOCOL_ID,
    hook_specs=(_HOOK_SPEC,),
))
