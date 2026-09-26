"""Training-only restoration of island_605 BPONLINE (five Weibull streams).

Unlike obp_online, unopened bins are legal choices. Instance objectives are
contributions normalized by the frozen dataset mean L1, so their arithmetic
mean preserves the historical ratio-of-means fitness, including partial eval.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from agent_skill_loop.evidence import BehaviorTraceRecorder, ObservedCandidateError, ObserverFailure
from agent_skill_loop.problems.obp import suite_hash, validate_instances

PROBLEM_NAME = "bp_online_island605"
ASSET = Path(__file__).with_name("data") / "island605_bp_train.json"
BASELINE_CODE = "def score(item: int, bins: np.ndarray) -> np.ndarray:\n    return -bins\n"
TASK_DESCRIPTION = (
    "Design an online bin-packing score(item, bins) function. bins contains "
    "remaining capacities of ALL feasible bins, including unopened capacity-100 "
    "bins; you may choose a fresh bin even when an open bin fits. Return one "
    "finite numeric score per bin; first argmax wins. Input is read-only. "
    "Minimize mean bins used relative to mean L1 lower bound on the fixed "
    "historically exposed five-stream training suite (5000 items each)."
)
BEHAVIOR_CONTRACT = {
    "id": "island605-all-feasible-bin-selection/v1",
    "event": ["item_index", "selected_bin_id", "opened_new_bin"],
    "terminal": ["bins_used"], "scope": "frozen-training-suite",
}


def build_suite(seed=0, split="dev_train", count=5, size=5000):
    if split != "dev_train":
        raise ValueError("invalid_split")
    if count != 5 or size != 5000:
        raise ValueError("historical_suite_requires_count_5_size_5000")
    asset = json.loads(ASSET.read_text(encoding="utf-8"))
    instances = asset["instances"]
    return {"problem": PROBLEM_NAME, "split": split, "instances": instances,
            "content_hash": suite_hash(PROBLEM_NAME, split, instances)}


def validate_suite(suite):
    if suite.get("problem") != PROBLEM_NAME or suite.get("split") != "dev_train":
        raise ValueError("invalid_suite")
    frozen = build_suite()
    if suite.get("instances") != frozen["instances"] or suite.get("content_hash") != frozen["content_hash"]:
        raise ValueError("suite_hash_mismatch")
    validate_instances(suite["instances"])
    return suite["instances"], frozen["content_hash"]


def _observe(recorder, method, **kwargs):
    if recorder is not None:
        try:
            return getattr(recorder, method)(**kwargs)
        except Exception as exc:
            raise ObserverFailure("observer_" + method + "_failed") from exc


def _evaluate(fn, instances, recorder=None):
    objectives, raw_values, refs, gaps = [], [], [], []
    for instance_index, instance in enumerate(instances):
        capacity = instance["capacity"]
        # Preserve the original integer capacities, full array, and tie order.
        bins = np.full(len(instance["items"]), capacity, dtype=np.int64)
        _observe(recorder, "begin_instance", instance_id=instance["instance_id"], instance_index=instance_index)
        try:
            for item_index, item in enumerate(instance["items"]):
                valid = np.nonzero((bins - item) >= 0)[0]
                argument = bins[valid]
                original = argument.copy()
                values = np.asarray(fn(item, argument), dtype=float)
                if not np.array_equal(argument, original):
                    raise ValueError("candidate_mutated_input")
                if values.ndim != 1 or len(values) != len(valid) or not np.all(np.isfinite(values)):
                    raise ValueError("invalid_return")
                selected = int(valid[np.argmax(values)])
                opened = bool(bins[selected] == capacity)
                bins[selected] -= item
                _observe(recorder, "record", event={"item_index": item_index, "selected_bin_id": selected, "opened_new_bin": opened})
        except ObserverFailure:
            raise
        except Exception as exc:
            if recorder is not None:
                _observe(recorder, "finish_instance", status="partial", terminal={"bins_used": int(np.count_nonzero(bins != capacity))})
                evidence = _observe(recorder, "finalize", status="partial")
                raise ObservedCandidateError(exc, evidence) from exc
            raise
        used = int(np.count_nonzero(bins != capacity))
        reference = instance["reference_objective"]
        _observe(recorder, "finish_instance", status="complete", terminal={"bins_used": used})
        objectives.append((used - reference) / instance["dataset_mean_l1"])
        raw_values.append(used)
        refs.append(reference)
        gaps.append((used - reference) / reference)
    return objectives, {"raw_objectives": raw_values, "bins_used": raw_values,
        "reference_objectives": refs, "raw_instance_relative_gaps": gaps,
        "reference_kind": ["analytical_reference"] * len(instances),
        "fitness_definition": "mean(bins_used - instance_L1) / frozen_dataset_mean_L1",
        "instance_objective_definition": "(bins_used - instance_L1) / frozen_dataset_mean_L1"}


def evaluate_instances(fn, instances):
    return _evaluate(fn, instances)


def evaluate_with_behavior(fn, instances, suite_hash_value):
    recorder = BehaviorTraceRecorder(contract=BEHAVIOR_CONTRACT, suite_hash=suite_hash_value)
    objectives, metrics = _evaluate(fn, instances, recorder)
    return objectives, metrics, _observe(recorder, "finalize", status="complete")
