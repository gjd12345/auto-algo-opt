from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InstanceFeatures:
    problem: str
    request_count: int
    max_batch_request_count: int
    avg_batch_request_count: float
    full_request_count: int
    density_ratio: float
    vehicle_num: int
    vehicle_pressure: float
    avg_window_width: float
    min_window_width: float
    time_tightness: float
    time_interval: int
    difficulty: float


def _station_window_width(station: dict[str, Any]) -> float:
    return float(station.get("timeEnd", 0)) - float(station.get("timeStart", 0))


def extract_instance_features(
    json_path: str | Path,
    *,
    full_request_count: int = 15,
    time_interval: int = 1,
) -> InstanceFeatures:
    path = Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    batches = data.get("batch", [])
    request_count = 0
    batch_counts: list[int] = []
    widths: list[float] = []
    for batch in batches:
        ori = batch.get("ori", [])
        des = batch.get("des", [])
        batch_count = max(len(ori), len(des))
        batch_counts.append(batch_count)
        request_count += batch_count
        widths.extend(_station_window_width(item) for item in ori)
        widths.extend(_station_window_width(item) for item in des)

    max_batch_count = max(batch_counts) if batch_counts else 0
    avg_batch_count = sum(batch_counts) / len(batch_counts) if batch_counts else 0.0
    avg_width = sum(widths) / len(widths) if widths else 0.0
    min_width = min(widths) if widths else 0.0
    vehicle_num = int(data.get("vehicleNum", 0) or 0)
    density_ratio = max_batch_count / full_request_count if full_request_count else 0.0
    vehicle_pressure = request_count / vehicle_num if vehicle_num else 0.0

    # A simple normalized tightness score. Wider windows are easier; the time
    # interval acts as an explicit difficulty multiplier in our experiments.
    window_tightness = 1.0 / max(avg_width, 1.0)
    time_tightness = min(1.0, window_tightness * 120.0 * max(time_interval, 1))
    difficulty = (
        0.55 * min(density_ratio, 1.0)
        + 0.30 * time_tightness
        + 0.15 * min(vehicle_pressure, 1.0)
    )

    return InstanceFeatures(
        problem=path.name,
        request_count=request_count,
        max_batch_request_count=max_batch_count,
        avg_batch_request_count=avg_batch_count,
        full_request_count=full_request_count,
        density_ratio=density_ratio,
        vehicle_num=vehicle_num,
        vehicle_pressure=vehicle_pressure,
        avg_window_width=avg_width,
        min_window_width=min_width,
        time_tightness=time_tightness,
        time_interval=time_interval,
        difficulty=difficulty,
    )


def choose_strategy_family(features: InstanceFeatures) -> str:
    if features.time_interval >= 2:
        return "robust"
    if features.density_ratio <= 0.35:
        return "fast"
    if features.density_ratio <= 0.65:
        return "balanced"
    return "robust"


def route_instance(
    json_path: str | Path,
    *,
    full_request_count: int = 15,
    time_interval: int = 1,
) -> dict[str, Any]:
    features = extract_instance_features(
        json_path,
        full_request_count=full_request_count,
        time_interval=time_interval,
    )
    family = choose_strategy_family(features)
    return {
        "problem": features.problem,
        "family": family,
        "features": features.__dict__,
    }
