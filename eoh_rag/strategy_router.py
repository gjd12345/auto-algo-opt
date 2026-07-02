"""
模块：strategy_router（策略路由器）
功能：读取一个优化问题实例（JSON 文件），提取其规模与紧张度特征，并据此挑选出一套合适的启发式策略族。
职责：管理"实例特征"这一数据结构；负责从原始 JSON 中统计请求数、批次规模、时间窗宽度等指标，
      计算综合难度分，并把难度映射为具体的策略族名称（fast / balanced / robust）。
接口：
      - InstanceFeatures：只读数据类，保存单个实例的全部特征字段。
      - extract_instance_features(json_path, *, full_request_count=15, time_interval=1) -> InstanceFeatures
        从 JSON 文件解析并计算特征。
      - choose_strategy_family(features) -> str
        根据特征返回策略族名称。
      - route_instance(json_path, *, full_request_count=15, time_interval=1) -> dict
        端到端入口：解析特征 + 选族，返回汇总字典。
输入：一个实例 JSON 文件路径；可选的关键字参数 full_request_count（满载请求数基准）与 time_interval（时间间隔难度倍数）。
输出：实例特征对象，或包含 problem / family / features 三个键的字典。
示例：
      >>> result = route_instance("instance_001.json", time_interval=1)
      >>> result["family"]
      'balanced'
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InstanceFeatures:
    """单个问题实例的特征集合（只读）。

    每个字段描述实例的一个维度，供选族逻辑使用：
    - problem：实例文件名，用作标识。
    - request_count：所有批次的请求总数。
    - max_batch_request_count：单个批次中最大的请求数。
    - avg_batch_request_count：每批请求数的平均值。
    - full_request_count：视为"满载"的请求数基准（用于归一化）。
    - density_ratio：最大批次请求数 / 满载基准，衡量瞬时拥挤程度。
    - vehicle_num：可用车辆数量。
    - vehicle_pressure：请求总数 / 车辆数，衡量车辆承载压力。
    - avg_window_width：所有站点时间窗宽度的平均值。
    - min_window_width：最窄的时间窗宽度。
    - time_tightness：归一化后的时间窗紧张度（越大越紧）。
    - time_interval：时间间隔，作为难度放大系数。
    - difficulty：综合难度分，融合密度、时间紧张度与车辆压力。
    """

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
    """计算单个站点的时间窗宽度：结束时间减去开始时间。缺失字段按 0 处理。"""
    return float(station.get("timeEnd", 0)) - float(station.get("timeStart", 0))


def extract_instance_features(
    json_path: str | Path,
    *,
    full_request_count: int = 15,
    time_interval: int = 1,
) -> InstanceFeatures:
    """从实例 JSON 文件中提取并计算特征。

    读取 JSON 里的 batch（批次）列表，统计请求规模与时间窗信息，
    再据此推导密度比、时间紧张度、车辆压力，最后融合成综合难度分。

    参数：
        json_path：实例 JSON 文件路径。
        full_request_count：满载请求数基准，用于把批次规模归一化为密度比。
        time_interval：时间间隔，越大越难，作为时间紧张度的放大系数。

    返回：填充好所有字段的 InstanceFeatures 对象。
    """
    path = Path(json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    batches = data.get("batch", [])
    request_count = 0
    batch_counts: list[int] = []
    widths: list[float] = []
    # 遍历每个批次：一个批次的请求数取"起点数"与"终点数"中的较大者；
    # 同时收集所有起点与终点站点的时间窗宽度。
    for batch in batches:
        ori = batch.get("ori", [])
        des = batch.get("des", [])
        batch_count = max(len(ori), len(des))
        batch_counts.append(batch_count)
        request_count += batch_count
        widths.extend(_station_window_width(item) for item in ori)
        widths.extend(_station_window_width(item) for item in des)

    # 汇总统计量；所有指标在列表为空时安全地回退到 0。
    max_batch_count = max(batch_counts) if batch_counts else 0
    avg_batch_count = sum(batch_counts) / len(batch_counts) if batch_counts else 0.0
    avg_width = sum(widths) / len(widths) if widths else 0.0
    min_width = min(widths) if widths else 0.0
    vehicle_num = int(data.get("vehicleNum", 0) or 0)
    # 密度比：最繁忙批次相对满载基准的拥挤程度；车辆压力：平均每辆车要承担多少请求。
    density_ratio = max_batch_count / full_request_count if full_request_count else 0.0
    vehicle_pressure = request_count / vehicle_num if vehicle_num else 0.0

    # A simple normalized tightness score. Wider windows are easier; the time
    # interval acts as an explicit difficulty multiplier in our experiments.
    # 时间紧张度：窗越窄越紧张（取倒数），并按 time_interval 放大，最后截断到 1.0 以内。
    window_tightness = 1.0 / max(avg_width, 1.0)
    time_tightness = min(1.0, window_tightness * 120.0 * max(time_interval, 1))
    # 综合难度分：密度占 55%、时间紧张度占 30%、车辆压力占 15%，各分量先截断到 [0, 1]。
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
    """根据实例特征挑选一套策略族，返回族名字符串。

    决策顺序：
    1) 时间间隔大（>= 2）视为最难场景，直接选择稳健族 "robust"。
    2) 否则按密度比分档：低密度选快速族 "fast"，中密度选均衡族 "balanced"，
       高密度回退到稳健族 "robust"。
    """
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
    """端到端路由入口：先提取实例特征，再选出策略族，最后打包成字典返回。

    参数与 extract_instance_features 一致。
    返回：包含三个键的字典——problem（实例名）、family（策略族名）、
          features（特征对象展开成的字典）。
    """
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
