"""FME 三问题反例有效性适配器；只验证开发域约束，不运行求解器。"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping, Protocol


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class CounterexampleValidityPolicy:
    problem: str
    distance_limit: float
    minimum_size: int
    maximum_size: int
    nominal_signature: tuple[float, ...]
    visible_scope: str = "dev_only"


@dataclass(frozen=True)
class ConstraintEvidence:
    problem: str
    distance_metric: str
    distance_to_nominal: float
    distance_limit: float
    observed_size: int
    size_bounds: tuple[int, int]
    distance_valid: bool
    size_valid: bool
    structural_feasible: bool
    domain_validity_status: str
    constraint_evidence_hash: str
    visible_scope: str = "dev_only"


class ProblemAdapter(Protocol):
    def validate_challenge(
        self,
        artifact: Mapping[str, object],
        policy: CounterexampleValidityPolicy,
    ) -> ConstraintEvidence: ...


class _BaseProblemAdapter:
    problem: str
    distance_metric: str

    def _validate_policy(self, policy: CounterexampleValidityPolicy) -> None:
        if (
            policy.problem != self.problem
            or policy.visible_scope != "dev_only"
            or not math.isfinite(policy.distance_limit)
            or policy.distance_limit < 0
            or policy.minimum_size <= 0
            or policy.minimum_size > policy.maximum_size
            or not policy.nominal_signature
            or any(not math.isfinite(value) for value in policy.nominal_signature)
        ):
            raise ValueError("invalid_counterexample_validity_policy")

    def _evidence(
        self,
        policy: CounterexampleValidityPolicy,
        distance: float,
        size: int,
        structural_feasible: bool,
    ) -> ConstraintEvidence:
        distance_valid = math.isfinite(distance) and distance <= policy.distance_limit
        size_valid = policy.minimum_size <= size <= policy.maximum_size
        status = (
            "valid"
            if distance_valid and size_valid and structural_feasible
            else "invalid_structure"
            if not structural_feasible
            else "out_of_domain"
        )
        payload = {
            "problem": self.problem,
            "distance_metric": self.distance_metric,
            "distance_to_nominal": distance,
            "distance_limit": policy.distance_limit,
            "observed_size": size,
            "size_bounds": [policy.minimum_size, policy.maximum_size],
            "distance_valid": distance_valid,
            "size_valid": size_valid,
            "structural_feasible": structural_feasible,
            "domain_validity_status": status,
            "visible_scope": "dev_only",
        }
        return ConstraintEvidence(
            problem=self.problem,
            distance_metric=self.distance_metric,
            distance_to_nominal=distance,
            distance_limit=policy.distance_limit,
            observed_size=size,
            size_bounds=(policy.minimum_size, policy.maximum_size),
            distance_valid=distance_valid,
            size_valid=size_valid,
            structural_feasible=structural_feasible,
            domain_validity_status=status,
            constraint_evidence_hash=_canonical_sha256(payload),
        )


class BPProblemAdapter(_BaseProblemAdapter):
    problem = "bp_online"
    distance_metric = "normalized_item_histogram_total_variation"

    def validate_challenge(self, artifact: Mapping[str, object], policy: CounterexampleValidityPolicy) -> ConstraintEvidence:
        self._validate_policy(policy)
        items = artifact.get("items")
        capacity = artifact.get("capacity")
        if not isinstance(items, (tuple, list)) or not isinstance(capacity, int) or capacity <= 0:
            return self._evidence(policy, float("inf"), 0, False)
        structural = bool(items) and all(isinstance(item, int) and 0 < item <= capacity for item in items)
        histogram = [0.0, 0.0, 0.0, 0.0]
        if structural:
            for item in items:
                histogram[min(3, (4 * item - 1) // capacity)] += 1.0 / len(items)
        distance = float("inf") if len(policy.nominal_signature) != 4 else 0.5 * sum(
            abs(left - right) for left, right in zip(histogram, policy.nominal_signature)
        )
        return self._evidence(policy, distance, len(items), structural)


class TSPProblemAdapter(_BaseProblemAdapter):
    problem = "tsp_construct"
    distance_metric = "coordinate_centroid_and_nearest_neighbor_divergence"

    def validate_challenge(self, artifact: Mapping[str, object], policy: CounterexampleValidityPolicy) -> ConstraintEvidence:
        self._validate_policy(policy)
        coordinates = artifact.get("coordinates")
        if not isinstance(coordinates, (tuple, list)) or len(coordinates) < 2:
            return self._evidence(policy, float("inf"), 0, False)
        points = tuple(coordinates)
        structural = all(
            isinstance(point, (tuple, list)) and len(point) == 2 and all(isinstance(value, (int, float)) and math.isfinite(value) for value in point)
            for point in points
        ) and len({(float(point[0]), float(point[1])) for point in points}) == len(points)
        if not structural or len(policy.nominal_signature) != 3:
            return self._evidence(policy, float("inf"), len(points), False)
        centroid_x = sum(float(point[0]) for point in points) / len(points)
        centroid_y = sum(float(point[1]) for point in points) / len(points)
        nearest = sum(
            min(math.dist(point, other) for other in points if other is not point)
            for point in points
        ) / len(points)
        distance = abs(centroid_x - policy.nominal_signature[0]) + abs(centroid_y - policy.nominal_signature[1]) + abs(nearest - policy.nominal_signature[2])
        return self._evidence(policy, distance, len(points), True)


class CVRPProblemAdapter(_BaseProblemAdapter):
    problem = "cvrp_construct"
    distance_metric = "coordinate_and_demand_mean_divergence"

    def validate_challenge(self, artifact: Mapping[str, object], policy: CounterexampleValidityPolicy) -> ConstraintEvidence:
        self._validate_policy(policy)
        depot = artifact.get("depot")
        customers = artifact.get("customer_coordinates")
        demands = artifact.get("demands")
        capacity = artifact.get("capacity")
        if not isinstance(customers, (tuple, list)) or not isinstance(demands, (tuple, list)) or not isinstance(capacity, (int, float)):
            return self._evidence(policy, float("inf"), 0, False)
        structural = (
            isinstance(depot, (tuple, list)) and len(depot) == 2
            and len(customers) == len(demands) and len(customers) > 0 and capacity > 0
            and all(isinstance(point, (tuple, list)) and len(point) == 2 and all(isinstance(value, (int, float)) and math.isfinite(value) for value in point) for point in customers)
            and all(isinstance(demand, (int, float)) and 0 <= demand <= capacity and math.isfinite(demand) for demand in demands)
        )
        if not structural or len(policy.nominal_signature) != 3:
            return self._evidence(policy, float("inf"), len(customers), False)
        mean_x = sum(float(point[0]) for point in customers) / len(customers)
        mean_y = sum(float(point[1]) for point in customers) / len(customers)
        mean_demand_ratio = sum(float(demand) for demand in demands) / len(demands) / float(capacity)
        distance = abs(mean_x - policy.nominal_signature[0]) + abs(mean_y - policy.nominal_signature[1]) + abs(mean_demand_ratio - policy.nominal_signature[2])
        return self._evidence(policy, distance, len(customers), True)


__all__ = [
    "BPProblemAdapter",
    "CVRPProblemAdapter",
    "ConstraintEvidence",
    "CounterexampleValidityPolicy",
    "ProblemAdapter",
    "TSPProblemAdapter",
]
