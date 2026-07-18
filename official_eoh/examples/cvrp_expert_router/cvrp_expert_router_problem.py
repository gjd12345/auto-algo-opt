"""CVRP 按实例选择冻结专家的 EoH 问题适配器（唯一模块名供 spawn 重载）。"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import sys
import time
import types
import warnings
from pathlib import Path
from typing import Any, Callable

import numpy as np

EXAMPLE_DIR = Path(__file__).resolve().parent
OFFICIAL_ROOT = EXAMPLE_DIR.parents[1]
REPO_ROOT = OFFICIAL_ROOT.parent
CVRP_CONSTRUCT_DIR = OFFICIAL_ROOT / "examples" / "cvrp_construct"
sys.path.insert(0, str(OFFICIAL_ROOT / "eoh" / "src"))
sys.path.insert(0, str(REPO_ROOT))
# Windows spawn 会按模块名重新导入 ``prob``；构造问题目录只能追加，不能抢在
# 当前 cvrp_expert_router/prob.py 前面，否则子进程会反序列化到错误的问题类。
sys.path.append(str(CVRP_CONSTRUCT_DIR))

from eoh import BaseProblem
from eoh_rag.experiments.research_contracts import (
    DecisionRecord,
    EvaluationResult,
    canonical_json_sha256,
)
from prob_broad import CVRP_MULTI_ENVIRONMENT_SPECS, CVRPCONSTBroad


_FORBIDDEN_CALL_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "vars",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _validate_selector_source(program_str: str) -> None:
    """拒绝合同禁止的外部访问；候选只应执行纯特征到 expert_id 的映射。"""
    tree = ast.parse(program_str)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("selector imports are forbidden")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_CALL_NAMES:
            raise ValueError(f"selector name is forbidden: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("selector dunder access is forbidden")


def compute_instance_features(instance: dict[str, Any], epsilon: float = 1e-12) -> dict[str, float]:
    """严格按冻结合同计算 9 个实例特征，并拒绝 NaN/Inf。"""
    coords = np.asarray(instance["coords"], dtype=float)
    demands = np.asarray(instance["demands"], dtype=float)
    capacity = float(instance["capacity"])
    customer_coords = coords[1:]
    customer_demands = demands[1:]
    if len(customer_coords) == 0 or capacity <= 0:
        raise ValueError("CVRP instance must contain customers and positive capacity")

    pairwise_delta = customer_coords[:, None, :] - customer_coords[None, :, :]
    customer_distances = np.sqrt(np.sum(pairwise_delta * pairwise_delta, axis=2))
    upper_triangle = customer_distances[np.triu_indices(len(customer_coords), k=1)]
    mean_pairwise = float(np.mean(upper_triangle)) if len(upper_triangle) else epsilon
    masked_distances = customer_distances.copy()
    np.fill_diagonal(masked_distances, np.inf)
    nearest_neighbor_mean = (
        float(np.mean(np.min(masked_distances, axis=1)))
        if len(customer_coords) > 1
        else 0.0
    )

    depot_distances = np.linalg.norm(customer_coords - coords[0], axis=1)
    mean_depot_distance = float(np.mean(depot_distances))
    mean_demand = float(np.mean(customer_demands))
    minimum_vehicle_count = max(1, math.ceil(float(np.sum(customer_demands)) / capacity))
    spans = np.ptp(coords, axis=0)
    short_span = max(float(np.min(spans)), epsilon)

    features = {
        "n_customers": float(len(customer_coords)),
        "capacity": capacity,
        "mean_demand_ratio": mean_demand / capacity,
        "demand_cv": float(np.std(customer_demands, ddof=0)) / max(mean_demand, epsilon),
        "capacity_fill_ratio": float(np.sum(customer_demands))
        / (minimum_vehicle_count * capacity),
        "span_aspect_ratio": max(1.0, float(np.max(spans)) / short_span),
        "depot_distance_ratio": mean_depot_distance / max(mean_pairwise, epsilon),
        "nearest_neighbor_ratio": nearest_neighbor_mean / max(mean_pairwise, epsilon),
        "radial_distance_cv": float(np.std(depot_distances, ddof=0))
        / max(mean_depot_distance, epsilon),
    }
    if not all(np.isfinite(value) for value in features.values()):
        raise ValueError("CVRP router feature contains NaN or infinity")
    return features


class CVRPEXPERTROUTER(BaseProblem):
    """进化 ``select_expert``，适应度仅来自冻结 development 三环境。"""

    template_program = '''
def select_expert(instance_features: dict[str, float],
                  expert_summaries: list[dict[str, str]]) -> str:
    """Return exactly one expert_id from expert_summaries."""
    return "n2"
'''

    task_description = (
        "Design a deterministic per-instance algorithm selector for CVRP. "
        "Use only the nine numeric instance features and the frozen expert summaries. "
        "Return exactly one listed expert_id. Lower development relative cost is better. "
        "Do not access files, network, environment variables, random state, time, or hidden costs, "
        "and do not mutate either input."
    )

    def __init__(
        self,
        timeout: int = 180,
        n_processes: int = 1,
        contract_path: str | Path | None = None,
    ):
        super().__init__(timeout=timeout, n_processes=n_processes)
        # 默认合同保持旧实验可复现；新 cohort 必须显式传入独立合同，避免复用已观察的确认集。
        self.contract_path = (
            Path(contract_path).resolve()
            if contract_path
            else EXAMPLE_DIR / "router_contract_v1.json"
        )
        self.contract_bytes = self.contract_path.read_bytes()
        self.contract_sha256 = _sha256_bytes(self.contract_bytes)
        self.contract = json.loads(self.contract_bytes.decode("utf-8"))
        self._validate_contract()
        self.expert_summaries = [
            {"expert_id": item["expert_id"], "summary": item["summary"]}
            for item in self.contract["experts"]
        ]
        self.expert_ids = tuple(self.contract["expert_ids"])
        self.development_instances = self._build_instances("development")
        # 专家均为已冻结、带哈希的可信资产；预计算成本后，候选选择器看不到真实成本。
        self.expert_costs = self._precompute_expert_costs()
        self.report_confirmation = False
        self.confirmation_report: dict[str, Any] = {}

    def evaluate(self, code_string: str) -> dict[str, Any] | None:
        """先验证纯函数边界，再交给 BaseProblem 编译，禁止违规代码抢先执行。"""
        try:
            _validate_selector_source(code_string)
        except (SyntaxError, ValueError):
            return None
        return super().evaluate(code_string)

    def _validate_contract(self) -> None:
        if self.contract.get("schema_version") != "cvrp_expert_router_contract/v1":
            raise ValueError("unsupported CVRP router contract")
        feature_order = self.contract.get("feature_order")
        if not isinstance(feature_order, list) or len(feature_order) != 9:
            raise ValueError("router contract must define exactly nine features")
        expert_ids = self.contract.get("expert_ids")
        contract_expert_ids = [
            item.get("expert_id") for item in self.contract.get("experts", [])
        ]
        if expert_ids != contract_expert_ids or len(set(expert_ids or [])) != 4:
            raise ValueError("router contract expert ids are inconsistent")
        if self.contract.get("data_split", {}).get("held_out_used") is not False:
            raise ValueError("router evolution must not use held-out data")

    def _build_instances(self, split_name: str) -> list[dict[str, Any]]:
        split = self.contract["data_split"][split_name]
        spec_by_name = {item["name"]: item for item in CVRP_MULTI_ENVIRONMENT_SPECS}
        instances: list[dict[str, Any]] = []
        for environment_name, bounds in split.items():
            if environment_name not in spec_by_name:
                raise ValueError(f"unknown router environment: {environment_name}")
            start_seed, end_seed = (int(bounds[0]), int(bounds[1]))
            for seed in range(start_seed, end_seed + 1):
                instance = CVRPCONSTBroad._generate_instance(
                    spec_by_name[environment_name],
                    seed,
                )
                instance["seed"] = seed
                instance["features"] = compute_instance_features(
                    instance,
                    float(self.contract["feature_numerics"]["distance_epsilon"]),
                )
                instances.append(instance)
        return instances

    def _load_expert_functions(self) -> dict[str, Callable[..., int]]:
        functions: dict[str, Callable[..., int]] = {}
        source_cache: dict[Path, list[dict[str, Any]]] = {}
        for expert in self.contract["experts"]:
            source_path = REPO_ROOT / expert["source_file"]
            source_bytes = source_path.read_bytes()
            if _sha256_bytes(source_bytes) != expert["source_file_sha256"].upper():
                raise ValueError(f"expert source hash mismatch: {expert['expert_id']}")
            rows = source_cache.setdefault(
                source_path,
                json.loads(source_bytes.decode("utf-8")),
            )
            row = next(
                (item for item in rows if item.get("candidate_id") == expert["expert_id"]),
                None,
            )
            if not row or not isinstance(row.get("code"), str):
                raise ValueError(f"expert code missing: {expert['expert_id']}")
            if _sha256_bytes(row["code"].encode("utf-8")) != expert["code_sha256"].upper():
                raise ValueError(f"expert code hash mismatch: {expert['expert_id']}")
            module = types.ModuleType(f"cvrp_router_expert_{expert['expert_id']}")
            module.__dict__["np"] = np
            exec(row["code"], module.__dict__)
            functions[expert["expert_id"]] = module.select_next_node
        return functions

    def _precompute_expert_costs(self) -> list[dict[str, float | None]]:
        expert_functions = self._load_expert_functions()
        route_evaluator = object.__new__(CVRPCONSTBroad)
        rows: list[dict[str, float | None]] = []
        for instance in self.development_instances:
            coords = instance["coords"]
            demands = instance["demands"]
            delta = coords[:, None, :] - coords[None, :, :]
            distance_matrix = np.sqrt(np.sum(delta * delta, axis=2))
            costs: dict[str, float | None] = {}
            for expert_id, expert_func in expert_functions.items():
                # 个别冻结专家在仅剩一个客户时会计算空邻域均值；其既有回退仍可形成
                # 合法路线，因此只屏蔽数值警告，不改变专家代码或选择结果。
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    route = route_evaluator._route_construct(
                        expert_func,
                        distance_matrix,
                        demands,
                        instance["capacity"],
                    )
                costs[expert_id] = (
                    route_evaluator._tour_cost(coords, route) if route is not None else None
                )
            rows.append(costs)
        return rows

    def evaluate_program(
        self,
        program_str: str,
        callable_func: Callable[[dict[str, float], list[dict[str, str]]], str],
    ) -> dict[str, Any] | None:
        started = time.perf_counter()
        if self.report_confirmation:
            confirmation_instances = self._build_instances("confirmation")
            confirmation_costs = self._precompute_costs_for_instances(confirmation_instances)
            result = self._evaluate_candidate(
                program_str,
                callable_func,
                confirmation_instances,
                confirmation_costs,
                suite="confirmation",
                started=started,
            )
            if result is not None:
                improvement_pct = -100.0 * float(result["objective"])
                if abs(improvement_pct) < 1e-12:
                    improvement_pct = 0.0
                self.confirmation_report = {
                    "suite": "confirmation",
                    "objective": result["objective"],
                    "mean_improvement_vs_n2_pct": improvement_pct,
                    **result["feedback"],
                }
            return result
        return self._evaluate_candidate(
            program_str,
            callable_func,
            self.development_instances,
            self.expert_costs,
            suite="development",
            started=started,
        )

    def _precompute_costs_for_instances(
        self,
        instances: list[dict[str, Any]],
    ) -> list[dict[str, float | None]]:
        original_instances = self.development_instances
        try:
            self.development_instances = instances
            return self._precompute_expert_costs()
        finally:
            self.development_instances = original_instances

    def _evaluate_candidate(
        self,
        program_str: str,
        callable_func: Callable[[dict[str, float], list[dict[str, str]]], str],
        instances: list[dict[str, Any]],
        expert_cost_rows: list[dict[str, float | None]],
        *,
        suite: str,
        started: float,
    ) -> dict[str, Any] | None:
        """评价一个冻结数据切分；调用方决定 development 或最终 confirmation。"""

        environment_values: dict[str, list[float]] = {}
        selection_counts = {expert_id: 0 for expert_id in self.expert_ids}
        fallback_count = 0
        instance_records: list[dict[str, Any]] = []
        for instance, expert_costs in zip(instances, expert_cost_rows):
            features = copy.deepcopy(instance["features"])
            summaries = copy.deepcopy(self.expert_summaries)
            features_before = copy.deepcopy(features)
            summaries_before = copy.deepcopy(summaries)
            try:
                selected_expert = callable_func(features, summaries)
            except Exception:
                return None
            if features != features_before or summaries != summaries_before:
                return None
            if not isinstance(selected_expert, str) or selected_expert not in self.expert_ids:
                return None

            used_fallback = False
            selected_cost = expert_costs[selected_expert]
            if selected_cost is None:
                selected_expert = "n2"
                selected_cost = expert_costs["n2"]
                fallback_count += 1
                used_fallback = True
            reference_cost = expert_costs["n2"]
            if selected_cost is None or reference_cost is None or reference_cost <= 0:
                return None
            relative_cost = (float(selected_cost) - float(reference_cost)) / float(reference_cost)
            environment = str(instance["environment"])
            environment_values.setdefault(environment, []).append(relative_cost)
            selection_counts[selected_expert] += 1
            instance_records.append(
                {
                    "environment": environment,
                    "seed": int(instance["seed"]),
                    "selected_expert": selected_expert,
                    "relative_cost_vs_n2": relative_cost,
                    "fallback": used_fallback,
                }
            )

        environment_objectives = {
            name: float(np.mean(values)) for name, values in environment_values.items()
        }
        objective = float(np.mean(list(environment_objectives.values())))
        candidate_id = hashlib.sha256(program_str.encode("utf-8")).hexdigest()
        instance_results_hash = canonical_json_sha256(instance_records)
        objective_field = (
            "development_objective"
            if suite == "development"
            else "confirmation_objective"
        )
        feedback = {
            objective_field: objective,
            "environment_relative_cost_vs_n2": environment_objectives,
            "expert_selection_counts": selection_counts,
            "selector_invalid_outputs": 0,
            "expert_fallback_count": fallback_count,
        }
        evaluation = EvaluationResult(
            candidate_id=candidate_id,
            suite=suite,
            objective=objective,
            feasible=True,
            runtime_seconds=round(time.perf_counter() - started, 6),
            failure_type=None,
            instance_results_hash=instance_results_hash,
            feedback=feedback,
        )
        evaluation_hash = canonical_json_sha256(evaluation.to_dict())
        observed_scope = "dev_only" if suite == "development" else "confirmation_only"
        decision_payload = {
            "actor": "research_agent",
            "observed_scope": observed_scope,
            "action": "select_expert_portfolio",
            "candidate_id": candidate_id,
            "evaluation_hash": evaluation_hash,
        }
        decision = DecisionRecord(
            decision_id=canonical_json_sha256(decision_payload),
            actor="research_agent",
            observed_scope=observed_scope,
            action="select_expert_portfolio",
            reason=(
                "仅依据当前冻结切分的实例特征评价选择器；"
                "confirmation 仅在候选冻结后报告，held-out 未使用。"
            ),
            input_hashes=(self.contract_sha256.lower(), candidate_id),
            output_hashes=(evaluation_hash, instance_results_hash),
        )
        payload = evaluation.to_eoh_payload()
        payload["feedback"]["decision_record"] = decision.to_dict()
        return payload
