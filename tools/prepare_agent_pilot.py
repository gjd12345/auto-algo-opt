"""Prepare D1 for a host Coding Agent. Never synthesize a Plan or call a provider."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_skill_loop import session_runtime as db
from agent_skill_loop.benchmark import ExperimentManifest


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def execution_environment():
    """Allowlisted execution identity, excluding credentials and arbitrary env vars."""
    packages = {}
    eoh_commit = None
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if name:
            packages[name.lower().replace("_", "-")] = dist.version
        if name and name.lower() == "eoh":
            direct = dist.read_text("direct_url.json")
            if direct:
                eoh_commit = json.loads(direct).get("vcs_info", {}).get("commit_id")
    return {
        "schema_version": "execution-environment/v1",
        "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable, "python_compiler": platform.python_compiler(),
        "platform": platform.platform(), "machine": platform.machine(),
        "processor": platform.processor(), "cpu_count": os.cpu_count(),
        "packages": dict(sorted(packages.items())), "installed_eoh_commit": eoh_commit,
        "thread_settings": {k: os.environ.get(k) for k in
                            ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "device": "cpu", "hardware_identity_scope": "OS-reported; no unique machine identifier",
    }


def source_identity():
    files = {}
    for folder in ("agent_skill_loop", "eoh_frozen", "skills/algorithm-optimization", "tools"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".md", ".yaml"}:
                files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_files_sha256": files,
        "source_scope": "Exact working-tree runtime, Skill and tools; git HEAD alone is insufficient",
    }


def prepare(template: dict, controller: dict, output: Path):
    if sys.version_info[:2] != (3, 11):
        raise ValueError("pilot_requires_python_3_11")
    if controller.get("kind") != "host_coding_agent" or not all(
        controller.get(key) for key in ("host", "model", "identity_source")
    ):
        raise ValueError("host_controller_identity_required")
    if output.exists():
        raise ValueError("new_pilot_output_required")
    values = {k: v for k, v in template.items() if k not in
              {"schema_version", "experiment_manifest_sha256", "manifest_version"}}
    if values.get("inheritance_mode") != "population_seeds" or values.get("rounds") != 2:
        raise ValueError("d1_requires_two_round_population_seeds")
    if values.get("repair_mode") != "off" or values.get("memory_enabled") is not False:
        raise ValueError("d1_requires_memory_repair_off")
    extra = dict(values["extra"])
    if extra.get("knowledge_mode", "off") != "off":
        raise ValueError("d1_requires_knowledge_off")
    env = execution_environment()
    if env["installed_eoh_commit"] != db.EOH_COMMIT:
        raise ValueError("installed_eoh_commit_unverified")
    extra.update({"treatment": "D1", "controller_identity": controller,
                  "execution_environment": env, "source_identity": source_identity(),
                  "knowledge_mode": "off", "benchmark_profile": "obp_evolution_mini",
                  "interpretation": "single host-agent wiring pilot; no causal comparison to historical D0",
                  "controller_cost": {"input_tokens": None, "output_tokens": None, "reason": "host usage unavailable"}})
    values.update(extra=extra, runtime_hash=db._runtime_source_hash(), skill_hash=db._skill_content_hash(),
                  agent_guidance=True)
    manifest = ExperimentManifest(**values)
    resources, generation = extra["resource_contract"], extra["generation_contract"]
    thinking = generation["thinking"]
    thinking = thinking.get("type", "provider-default") if isinstance(thinking, dict) else thinking
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_bytes(encoded(manifest.as_dict()))
    receipt = db.initialize_session(
        output=output / "session", operation_id="D1-init", eoh_model=manifest.model,
        eoh_endpoint=manifest.endpoint_identity, eoh_api_key_env=extra.get("api_key_env", "DEEPSEEK_API_KEY"),
        benchmark_id="eohs_v1", benchmark_profile_name="obp_evolution_mini",
        inheritance_mode="population_seeds", feedback_mode=manifest.feedback_mode,
        agent_guidance=True, memory_enabled=False, repair_mode="off", eoh_thinking=thinking,
        max_rounds=2, round_budget=manifest.round_budget, max_solver_calls=manifest.evaluation_budget,
        eoh_max_requests=resources["request_budget"], eoh_round_max_requests=resources["round_request_budget"],
        engine_wall_seconds=resources["wall_clock_budget"], round_wall_seconds=resources["round_wall_clock_budget"],
        request_timeout=generation["request_timeout_seconds"], solver_timeout=resources["solver_timeout_seconds"],
        repair_max_requests=resources["repair_request_budget"],
        search_policy_defaults=extra["search_policy_defaults"], search_policy_limits=extra["search_policy_limits"],
        seed=manifest.search_seed, experiment_manifest=manifest.as_dict(),
    )
    (output / "init_receipt.json").write_bytes(encoded(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-manifests", type=Path, required=True)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    template = json.loads(args.pilot_manifests.read_text(encoding="utf-8"))["groups"]["D"]["manifest"]
    result = prepare(template, json.loads(args.controller.read_text(encoding="utf-8")), args.output)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
