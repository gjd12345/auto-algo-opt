"""Prepare the frozen three-seed A/B/C diagnostic without provider requests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skill_loop import session_runtime as db
from agent_skill_loop.benchmark import (
    build_research_loop_manifests, build_island605_bp_research_loop_manifests,
)
from agent_skill_loop.client import load_local_env


SEED_DERIVATION_TEXT = "obp_research_loop_v1/three_seed_diagnostic"
SEED_DERIVATION_SHA256 = "55a062797c1fba96d6c38bc6a252f53eabbd991d2b5c202899a8366fd6c1498a"
DIAGNOSTIC_SEEDS = (1436574329, 2082454166, 3603139526)
EXPECTED_ENDPOINT = "https://model-router.edu-aliyun.com/v1/chat/completions"
EXPECTED_MODEL = "qwen/deepseek-v4.1-flash"
EXPECTED_KEY_ENV = "MODEL_ROUTER_API_KEY"


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _derive_seeds() -> tuple[int, int, int]:
    digest = hashlib.sha256(SEED_DERIVATION_TEXT.encode("utf-8")).digest()
    seeds = tuple(int.from_bytes(digest[offset:offset + 4], "big") for offset in (0, 4, 8))
    if hashlib.sha256(SEED_DERIVATION_TEXT.encode("utf-8")).hexdigest() != SEED_DERIVATION_SHA256 \
            or seeds != DIAGNOSTIC_SEEDS:
        raise RuntimeError("diagnostic_seed_derivation_drift")
    return seeds


def prepare(output: Path, *, domain: str = "obp") -> dict:
    if domain not in {"obp", "island605-bp"}:
        raise ValueError("unknown_research_domain")
    is_bp = domain == "island605-bp"
    seed_text = "island605_bp_research_loop_v1/three_seed_diagnostic" if is_bp else SEED_DERIVATION_TEXT
    seeds = (tuple(int.from_bytes(hashlib.sha256(seed_text.encode("utf-8")).digest()[offset:offset + 4], "big")
                   for offset in (0, 4, 8)) if is_bp else _derive_seeds())
    problem = "bp_online_island605" if is_bp else "obp_online"
    benchmark_id = "island605_bp" if is_bp else "eohs_v1"
    profile = "historically_exposed_train_v1" if is_bp else "obp_evolution_mini"
    builder = build_island605_bp_research_loop_manifests if is_bp else build_research_loop_manifests
    experiment_id = "island605_bp_research_loop_v1_three_seed_diagnostic" if is_bp else "obp_research_loop_v1_three_seed_diagnostic"
    load_local_env()
    endpoint = os.environ.get("MODEL_ROUTER_ENDPOINT", "").strip()
    model = os.environ.get("MODEL_ROUTER_MODEL", "").strip()
    key_env = os.environ.get("MODEL_ROUTER_API_KEY_ENV", "").strip()
    if (endpoint, model, key_env) != (EXPECTED_ENDPOINT, EXPECTED_MODEL, EXPECTED_KEY_ENV):
        raise RuntimeError("router_public_configuration_mismatch")
    if not os.environ.get(key_env, "").strip():
        raise RuntimeError("router_key_missing")

    output = output.resolve()
    source = output / "manifest_source"
    if source.exists():
        raise RuntimeError("pre_registration_output_already_exists")
    db.initialize_session(
        output=source,
        operation_id="island605-bp-manifest-source" if is_bp else "research-loop-v2-manifest-source",
        problem=problem,
        benchmark_id=benchmark_id,
        benchmark_profile_name=profile,
        eoh_model=model,
        eoh_endpoint=endpoint,
        eoh_api_key_env=key_env,
        eoh_thinking="disabled",
        memory_enabled=False,
        inheritance_mode="population_seeds",
        repair_mode="off",
        max_rounds=4,
        round_budget=25,
        max_solver_calls=100,
        eoh_max_requests=240,
        eoh_round_max_requests=60,
        engine_wall_seconds=7200,
        round_wall_seconds=1800,
        search_policy_defaults={"pop_size": 4, "n_pop": 2, "max_sample_nums": 100},
        search_policy_limits={"pop_size": [4, 4], "n_pop": [2, 2], "max_sample_nums": [100, 100]},
    )
    frozen = json.loads((source / "config_frozen.json").read_text(encoding="utf-8"))
    base = dict(frozen["experiment_manifest"]["document"])
    initial_plan = {
        "round_id": 1,
        "direction": ("Explore legal item-relative bin scores on the restored five-stream island_605 BP training contract."
                      if is_bp else "Explore behaviorally distinct legal OBP priority mechanisms under the frozen training contract."),
        "operations": [{
            "type": "replace",
            "target": "score mechanism family" if is_bp else "priority mechanism family",
            "mechanism": ("Compare exact-fill, residual-capacity fit and bounded item-conditioned alternatives under the all-feasible-bin interface."
                          if is_bp else "compare stable order, residual-capacity fit and item-conditioned alternatives"),
        }],
        "preserve": "problem, suite, evaluator, MetricSpec, provider configuration, repair mode and budgets",
        "feedback_basis": None,
        "memory_basis": [],
        "reference_skill_ref": None,
        "hypothesis": "At least one legal mechanism family may improve the frozen baseline; this is unproven.",
        "search_intent": {"phase": "exploration"},
        "reflection_basis": None,
    }
    _write(output / "initial_plan.json", initial_plan)

    runs = []
    for seed in seeds:
        seeded = {**base, "search_seed": seed}
        pilot = builder(seeded)
        _write(output / "manifests" / f"seed_{seed}.json", pilot)
        for group in ("A", "B", "C"):
            manifest = pilot["groups"][group]["manifest"]
            manifest_ref = f"manifests/seed_{seed}_{group}.json"
            _write(output / manifest_ref, manifest)
            runs.append({
                "group": group,
                "seed": seed,
                "manifest_ref": manifest_ref,
                "manifest_sha256": manifest["experiment_manifest_sha256"],
                "run_ref": f"runs/seed_{seed}/{group}",
                "bundle_ref": f"bundles/seed_{seed}/{group}",
            })
    registration = {
        "schema_version": "algorithm-optimization-research-loop-pre-registration/v1",
        "experiment_id": experiment_id,
        "problem_scope": problem,
        "benchmark_profile": profile,
        "seed_derivation": {"text": seed_text, "sha256": hashlib.sha256(seed_text.encode("utf-8")).hexdigest(),
                            "seeds": list(seeds)},
        "provider": {"endpoint": endpoint, "model": model, "api_key_env": key_env},
        "budget": {"primary_resource": "solver_calls", "per_run": 100, "rounds": 4,
                   "per_round": 25, "run_count": len(runs), "maximum_total_solver_calls": 900},
        "heldout_policy": "locked_no_access_diagnostic",
        "initial_plan_ref": "initial_plan.json",
        "runs": runs,
    }
    _write(output / "pre_registration.json", registration)
    _write(output / "report_index.template.json", {
        "schema_version": "algorithm-optimization-research-loop-index/v1",
        "problem_scope": problem,
        "runs": [{"group": item["group"], "seed": item["seed"], "bundle": item["bundle_ref"]}
                 for item in runs],
    })
    return {"output": str(output), "seeds": list(seeds), "runs": len(runs),
            "maximum_total_solver_calls": 900, "provider_requests": 0, "heldout_access": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain", choices=["obp", "island605-bp"], default="obp")
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, domain=args.domain), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
