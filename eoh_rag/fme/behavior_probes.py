"""Small, frozen CVRP behavior panels for RQ1b.

The panel deliberately contains no target choice: a forecast is compared with
the candidate's actual choice after the forecast has been durably recorded.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from eoh_rag.fme.pilot_evaluation import build_suite, _suite_hash

ROOT = Path(__file__).resolve().parents[2]
_FAMILY_OFFSETS = {"clustered_far": 101, "capacity_tight": 211, "radial_mixed": 307}
TARGET_DESCRIPTIONS = {
    "clustered_far": "capacity=40; depot=[0.5,0.5]; equal-sized clusters centered at [0.15,0.15] and [0.85,0.85] with independent uniform coordinate jitter +/-0.045; integer demands uniform1..9; random node permutation",
    "capacity_tight": "capacity=40; depot=[0.5,0.5]; uniform [0,1]^2 customers; each instance includes demands16 and30; other integer demands uniform4..9; random node permutation",
    "radial_mixed": "capacity=40; depot=[0.5,0.5]; alternating radii0.12 and0.42 with uniform jitter+/-0.025 and independent uniform angles; integer demands uniform1..9; random node permutation",
}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _matrix(points: list[list[float]]) -> list[list[float]]:
    a = np.asarray(points, dtype=float)
    d = a[:, None, :] - a[None, :, :]
    return np.round(np.sqrt(np.sum(d * d, axis=2)), 6).tolist()


def _state(rng: random.Random, family: str, ordinal: int) -> dict[str, Any]:
    # Five customers plus depot.  Generate a legal prefix, then expose the
    # resulting state; the prefix is provenance, not an input to the candidate.
    depot = [0.5, 0.5]
    if family == "distance_depot_conflict":
        customers = [[0.10, 0.50], [0.16, 0.50], [0.49, 0.52], [0.88, 0.12], [0.88, 0.88]]
        demands = [4, 4, 4, 4, 4]
        prefix = [0, 1]
    elif family == "capacity_pressure":
        customers = [[0.48, 0.49], [0.54, 0.50], [0.20, 0.20], [0.80, 0.80], [0.20, 0.80]]
        demands = [9, 16, 30, 4, 4]
        prefix = [0, 3]
    else:  # route closure: depot is materially attractive from current node.
        customers = [[0.50, 0.51], [0.08, 0.08], [0.90, 0.90], [0.10, 0.90], [0.90, 0.10]]
        demands = [5, 5, 5, 5, 5]
        prefix = [0, 1]
    # Tiny deterministic jitter avoids duplicate distances while retaining the
    # intended family geometry; all values remain in [0, 1].
    customers = [[round(min(0.99, max(0.01, x + (rng.random() - .5) * .004)), 8),
                  round(min(0.99, max(0.01, y + (rng.random() - .5) * .004)), 8)] for x, y in customers]
    permutation = list(range(1, 6))
    rng.shuffle(permutation)
    ordered = [customers[i - 1] for i in permutation]
    ordered_demands = [demands[i - 1] for i in permutation]
    points = [depot] + ordered
    matrix = _matrix(points)
    current = permutation.index(prefix[1]) + 1
    visited = {0, current}
    capacity = 40.0
    remaining = capacity - float(ordered_demands[current - 1])
    feasible = [i for i in range(1, 6) if i not in visited and ordered_demands[i - 1] <= remaining]
    if not feasible:
        # This is defensive only; all current fixtures are designed feasible.
        current, visited, remaining = 0, {0}, capacity
        feasible = [i for i in range(1, 6) if ordered_demands[i - 1] <= remaining]
    return {
        "state_id": f"{family}-{ordinal}", "family": family, "current_node": current,
        "depot": 0, "unvisited_nodes": sorted(feasible), "rest_capacity": remaining,
        "demands": [0] + ordered_demands, "distance_matrix": matrix,
        "capacity": capacity, "coordinates": points,
        "reachability": {"prefix_nodes": [0, current], "prefix_is_legal": True,
                          "intervention": "independent_state_after_legal_prefix",
                          "node_permutation": permutation},
    }


def build_probe_panel(seed: int, attempt: int) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int) or isinstance(attempt, bool) or not isinstance(attempt, int):
        raise ValueError("invalid_probe_coordinate")
    families = ("distance_depot_conflict", "capacity_pressure", "route_closure")
    rng = random.Random(seed ^ 0xB17B1E ^ (attempt * 0x9E3779B1))
    states = [_state(rng, family, ordinal) for family in families for ordinal in (0, 1)]
    panel = {"schema_version": "rq1b-cvrp-behavior-panel/v1", "seed": seed, "attempt": attempt, "states": states}
    panel["content_hash"] = _digest(panel)
    return panel


def build_target_suites(seed: int, split: str, count_per_family: int = 2, size: int = 24) -> dict[str, dict[str, Any]]:
    if split not in {"dev_train", "dev_probe", "heldout", "dev"} or count_per_family < 1:
        raise ValueError("invalid_target_suite_request")
    result = {}
    for family, offset in _FAMILY_OFFSETS.items():
        suite = build_suite("cvrp_construct", seed + offset, split, count=count_per_family, size=size)
        split_offset={'dev_train':0x031711,'dev_probe':0x1A8251,'heldout':0x917355,'dev':0x031711}[split]
        rng=random.Random(seed+offset+split_offset)
        for instance in suite["instances"]:
            instance['capacity']=40
            instance['depot']=[0.5,0.5]
            if family == "clustered_far":
                instance['customer_coordinates']=[[round((0.15 if k<size//2 else 0.85)+rng.uniform(-0.045,0.045),8) for _ in range(2)] for k in range(size)]
                instance['demands']=[rng.randint(1,9) for _ in range(size)]
            elif family == "capacity_tight":
                instance['customer_coordinates']=[[round(rng.random(),8),round(rng.random(),8)] for _ in range(size)]
                instance['demands']=[16,30]+[rng.randint(4,9) for _ in range(size-2)]
            else:
                points=[]
                for k in range(size):
                    radius=(0.12 if k%2==0 else 0.42)+rng.uniform(-0.025,0.025)
                    angle=rng.uniform(0,2*math.pi)
                    points.append([round(0.5+radius*math.cos(angle),8),round(0.5+radius*math.sin(angle),8)])
                instance['customer_coordinates']=points
                instance['demands']=[rng.randint(1,9) for _ in range(size)]
            order=list(range(size)); rng.shuffle(order)
            instance['customer_coordinates']=[instance['customer_coordinates'][i] for i in order]
            instance['demands']=[instance['demands'][i] for i in order]
        suite["content_hash"] = _suite_hash("cvrp_construct", split, suite["instances"])
        result[family] = suite
    return result


def execute_behavior(code: str, panel: Mapping[str, Any], timeout: float = 20.0) -> dict[str, Any]:
    started = time.monotonic()
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(float(timeout)) or timeout <= 0:
        return {"valid": False, "choices": {}, "state_results": [], "panel_hash": None, "error_code": "invalid_timeout", "elapsed_seconds": time.monotonic() - started}
    expected = panel.get("content_hash") if isinstance(panel, Mapping) else None
    check = dict(panel) if isinstance(panel, Mapping) else {}
    check.pop("content_hash", None)
    if not isinstance(expected, str) or _digest(check) != expected:
        return {"valid": False, "choices": {}, "state_results": [], "panel_hash": expected, "error_code": "panel_hash_mismatch", "elapsed_seconds": time.monotonic() - started}
    if not isinstance(code, str) or not isinstance(panel, Mapping) or not isinstance(panel.get("states"), list):
        return {"valid": False, "choices": {}, "state_results": [], "panel_hash": panel.get("content_hash") if isinstance(panel, Mapping) else None, "error_code": "invalid_request", "elapsed_seconds": time.monotonic() - started}
    worker = Path(__file__).resolve().parents[2] / "scripts" / "rq1b_probe_worker.py"
    request = {"code": code, "panel": dict(panel)}
    try:
        with tempfile.TemporaryDirectory(prefix="rq1b-probe-") as cwd:
            proc = subprocess.Popen([sys.executable, str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, cwd=cwd,
                env={k: v for k, v in os.environ.items() if k in {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}} | {"PYTHONPATH": str(ROOT)})
            try:
                out, _ = proc.communicate(json.dumps(request, separators=(",", ":")).encode(), timeout=float(timeout))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=1)
                return {"valid": False, "choices": {}, "state_results": [], "panel_hash": expected, "error_code": "timeout", "elapsed_seconds": time.monotonic() - started}
            result = json.loads(out.decode())
        if not isinstance(result, dict) or "state_results" not in result or "choices" not in result:
            raise ValueError
        ids = {str(s.get("state_id")) for s in panel["states"]}
        allowed_by_id = {str(s.get("state_id")): {0} | {int(n) for n in s.get("unvisited_nodes", [])} for s in panel["states"]}
        if not result.get('choices') and not result.get('state_results') and result.get('valid') is False:
            result.update(panel_hash=expected,elapsed_seconds=time.monotonic()-started)
            return result
        if result.get("panel_hash") != expected or set(result.get("choices", {})) != ids or len(result.get("state_results", [])) != len(ids) or not isinstance(result.get("valid"), bool) or any(v is not None and (isinstance(v, bool) or not isinstance(v, int) or v not in allowed_by_id[k]) for k, v in result.get("choices", {}).items()):
            raise ValueError
        state_rows={r['state_id']:r for r in result['state_results']}
        if set(state_rows)!=ids or any(not isinstance(r.get('valid'),bool) or r.get('choice')!=result['choices'][sid] or r['valid']!=(r['choice'] is not None) for sid,r in state_rows.items()) or result['valid']!=all(r['valid'] for r in state_rows.values()):
            raise ValueError
        result["panel_hash"] = expected
        result["elapsed_seconds"] = time.monotonic() - started
        return result
    except Exception:
        return {"valid": False, "choices": {}, "state_results": [], "panel_hash": panel.get("content_hash"), "error_code": "worker_protocol", "elapsed_seconds": time.monotonic() - started}


__all__ = ["build_probe_panel", "build_target_suites", "execute_behavior"]
