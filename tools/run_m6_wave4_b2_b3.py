"""Wave 4 numerical diagnostics and cross-run CVRP memory experiments."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing, contextmanager
from itertools import combinations, product
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop import session_actions, session_runner, session_runtime, session_supervisor
from agent_skill_loop.client import ProviderFailure
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.evidence import report as evidence_report
from agent_skill_loop.file_lock import exclusive_file_lock
from agent_skill_loop.interface_design import session_bridge
from agent_skill_loop.interface_design.blind_commitment import (
    _CAPACITY_LEVELS, _gen_coords, _gen_demands, _seeded_rng, _sha256_payload, require_external_custody_path,
)
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m32 import _cell, _write_once
from agent_skill_loop.interface_design.blind_eval_m5 import _blind_design_rows, build_m5_public_record
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.session_baseline import load_dev_or_public_suite
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.memory.api import MemoryAPI, MemoryEntry
from agent_skill_loop.memory.auto_dream import auto_dream, evidence_digest
from agent_skill_loop.memory.retrieval_m35 import iter_attributed_outcomes
from agent_skill_loop.problems.base import get_problem
from eoh_frozen.identity import loaded_identity
from research_agent import loop as research_loop
from research_agent.contracts import AgentConfig, atomic_write_json, sha256_file, sha256_text
from research_agent.llm_driver import ScriptedMockAgentDriver
from research_agent.tools import session_tools
from research_agent.tools.kb_tools import KnowledgeBaseTool, verify_pinned_release
from tools.run_b4_intron_ablation import EXTERNAL_CVRPLIB_SUITES
from tools.run_m5_trajectory_control import _fleet_metrics, _penalized
from tools.run_m6_wave3_c1_exact_k import _json_skill
from tools.run_s1_sandbox_ablation import DENOMINATORS, FLEETS, _paired_tests, inspect_scripts

DEFAULT_OUTPUT = REPO / "experiments" / "milestone6_wave4_b2_b3"
DEFAULT_CUSTODY = Path.home() / ".agent_skill_custody" / "m6_wave4_b2"
RELEASE_ID = "20261125-main-co-workbench-m5-final"
BASE_RELEASE = REPO / "knowledge_store" / "releases" / RELEASE_ID
DEV = "cvrp_dev_hetero_24"
BLIND = "cvrp_b2_clean_blind_120"
SELECT = ("cvrp_select_multiscale_64", "selection", "selection_tuning")
FINAL = ("cvrp_final_accept_120", "heldout", "final_acceptance")
SUITE_COUNTS = dict(zip((BLIND, SELECT[0], *(spec[0] for spec in EXTERNAL_CVRPLIB_SUITES), FINAL[0]),
                        (120, 64, 74, 100, 120), strict=True))
STATIC = "cvrp_parallel_merge_static"
TEMPLATES = (STATIC, "cvrp_ruin_recreate")
MODELS = ("DeepSeek-V4.1-Flash", "Qwen4-Max")
SEEDS = (20261124, 20261125, 20261126, 20261127, 20261128)
REQUEST_CAP = 36
DEADLINE_MS = 500.0
B2_ARMS = {"arm_b2_0_free_tool": "off", "arm_b2_1_slice_only": "slice_only", "arm_b2_2_sandbox_only": "sandbox_only"}
B3_ARMS = ("arm_b3_0_base_kb_only", "arm_b3_1_online_writeback", "arm_b3_2_offline_l3_c2_gated",
           "arm_b3_3_full_closed_loop_c2_gated")
B2_CELLS = tuple(product(MODELS, SEEDS, B2_ARMS))
PILOT_CELLS = tuple(product(MODELS, SEEDS[:2], (tuple(B2_ARMS)[2],)))
B3_CELLS = tuple(product(MODELS[:1], SEEDS[:3], B3_ARMS))
TERMINAL = {"completed", "budget_stopped", "no_champion"}
COMMITMENT = f"{BLIND}_commitment.json"
PILOT_AUDIT = "b2_pilot_audit.json"
APPROVAL = "b2_pilot_approval.json"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _inside(root: Path, *parts: str) -> Path:
    path = root.joinpath(*parts)
    if path != path.resolve() or not path.is_relative_to(root):
        raise ValueError("wave4_path_outside_root_or_linked")
    return path


def _output(path: Path) -> Path:
    path = path.resolve()
    if not (path.is_relative_to(DEFAULT_OUTPUT) or path.is_relative_to(REPO / "build")):
        raise ValueError("wave4_output_must_use_wave4_or_build_directory")
    return path


def _check_artifacts(root: Path) -> None:
    if any(path.suffix.casefold() == ".md" for path in root.rglob("*")):
        raise ValueError("wave4_markdown_artifact")


def _base_pin() -> dict[str, str]:
    digest = sha256_file(BASE_RELEASE / "manifest.json")
    verify_pinned_release(BASE_RELEASE, release_id=RELEASE_ID, manifest_sha256=digest, json_only=True)
    return {"release_dir": str(BASE_RELEASE), "release_id": RELEASE_ID, "manifest_sha256": digest}


class _JsonKnowledgeBase(KnowledgeBaseTool):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, json_only=True, **kwargs)


class _SessionProcesses:
    def __getattr__(self, name):
        return getattr(subprocess, name)

    def Popen(self, argv, *args, **kwargs):
        modules = {"agent_skill_loop.session_supervisor": "supervisor", "agent_skill_loop.session_runner": "runner"}
        mode = modules.get(argv[2]) if len(argv) >= 3 and argv[1] == "-m" else None
        if mode:
            argv = [argv[0], str(Path(__file__).resolve()), "--session-process", mode, *argv[3:]]
        elif len(argv) == 4 and argv[1] == "-c" and "from eoh_frozen.identity import loaded_identity" in argv[2]:
            argv = [argv[0], str(Path(__file__).resolve()), "--session-process", "identity", argv[3]]
        return subprocess.Popen(argv, *args, **kwargs)


@contextmanager
def _json_session_profile():
    writer = research_loop.atomic_write_text

    def write_policy(path, content):
        if path.name == "research_policy.md":
            atomic_write_json(path.with_suffix(".json"), {"policy": content})
        else:
            writer(path, content)

    def policy_hash():
        return sha256_text("wave4-json-session-policy/v1\n" + research_loop.RESEARCH_POLICY_MD)

    with ExitStack() as stack:
        for module, name, adapter in (
            (research_loop, "atomic_write_text", write_policy),
            (research_loop, "KnowledgeBaseTool", _JsonKnowledgeBase),
            (session_tools, "KnowledgeBaseTool", _JsonKnowledgeBase),
            (session_bridge, "save_skill", _json_skill),
            (session_runtime, "_skill_content_hash", policy_hash),
            (session_actions, "subprocess", _SessionProcesses()),
            (session_supervisor, "subprocess", _SessionProcesses()),
            (evidence_report, "write_round_progress", lambda root: root / "session.sqlite3"),
        ):
            stack.enter_context(patch.object(module, name, adapter))
        yield


def _session_process(mode: str, args: Sequence[str]) -> int:
    with _json_session_profile():
        if mode == "supervisor":
            session_supervisor.run_task(Path(args[0]), args[1])
        elif mode == "runner":
            sys.argv = [sys.argv[0], *args]
            session_runner.main()
        elif mode == "identity":
            print(json.dumps(loaded_identity(args[0] or None), sort_keys=True))
        else:
            raise ValueError("wave4_session_process_unknown")
    return 0


def _key(cell) -> str:
    model, seed, arm = cell
    return f"{model}/{seed}/{arm}"


def _config(root: Path, cell, args, pin, *, b3: bool) -> AgentConfig:
    model, seed, arm = cell
    run = _inside(root, "runs", *_key(cell).split("/"))
    memory = b3 and arm != B3_ARMS[0]
    online = b3 and arm in (B3_ARMS[1], B3_ARMS[3])
    return AgentConfig(
        run_id=f"m6_{arm}_{model}_s{seed}", output_dir=str(run), arm_id=arm, search_seed=seed,
        planner_model=model, eoh_model=model, initial_template_id=STATIC, template_version="v2",
        allowed_templates=(STATIC,) if b3 else TEMPLATES,
        allowed_postprocess_modes=("none", "relocate_2opt"), initial_postprocess_mode="relocate_2opt",
        use_benchmark_dev_suite=True, dev_suite_id=DEV, dev_instance_count=24, dev_split="dev_train",
        strict_checkpoint_barriers=True, checkpoint_budgets=(REQUEST_CAP,),
        instance_time_budget_ms=DEADLINE_MS, total_request_cap=REQUEST_CAP,
        max_rounds=8 if args.live else 2, eoh_n_pop=1, eoh_max_sample_nums=8 if args.live else 3,
        outer_requests_per_round_cap=6, outer_reflect_cap=1,
        endpoint=args.endpoint if args.live else "mock://local", api_key_env=args.api_key_env,
        mode="live" if args.live else "mock", request_timeout_s=240.0 if args.live else 5.0,
        wall_seconds=14400.0 if args.live else 1200.0,
        enable_c2_joint_screen=True, enable_multiscale_latency_ratio_screen=True,
        kb_enabled=True, kb_store_path=pin["release_dir"], pinned_kb_release_id=pin["release_id"],
        pinned_kb_manifest_sha256=pin["manifest_sha256"],
        memory_enabled=memory, memory_online_writeback_enabled=online,
        memory_store_path=str(run / "memory") if memory else None, memory_mode="m35_full" if memory else "off",
        require_c2_multiscale_admission=memory, strict_diagnostic_gate=not b3,
        stagnation_diagnostic_mode=B2_ARMS[arm] if not b3 else "off", archive_feedback_enabled=False,
    )


def _custody(root: Path, args) -> Path:
    if args.live:
        path = require_external_custody_path(args.custody_dir or DEFAULT_CUSTODY, repo_root=REPO)
        shared = DEFAULT_CUSTODY.parent.resolve()
        if path == shared or path in shared.parents or (path.is_relative_to(shared) and path != DEFAULT_CUSTODY.resolve()):
            raise ValueError("wave4_requires_dedicated_live_custody")
        return path
    path = Path(args.custody_dir or (REPO / "build" / "wave4_mock_custody" / sha256_text(str(root))[:20])).resolve()
    shared = DEFAULT_CUSTODY.parent.resolve()
    if (path == shared or path.is_relative_to(shared) or path in shared.parents or path == root
            or root.is_relative_to(path) or (path.is_relative_to(REPO) and not path.is_relative_to(REPO / "build"))
            or any(part.casefold() == ".secrets" for part in path.parts)):
        raise ValueError("wave4_requires_isolated_mock_custody")
    return path


def _seal(root: Path, args, pin) -> dict:
    custody = _custody(root, args)
    private_path = _inside(custody, f"{BLIND}_sealed.json")
    public_path = _inside(root, COMMITMENT)
    protocol_path = _inside(root, "b2_protocol.json")
    if protocol_path.is_file():
        return _b2_protocol(root, args, pin)
    if private_path.exists() or public_path.exists():
        raise FileExistsError("wave4_incomplete_seal_or_custody_already_used")
    token = secrets.token_hex(32)
    instances = []
    design = _blind_design_rows()
    for index, (size, spatial, depot, capacity, demand) in enumerate(design if args.live else list(design)[:4]):
        cell = _cell(size, spatial, depot, capacity, demand)
        rng = _seeded_rng(token, f"{BLIND}/{cell}", index)
        inst = {"instance_id": f"b2-{index:03d}", "cell": cell, "size": size, "spatial": spatial,
                "depot_style": depot, "capacity_level": capacity, "demand_dist": demand, "source_tag": BLIND,
                "protocol_id": "cvrp/v1", "depot": [0.5, 0.5] if depot == "centre" else [0.05, 0.95],
                "customer_coordinates": _gen_coords(spatial, rng, size), "demands": _gen_demands(demand, rng, size),
                "capacity": _CAPACITY_LEVELS[capacity]}
        reference = evaluate_algorithm_on_instance("nn", inst, record_trace=False)
        objective, fleet = reference["tour_length"], reference["route_count"]
        if not (reference["valid"] is True and math.isfinite(objective) and objective > 0 and fleet > 0):
            raise ValueError("wave4_blind_reference_invalid")
        instances.append({**inst, "reference_objective": objective, "reference_kind": "solver_reference",
                          "k_vehicles": fleet})
    if len(instances) != (SUITE_COUNTS[BLIND] if args.live else 4):
        raise ValueError("wave4_blind_design_count")
    metadata = {"suite_id": BLIND, "suite_role": "final_blind_acceptance", "split": "blind", "problem_family": "cvrp",
                "protocol_id": "cvrp/v1", "distance_convention": "euc_2d_float", "vehicle_limit_policy": "unconstrained",
                "run_mode": "live" if args.live else "mock", "instance_count": len(instances),
                "suite_content_sha256": _sha256_payload(instances)}
    _write_once(private_path, {**metadata, "sealed_seed_token": token, "instances": instances})
    _write_once(public_path, {**metadata, "instances": [{"instance_id": inst["instance_id"], "cell": inst["cell"],
                "instance_sha256": _sha256_payload(inst)} for inst in instances]})
    protocol = {"schema_version": "m6-wave4-b2/v1", "run_mode": metadata["run_mode"], "base_kb": pin,
                "commitment_sha256": sha256_file(public_path), "roster": [_key(cell) for cell in B2_CELLS],
                "pilot_roster": [_key(cell) for cell in PILOT_CELLS], "workers": 1, "deadline_ms": DEADLINE_MS,
                "request_cap": REQUEST_CAP, "strict_diagnostic_gate": True}
    _write_once(protocol_path, protocol)
    return protocol


def _b2_protocol(root: Path, args, pin) -> dict:
    protocol = _read(_inside(root, "b2_protocol.json"))
    commitment = _inside(root, COMMITMENT)
    if (protocol.get("schema_version") != "m6-wave4-b2/v1" or protocol.get("base_kb") != pin
            or protocol.get("run_mode") != ("live" if args.live else "mock")
            or protocol.get("roster") != [_key(cell) for cell in B2_CELLS]
            or protocol.get("pilot_roster") != [_key(cell) for cell in PILOT_CELLS]
            or protocol.get("commitment_sha256") != sha256_file(commitment)):
        raise ValueError("wave4_b2_protocol_binding_mismatch")
    return protocol


def _claim_blind(root: Path, args, roster_sha: str) -> dict:
    custody = _custody(root, args)
    commitment = _read(_inside(root, COMMITMENT))
    sealed = _inside(custody, f"{BLIND}_sealed.json")
    if not sealed.is_file():
        raise FileNotFoundError("wave4_missing_sealed_custody")
    _write_once(_inside(custody, f"{BLIND}.consumed.json"), {"roster_sha256": roster_sha,
                "commitment_sha256": sha256_file(root / COMMITMENT)})
    try:
        suite = _read(sealed)
        rows = suite["instances"]
        if (any(suite.get(key) != value for key, value in commitment.items() if key != "instances")
                or len(rows) != commitment["instance_count"] or _sha256_payload(rows) != commitment["suite_content_sha256"]
                or [{"instance_id": row["instance_id"], "cell": row["cell"], "instance_sha256": _sha256_payload(row)}
                    for row in rows] != commitment["instances"]):
            raise ValueError("binding_mismatch")
    except (KeyError, ValueError, OSError):
        raise ValueError("wave4_blind_payload_invalid_attempt_consumed") from None
    return suite


def _dev_source(root: Path, args) -> dict:
    receipt = _inside(root, "b3_dev_seed.json")
    store = _inside(root, "dev_seed", "memory")
    artifact = _inside(root, "dev_seed", "dev_evidence.json")
    if receipt.is_file():
        saved = _read(receipt)
        if (saved["run_mode"] != ("live" if args.live else "mock")
                or saved["dev_artifact_sha256"] != sha256_file(artifact)
                or saved["common_start_sha256"] != sha256_file(_inside(root, "dev_seed", "common_start.json"))):
            raise ValueError("wave4_b3_dev_seed_binding_mismatch")
        return saved
    solver = research_loop._build_initial_baseline_solver(AgentConfig(
        "wave4_dev_seed", str(root), template_version="v2", allowed_templates=(STATIC,),
        initial_postprocess_mode="relocate_2opt", kb_enabled=False,
    ))
    suite = load_dev_or_public_suite(DEV, split="dev_train", role="diagnostic_interactive")
    measured = suite["instances"]
    rows = _score_suite({**suite, "instances": measured}, {"stock": solver})["stock"]
    completed = sum(row["completed"] for row in rows)
    if not completed:
        raise ValueError("wave4_b3_dev_seed_has_no_completed_evaluation")
    spec = get_problem("cvrp_construct")
    code = solver.hook_code
    anchor = {"code_sha256": sha256_text(code), "canonical_ast_sha256": sha256_text(ast.unparse(ast.parse(code)))}
    ref = "evaluation:b3_stock_v2_dev"
    geometry = {
        "spatial_regime": sorted({str(inst["spatial"]) for inst in measured if inst.get("spatial")}),
        "demand_cv_regime": sorted({str(inst["demand_dist"]) for inst in measured if inst.get("demand_dist")}),
        "eccentricity_regime": sorted({str(inst["depot_style"]) for inst in measured if inst.get("depot_style")}),
        "scale_range": [min(inst["size"] for inst in measured), max(inst["size"] for inst in measured)],
    }
    scope = {"problem": spec.problem_id, "interface_id": STATIC, "fleet_policy": suite["vehicle_limit_policy"],
             "evaluator_version": evaluator_source_hash(), "n_range": geometry["scale_range"],
             "budget_ms_range": [DEADLINE_MS, DEADLINE_MS]}
    facts = {"problem": spec.problem_id, "split": "dev_train", "suite_id": DEV,
             "interface_id": STATIC, "template_version": "v2", "postprocess_mode": solver.postprocess_mode,
             "fleet_policy": scope["fleet_policy"],
             "evaluator_version": scope["evaluator_version"], "evidence_refs": [ref], "geometry_scale": geometry,
             "candidates": [{**anchor, "evaluation_id": "b3_stock_v2_dev", "valid": completed == len(rows),
                             "code": code, "synthetic": not args.live, "geometry_scale": geometry}]}
    digest = evidence_digest(facts)
    api = MemoryAPI(store, json_only=True)
    claims = []
    for kind, body in (
        ("insight", f"**Why:** CVRP static merge completed {completed}/{len(rows)} measured dev cases at 500 ms.\n"
                    "**How to apply:** Compare geometry-aware changes to the same dev anchor.\n"
                    "**Limitations:** One dev baseline does not establish cross-suite transfer."),
        ("solution", f"## Execution\n```python\n{code}\n```\n"
                     "**Why:** The stock merge hook was evaluated on the Wave 4 dev profile.\n"
                     "**How to apply:** Compare to the identical static CVRP interface and dev budget.\n"
                     "**Reusable Experience:** Preserve normalized savings as a reference implementation."),
    ):
        # A partially completed evaluation supports the observation only.
        if kind == "solution" and completed != len(rows):
            continue
        claim_id = f"b3-stock-v2-{kind}"
        entry = MemoryEntry(claim_id, f"CVRP static merge dev reference ({kind})", kind,
                            spec.problem_id, spec.entrypoint, body, applicability_scope=scope,
                            code_anchor=anchor, validity_status="active", evidence_tier="single_run")
        source = api.write(entry, operation_key=claim_id, format_version=3, provenance={
            "evaluation_facts_sha256": digest, "evidence_ref": ref, "parent_version_id": "stock_static_v2",
            "candidate_code_sha256": anchor["code_sha256"], "canonical_ast_sha256": anchor["canonical_ast_sha256"],
            "evaluator_hash": scope["evaluator_version"], "interface_id": STATIC,
        })
        claims.append({"claim_id": claim_id, "source_reference": source["reference"], "applicability_scope": scope,
                       "denominators": {"attempted": len(rows), "completed": completed}, "code_anchor": anchor,
                       "adverse_results": ([f"{len(rows) - completed} dev cases missed completion."]
                                           if completed < len(rows) else []),
                       "contradictions": [], "evaluation_facts_sha256": digest, "evidence_ref": ref})
    atomic_write_json(artifact, {"split": "dev_train", "suite_id": DEV, "evaluation_facts": facts, "claims": claims})
    common_start_sha = atomic_write_json(_inside(root, "dev_seed", "common_start.json"), {
        "frozen_solver": solver.to_dict(), "dev_suite_hash": _sha256_payload(measured),
        "baseline_dev_eval": {"instance_count": len(rows), "valid_count": completed,
            "completion_rate": completed / len(rows), "all_feasible": completed == len(rows),
            "valid_only_mean_objective": math.fsum(row["objective"] for row in rows if row["completed"]) / completed,
            "penalized_mean_objective": math.fsum(_penalized(row) for row in rows) / len(rows)},
    })
    saved = {"run_mode": "live" if args.live else "mock", "dev_artifact_sha256": sha256_file(artifact),
             "store_path": "dev_seed/memory", "artifact_path": "dev_seed/dev_evidence.json",
             "common_start_sha256": common_start_sha, "completed": completed, "attempted": len(rows)}
    _write_once(receipt, saved)
    return saved


def _merge_kb(root: Path, pin, dream) -> dict:
    dream_root = _inside(root, "runs", "dream")
    dream_sha = sha256_file(dream_root / "auto_dream_manifest.json")
    release_id = "wave4-m5-dev-l3-" + sha256_text(pin["manifest_sha256"] + dream_sha)[:20]
    release = _inside(dream_root, "l3_merged_release", release_id)
    release.parent.mkdir(parents=True, exist_ok=True)
    if not release.exists():
        memory = MemoryAPI(dream_root / "memory", read_only=True)
        index = _read(BASE_RELEASE / "index.json")
        with TemporaryDirectory(dir=release.parent) as tmp:
            stage = Path(tmp) / release_id
            (stage / "entries").mkdir(parents=True)
            entries = []
            for entry in index["entries"]:
                rel = f"entries/{sha256_text(entry['id'])}.json"
                sha = atomic_write_json(stage / rel, {"body": entry.get("search_text") or entry.get("summary") or "",
                                        "body_source": "verified_index_text" if entry.get("search_text")
                                        else "verified_index_summary"})
                projected = {key: value for key, value in entry.items() if key not in {"metadata_path", "metadata_sha256"}}
                entries.append({**projected, "path": rel, "content_sha256": sha})
            for candidate in dream["cards"]:
                card = memory.read_version(candidate["reference"], max_chars=8000)
                tags = candidate.get("geometry_scale") or {}
                if (card["next_offset"] is not None or any(card["provenance"].get(key) != value for key, value in tags.items())
                        or (card["type"] == "solution" and tags.get("c2_multiscale_screen_passed") is not True)):
                    raise ValueError("wave4_b3_l3_publication_admission_failed")
                entry_id = "wave4-dev-l3-" + sha256_text(card["reference"])
                rel = f"entries/{entry_id}.json"
                sha = atomic_write_json(stage / rel, {"body": card["body"], "body_source": "admitted_dev_memory"})
                entries.append({"id": entry_id, "path": rel, "title": card["description"], "summary": card["description"],
                                "type": "evidence", "category": "dev-memory", "problem_family": "cvrp",
                                "tags": ["wave4", "auto-dream", "dev", card["type"]], "content_sha256": sha,
                                "attributes": {**tags, "knowledge_tier": "l3", "source_split": "dev",
                                               "memory_type": card["type"], "memory_reference": card["reference"],
                                               "applicability_scope": card["applicability_scope"],
                                               "code_anchor": card["code_anchor"]}})
            for name in ("sources.json", "taxonomy.json", "relations.json", "classification.json"):
                if (BASE_RELEASE / name).is_file():
                    shutil.copyfile(BASE_RELEASE / name, stage / name)
            if len({entry["id"].casefold() for entry in entries}) != len(entries):
                raise ValueError("wave4_b3_merged_entry_collision")
            atomic_write_json(stage / "index.json", {"schema_version": "knowledge-v1", "release_id": release_id,
                                                       "entries": entries})
            files = [{"path": path.relative_to(stage).as_posix(), "sha256": sha256_file(path), "size": path.stat().st_size}
                     for path in sorted(stage.rglob("*.json"))]
            digest = atomic_write_json(stage / "manifest.json", {"schema_version": "knowledge-v1", "release_id": release_id,
                "self_hash_file": "manifest_digest.json", "base_kb": pin, "auto_dream_manifest_sha256": dream_sha,
                "source_split": "dev", "files": files})
            atomic_write_json(stage / "manifest_digest.json", {"manifest_sha256": digest})
            verify_pinned_release(stage, release_id=release_id, manifest_sha256=digest, json_only=True)
            stage.rename(release)
    digest = sha256_file(release / "manifest.json")
    verify_pinned_release(release, release_id=release_id, manifest_sha256=digest, json_only=True)
    return {"release_dir": str(release), "release_id": release_id, "manifest_sha256": digest}


def _memory_assets(store: Path) -> dict[str, str]:
    assets = {}
    for path in sorted(store.glob("*/*.json")):
        rel = path.relative_to(store).as_posix()
        if not path.name.endswith(".installing.json"):
            assets[rel] = sha256_file(_inside(store, rel))
    return assets


def _freeze_fork(root: Path, args, pin) -> dict:
    path = _inside(root, "b3_fork_roster.json")
    if path.is_file():
        return _b3_fork(root, args, pin)
    source = _read(_inside(root, "b3_dev_seed.json"))
    artifact = _inside(root, source["artifact_path"])
    store = _inside(root, source["store_path"])
    if (source["run_mode"] != ("live" if args.live else "mock") or sha256_file(artifact) != source["dev_artifact_sha256"]
            or not (store / ".memory_format.json").is_file()):
        raise ValueError("wave4_b3_dev_seed_binding_mismatch")
    dream_root = _inside(root, "runs", "dream")
    dream = auto_dream(dev_artifacts=[artifact], source_stores=[store], output_store=dream_root / "memory",
                       output_dir=dream_root, require_c2_multiscale_admission=True)
    merged = _merge_kb(root, pin, dream)
    fork = {"run_mode": source["run_mode"], "base_kb": pin, "merged_kb": merged,
            "dream_sha256": sha256_file(dream_root / "auto_dream_manifest.json"),
            "common_start_sha256": source["common_start_sha256"],
            "memory_assets": _memory_assets(dream_root / "memory"), "roster": [_key(cell) for cell in B3_CELLS],
            "rejected_candidates": dream["rejected_candidates"]}
    _write_once(path, fork)
    return fork


def _b3_fork(root: Path, args, pin) -> dict:
    fork = _read(_inside(root, "b3_fork_roster.json"))
    merged = fork["merged_kb"]
    dream_root = _inside(root, "runs", "dream")
    if (fork["run_mode"] != ("live" if args.live else "mock") or fork["base_kb"] != pin
            or fork["roster"] != [_key(cell) for cell in B3_CELLS]
            or fork["dream_sha256"] != sha256_file(dream_root / "auto_dream_manifest.json")
            or fork["common_start_sha256"] != sha256_file(_inside(root, "dev_seed", "common_start.json"))
            or fork["memory_assets"] != _memory_assets(dream_root / "memory")
            or Path(merged["release_dir"]) != _inside(dream_root, "l3_merged_release", merged["release_id"])):
        raise ValueError("wave4_b3_fork_binding_mismatch")
    verify_pinned_release(Path(merged["release_dir"]), release_id=merged["release_id"],
                          manifest_sha256=merged["manifest_sha256"], json_only=True)
    return fork


def _install_memory(root: Path, config: AgentConfig, fork) -> None:
    if not config.memory_enabled:
        return
    store = Path(config.memory_store_path)
    run = Path(config.output_dir)
    receipt = _inside(run, "memory_seed.json")
    assets = fork["memory_assets"] if config.arm_id in B3_ARMS[2:] else {}
    if receipt.is_file():
        MemoryAPI(store, read_only=True, json_only=True)
        now = _memory_assets(store)
        if (_read(receipt) != assets or any(now.get(rel) != digest for rel, digest in assets.items())
                or (not config.memory_online_writeback_enabled and now != assets)):
            raise ValueError("wave4_b3_memory_seed_mismatch")
        return
    MemoryAPI(store, json_only=True)
    for rel, digest in assets.items():
        source = _inside(root, "runs", "dream", "memory", rel)
        target = _inside(store, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            pending = _inside(store, target.with_suffix(".installing.json").relative_to(store).as_posix())
            shutil.copyfile(source, pending)
            os.replace(pending, target)
        if sha256_file(target) != digest:
            raise ValueError("wave4_b3_memory_asset_mismatch")
    _write_once(receipt, assets)


def zero_alarms(
    arm: str,
    counts: Mapping[str, int],
    *,
    live_mode: bool = False,
    check_injection: bool = False,
    read_only_memory_intact: bool = True,
) -> dict[str, bool]:
    if arm not in B3_ARMS:
        raise ValueError("wave4_b3_unknown_arm")
    read = counts["kb_read_count"] + counts["memory_read_count"] == 0 or (
        arm != B3_ARMS[0] and counts["memory_read_count"] == 0)
    write = arm in (B3_ARMS[1], B3_ARMS[3]) and counts["memory_write_count"] == 0
    injection = (
        (check_injection and arm in B3_ARMS[2:] and counts.get("memory_injected_rounds", 0) == 0)
        or (live_mode and check_injection and arm in B3_ARMS[2:] and counts.get("memory_attributed_candidate_count", 0) == 0)
        or (not read_only_memory_intact)
    )
    return {
        "zero_read_alarm": read,
        "zero_write_alarm": write,
        "zero_injection_alarm": injection,
        "attribution_valid": not (read or write or injection),
    }


def audit_b3_cell(cell_dir: Path, arm: str) -> dict:
    cell_dir = cell_dir.resolve()
    counts = dict.fromkeys((
        "memory_search_count", "memory_read_count", "memory_write_count", "kb_search_count", "kb_read_count",
        "memory_injected_rounds", "memory_gateway_attributed_rounds", "memory_attributed_candidate_count", "kb_cited_rounds",
    ), 0)
    config_path = _inside(cell_dir, "agent_config.json")
    config = _read(config_path) if config_path.is_file() else {}
    path = _inside(cell_dir, "agent_artifacts", "kb_events.jsonl")
    if path.is_file():
        with path.open(encoding="utf-8") as log:
            for line in log:
                event = json.loads(line)
                op = event.get("op")
                if op not in ("kb_read", "kb_search"):
                    raise ValueError("wave4_b3_invalid_kb_event")
                if config and (event.get("release_id") != config["pinned_kb_release_id"]
                               or event.get("manifest_sha256") != config["pinned_kb_manifest_sha256"]
                               or op == "kb_read" and not (event.get("entry_id") and event.get("entry_sha256"))):
                    raise ValueError("wave4_b3_kb_event_pin_mismatch")
                counts[f"{op}_count"] += 1
    budget_ledger = _inside(cell_dir, "agent_budget.sqlite3") if (cell_dir / "agent_budget.sqlite3").is_file() else None
    has_rounds = False
    for session in sorted(cell_dir.glob("session_run*")):
        ledger = _inside(cell_dir, session.name, "session.sqlite3")
        if ledger.is_file():
            with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True)) as db:
                for key, query in {
                    "memory_search_count": "SELECT count(*) FROM memory_searches WHERE status IN ('hit','no_hits')",
                    "memory_read_count": "SELECT count(*) FROM memory_reads WHERE status != 'failed' AND returned_chars > 0",
                    "memory_write_count": "SELECT count(*) FROM memory_writes WHERE status = 'published'",
                }.items():
                    counts[key] += db.execute(query).fetchone()[0]
        if (session / "rounds").is_dir():
            has_rounds = True
            for round_dir in sorted(session.glob("rounds/round_*")):
                plan_path = round_dir / "plan.json"
                if plan_path.is_file():
                    plan_doc = _read(plan_path)
                    cited = (plan_doc.get("interface_selection") or {}).get("cited_kb_ids") or plan_doc.get("cited_kb_ids") or []
                    if cited:
                        counts["kb_cited_rounds"] += 1
                cons_path = round_dir / "memory_consumption.json"
                if cons_path.is_file():
                    consumption = _read(cons_path)
                    if consumption.get("compiled"):
                        counts["memory_injected_rounds"] += 1
                    facts_path = round_dir / "evaluation_facts.json"
                    if facts_path.is_file():
                        outcomes = list(iter_attributed_outcomes(
                            session,
                            _read(facts_path),
                            consumption,
                            request_ledger=budget_ledger,
                            request_run_id=config.get("run_id") if config else None,
                        ))
                        if outcomes:
                            counts["memory_gateway_attributed_rounds"] += 1
                            counts["memory_attributed_candidate_count"] += len(outcomes)
    if config and ((not config["memory_enabled"] and any(counts[key] for key in counts if key.startswith("memory_")))
                   or (not config["memory_online_writeback_enabled"] and counts["memory_write_count"])):
        raise ValueError("wave4_b3_unexpected_memory_activity")
    read_only_memory_intact = True
    if arm == B3_ARMS[2]:
        seed_receipt = _inside(cell_dir, "memory_seed.json")
        store_path = config.get("memory_store_path")
        store = Path(store_path) if store_path else cell_dir / "memory"
        read_only_memory_intact = (
            seed_receipt.is_file() and store.is_dir() and _memory_assets(store) == _read(seed_receipt)
        )
    return {
        **counts,
        "read_only_memory_intact": read_only_memory_intact,
        **zero_alarms(
            arm,
            counts,
            live_mode=bool(config and config.get("mode") == "live"),
            check_injection=bool(config or has_rounds),
            read_only_memory_intact=read_only_memory_intact,
        ),
    }


def _sandbox_cell(run: Path) -> dict:
    raw = inspect_scripts(run)
    checkpoint = _read(run / "agent_checkpoint.json")
    events = checkpoint["trajectory_control_events"]
    required = {event["round_id"] for event in events if event["event"] == "strict_diagnostic_round_required"}
    satisfied = {event["round_id"] for event in events if event["event"] == "strict_diagnostic_round_satisfied"}
    failed = set()
    recovered = set()
    attempts = {}
    for event in events:
        if event["event"] != "strict_sandbox_attempt":
            continue
        rid = event["round_id"]
        attempts[event["artifact_ref"]] = event["has_finite_numeric_evidence"]
        if not event["has_finite_numeric_evidence"]:
            failed.add(rid)
        elif rid in failed:
            recovered.add(rid)
    scripts = raw["scripts"]
    errors = list(raw["errors"])
    if attempts != {item["artifact_ref"]: item["finite_numeric_evidence"] for item in scripts}:
        errors.append("wave4_script_trajectory_binding_mismatch")
    if raw["orphan_scripts"] or any(item["uncommitted"] for item in scripts):
        errors.append("wave4_orphan_or_uncommitted_script")
    if (checkpoint.get("round_plan_args") or {}).get("diagnostic_bypassed_on_cap"):
        errors.append("wave4_bypassed_plan")
    return {"phase": raw["final_phase"], "scripts_executed": len(scripts),
            "valid_scripts": sum(item["finite_numeric_evidence"] for item in scripts),
            "gate_bypass_count": raw["gate_bypass_count"], "diagnostic_rounds_required": len(required),
            "diagnostic_rounds_completed": len(required & satisfied), "self_repair_rounds": len(recovered),
            "rounds_with_failed_scripts": len(failed), "errors": errors,
            "script_artifacts": [{key: row[key] for key in ("artifact_ref", "artifact_sha256", "script_sha256",
                                 "finite_numeric_evidence", "error_code")} for row in scripts]}


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _sandbox_rates(rows) -> dict:
    rows = list(rows)
    counters = ("scripts_executed", "valid_scripts", "gate_bypass_count", "diagnostic_rounds_required",
                "diagnostic_rounds_completed", "self_repair_rounds", "rounds_with_failed_scripts")
    result = {key: sum(row[key] for row in rows) for key in counters}
    result.update(cell_count=len(rows), success_cells=sum(row["valid_scripts"] > 0 for row in rows),
                  valid_script_execution_rate=_rate(result["valid_scripts"], result["scripts_executed"]),
                  post_repair_diagnostic_round_completion_rate=_rate(result["diagnostic_rounds_completed"],
                                                                     result["diagnostic_rounds_required"]),
                  fail_to_pass_rate=_rate(result["self_repair_rounds"], result["rounds_with_failed_scripts"]))
    result["cell_sandbox_success_rate"] = _rate(result["success_cells"], len(rows))
    return result


def _finished(config: AgentConfig) -> dict | None:
    run = Path(config.output_dir)
    path = _inside(run, "research_summary.json")
    if not path.is_file():
        return None
    summary = _read(path)
    actual = AgentConfig.from_dict(_read(_inside(run, "agent_config.json")))
    checkpoint = _read(_inside(run, "agent_checkpoint.json"))
    if (actual != config or summary.get("run_id") != config.run_id or checkpoint.get("run_id") != config.run_id
            or summary.get("final_phase") not in TERMINAL or summary.get("final_phase") != checkpoint.get("phase")):
        raise ValueError(f"wave4_invalid_terminal_cell:{config.run_id}")
    return summary


def _pilot_audit(root: Path, args, pin, protocol) -> dict:
    rows = {}
    for cell in PILOT_CELLS:
        config = _persisted_config(root, cell, args, pin, b3=False)
        if config is None or _finished(config) is None:
            continue
        rows[_key(cell)] = _sandbox_cell(Path(config.output_dir))
    models = {model: _sandbox_rates(value for key, value in rows.items() if key.startswith(model + "/")) for model in MODELS}
    overall = _sandbox_rates(rows.values())
    missing = [_key(cell) for cell in PILOT_CELLS if _key(cell) not in rows]
    passed = not missing and not any(row["errors"] for row in rows.values()) and all(
        item["valid_script_execution_rate"] is not None and item["valid_script_execution_rate"] >= 0.8
        and item["gate_bypass_count"] == 0 for item in (*models.values(), overall))
    return {"schema_version": "wave4-b2-pilot-audit/v1", "protocol_sha256": sha256_file(root / "b2_protocol.json"),
            "run_mode": protocol["run_mode"], "models": models, "overall": overall, "cells": rows, "missing_cells": missing,
            "definitions": {"valid_script_execution_rate": "ok and finite-numeric scripts divided by executed scripts",
                            "cell_sandbox_success_rate": "cells with at least one valid script divided by audited cells",
                            "post_repair_diagnostic_round_completion_rate": "required rounds with verified evidence divided by required rounds",
                            "fail_to_pass_rate": "rounds with valid evidence after a script failure divided by rounds with failures"},
            "passed": passed}


def _require_approval(root: Path, args, pin, protocol) -> None:
    if args.live:
        audit_path = _inside(root, PILOT_AUDIT)
        approved = _read(_inside(root, APPROVAL))
        current = _pilot_audit(root, args, pin, protocol)
        if (approved != {"audit_sha256": sha256_file(audit_path), "protocol_sha256": current["protocol_sha256"]}
                or current != _read(audit_path) or current["passed"] is not True):
            raise ValueError("wave4_b2_pilot_approval_mismatch")


def _cell_pin(arm: str, pin, fork):
    return fork["merged_kb"] if fork is not None and arm in B3_ARMS[2:] else pin


def _persisted_config(root, cell, args, pin, *, b3):
    expected = _config(root, cell, args, pin, b3=b3)
    path = _inside(Path(expected.output_dir), "agent_config.json")
    if not path.is_file():
        return None
    stored = AgentConfig.from_dict(_read(path))
    # Live evaluation uses each cell's registered endpoint without a provider call.
    endpoint_args = argparse.Namespace(**{**vars(args), "endpoint": stored.endpoint, "api_key_env": stored.api_key_env})
    expected = _config(root, cell, endpoint_args, pin, b3=b3)
    if stored != expected or (args.live and stored.endpoint.startswith("mock://")):
        raise ValueError(f"wave4_cell_config_mismatch:{stored.run_id}")
    return stored


class _Wave4MockDriver(ScriptedMockAgentDriver):
    def _next_scripted_action(self, *, round_id, phase, step_index, last_tool_result):
        if phase == "reflect":
            return {"action": "finish_round", "summary": "Completed Wave 4 mock reflection."}
        arm = self.config.arm_id
        if arm in B3_ARMS:
            if step_index == 0:
                query = "CVRP static merge" if arm in B3_ARMS[2:] else "CVRP"
                return {"action": "call_tool", "tool": "kb_search", "arguments": {"query": query}}
            if step_index == 1 and (last_tool_result or {}).get("results"):
                hit = last_tool_result["results"][0]
                return {"action": "call_tool", "tool": "kb_read", "arguments": {"entry_id": hit["id"]}}
            if self.config.memory_enabled and step_index == 2:
                return {"action": "call_tool", "tool": "memory_search", "arguments": {"query": ""}}
            if step_index == 3 and (last_tool_result or {}).get("memories"):
                hit = last_tool_result["memories"][0]
                return {"action": "call_tool", "tool": "memory_read", "arguments": {"reference": hit["reference"]}}
        elif round_id == 2 and B2_ARMS[arm] == "sandbox_only" and step_index < 5:
            script = "RESULT = {'value': float('nan')}" if step_index == 0 else (
                "insts = load_dev_suite(max_instances=4)\n"
                "RESULT = {'dev_count': len(insts), 'demo': float(isinstance(repr(insts[0]['size']), str))}")
            return {"action": "call_tool", "tool": "run_math_sandbox", "arguments": {"script": script}}
        elif round_id == 2 and B2_ARMS[arm] == "slice_only" and step_index == 0:
            return {"action": "call_tool", "tool": "diagnose_suite", "arguments": {"max_instances": 4}}
        return {"action": "submit_plan", "template_id": STATIC, "postprocess_mode": "relocate_2opt",
                "direction": "Check a scale-invariant CVRP merge ranking on the dev profile.",
                "hypothesis": "Normalized savings preserve a useful merge ordering.", "cited_kb_ids": []}


def _run_cell(root, cell, args, pin, *, fork=None, b3=False) -> dict:
    if args.live and (args.endpoint.startswith("mock://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1"):
        raise ValueError("wave4_live_cell_has_mock_endpoint_or_environment")
    config = _config(root, cell, args, _cell_pin(cell[2], pin, fork), b3=b3)
    run = Path(config.output_dir)
    roster = _inside(root, "b3_roster_lock.json" if b3 else "b2_roster_lock.json")
    run.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(_inside(run, ".cell.lock"), busy=f"wave4_cell_busy:{config.run_id}"):
        summary = _finished(config)
        if summary is None:
            if roster.exists():
                raise ValueError("wave4_evaluation_roster_already_locked")
            if b3:
                _install_memory(root, config, fork)
            def session_factory(**kwargs):
                session = session_tools.SessionRunnerTool(**kwargs)
                if not args.live:
                    mock_driver.budget = session.budget
                    mock_driver.session_dir = session.session_dir
                return session

            mock_driver = None if args.live else _Wave4MockDriver(config=config, budget=None, session_dir=None)
            common_start = _read(_inside(root, "dev_seed", "common_start.json")) if b3 else None
            with _json_session_profile():
                summary = research_loop.run_research_agent(config, driver=mock_driver, session_factory=session_factory,
                                                           resume=(run / "agent_checkpoint.json").is_file(),
                                                           common_start=common_start)
        audit = audit_b3_cell(run, config.arm_id) if b3 else _sandbox_cell(run)
        _check_artifacts(run)
        payload = {"cell": _key(cell), "phase": summary["final_phase"], **audit}
        atomic_write_json(run / "wave4_cell_audit.json", payload)
        return payload


def _cell_command(cell, args, *, b3, phase):
    model, seed, arm = cell
    command = [sys.executable, str(Path(__file__).resolve()), "--stage", "b3_cell" if b3 else "b2_cell",
               "--phase", phase, "--output-dir", str(args.output_dir), "--model", model, "--seed", str(seed),
               "--arm", arm, "--endpoint", args.endpoint, "--api-key-env", args.api_key_env]
    if args.live:
        command.append("--live")
    if args.custody_dir is not None:
        command.extend(("--custody-dir", str(args.custody_dir)))
    command.append("--resume")
    return command


def _mux(root, cells, args, pin, *, phase, fork=None) -> dict:
    b3 = fork is not None
    panes, skipped, alarms = [], [], []
    for cell in cells:
        config = _persisted_config(root, cell, args, _cell_pin(cell[2], pin, fork), b3=b3)
        if config is not None and _finished(config) is not None:
            skipped.append(_key(cell))
            if b3:
                audit = audit_b3_cell(Path(config.output_dir), config.arm_id)
                if not audit["attribution_valid"]:
                    alarms.append({"cell": _key(cell), **audit})
            continue
        model, seed, arm = cell
        command = _cell_command(cell, args, b3=b3, phase=phase)
        panes.append({"id": f"{model}-{seed}-{arm}", "command": command, "cwd": str(REPO)})
    payload = {"panes": panes, "roster": [_key(cell) for cell in cells], "skipped_terminal_cells": skipped,
               "hard_alarms": alarms}
    atomic_write_json(root / ("b3_mux.json" if b3 else f"b2_{phase}_mux.json"), payload)
    return payload


def _champion(config: AgentConfig, summary: Mapping) -> tuple[FrozenInterfaceSolver | None, dict]:
    run = Path(config.output_dir)
    spend = summary["realized_request_spend"]
    ledger = _inside(run, "agent_budget.sqlite3")
    with closing(sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True)) as db:
        requests = db.execute("SELECT idx,state FROM budget_requests WHERE run_id=? ORDER BY idx", (config.run_id,)).fetchall()
        if (type(spend) is not int or not 0 <= spend <= REQUEST_CAP or len(requests) != spend or any(
                index != number or status in {"reserved", "sent"} for number, (index, status) in enumerate(requests, 1))):
            raise ValueError(f"wave4_request_ledger_mismatch:{config.run_id}")
        if spend == REQUEST_CAP:
            path = _inside(run, "checkpoints", f"frozen_checkpoint_{REQUEST_CAP}.json")
            digest = sha256_file(path)
            record = db.execute("SELECT state,payload_sha256,settled_through_ordinal FROM milestone_checkpoints"
                                " WHERE run_id=? AND ckpt_budget=?", (config.run_id, REQUEST_CAP)).fetchone()
            if record != ("sealed", digest, REQUEST_CAP):
                raise ValueError(f"wave4_budget_checkpoint_unsealed:{config.run_id}")
            payload = _read(path)["frozen_solver"]
        elif ref := summary.get("best_solver_manifest_ref"):
            path = _inside(run, ref)
            digest = sha256_file(path)
            payload = _read(path)
            candidates = db.execute("SELECT solver_manifest_json FROM candidate_provenance WHERE run_id=?"
                                    " AND global_ordinal<=? AND eligible=1", (config.run_id, spend))
            if not any(text and json.loads(text) == payload for (text,) in candidates):
                raise ValueError(f"wave4_champion_provenance_mismatch:{config.run_id}")
        else:
            payload = digest = None
    solver = FrozenInterfaceSolver.from_dict(payload) if payload is not None else None
    if solver is not None:
        template = get_template_spec(solver.template_id, solver.template_version)
        if (solver.problem_family != "cvrp" or solver.template_id not in config.allowed_templates
                or solver.template_version != config.version_for_template(solver.template_id)
                or solver.template_source_sha256 != template.template_source_sha256 or solver.hook_specs != template.hook_specs
                or solver.postprocess_mode not in config.allowed_postprocess_modes):
            raise ValueError(f"wave4_champion_template_mismatch:{config.run_id}")
    return solver, {"phase": summary["final_phase"], "requests_used": spend, "source_sha256": digest,
                    "bundle_hash": solver.bundle_hash if solver else None}


def _lock_roster(root, cells, args, pin, *, fork=None) -> tuple[dict, str]:
    b3 = fork is not None
    path = _inside(root, "b3_roster_lock.json" if b3 else "b2_roster_lock.json")
    solvers, rows = {}, {}
    for cell in cells:
        key = _key(cell)
        config = _persisted_config(root, cell, args, _cell_pin(cell[2], pin, fork), b3=b3)
        summary = _finished(config) if config is not None else None
        if summary is None:
            raise ValueError(f"wave4_missing_terminal_cell:{key}")
        run = Path(config.output_dir)
        if b3 and cell[2] == B3_ARMS[2]:
            seed_receipt = _inside(run, "memory_seed.json")
            if not seed_receipt.is_file() or _read(seed_receipt) != fork["memory_assets"]:
                raise ValueError(f"wave4_b3_memory_seed_mismatch:{key}")
        solvers[key], row = _champion(config, summary)
        audit = audit_b3_cell(run, config.arm_id) if b3 else _sandbox_cell(run)
        if not b3 and (audit["errors"] or audit["gate_bypass_count"]):
            raise ValueError(f"wave4_b2_roster_script_or_gate_audit_failed:{key}")
        rows[key] = {**row, "audit": audit, "config_sha256": sha256_file(run / "agent_config.json")}
    binding = root / ("b3_fork_roster.json" if b3 else "b2_protocol.json")
    roster = {"run_mode": "live" if args.live else "mock", "binding_sha256": sha256_file(binding),
              "deadline_ms": DEADLINE_MS, "workers": 1, "cells": rows}
    if path.is_file():
        if _read(path) != roster:
            raise ValueError("wave4_locked_roster_drift")
    else:
        _write_once(path, roster)
    return solvers, sha256_file(path)


def _public_suite(spec, *, live: bool):
    suite_id, split, role = spec
    suite = load_dev_or_public_suite(suite_id, split=split, role=role)
    if len(suite["instances"]) != SUITE_COUNTS[suite_id]:
        raise ValueError(f"wave4_suite_count_mismatch:{suite_id}")
    return suite if live else {**suite, "instances": suite["instances"][:3]}


def _score_suite(suite, solvers: Mapping) -> dict:
    records = {key: [] for key in solvers}
    keys = tuple(solvers)
    exact = suite["vehicle_limit_policy"] != "free_fleet_min_k_lb"
    for index, instance in enumerate(suite["instances"]):
        offset = index % len(keys)
        for key in (*keys[offset:], *keys[:offset]):
            solver = solvers[key]
            result = (evaluate_frozen_interface_solver(solver, instance, distance_convention=suite["distance_convention"],
                      vehicle_limit_policy=suite["vehicle_limit_policy"], solve_deadline_ms=DEADLINE_MS,
                      enforce_wall_deadline=True, capture_timed_incumbents=True)
                      if solver is not None else {})
            if result.get("error_code") in {"worker_protocol", "worker_crash", "worker_start_failed"}:
                raise RuntimeError(f"wave4_evaluator_worker_failed:{result['error_code']}")
            row = build_m5_public_record(instance, result, solve_deadline_ms=DEADLINE_MS, exact_k_applicable=exact)
            on_time = (result.get("returned_before_deadline") is True and row["solve_ms"] is not None
                       and row["solve_ms"] < DEADLINE_MS)
            records[key].append({**row, "returned_before_deadline": on_time,
                                 "completed": row["completed"] and on_time})
    return records


def _comparison(records, cells) -> dict:
    groups = {}
    for model, seed, arm in cells:
        groups.setdefault(model, {}).setdefault(seed, []).append(arm)
    contrasts = []
    for model, seeds in groups.items():
        by_model = []
        for seed, arms in seeds.items():
            per_seed = []
            for left, right in combinations(arms, 2):
                control, treatment = records[_key((model, seed, left))], records[_key((model, seed, right))]
                per_seed.append({"model": model, "seed": seed, "treatment": right, "control": left,
                    **{fleet: _paired_tests(treatment, control, seed, exact=fleet == "exact_k") for fleet in FLEETS}})
            for fleet, denominator in product(FLEETS, DENOMINATORS):
                tests = [row[fleet][denominator] for row in per_seed]
                active = [test for test in tests if test["wilcoxon"] is not None]
                adjusted = holm_bonferroni_adjust([test["wilcoxon"]["p_two_sided"] for test in active])
                for test in tests:
                    test["wilcoxon_p_holm"] = None
                for test, p_value in zip(active, adjusted, strict=True):
                    test["wilcoxon_p_holm"] = p_value
            by_model.extend(per_seed)
        contrasts.extend(by_model)
    return {"per_cell": {key: _fleet_metrics(rows) for key, rows in records.items()}, "per_seed_contrasts": contrasts}


def _transfer_alarms(suites, audits, *, live: bool) -> dict:
    x_suite = "cvrp_ext_cvrplib_x_100"
    transfer = []
    for suite_id, records in suites.items():
        for _model, seed, arm in B3_CELLS:
            if arm == B3_ARMS[0]:
                continue
            model = MODELS[0]
            control = records[_key((model, seed, B3_ARMS[0]))]
            key = _key((model, seed, arm))
            treated = records[key]
            control_count = sum(row["completed"] for row in control)
            treated_count = sum(row["completed"] for row in treated)
            common = [(t["objective"], c["objective"]) for t, c in zip(treated, control, strict=True)
                      if t["completed"] and c["completed"]]
            delta = sum(t - c for t, c in common) / len(common) if common else None
            transfer.append({"suite_id": suite_id, "cell": key, "control_completed": control_count,
                "treatment_completed": treated_count, "denominator": len(control), "common_completed": len(common),
                "common_completed_mean_treatment_minus_control": delta,
                "negative_transfer": treated_count < control_count or (delta is not None and delta > 0),
                "attribution_valid": audits[key]["attribution_valid"] and audits[_key((model, seed, B3_ARMS[0]))]["attribution_valid"]})
    parity = all(sum(row["completed"] for row in rows) == (100 if live else len(rows))
                 for rows in suites[x_suite].values())
    return {"set_x_all_cells_complete": parity, "set_x_expected_completed": 100 if live else 3,
            "negative_transfer_checks": transfer}


def _evaluate(root, args, pin, *, protocol=None, fork=None) -> dict:
    b3 = fork is not None
    cells = B3_CELLS if b3 else B2_CELLS
    path = _inside(root, "b3_evaluation.json" if b3 else "b2_evaluation.json")
    if path.exists():
        raise FileExistsError("wave4_evaluation_already_published")
    solvers, roster_sha = _lock_roster(root, cells, args, pin, fork=fork)
    specs = (SELECT, *EXTERNAL_CVRPLIB_SUITES, FINAL) if b3 else EXTERNAL_CVRPLIB_SUITES
    suites = {spec[0]: _score_suite(_public_suite(spec, live=args.live), solvers) for spec in specs}
    if not b3:
        if protocol["commitment_sha256"] != sha256_file(root / COMMITMENT):
            raise ValueError("wave4_commitment_digest_changed")
        blind = _claim_blind(root, args, roster_sha)
        try:
            suites[BLIND] = _score_suite(blind, solvers)
        except Exception:
            raise RuntimeError("wave4_blind_evaluation_failed_attempt_consumed") from None
    report = {"roster_sha256": roster_sha, "workers": 1, "deadline_ms": DEADLINE_MS,
              "pool_seeds": False, "suites": {key: {**_comparison(rows, cells), "records": rows} for key, rows in suites.items()}}
    locked = _read(root / ("b3_roster_lock.json" if b3 else "b2_roster_lock.json"))
    audits = {key: row["audit"] for key, row in locked["cells"].items()}
    if b3:
        hard = {key: audit for key, audit in audits.items() if not audit["attribution_valid"]}
        report.update(memory_kb_audit=audits, hard_alarms=hard, attribution_valid=not hard,
                      **_transfer_alarms(suites, audits, live=args.live))
        report["passed"] = not hard and report["set_x_all_cells_complete"]
    else:
        report.update(script_audit=audits, sandbox_rates=_sandbox_rates(audits.values()), passed=True)
    _write_once(path, report)
    return {"evaluation": str(path), "passed": report["passed"], "hard_alarms": report.get("hard_alarms", {}),
            **({"sandbox_rates": report["sandbox_rates"]} if not b3 else
               {"set_x_all_cells_complete": report["set_x_all_cells_complete"]})}


def _mock(root, args, pin, *, b3):
    if args.live:
        raise ValueError("wave4_mock_stage_cannot_be_live")
    if b3:
        _dev_source(root, args)
        fork = _freeze_fork(root, args, pin)
        cells = [cell for cell in B3_CELLS if cell[1] == SEEDS[0]]
    else:
        _seal(root, args, pin)
        fork = None
        cells = [cell for cell in B2_CELLS if cell[:2] == (MODELS[0], SEEDS[0])]
    def run_mock_cell(cell):
        result = subprocess.run(_cell_command(cell, args, b3=b3, phase="full"), cwd=REPO,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        path = _inside(root, "runs", *_key(cell).split("/"), "wave4_cell_audit.json")
        if result.returncode and not (b3 and path.is_file() and not _read(path)["attribution_valid"]):
            raise RuntimeError(f"wave4_mock_cell_failed:{_key(cell)}\n{result.stderr[-4000:]}")
        return _key(cell), _read(path)

    with ThreadPoolExecutor(max_workers=2) as workers:
        audits = dict(workers.map(run_mock_cell, cells))
    if b3:
        passed = all(row["attribution_valid"] for row in audits.values()) and bool(fork["rejected_candidates"])
    else:
        sandbox = audits[_key(cells[-1])]
        passed = (all(not row["errors"] and row["gate_bypass_count"] == 0 for row in audits.values())
                  and sandbox["self_repair_rounds"] > 0 and sandbox["diagnostic_rounds_completed"] > 0)
    prefix = "b3" if b3 else "b2"
    report = {"schema_version": f"wave4-{prefix}-mock/v1", "passed": passed, "cells": audits}
    atomic_write_json(root / f"{prefix}_mock_report.json", report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if values[:1] == ["--session-process"]:
        return _session_process(values[1], values[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("b2_mock", "b2_seal", "b2_pilot_mux", "b2_cell", "b2_pilot_audit",
        "b2_full_mux", "b2_eval", "b3_mock", "b3_build_dev_seed", "b3_freeze_fork", "b3_mux", "b3_cell", "b3_eval"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--custody-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--phase", choices=("pilot", "full"), default="full")
    parser.add_argument("--model", choices=MODELS, default=MODELS[0])
    parser.add_argument("--seed", type=int, choices=SEEDS, default=SEEDS[0])
    parser.add_argument("--arm", choices=(*B2_ARMS, *B3_ARMS))
    parser.add_argument("--endpoint", default="https://llmapi.paratera.com/v1/chat/completions")
    parser.add_argument("--api-key-env", default="PARATERA_API_KEY")
    parser.add_argument("--approve-pilot", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(values)
    args.output_dir = _output(args.output_dir)
    if args.custody_dir is not None:
        args.custody_dir = args.custody_dir.resolve()
    stage = args.stage
    b3 = stage.startswith("b3_")
    root = _inside(args.output_dir, "b3_memory_kb" if b3 else "b2_sandbox")
    if not args.live:
        root = _inside(root, "mock")
    _check_artifacts(root)
    pin = _base_pin()
    cell = (args.model, args.seed, args.arm)
    try:
        if stage in {"b2_mock", "b3_mock"}:
            payload = _mock(root, args, pin, b3=b3)
        elif stage == "b2_seal":
            payload = _seal(root, args, pin)
        elif stage == "b3_build_dev_seed":
            payload = _dev_source(root, args)
        elif stage == "b3_freeze_fork":
            payload = _freeze_fork(root, args, pin)
        elif b3:
            fork = _b3_fork(root, args, pin)
            if stage == "b3_mux":
                payload = _mux(root, B3_CELLS, args, pin, phase="full", fork=fork)
            elif stage == "b3_cell":
                if cell not in B3_CELLS:
                    raise ValueError("wave4_b3_cell_not_registered")
                payload = _run_cell(root, cell, args, pin, fork=fork, b3=True)
            else:
                payload = _evaluate(root, args, pin, fork=fork)
        else:
            protocol = _b2_protocol(root, args, pin)
            if stage == "b2_pilot_audit":
                payload = _pilot_audit(root, args, pin, protocol)
                audit_path = _inside(root, PILOT_AUDIT)
                atomic_write_json(audit_path, payload)
                if args.approve_pilot and payload["passed"]:
                    atomic_write_json(_inside(root, APPROVAL), {"audit_sha256": sha256_file(audit_path),
                                                               "protocol_sha256": payload["protocol_sha256"]})
            elif stage in {"b2_pilot_mux", "b2_full_mux"}:
                pilot = stage == "b2_pilot_mux"
                if not pilot:
                    _require_approval(root, args, pin, protocol)
                payload = _mux(root, PILOT_CELLS if pilot else B2_CELLS, args, pin, phase="pilot" if pilot else "full")
            elif stage == "b2_cell":
                if cell not in (PILOT_CELLS if args.phase == "pilot" else B2_CELLS):
                    raise ValueError("wave4_b2_cell_not_registered")
                if args.phase == "full":
                    _require_approval(root, args, pin, protocol)
                payload = _run_cell(root, cell, args, pin)
            else:
                _require_approval(root, args, pin, protocol)
                payload = _evaluate(root, args, pin, protocol=protocol)
    except ProviderFailure as exc:
        print(json.dumps({"status": "resumable", "reason": exc.error_code}), file=sys.stderr)
        return 75
    _check_artifacts(root)
    print(json.dumps(payload, ensure_ascii=True, allow_nan=False, indent=2))
    return int(payload.get("passed") is False or payload.get("attribution_valid") is False or bool(payload.get("hard_alarms")))


if __name__ == "__main__":
    raise SystemExit(main())
