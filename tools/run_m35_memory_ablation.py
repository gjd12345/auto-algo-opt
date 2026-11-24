"""Freeze, run, and report the M3.5 four-arm common-start experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys
from tempfile import TemporaryDirectory
from collections.abc import Mapping, Sequence
from contextlib import ExitStack, closing
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.evidence.memory import SCHEMA_VERSION as MEMORY_RECEIPT_SCHEMA
from agent_skill_loop.file_lock import exclusive_file_lock
from agent_skill_loop.interface_design.blind_eval import paired_bootstrap_comparison
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m5 import build_m5_public_record
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.memory import MemoryAPI, MemoryEntry
from agent_skill_loop.memory.api import solution_execution_ast_sha256
from agent_skill_loop.memory.auto_dream import auto_dream
from agent_skill_loop.problems.base import get_problem
from knowledge_tools import SCHEMA_VERSION as KB_SCHEMA_VERSION
from research_agent.contracts import AgentConfig, AgentCheckpoint, atomic_write_json, sha256_bytes, sha256_file, sha256_text
from research_agent.loop import _build_initial_baseline_solver, run_research_agent
from research_agent.tools.kb_tools import verify_pinned_release
from tools.run_b4_intron_ablation import EXTERNAL_CVRPLIB_SUITES, evaluate_public_frozen_solver
from tools.run_m5_trajectory_control import TERMINAL_PHASES, _completed, _indexed, _open_ledger, _penalized

SEEDS = (20261124, 20261125, 20261126)
ARMS = {
    "arm_m35_0_m5_nomem": "off",
    "arm_m35_1_naive_mem": "naive_static",
    "arm_m35_2_m35_l12": "m35_l12",
    "arm_m35_3_m35_full": "m35_full",
}
ARM_0, ARM_1, ARM_2, ARM_3 = ARMS
CONTRASTS = ((ARM_1, ARM_0), (ARM_2, ARM_0), (ARM_3, ARM_0), (ARM_2, ARM_1), (ARM_3, ARM_2))
MODEL = "DeepSeek-V4.1-Flash"
ENDPOINT_ENV, API_KEY_ENV = "PARATERA_ENDPOINT", "PARATERA_API_KEY"
RELEASE_ID = "20261124-main-co-workbench-m4"
DEV = ("cvrp_dev_hetero_24", "dev_train", "diagnostic_interactive")
SELECT = (("cvrp_select_multiscale_64", "selection", "selection_tuning"),)
REQUEST_CAP, SOLVE_MS, BOOTSTRAPS = 36, 500.0, 10_000
DEFAULT_OUTPUT = REPO / "experiments" / "milestone3_5"
FORK = "common_start_manifest.json"
ROSTER = "m35_fork_roster.json"
CANDIDATES = "frozen_candidate_roster.json"
EVALUATIONS = {"select": "select_evaluation.json", "external": "external_evaluation.json"}
REPORT = "m35_ablation_report.json"
L3_RELEASE_ROOT = "runs/dream/l3_release"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected_object:{path.name}")
    return value


def _digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _inside(root: Path, reference: str) -> Path:
    rel = Path(reference)
    destination = (root / rel).resolve()
    if rel.is_absolute() or not destination.is_relative_to(root.resolve()):
        raise ValueError(f"m35_artifact_outside_root:{rel.name}")
    return destination


def _output(args: argparse.Namespace) -> Path:
    root = args.output_dir.resolve()
    forbidden = {"knowledge_store", "eoh_frozen", "eohs_v1", ".env", ".secrets", ".agent_skill_custody"}
    if forbidden.intersection(part.casefold() for part in root.parts):
        raise ValueError("m35_output_in_protected_location")
    return root


def _suite(spec: tuple[str, str, str]) -> dict[str, Any]:
    suite_id, split, role = spec
    return load_dev_or_public_suite(suite_id, split=split, role=role)


def _arm_configuration(root: Path, fork: Mapping[str, Any], arm: str) -> AgentConfig:
    seed = fork["seed"]
    mode = ARMS[arm]
    run_dir = _inside(root, f"runs/{seed}/{arm}")
    experiment = fork["agent"]
    kb = fork["memory"].get("l3_release", fork["kb"]) if arm == ARM_3 else fork["kb"]
    return AgentConfig.from_dict({
        **experiment,
        "run_id": f"{arm}_s{seed}",
        "output_dir": str(run_dir),
        "arm_id": arm,
        "search_seed": seed,
        "kb_enabled": arm != ARM_0,
        "kb_store_path": kb["release_dir"] if arm != ARM_0 else None,
        "pinned_kb_release_id": kb["release_id"] if arm != ARM_0 else None,
        "pinned_kb_manifest_sha256": kb["manifest_sha256"] if arm != ARM_0 else None,
        "memory_enabled": arm != ARM_0,
        "memory_mode": mode,
        "memory_store_path": str(run_dir / "memory") if arm != ARM_0 else None,
    })


def _endpoint(mode: str) -> str:
    if mode == "mock":
        return "mock://local"
    value = os.environ.get(ENDPOINT_ENV, "").strip()
    address = urlsplit(value)
    if (address.scheme != "https" or not address.hostname or address.username is not None
            or address.password is not None or address.query or address.fragment):
        raise ValueError(f"{ENDPOINT_ENV}_must_be_https_endpoint_without_credentials")
    return value


def _agent_settings(mode: str) -> dict[str, Any]:
    mock = mode == "mock"
    return {
        "problem_family": "cvrp", "planner_model": MODEL, "eoh_model": MODEL,
        "mode": mode, "endpoint": _endpoint(mode), "api_key_env": API_KEY_ENV,
        "max_rounds": 1 if mock else 8, "wall_seconds": 1200.0 if mock else 14400.0, "request_timeout_s": 60.0,
        "total_request_cap": REQUEST_CAP, "checkpoint_budgets": [REQUEST_CAP],
        "strict_checkpoint_barriers": True, "instance_time_budget_ms": SOLVE_MS,
        "use_benchmark_dev_suite": True, "dev_suite_id": DEV[0], "dev_split": DEV[1],
        "dev_instance_count": 24, "initial_template_id": "cvrp_parallel_merge_static",
        "initial_postprocess_mode": "none", "outer_requests_per_round_cap": 4, "outer_reflect_cap": 2,
        "eoh_pop_size": 2 if mock else 4, "eoh_n_pop": 1 if mock else 2,
        "eoh_max_sample_nums": 2 if mock else 30,
        "allow_extended_numpy_whitelist": True, "enable_n200_latency_screen": True,
        "enable_degenerate_constant_screen": True, "enable_stagnation_diagnostic_gate": True,
        "early_stop_no_jump_requests": 24, "basin_restart_on_stagnation": True,
        "memory_max_solution_cards": 1, "memory_mmr_lambda": 0.7, "memory_cooldown_rounds": 2,
    }


def _evaluate(solver: FrozenInterfaceSolver | None, instance: Mapping[str, Any], suite: Mapping[str, Any]) -> dict[str, Any]:
    result = {} if solver is None else evaluate_public_frozen_solver(solver, instance, suite, solve_deadline_ms=SOLVE_MS)
    if result.get("error_code") in {"worker_protocol", "worker_crash", "worker_start_failed"}:
        raise RuntimeError(f"m35_evaluation_worker_failure:{suite['suite_id']}:{result['error_code']}")
    has_target = instance.get("k_vehicles") is not None or instance.get("max_vehicles") is not None
    return build_m5_public_record(instance, result, exact_k_applicable=has_target, solve_deadline_ms=SOLVE_MS)


def _common_start(settings: Mapping[str, Any], suite: Mapping[str, Any]) -> dict[str, Any]:
    config = AgentConfig.from_dict({**settings, "run_id": "m35_common_start", "output_dir": "."})
    solver = _build_initial_baseline_solver(config)
    rows = [_evaluate(solver, item, suite) for item in suite["instances"]]
    valid = [row["objective"] for row in rows if _completed(row)]
    if not rows or not valid:
        raise ValueError("m35_initial_baseline_has_no_completed_dev_evidence")
    return {
        "frozen_solver": solver.to_dict(),
        "baseline_dev_eval": {
            "instance_count": len(rows), "valid_count": len(valid), "completion_rate": round(len(valid) / len(rows), 6),
            "all_feasible": len(valid) == len(rows), "valid_only_mean_objective": round(sum(valid) / len(valid), 6),
            "penalized_mean_objective": round(sum(_penalized(row) for row in rows) / len(rows), 6),
        },
        "dev_suite_hash": _digest(suite["instances"]),
        "checkpoint": {
            "schema_version": AgentCheckpoint().schema_version, "phase": "diagnose", "current_round": 1,
            "completed_rounds": [], "archive": [], "hypotheses": [], "initial_population": [],
            "initial_incumbent_ordinal": 0, "attempted_requests": 0,
        },
    }


def _store_card_files(store: Path) -> list[Path]:
    if store.is_symlink() or store.resolve() != store:
        raise ValueError("m35_memory_store_link")
    if not store.is_dir():
        raise FileNotFoundError(f"m35_memory_store_missing:{store.name}")
    files = []
    for path in sorted(store.glob("*/*")):
        if path.is_symlink() or path.resolve() != path or not path.resolve().is_relative_to(store):
            raise ValueError("m35_memory_store_link")
        if path.is_file() and path.name != "MEMORY.md" and path.suffix in {".md", ".json"}:
            files.append(path)
    return files


def _store_digest(store: Path) -> str:
    return _digest({path.relative_to(store).as_posix(): sha256_file(path) for path in _store_card_files(store)})


def _read_card(store: MemoryAPI, reference: str) -> dict[str, Any]:
    card = store.read_version(reference, require_active=True)
    offset = card["next_offset"]
    while offset is not None:
        page = store.read_version(reference, require_active=True, offset=offset)
        if page["body_sha256"] != card["body_sha256"]:
            raise ValueError("m35_seed_card_mutated_during_read")
        card["body"] += page["body"]
        offset = page["next_offset"]
    return card


def _promote_dev_kb(root: Path, dream: Mapping[str, Any]) -> dict[str, str]:
    """Publish only this fork's authorized dev cards in a standalone KB release."""
    release_root = root / L3_RELEASE_ROOT
    if release_root.resolve() != release_root:
        raise ValueError("m35_l3_release_root_link")
    dream_root = release_root.parent
    manifest_sha = sha256_file(dream_root / "auto_dream_manifest.json")
    staging_path = dream_root / "l3_promotion_candidates.json"
    staging_bytes = staging_path.read_bytes()
    staging = json.loads(staging_bytes)
    if (staging.get("schema_version") != "m35-l3-promotion-candidates/v1"
            or staging.get("source_split") != "dev" or staging.get("activation") != "staged"
            or staging.get("auto_dream_manifest_sha256") != manifest_sha
            or dream.get("source_split") != "dev" or staging.get("candidates") != dream["cards"]):
        raise ValueError("m35_l3_promotion_evidence_mismatch")

    candidates_sha = sha256_bytes(staging_bytes)
    release_id = f"m35-dev-{candidates_sha[:24]}"
    release_dir = release_root / release_id
    release_root.mkdir(parents=True, exist_ok=True)
    api = MemoryAPI(dream_root / "memory")
    with TemporaryDirectory(prefix=".staging-", dir=release_root) as tmp:
        stage = Path(tmp) / release_id
        (stage / "entries").mkdir(parents=True)
        (stage / staging_path.name).write_bytes(staging_bytes)
        entries = []
        for candidate in staging["candidates"]:
            card = _read_card(api, candidate["reference"])
            provenance = card["provenance"]
            if (card["project"] != "cvrp_construct" or provenance.get("source_split") != "dev"
                    or provenance.get("claim_evidence_manifest_sha256") != _digest(candidate["claim_evidence_manifest"])):
                raise ValueError("m35_l3_card_evidence_mismatch")
            claims = candidate["claim_evidence_manifest"]["claims"]
            if card["type"] == "solution":
                try:
                    canonical_sha = solution_execution_ast_sha256(card["body"])
                except (SyntaxError, ValueError) as exc:
                    raise ValueError("m35_l3_solution_code_mismatch") from exc
                if (not claims or (card.get("code_anchor") or {}).get("canonical_ast_sha256") != canonical_sha
                        or any(claim["code_anchor"].get("canonical_ast_sha256") != canonical_sha for claim in claims)):
                    raise ValueError("m35_l3_solution_code_mismatch")
            entry_id = f"evidence-m35-{card['name']}"
            rel = f"entries/{entry_id}.md"
            body_bytes = card["body"].encode("utf-8")
            if sha256_bytes(body_bytes) != card["body_sha256"]:
                raise ValueError("m35_l3_card_digest_mismatch")
            (stage / rel).write_bytes(body_bytes)
            entries.append({
                "id": entry_id, "path": rel, "title": card["description"], "summary": card["description"],
                "type": "evidence", "category": "dev-memory", "problem_family": "cvrp",
                "tags": ["m35", "auto-dream", "dev", card["type"]], "content_sha256": card["body_sha256"],
                "evidence_refs": [claim["evidence_ref"] for claim in claims],
                "attributes": {"knowledge_tier": "l3", "source_split": "dev", "memory_reference": card["reference"],
                               "applicability_scope": card["applicability_scope"], "code_anchor": card["code_anchor"]},
            })
        atomic_write_json(stage / "index.json", {
            "schema_version": KB_SCHEMA_VERSION, "release_id": release_id, "entries": entries,
        })
        files = [{"path": path.relative_to(stage).as_posix(), "sha256": sha256_file(path), "size": path.stat().st_size}
                 for path in sorted(stage.rglob("*")) if path.is_file()]
        digest = atomic_write_json(stage / "manifest.json", {
            "schema_version": KB_SCHEMA_VERSION, "release_id": release_id, "files": files,
            "self_hash_file": "manifest.sha256", "source_split": "dev", "content_digest": _digest(files),
            "auto_dream_manifest_sha256": manifest_sha, "l3_promotion_candidates_sha256": candidates_sha,
        })
        (stage / "manifest.sha256").write_text(f"{digest}  manifest.json\n", encoding="utf-8", newline="\n")
        if release_dir.resolve() != release_dir:
            raise ValueError("m35_l3_release_link")
        if not release_dir.exists():
            verify_pinned_release(stage, release_id=release_id, manifest_sha256=digest)
            stage.rename(release_dir)
        else:
            verify_pinned_release(release_dir, release_id=release_id, manifest_sha256=digest)
    return {"release_dir": str(release_dir), "release_id": release_id, "manifest_sha256": digest}


def _mock_memory(root: Path, start: Mapping[str, Any], suite: Mapping[str, Any]) -> tuple[list[Path], list[Path]]:
    store = root / "mock_dev_memory"
    solver = start["frozen_solver"]
    scope = {
        "problem": "cvrp_construct", "interface_id": solver["template_id"],
        "fleet_policy": suite["vehicle_limit_policy"], "evaluator_version": evaluator_source_hash(),
        "n_range": [1, 2000], "budget_ms_range": [500, 500],
    }
    anchor = {"code_sha256": solver["hook_code_sha256"]}
    evidence_ref = "dev/ordinal_0"
    facts = {
        "problem": scope["problem"], "evaluator_version": scope["evaluator_version"],
        "interface_id": scope["interface_id"], "fleet_policy": scope["fleet_policy"],
        "evidence_refs": [evidence_ref], "candidates": [anchor],
    }
    facts_sha = _digest(facts)
    entry = MemoryEntry(
        "scale-invariant-dev-baseline", "CVRP scale-invariant merge ranking", "insight",
        scope["problem"], get_problem(scope["problem"]).entrypoint,
        "### Why\n**Why:** Compare the normalized construction score on the fixed dev suite.\n"
        "**How to apply:** Preserve scale invariance and evaluate each candidate against the ordinal-zero solver.",
        code_anchor=anchor, evidence_tier="single_run", validity_status="active",
    )
    result = MemoryAPI(store).write(
        entry, format_version=3, operation_key="m35_mock_dev_baseline",
        provenance={"evaluation_facts_sha256": facts_sha, "evidence_ref": evidence_ref},
    )
    artifact = root / "mock_dev_evidence.json"
    atomic_write_json(artifact, {
        "split": "dev_train", "suite_id": DEV[0], "evaluation_facts": facts,
        "claims": [{
            "claim_id": "dev-scale-invariant-baseline", "source_reference": result["reference"],
            "applicability_scope": scope, "code_anchor": anchor, "denominators": {
                "instances": start["baseline_dev_eval"]["instance_count"],
                "completed": start["baseline_dev_eval"]["valid_count"],
            },
            "adverse_results": ["One baseline trajectory provides limited evidence."], "contradictions": [],
            "evaluation_facts_sha256": facts_sha, "evidence_ref": evidence_ref,
            "hook_code": solver["hook_code"],
        }],
    })
    return [store], [artifact]


def _prepare_memory(root: Path, source_stores: Sequence[Path], dev_artifacts: Sequence[Path]) -> dict[str, Any]:
    baseline = root / "baseline_memory"
    full = root / "dream" / "memory"
    dream = auto_dream(
        source_stores=source_stores, dev_artifacts=dev_artifacts,
        output_store=full, output_dir=root / "dream",
    )
    baseline_store = MemoryAPI(baseline)
    sources = [MemoryAPI(path) for path in source_stores]
    seen: set[str] = set()
    for card in dream["cards"]:
        claims = card["claim_evidence_manifest"]["claims"]
        for claim in claims:
            ref = card["source_bindings"].get(claim["claim_id"])
            if ref is None or ref in seen:
                continue
            records = []
            for store in sources:
                try:
                    records.append(_read_card(store, ref))
                except FileNotFoundError:
                    continue
            if len(records) != 1:
                raise ValueError("m35_dev_source_card_missing_or_ambiguous")
            source = records[0]
            entry = MemoryEntry(**{key: source[key] for key in MemoryEntry.__dataclass_fields__ if key in source})
            baseline_store.write(
                entry, format_version=3, operation_key=f"m35_baseline:{ref}",
                provenance={
                    **{key: source["provenance"][key] for key in (
                        "candidate_code_sha256", "canonical_ast_sha256", "parent_version_id", "interface_id",
                        "evaluator_hash", "prefix_trace_equal",
                    ) if key in source["provenance"]},
                    **{key: claim[key] for key in ("evaluation_facts_sha256", "evidence_ref")},
                },
            )
            seen.add(ref)
    if not seen or not dream["cards"]:
        raise ValueError("m35_requires_admitted_dev_source_cards")
    return {
        "baseline": {"path": "baseline_memory", "sha256": _store_digest(baseline)},
        "full": {"path": "dream/memory", "sha256": _store_digest(full)},
        "auto_dream_manifest_sha256": sha256_file(root / "dream" / "auto_dream_manifest.json"),
        "l3_promotion_candidates_sha256": sha256_file(root / "dream" / "l3_promotion_candidates.json"),
        "l3_release": _promote_dev_kb(root.parent, dream),
    }


def _emit(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, indent=2, allow_nan=False))


def cmd_build_dev_seed(args: argparse.Namespace) -> int:
    import ast

    load_local_env()
    root = _output(args)
    seed_root = _inside(root, "dev_seed")
    source_store = seed_root / "source_memory"
    artifact = seed_root / "dev_evidence.json"
    suite = _suite(DEV)
    instances = list(suite["instances"])
    limit = getattr(args, "instance_limit", None)
    if limit is not None:
        instances = instances[: max(1, int(limit))]
    eval_suite = {**suite, "instances": instances}
    templates = AgentConfig("seed", ".").allowed_templates
    evaluator_version = evaluator_source_hash()
    spec = get_problem("cvrp_construct")
    fleet_policy = suite["vehicle_limit_policy"]
    measured: list[dict[str, Any]] = []
    for template_id in templates:
        cfg = AgentConfig.from_dict({
            "run_id": f"dev_seed_{template_id}",
            "output_dir": ".",
            "problem_family": "cvrp",
            "initial_template_id": template_id,
            "initial_postprocess_mode": "none",
            "instance_time_budget_ms": SOLVE_MS,
            "kb_enabled": False,
        })
        solver = _build_initial_baseline_solver(cfg)
        rows = [_evaluate(solver, inst, eval_suite) for inst in instances]
        valid_objs = [float(r["objective"]) for r in rows if _completed(r)]
        penalized_mean = sum(_penalized(r) for r in rows) / len(rows)
        canonical_ast_sha = sha256_text(ast.unparse(ast.parse(solver.hook_code)))
        measured.append({
            "template_id": template_id,
            "evaluation_id": f"dev_ordinal0_{template_id}",
            "evidence_ref": f"evaluation:dev_ordinal0_{template_id}",
            "code_sha256": solver.hook_code_sha256,
            "canonical_ast_sha256": canonical_ast_sha,
            "instance_count": len(rows),
            "valid_count": len(valid_objs),
            "penalized_mean": penalized_mean,
            "valid": bool(valid_objs),
        })
    best_tpl = min(measured, key=lambda item: item["penalized_mean"])
    worst_tpl = max(measured, key=lambda item: item["penalized_mean"])
    facts = {
        "problem": spec.problem_id,
        "split": DEV[1],
        "suite_id": DEV[0],
        "evaluator_version": evaluator_version,
        "fleet_policy": fleet_policy,
        "evidence_refs": [item["evidence_ref"] for item in measured],
        "candidates": [
            {
                "evaluation_id": item["evaluation_id"],
                "interface_id": item["template_id"],
                "code_sha256": item["code_sha256"],
                "canonical_ast_sha256": item["canonical_ast_sha256"],
                "objective": item["penalized_mean"],
                "valid": item["valid"],
            }
            for item in measured
        ],
    }
    facts_sha = _digest(facts)
    api = MemoryAPI(source_store)
    claims: list[dict[str, Any]] = []
    for item in measured:
        tpl_id = item["template_id"]
        anchor = {"code_sha256": item["code_sha256"], "canonical_ast_sha256": item["canonical_ast_sha256"]}
        entry = MemoryEntry(
            name=f"dev-baseline-{tpl_id.replace('_', '-')}",
            description=f"CVRP {tpl_id} baseline dev_train benchmark ({item['penalized_mean']:.4f}).",
            type="insight",
            project=spec.problem_id,
            scene=spec.entrypoint,
            body=(
                f"**Why:** Evaluated stock {tpl_id} on {item['instance_count']} authorized dev_train cases "
                f"({item['valid_count']}/{item['instance_count']} valid, penalized mean {item['penalized_mean']:.4f}; "
                f"best baseline is {best_tpl['template_id']} at {best_tpl['penalized_mean']:.4f}).\n"
                "**How to apply:** Use verified dev differences across templates to prioritize constructive vs ruin-recreate updates while keeping interface constraints intact.\n"
                "**Limitations:** Baseline-only dev observation; verify any evolved candidate on the same evaluator."
            ),
            code_anchor=anchor,
            evidence_tier="single_run",
            validity_status="active",
        )
        written = api.write(
            entry,
            format_version=3,
            operation_key=f"m35_dev_seed:{tpl_id}:{evaluator_version}",
            provenance={"evaluation_facts_sha256": facts_sha, "evidence_ref": item["evidence_ref"]},
        )
        adverse = [f"Valid {item['valid_count']}/{item['instance_count']} cases on {DEV[0]} at 500ms."]
        if item["valid_count"] < item["instance_count"]:
            adverse.append(f"{item['instance_count'] - item['valid_count']} dev cases incomplete/penalized.")
        contradictions = []
        if tpl_id != best_tpl["template_id"]:
            contradictions.append(
                f"Underperformed best stock template {best_tpl['template_id']} ({best_tpl['penalized_mean']:.4f} vs {item['penalized_mean']:.4f})."
            )
        else:
            contradictions.append(
                f"Stock comparison span against {worst_tpl['template_id']} ({worst_tpl['penalized_mean']:.4f})."
            )
        claims.append({
            "claim_id": f"dev-baseline-{tpl_id}",
            "source_reference": written["reference"],
            "applicability_scope": {
                "problem": spec.problem_id,
                "interface_id": tpl_id,
                "fleet_policy": fleet_policy,
                "evaluator_version": evaluator_version,
                "n_range": [1, 2000],
                "budget_ms_range": [SOLVE_MS, SOLVE_MS],
            },
            "denominators": {"attempted": item["instance_count"], "valid": item["valid_count"]},
            "adverse_results": adverse,
            "contradictions": contradictions,
            "code_anchor": anchor,
            "evaluation_facts_sha256": facts_sha,
            "evidence_ref": item["evidence_ref"],
        })
    atomic_write_json(
        artifact,
        {"split": DEV[1], "suite_id": DEV[0], "evaluation_facts": facts, "claims": claims},
    )
    payload = {
        "source_store": str(source_store),
        "dev_artifact": str(artifact),
        "template_count": len(templates),
        "evaluator_version": evaluator_version,
    }
    _emit(payload)
    return 0


def cmd_init_fork(args: argparse.Namespace) -> int:
    load_local_env()
    root = _output(args)
    runs = root / "runs"
    with exclusive_file_lock(runs / "init_fork.lock", busy="m35_fork_initialization_busy"):
        if (runs / ROSTER).exists():
            raise FileExistsError("m35_fork_already_frozen")
        seeds = sorted(set(args.seed or SEEDS))
        settings = _agent_settings(args.mode)
        kb = verify_pinned_release(REPO / "knowledge_store" / "current", release_id=RELEASE_ID)
        suite = _suite(DEV)
        common = _common_start(settings, suite)
        stores, dev_artifacts = args.source_store, args.dev_artifact
        if not stores and not dev_artifacts and args.mode == "mock":
            stores, dev_artifacts = _mock_memory(runs, common, suite)
        if not stores or not dev_artifacts:
            raise ValueError("m35_init_requires_source_stores_and_authorized_dev_artifacts")
        memory = _prepare_memory(runs, stores, dev_artifacts)
        forks = {}
        for seed in seeds:
            launch_order = list(ARMS)
            random.Random(seed).shuffle(launch_order)
            forks[str(seed)] = atomic_write_json(runs / str(seed) / FORK, {
                "schema_version": "m35-common-start/v1", "seed": seed, "agent": settings,
                "provider": {"name": "Paratera", "endpoint_env": ENDPOINT_ENV, "api_key_env": API_KEY_ENV},
                "kb": {"release_dir": kb["release"], "release_id": RELEASE_ID, "manifest_sha256": kb["manifest_sha256"]},
                "common_start": common, "common_start_sha256": _digest(common),
                "memory": memory, "arm_launch_order": launch_order,
                "arms": {
                    arm: {
                        "memory_mode": mode, "memory_enabled": arm != ARM_0, "kb_enabled": arm != ARM_0,
                        "auto_dream": arm == ARM_3,
                        "initial_memory_sha256": None if arm == ARM_0 else memory["full" if arm == ARM_3 else "baseline"]["sha256"],
                        "memory_store": None if arm == ARM_0 else f"runs/{seed}/{arm}/memory",
                    } for arm, mode in ARMS.items()
                },
            })
        atomic_write_json(runs / ROSTER, {
            "schema_version": "m35-fork-roster/v1", "mode": args.mode, "forks": forks,
            "analysis_plan": {
                "inference_unit": "paired_instances_within_seed", "contrasts": CONTRASTS,
                "holm_bonferroni_families": "contrasts within each suite, seed, fleet and denominator",
                "bootstrap_replicates": BOOTSTRAPS,
                "overall_failure_penalty": "twice_reference_objective",
                "common_completed": "intersection of completed, feasible, within-budget paired runs",
                "exact_k": "strict equality with the published target where one exists",
            },
        })
    _emit({"fork_roster": str(runs / ROSTER), "seeds": seeds})
    return 0


def _forks(root: Path) -> dict[int, dict[str, Any]]:
    roster = _json(root / "runs" / ROSTER)
    if roster.get("schema_version") != "m35-fork-roster/v1":
        raise ValueError("m35_invalid_fork_roster")
    entries = roster["forks"]
    if not entries or set(entries) - {str(seed) for seed in SEEDS}:
        raise ValueError("m35_invalid_fork_seeds")
    result = {}
    checked_l3 = set()
    for seed, digest in entries.items():
        path = _inside(root, f"runs/{seed}/{FORK}")
        if sha256_file(path) != digest:
            raise ValueError(f"m35_fork_manifest_digest_mismatch:{seed}")
        fork = _json(path)
        if (fork.get("schema_version") != "m35-common-start/v1" or fork.get("seed") != int(seed)
                or fork["common_start_sha256"] != _digest(fork["common_start"])
                or fork["agent"]["mode"] != roster["mode"] or set(fork["arms"]) != set(ARMS)
                or sorted(fork["arm_launch_order"]) != sorted(ARMS)):
            raise ValueError(f"m35_invalid_fork_manifest:{seed}")
        l3 = fork["memory"].get("l3_release")
        if l3 is not None:
            release = root / L3_RELEASE_ROOT / l3["release_id"]
            candidates_sha = fork["memory"]["l3_promotion_candidates_sha256"]
            dream_sha = fork["memory"]["auto_dream_manifest_sha256"]
            if (l3["release_id"] != f"m35-dev-{candidates_sha[:24]}" or Path(l3["release_dir"]) != release
                    or _inside(root, f"{L3_RELEASE_ROOT}/{l3['release_id']}") != release):
                raise ValueError("m35_l3_release_outside_fork")
            pin = (release, l3["manifest_sha256"], candidates_sha, dream_sha)
            if pin not in checked_l3:
                verify_pinned_release(release, release_id=l3["release_id"], manifest_sha256=l3["manifest_sha256"])
                manifest = _json(release / "manifest.json")
                if (manifest.get("source_split") != "dev" or manifest.get("l3_promotion_candidates_sha256") != candidates_sha
                        or manifest.get("auto_dream_manifest_sha256") != dream_sha
                        or sha256_file(release / "l3_promotion_candidates.json") != candidates_sha):
                    raise ValueError("m35_l3_release_evidence_mismatch")
                checked_l3.add(pin)
        result[int(seed)] = fork
    return result


def cmd_emit_mux(args: argparse.Namespace) -> int:
    root = _output(args)
    panes = []
    for seed, fork in _forks(root).items():
        for arm in fork["arm_launch_order"]:
            panes.append({
                "id": f"{arm}_s{seed}", "cwd": str(REPO),
                "command": [sys.executable, str(Path(__file__).resolve()), "--output-dir", str(root),
                            "run-arm", "--seed", str(seed), "--arm", arm, "--resume"],
            })
    path = root / "mux_m35.json"
    atomic_write_json(path, {"panes": panes})
    _emit({"manifest_path": str(path), "pane_count": len(panes)})
    return 0


def _install_arm_memory(root: Path, fork: Mapping[str, Any], config: AgentConfig) -> None:
    if not config.memory_enabled:
        return
    run_dir = Path(config.output_dir)
    draft = fork["memory"]["full" if config.arm_id == ARM_3 else "baseline"]
    src = _inside(root, f"runs/{draft['path']}")
    dst = Path(config.memory_store_path)
    receipt = run_dir / "initial_memory_receipt.json"
    expected = {"sha256": draft["sha256"], "common_start_sha256": fork["common_start_sha256"]}
    if receipt.is_file():
        if _json(receipt) != expected or not dst.is_dir() or dst.resolve() != dst:
            raise ValueError("m35_arm_memory_receipt_mismatch")
        if (run_dir / "agent_checkpoint.json").is_file():
            return  # This arm owns all later mutations to its private store.
    if _store_digest(src) != draft["sha256"]:
        raise ValueError("m35_seed_memory_digest_mismatch")
    for path in _store_card_files(src):
        target = _inside(dst, path.relative_to(src).as_posix())
        if target.is_file():
            if sha256_file(target) != sha256_file(path):
                raise ValueError("m35_existing_arm_memory_mismatch")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    if _store_digest(dst) != draft["sha256"]:
        raise ValueError("m35_arm_memory_copy_digest_mismatch")
    atomic_write_json(receipt, expected)


def cmd_run_arm(args: argparse.Namespace) -> int:
    load_local_env()
    root = _output(args)
    fork = _forks(root).get(args.seed)
    if fork is None:
        raise ValueError(f"m35_unregistered_seed:{args.seed}")
    config = _arm_configuration(root, fork, args.arm)
    if config.mode == "live" and (
        _endpoint(config.mode) != config.endpoint or not os.environ.get(API_KEY_ENV, "").strip()
        or os.environ.get("AGENT_SKILL_M2_MOCK") == "1"
    ):
        raise ValueError("m35_paratera_environment_does_not_match_frozen_configuration")
    run_dir = Path(config.output_dir)
    with exclusive_file_lock(run_dir / "run_arm.lock", busy="m35_arm_run_busy"):
        if (root / "runs" / CANDIDATES).exists():
            raise ValueError("m35_candidates_already_frozen")
        checkpoint = run_dir / "agent_checkpoint.json"
        if checkpoint.is_file() and not args.resume:
            raise FileExistsError("m35_run_exists_use_resume")
        _install_arm_memory(root, fork, config)
        try:
            summary = run_research_agent(config, resume=checkpoint.is_file(), common_start=fork["common_start"])
        except ProviderFailure as exc:
            atomic_write_json(run_dir / "run_interrupt_status.json", {"status": "resumable", "reason": exc.error_code})
            _emit({"run_id": config.run_id, "status": "resumable", "reason": exc.error_code})
            return 75
    _emit({"run_id": config.run_id, "status": summary["final_phase"], "feature_count": summary.get("feature_count", 0)})
    return 0


def _check_ordinal_zero(run_dir: Path, run_id: str, common_start: Mapping[str, Any]) -> None:
    ledger = run_dir / "agent_budget.sqlite3"
    with closing(sqlite3.connect(f"{ledger.as_uri()}?mode=ro", uri=True)) as con:
        row = con.execute(
            "SELECT solver_manifest_json, dev_suite_hash, solve_budget_ms, dev_completion_rate, "
            "dev_penalized_mean, dev_valid_mean, dev_all_feasible FROM candidate_provenance "
            "WHERE run_id=? AND global_ordinal=0 AND generation_status='baseline_seed'", (run_id,),
        ).fetchone()
    expected = common_start["baseline_dev_eval"]
    if (row is None or json.loads(row[0]) != common_start["frozen_solver"] or row[1:] != (
        common_start["dev_suite_hash"], SOLVE_MS, expected["completion_rate"], expected["penalized_mean_objective"],
        expected["valid_only_mean_objective"], int(expected["all_feasible"]),
    )):
        raise ValueError(f"m35_ordinal_zero_mismatch:{run_id}")


def _read_arm_champion(run_dir: Path, run_id: str, arm: str, seed: int, cap: int) -> tuple[bytes | None, dict[str, Any]]:
    cell = f"{arm}:{seed}"
    summary = _json(run_dir / "research_summary.json")
    phase = summary.get("final_phase")
    if phase not in TERMINAL_PHASES or summary.get("run_id") != run_id:
        raise ValueError(f"cannot_lock_non_terminal_or_mismatched_run:{cell}")
    checkpoint = run_dir / "checkpoints" / f"frozen_checkpoint_{cap}.json"
    with closing(_open_ledger(run_dir / "agent_budget.sqlite3")) as db:
        row = db.execute(
            "SELECT state, payload_sha256, winner_source_ordinal, settled_through_ordinal "
            "FROM milestone_checkpoints WHERE run_id=? AND ckpt_budget=?", (run_id, cap),
        ).fetchone()
        requests = db.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (run_id,)).fetchone()[0]
    metadata = {"final_phase": phase, "attempted_requests": requests}
    if checkpoint.is_file():
        data = checkpoint.read_bytes()
        if row is None or row["state"] != "sealed":
            raise ValueError(f"cannot_lock_unsealed_checkpoint:{cell}")
        if sha256_bytes(data) != row["payload_sha256"]:
            raise ValueError(f"checkpoint_sqlite_sha256_mismatch:{cell}")
        payload = json.loads(data)
        if (
            payload["run_id"] != run_id or payload["checkpoint_budget"] != cap
            or payload["winner_source_ordinal"] != row["winner_source_ordinal"]
            or payload["settled_through_ordinal"] != row["settled_through_ordinal"]
            or row["settled_through_ordinal"] != cap
        ):
            raise ValueError(f"checkpoint_identity_mismatch:{cell}")
        candidate = payload.get("frozen_solver")
        if candidate is not None:
            serialized = (json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
            return serialized, {
                **metadata, "winner_source": f"sealed_checkpoint_{cap}",
                "winner_source_ordinal": row["winner_source_ordinal"],
                "source_sha256": row["payload_sha256"],
            }
    elif row is not None and row["state"] == "sealed":
        raise FileNotFoundError(f"sealed_checkpoint_export_missing:{cell}")
    ref = summary.get("best_solver_manifest_ref")
    if ref:
        if phase not in {"completed", "budget_stopped"} or requests >= cap:
            raise ValueError(f"ineligible_agent_best_solver_fallback:{cell}")
        manifest = Path(ref)
        if manifest.is_absolute() or not (path := (run_dir / manifest).resolve()).is_relative_to(run_dir):
            raise ValueError(f"agent_best_solver_ref_outside_run:{cell}")
        data = path.read_bytes()
        return data, {**metadata, "winner_source": "agent_best_solver", "source_sha256": sha256_bytes(data)}
    if phase == "no_champion":
        return None, metadata
    raise ValueError(f"terminal_run_missing_champion:{cell}")


def _candidate_roster(root: Path, forks: Mapping[int, dict[str, Any]]) -> dict[str, Any]:
    path = root / "runs" / CANDIDATES
    roster_digest = sha256_file(root / "runs" / ROSTER)
    if path.is_file():
        roster = _json(path)
        if roster.get("fork_roster_sha256") != roster_digest:
            raise ValueError("m35_candidate_roster_fork_binding_mismatch")
        return roster
    with ExitStack() as stack:
        configs = [_arm_configuration(root, fork, arm) for fork in forks.values() for arm in ARMS]
        for config in configs:
            run_dir = Path(config.output_dir)
            if not (run_dir / "research_summary.json").is_file():
                raise FileNotFoundError(f"m35_missing_arm_summary:{config.run_id}")
            stack.enter_context(exclusive_file_lock(run_dir / "run_arm.lock", busy="m35_arm_run_busy"))
        cells = {}
        for config in configs:
            run_dir = Path(config.output_dir)
            if AgentConfig.from_dict(_json(run_dir / "agent_config.json")) != config:
                raise ValueError(f"m35_arm_config_mismatch:{config.run_id}")
            _check_ordinal_zero(run_dir, config.run_id, forks[config.search_seed]["common_start"])
            data, outcome = _read_arm_champion(run_dir, config.run_id, config.arm_id, config.search_seed, REQUEST_CAP)
            if outcome["attempted_requests"] > REQUEST_CAP:
                raise ValueError(f"m35_request_cap_exceeded:{config.run_id}")
            cell = {"winner": None, "summary_sha256": sha256_file(run_dir / "research_summary.json"), "outcome": outcome}
            if data is not None:
                winner = FrozenInterfaceSolver.from_dict(json.loads(data))
                if winner.problem_family != config.problem_family or winner.template_id not in config.allowed_templates:
                    raise ValueError(f"m35_candidate_interface_not_registered:{config.run_id}")
                ref = f"runs/{config.search_seed}/{config.arm_id}/ablation_frozen_candidate.json"
                cell["winner"] = {"ref": ref, "sha256": atomic_write_json(_inside(root, ref), winner.to_dict())}
            cells[f"{config.search_seed}:{config.arm_id}"] = cell
        roster = {"schema_version": "m35-frozen-candidate-roster/v1", "fork_roster_sha256": roster_digest, "cells": cells}
        atomic_write_json(path, roster)
    return roster


def _solvers(root: Path, roster: Mapping[str, Any], forks: Mapping[int, Any]) -> dict[str, FrozenInterfaceSolver | None]:
    cells = roster["cells"]
    if (roster.get("schema_version") != "m35-frozen-candidate-roster/v1"
            or set(cells) != {f"{seed}:{arm}" for seed in forks for arm in ARMS}):
        raise ValueError("m35_frozen_candidate_roster_incomplete")
    solvers = {}
    for key, cell in cells.items():
        seed, arm = key.split(":")
        config = _arm_configuration(root, forks[int(seed)], arm)
        summary = Path(config.output_dir) / "research_summary.json"
        if sha256_file(summary) != cell["summary_sha256"]:
            raise ValueError(f"m35_frozen_summary_mutated:{key}")
        info = cell["winner"]
        solvers[key] = None
        if info is not None:
            path = _inside(root, info["ref"])
            if path.parent != Path(config.output_dir) or sha256_file(path) != info["sha256"]:
                raise ValueError(f"m35_frozen_candidate_mutated:{key}")
            solvers[key] = FrozenInterfaceSolver.from_dict(_json(path))
    return solvers


def _eval(args: argparse.Namespace, name: str, specs: Sequence[tuple[str, str, str]]) -> int:
    root = _output(args)
    forks = _forks(root)
    roster_file = root / "runs" / CANDIDATES
    if name == "external" and not (root / "runs" / EVALUATIONS["select"]).is_file():
        raise FileNotFoundError("m35_eval_select_required_before_eval_external")
    roster = _candidate_roster(root, forks)
    solvers = _solvers(root, roster, forks)
    roster_sha = sha256_file(roster_file)
    if name == "external":
        _verified_evaluation(root, "select", roster_sha, SELECT)
    path = root / "runs" / EVALUATIONS[name]
    with exclusive_file_lock(path.with_suffix(".lock"), busy=f"m35_{name}_evaluation_busy"):
        if path.is_file():
            _verified_evaluation(root, name, roster_sha, specs)
        else:
            suites = {}
            mock = next(iter(forks.values()))["agent"]["mode"] == "mock"
            for spec in specs:
                suite = _suite(spec)
                instances = suite["instances"][:3] if mock else suite["instances"]
                suites[spec[0]] = {
                    "split": spec[1], "vehicle_limit_policy": suite["vehicle_limit_policy"],
                    "instance_count": len(instances), "instance_set_sha256": _digest(instances),
                    "records": {
                        cell: [_evaluate(solver, instance, suite) for instance in instances]
                        for cell, solver in solvers.items()
                    },
                }
            atomic_write_json(path, {
                "schema_version": "m35-public-evaluation/v1", "kind": name,
                "candidate_roster_sha256": roster_sha, "suites": suites,
            })
    _emit({"evaluation": name, "path": str(path)})
    return 0


def _verified_evaluation(root: Path, kind: str, roster_sha: str,
                         specs: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    result = _json(root / "runs" / EVALUATIONS[kind])
    suites = result.get("suites", {})
    if (result.get("schema_version") != "m35-public-evaluation/v1" or result.get("kind") != kind
            or result.get("candidate_roster_sha256") != roster_sha or set(suites) != {spec[0] for spec in specs}
            or any(suites[spec[0]]["split"] != spec[1] for spec in specs)):
        raise ValueError(f"m35_invalid_evaluation_binding:{kind}")
    return suites


def _verify_consumption_digest(session: Path, reference: str, evidence: Mapping[str, Any], data: bytes) -> bool:
    ledger = session / "session.sqlite3"
    if not ledger.is_file() or ledger.resolve() != ledger:
        raise ValueError("m35_missing_memory_consumption_session_ledger")
    with closing(sqlite3.connect(f"{ledger.as_uri()}?mode=ro", uri=True)) as con:
        rows = con.execute(
            "SELECT receipt_json FROM operations WHERE run_id=? AND round_id=? "
            "AND action='finish-round' AND status='SUCCEEDED'", (evidence["run_id"], evidence["round_id"]),
        ).fetchall()
    if len(rows) != 1 or not rows[0][0]:
        raise ValueError("m35_missing_memory_consumption_finish_receipt")
    receipt = json.loads(rows[0][0])["result"]
    if "memory_consumption_sha256" not in receipt:
        # Legacy finishes can still substantiate a gateway attempt using its
        # independent input and context hashes, but cannot certify delivery.
        if receipt.get("memory_consumption_ref", reference) != reference:
            raise ValueError("m35_memory_consumption_finish_reference_mismatch")
        return False
    if receipt.get("memory_consumption_ref") != reference:
        raise ValueError("m35_memory_consumption_finish_reference_mismatch")
    if receipt["memory_consumption_sha256"] != sha256_bytes(data):
        raise ValueError("m35_memory_consumption_digest_mismatch")
    return True


def _verify_gateway(run_dir: Path, summary: Mapping[str, Any], *, enabled: bool) -> dict[str, Any]:
    feature_count = summary.get("feature_count", 0)
    if type(feature_count) is not int or feature_count < 0:
        raise ValueError("m35_invalid_feature_count")
    observed = set()
    compiled_count = 0
    delivered = set()
    artifacts = []
    for expected in summary.get("memory_consumption", []):
        ref = expected.get("artifact_ref")
        if ref is None:
            if expected.get("injected_refs") or expected.get("gateway_refs"):
                raise ValueError("m35_missing_memory_consumption_receipt")
            continue
        round_id = expected["round_id"]
        if type(round_id) is not int or round_id <= 0:
            raise ValueError("m35_invalid_memory_consumption_reference")
        session = run_dir.resolve() / "session_run"
        local_ref = f"rounds/round_{round_id:04d}/memory_consumption.json"
        path = _inside(run_dir, ref)
        if path != session / local_ref or ref != f"session_run/{local_ref}":
            raise ValueError("m35_invalid_memory_consumption_reference")
        data = path.read_bytes()
        evidence = json.loads(data)
        if (evidence.get("schema_version") != MEMORY_RECEIPT_SCHEMA or evidence.get("memory_enabled") is not enabled
                or evidence.get("round_id") != round_id or ref in artifacts):
            raise ValueError("m35_invalid_memory_consumption_receipt")
        digest_verified = _verify_consumption_digest(session, local_ref, evidence, data)
        artifacts.append(ref)
        excerpts = {row["reference"]: row for row in evidence["compiled"]}
        if list(excerpts) != expected["injected_refs"] or len(excerpts) != len(evidence["compiled"]):
            raise ValueError("m35_compiled_memory_receipt_mismatch")
        compiled_count += len(excerpts)
        gateway = set()
        context = None
        if evidence.get("context_manifest_ref") is not None:
            # Session evidence refs are relative to the Session root, not the outer run.
            manifest = _inside(session, evidence["context_manifest_ref"])
            if sha256_file(manifest) != evidence["context_manifest_sha256"]:
                raise ValueError("m35_gateway_context_manifest_digest_mismatch")
            context_path = path.with_name("round_context.txt")
            if sha256_file(context_path) != _json(manifest)["context_sha256"]:
                raise ValueError("m35_gateway_context_digest_mismatch")
            context = context_path.read_bytes().decode("utf-8")
        for request in evidence["gateway_requests"]:
            if request.get("context_status") != "gateway_attempt_exact_context":
                continue
            if not request.get("input_ref") or request["transport_status"] not in {"attempted_send", "delivered"}:
                raise ValueError("m35_invalid_gateway_request_receipt")
            payload = _inside(session, request["input_ref"])
            if sha256_file(payload) != request.get("input_sha256"):
                raise ValueError("m35_gateway_input_digest_mismatch")
            messages = _json(payload)["messages"]
            prompt = "\n".join(item["content"] for item in messages if isinstance(item.get("content"), str))
            if context is None or prompt.count(context) != 1:
                raise ValueError("m35_gateway_did_not_carry_exact_context")
            request_refs = set()
            for card in request["memory"]:
                ref_ = card["reference"]
                compiled = excerpts.get(ref_, {})
                if (card.get("status") != "gateway_attempt" or compiled.get("status") != "compiled_into_context"
                        or card.get("injected_sha256") != compiled["injected_sha256"]
                        or card.get("body_sha256") != compiled["body_sha256"]):
                    raise ValueError("m35_gateway_card_receipt_mismatch")
                request_refs.add(ref_)
            if request_refs != set(excerpts):
                raise ValueError("m35_gateway_card_set_mismatch")
            gateway.update(request_refs)
            if digest_verified and request["transport_status"] == "delivered":
                delivered.update(request_refs)
        if sorted(gateway) != expected["gateway_refs"]:
            raise ValueError("m35_gateway_reference_mismatch")
        observed.update(gateway)
    if enabled and (feature_count <= 0 or compiled_count != feature_count or not observed):
        raise ValueError(f"m35_memory_gateway_unverified:{run_dir.name}")
    if not enabled and (feature_count or compiled_count or observed or (run_dir / "agent_artifacts/kb_events.jsonl").exists()):
        raise ValueError("m35_control_arm_memory_or_kb_exposure")
    return {"feature_count": feature_count, "gateway_refs": sorted(observed), "delivered_refs": sorted(delivered),
            "memory_consumption": artifacts}


def _paired_stats(left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]], *, seed: int,
                  exact_k: bool, common_completed: bool) -> dict[str, Any]:
    left_map, right_map = _indexed(left), _indexed(right)
    if not left_map or left_map.keys() != right_map.keys():
        raise ValueError("m35_paired_instance_ids_mismatch")
    pairs = []
    for key in sorted(left_map):
        left_row, right_row = left_map[key], right_map[key]
        fields = ("reference_objective", "exact_k_applicable", "size")
        if any(left_row[field] != right_row[field] for field in fields):
            raise ValueError("m35_paired_instance_metadata_mismatch")
        if not exact_k or left_row["exact_k_applicable"]:
            pairs.append((left_row, right_row))
    common = [(lrow, rrow) for lrow, rrow in pairs if _completed(lrow, exact_k) and _completed(rrow, exact_k)]
    included = common if common_completed else pairs
    counts = {
        "eligible_count": len(pairs), "common_completed_count": len(common), "paired_count": len(included),
        "left_completed_count": sum(_completed(left_row, exact_k) for left_row, _ in pairs),
        "right_completed_count": sum(_completed(right_row, exact_k) for _, right_row in pairs),
    }
    if not included:
        status = "not_applicable" if not pairs else "no_common_completed"
        return {**counts, "status": status, "wilcoxon": None, "bootstrap": None, "wilcoxon_p_holm": None}
    if any(not _completed(row, exact_k) and row["reference_objective"] is None for pair in included for row in pair):
        return {**counts, "status": "penalty_reference_unavailable", "wilcoxon": None, "bootstrap": None,
                "wilcoxon_p_holm": None}
    left_values, right_values = zip(*[(_penalized(lrow, exact_k), _penalized(rrow, exact_k))
                                     for lrow, rrow in included], strict=True)
    bootstrap = paired_bootstrap_comparison(left_values, right_values, n_boot=BOOTSTRAPS, seed=seed)
    wilcoxon = bootstrap.pop("wilcoxon_signed_rank")
    return {**counts, "status": "paired", "wilcoxon": wilcoxon, "bootstrap": {**bootstrap, "replicates": BOOTSTRAPS}}


def _suite_report(suite: Mapping[str, Any], forks: Mapping[int, Any]) -> dict[str, Any]:
    by_cell = suite["records"]
    if set(by_cell) != {f"{seed}:{arm}" for seed in forks for arm in ARMS} or any(
        len(rows) != suite["instance_count"] for rows in by_cell.values()
    ):
        raise ValueError("m35_evaluation_roster_or_instance_count_mismatch")
    seeds = {}
    for seed in forks:
        fleets = {}
        for fleet in ("exact_k", "free_fleet"):
            denominators = {}
            for denominator in ("overall", "common_completed"):
                rows = []
                for arm, comparator in CONTRASTS:
                    stats = _paired_stats(
                        by_cell[f"{seed}:{arm}"], by_cell[f"{seed}:{comparator}"], seed=seed,
                        exact_k=fleet == "exact_k", common_completed=denominator == "common_completed",
                    )
                    rows.append({"arm": arm, "comparator": comparator, **stats})
                # Unavailable tests retain their slot in the prespecified family.
                adjusted = holm_bonferroni_adjust([
                    row["wilcoxon"]["p_two_sided"] if row["wilcoxon"] is not None else 1.0 for row in rows
                ])
                for row, p_value in zip(rows, adjusted, strict=True):
                    row["wilcoxon_p_holm"] = p_value if row["wilcoxon"] is not None else None
                denominators[denominator] = rows
            fleets[fleet] = denominators
        seeds[str(seed)] = fleets
    return {key: suite[key] for key in ("split", "vehicle_limit_policy", "instance_count", "instance_set_sha256")} | {
        "per_seed": seeds,
    }


def cmd_report(args: argparse.Namespace) -> int:
    root = _output(args)
    forks = _forks(root)
    roster_path = root / "runs" / CANDIDATES
    if not roster_path.is_file():
        raise FileNotFoundError("m35_eval_select_required_before_report")
    roster = _candidate_roster(root, forks)
    _solvers(root, roster, forks)
    arms = {}
    for seed, fork in forks.items():
        for arm in ARMS:
            config = _arm_configuration(root, fork, arm)
            run_dir = Path(config.output_dir)
            arms[f"{seed}:{arm}"] = _verify_gateway(run_dir, _json(run_dir / "research_summary.json"),
                                                   enabled=config.memory_enabled)
    digest = sha256_file(roster_path)
    suites = _verified_evaluation(root, "select", digest, SELECT) | _verified_evaluation(
        root, "external", digest, EXTERNAL_CVRPLIB_SUITES,
    )
    path = root / "runs" / REPORT
    atomic_write_json(path, {
        "schema_version": "m35-ablation-report/v1", "candidate_roster_sha256": digest,
        "mode": next(iter(forks.values()))["agent"]["mode"],
        "analysis_plan": _json(root / "runs" / ROSTER)["analysis_plan"],
        "arm_wiring": arms, "suites": {name: _suite_report(suite, forks) for name, suite in suites.items()},
    })
    _emit({"path": str(path), "seed_count": len(forks), "suite_count": len(suites)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    commands = parser.add_subparsers(required=True)
    dev_seed = commands.add_parser("build-dev-seed", help="Build authorized dev_train source store and claim evidence.")
    dev_seed.add_argument("--instance-limit", type=int, default=None)
    dev_seed.set_defaults(handler=cmd_build_dev_seed)
    init = commands.add_parser("init-fork", help="Freeze the common dev start and arm memory snapshots.")
    init.add_argument("--mode", choices=("mock", "live"), default="mock")
    init.add_argument("--seed", action="append", type=int, choices=SEEDS, help="Subset of frozen seeds, for mock runs.")
    init.add_argument("--source-store", action="append", type=Path, default=[])
    init.add_argument("--dev-artifact", action="append", type=Path, default=[])
    init.set_defaults(handler=cmd_init_fork)

    commands.add_parser("emit-mux", help="Emit multiplexed commands in frozen launch order.").set_defaults(handler=cmd_emit_mux)
    run = commands.add_parser("run-arm", help="Run or resume one registered arm and seed.")
    run.add_argument("--seed", type=int, required=True, choices=SEEDS)
    run.add_argument("--arm", required=True, choices=tuple(ARMS))
    run.add_argument("--resume", action="store_true")
    run.set_defaults(handler=cmd_run_arm)
    commands.add_parser("eval-select", help="Freeze candidates and evaluate on public select_64.").set_defaults(
        handler=lambda args: _eval(args, "select", SELECT),
    )
    commands.add_parser("eval-external", help="Evaluate the frozen roster on public external CVRPLIB.").set_defaults(
        handler=lambda args: _eval(args, "external", EXTERNAL_CVRPLIB_SUITES),
    )
    commands.add_parser("report", help="Verify memory exposure and report the paired per-seed results.").set_defaults(handler=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
