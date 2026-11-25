"""Run the M3.5 unified-base-KB common-start re-test in separate stages."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import sys
from collections.abc import Mapping, Sequence
from contextlib import ExitStack, closing
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.file_lock import exclusive_file_lock
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver
from agent_skill_loop.memory import MemoryAPI
from agent_skill_loop.memory.api import solution_execution_ast_sha256
from agent_skill_loop.memory.auto_dream import auto_dream
from knowledge_tools import SCHEMA_VERSION as KB_SCHEMA_VERSION
from research_agent.contracts import AgentConfig, atomic_write_json, sha256_bytes, sha256_file
from research_agent.loop import run_research_agent
from research_agent.tools.kb_tools import verify_pinned_release
from tools import run_m35_memory_ablation as v1
from tools.m35_pure_kb_analysis import audit_cell, suite_report
from tools.run_m5_trajectory_control import TERMINAL_PHASES, _completed, _open_ledger, _penalized

SEEDS, REQUEST_CAP, SOLVE_MS, MODEL = v1.SEEDS, v1.REQUEST_CAP, v1.SOLVE_MS, v1.MODEL
RELEASE_ID = "20261124-main-co-workbench-m4"
BASE_MANIFEST_SHA256 = "3c9e5507de4a503bb7f9a577dac4dbbc164ab9cb3d1cc5ec193ba39112003b3f"
BASE_COUNT = 354
ARMS = {
    "arm_m35v2_0_base_kb_only": "off",
    "arm_m35v2_1_online_writeback": "m35_l12",
    "arm_m35v2_2_offline_l3_switch": "m35_full",
    "arm_m35v2_3_full_closed_loop": "m35_full",
}
ARM_0, ARM_1, ARM_2, ARM_3 = ARMS
CONTRASTS = tuple((arm, comparator) for index, arm in enumerate(ARMS) for comparator in tuple(ARMS)[:index])
OFFLINE_LABEL = "离线整理记忆读取 + 合并式 L3 KB 切换（无在线写回）"
SELECT = v1.SELECT[0]
INDEPENDENT = (*v1.EXTERNAL_CVRPLIB_SUITES, ("cvrp_final_accept_120", "heldout", "final_acceptance"))
SUITE_COUNTS = dict(zip((spec[0] for spec in (SELECT, *INDEPENDENT)), (64, 74, 100, 120), strict=True))
DEFAULT_OUTPUT = REPO / "experiments" / "milestone3_5_pure_kb_retest"
MERGED_ROOT = "runs/dream/l3_merged_release"
ROSTER = "m35v2_fork_roster.json"
FORK = "common_start_manifest.json"
SHORTLIST = "dev_shortlist.json"
SELECT_EVAL = "select_evaluation.json"
CHAMPIONS = "frozen_champions.json"
INDEPENDENT_EVAL = "independent_evaluation.json"
REPORT = "m35_pure_kb_retest_report.json"
SHORTLIST_SIZE = 4
EMPTY_STORE_SHA256 = v1._digest({})


def _base_pin() -> dict[str, str]:
    return {"release_dir": str(REPO / "knowledge_store" / "releases" / RELEASE_ID),
            "release_id": RELEASE_ID, "manifest_sha256": BASE_MANIFEST_SHA256}


def _verify_pin(pin: Mapping[str, str]) -> Path:
    path = Path(pin["release_dir"])
    result = verify_pinned_release(path, release_id=pin["release_id"], manifest_sha256=pin["manifest_sha256"])
    if path != Path(result["release"]):
        raise ValueError("m35v2_kb_release_path_mismatch")
    return path


_BASE_SUPPORT_FILES = ("sources.json", "taxonomy.json", "relations.json", "classification.json")


def _base_records(base: Mapping[str, str]) -> tuple[list[dict], dict[str, str]]:
    path = _verify_pin(base)
    entries = v1._json(path / "index.json")["entries"]
    files = {item["path"]: item["sha256"] for item in v1._json(path / "manifest.json")["files"]}
    if len(entries) != BASE_COUNT or len({entry["id"].casefold() for entry in entries}) != BASE_COUNT:
        raise ValueError("m35v2_base_index_count_or_id_collision")
    referenced: dict[str, str] = {}
    for entry in entries:
        for field, hash_field in (("path", "content_sha256"), ("metadata_path", "metadata_sha256")):
            if field == "metadata_path" and field not in entry:
                continue
            rel = entry[field]
            digest = entry[hash_field]
            if (PurePosixPath(rel).as_posix() != rel or rel in {"index.json", "manifest.json", "manifest.sha256"}
                    or files.get(rel) != digest or sha256_file(v1._inside(path, rel)) != digest):
                raise ValueError("m35v2_base_entry_file_binding_mismatch")
            referenced[rel] = digest
    for support in _BASE_SUPPORT_FILES:
        if support in files:
            digest = files[support]
            if sha256_file(v1._inside(path, support)) != digest:
                raise ValueError(f"m35v2_base_support_file_mismatch:{support}")
            referenced[support] = digest
    return entries, referenced


def _promote_merged_base_plus_dev_kb(root: Path, dream: Mapping[str, Any],
                                    base: Mapping[str, str]) -> dict[str, str]:
    """Materialize the original indexed corpus and admitted dev-L3 cards."""
    base_entries, base_files = _base_records(base)
    dream_root = v1._inside(root, "runs/dream")
    dream_path = dream_root / "auto_dream_manifest.json"
    candidates_path = dream_root / "l3_promotion_candidates.json"
    dream_sha = sha256_file(dream_path)
    candidates_bytes = candidates_path.read_bytes()
    candidates_sha = sha256_bytes(candidates_bytes)
    staging = json.loads(candidates_bytes)
    if (not isinstance(staging, dict) or v1._json(dream_path) != dream
            or dream.get("source_split") != "dev" or not dream.get("cards")
            or staging.get("schema_version") != "m35-l3-promotion-candidates/v1"
            or staging.get("source_split") != "dev" or staging.get("activation") != "staged"
            or staging.get("auto_dream_manifest_sha256") != dream_sha or staging.get("candidates") != dream["cards"]):
        raise ValueError("m35v2_l3_promotion_evidence_mismatch")

    release_key = v1._digest([base["manifest_sha256"], candidates_sha])
    release_id = f"m35v2-m4-dev-{release_key[:24]}"
    release_root = v1._inside(root, MERGED_ROOT)
    if release_root != root / MERGED_ROOT:
        raise ValueError("m35v2_merged_release_root_link")
    release_root.mkdir(parents=True, exist_ok=True)
    release = release_root / release_id
    if release.resolve() != release:
        raise ValueError("m35v2_merged_release_link")

    backend = MemoryAPI(dream_root / "memory", read_only=True)
    occupied_ids = {entry["id"].casefold() for entry in base_entries}
    occupied_paths = {rel.casefold() for rel in base_files}
    l3_entries = []
    with TemporaryDirectory(prefix=".staging-", dir=release_root) as temp:
        stage = Path(temp) / release_id
        stage.mkdir()
        for rel, original_sha in base_files.items():
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(base["release_dir"]) / rel, target)
            if sha256_file(target) != original_sha:
                raise ValueError("m35v2_base_copy_hash_mismatch")
        for candidate in staging["candidates"]:
            card = v1._read_card(backend, candidate["reference"])
            evidence = candidate["claim_evidence_manifest"]
            claims = evidence["claims"]
            provenance = card["provenance"]
            if (card["project"] != "cvrp_construct" or provenance.get("source_split") != "dev" or not claims
                    or provenance.get("claim_evidence_manifest_sha256") != v1._digest(evidence)):
                raise ValueError("m35v2_l3_card_evidence_mismatch")
            if card["type"] == "solution":
                canonical = solution_execution_ast_sha256(card["body"])
                if ((card.get("code_anchor") or {}).get("canonical_ast_sha256") != canonical
                        or any(claim["code_anchor"].get("canonical_ast_sha256") != canonical for claim in claims)):
                    raise ValueError("m35v2_l3_solution_code_mismatch")

            identity = v1._digest([card[key] for key in ("project", "scene", "type", "name")])
            entry_id = f"evidence-m35-l3-{identity}"
            rel = f"entries/{entry_id}.md"
            if entry_id.casefold() in occupied_ids:
                raise ValueError("m35v2_l3_entry_id_collision")
            folded = rel.casefold()
            if any(old == folded or old.startswith(folded + "/") or folded.startswith(old + "/")
                   for old in occupied_paths):
                raise ValueError("m35v2_l3_path_collision")
            occupied_ids.add(entry_id.casefold())
            occupied_paths.add(folded)
            body = card["body"].encode("utf-8")
            if sha256_bytes(body) != card["body_sha256"]:
                raise ValueError("m35v2_l3_card_digest_mismatch")
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(body)
            l3_entries.append({
                "id": entry_id, "path": rel, "title": card["description"], "summary": card["description"],
                "type": "evidence", "category": "dev-memory", "problem_family": "cvrp",
                "tags": ["m35", "auto-dream", "dev", card["type"]], "content_sha256": card["body_sha256"],
                "evidence_refs": [claim["evidence_ref"] for claim in claims],
                "attributes": {"knowledge_tier": "l3", "source_split": "dev", "memory_reference": card["reference"],
                               "applicability_scope": card["applicability_scope"], "code_anchor": card["code_anchor"]},
            })
        entries = [*base_entries, *sorted(l3_entries, key=lambda entry: entry["id"])]
        atomic_write_json(stage / "index.json", {"schema_version": KB_SCHEMA_VERSION, "release_id": release_id,
                                                 "entries": entries})
        files = [{"path": path.relative_to(stage).as_posix(), "sha256": sha256_file(path), "size": path.stat().st_size}
                 for path in sorted(stage.rglob("*")) if path.is_file()]
        digest = atomic_write_json(stage / "manifest.json", {
            "schema_version": KB_SCHEMA_VERSION, "release_id": release_id, "self_hash_file": "manifest.sha256",
            "source_split": "dev", "base_release_id": base["release_id"],
            "base_manifest_sha256": base["manifest_sha256"], "auto_dream_manifest_sha256": dream_sha,
            "l3_promotion_candidates_sha256": candidates_sha, "content_digest": v1._digest(files), "files": files,
        })
        (stage / "manifest.sha256").write_text(f"{digest}  manifest.json\n", encoding="utf-8", newline="\n")
        verify_pinned_release(stage, release_id=release_id, manifest_sha256=digest)
        if not release.exists():
            stage.rename(release)

    pin = {"release_dir": str(release), "release_id": release_id, "manifest_sha256": digest}
    actual = v1._json(_verify_pin(pin) / "index.json")["entries"]
    expected_ids = {entry["id"] for entry in base_entries} | {entry["id"] for entry in l3_entries}
    if actual != entries or len(actual) != len(expected_ids) or {entry["id"] for entry in actual} != expected_ids:
        raise ValueError("m35v2_merged_kb_union_mismatch")
    return pin


def _arm_specs(base: Mapping, memory: Mapping) -> dict[str, dict[str, Any]]:
    return {
        arm: {"label": OFFLINE_LABEL if arm == ARM_2 else arm, "kb_enabled": True,
              "kb": memory["merged_kb"] if arm in (ARM_2, ARM_3) else base,
              "memory_enabled": arm != ARM_0, "memory_mode": mode,
              "memory_online_writeback_enabled": arm in (ARM_1, ARM_3),
              "initial_memory_sha256": (None if arm == ARM_0 else EMPTY_STORE_SHA256 if arm == ARM_1 else memory["sha256"])}
        for arm, mode in ARMS.items()
    }


def _arm_configuration(root: Path, fork: Mapping, arm: str) -> AgentConfig:
    seed = fork["seed"]
    spec = fork["arms"][arm]
    pin = spec["kb"]
    run = v1._inside(root, f"runs/{seed}/{arm}")
    if run != root / "runs" / str(seed) / arm:
        raise ValueError("m35v2_cell_path_link")
    return AgentConfig.from_dict({
        **fork["agent"], "run_id": f"{arm}_s{seed}", "output_dir": str(run), "arm_id": arm, "search_seed": seed,
        "kb_enabled": spec["kb_enabled"], "kb_store_path": pin["release_dir"], "pinned_kb_release_id": pin["release_id"],
        "pinned_kb_manifest_sha256": pin["manifest_sha256"], "memory_mode": spec["memory_mode"],
        "memory_enabled": spec["memory_enabled"], "memory_online_writeback_enabled": spec["memory_online_writeback_enabled"],
        "memory_store_path": str(run / "memory") if spec["memory_enabled"] else None,
    })


def cmd_build_dev_seed(args: argparse.Namespace) -> int:
    return v1.cmd_build_dev_seed(args)


def cmd_freeze_fork(args: argparse.Namespace) -> int:
    load_local_env()
    root = v1._output(args)
    runs = v1._inside(root, "runs")
    if runs != root / "runs" or (runs.exists() and runs.is_symlink()):
        raise ValueError("m35v2_runs_path_link_forbidden")
    forbidden = {"knowledge_store", "eoh_frozen", "eohs_v1", ".env", ".secrets", ".agent_skill_custody"}
    if forbidden.intersection(part.casefold() for part in runs.resolve().parts):
        raise ValueError("m35v2_runs_in_protected_location")
    seeds = sorted(set(args.seed or SEEDS))
    if args.mode == "live" and tuple(seeds) != SEEDS:
        raise ValueError("m35v2_live_requires_all_seeds")
    with exclusive_file_lock(runs / "freeze_fork.lock", busy="m35v2_freeze_busy"):
        if (runs / ROSTER).exists():
            raise FileExistsError("m35v2_fork_already_frozen")
        settings = v1._agent_settings(args.mode)
        base = _base_pin()
        _verify_pin(base)
        suite = v1._suite(v1.DEV)
        common = v1._common_start(settings, suite)
        stores, artifacts = args.source_store, args.dev_artifact
        if not stores and not artifacts:
            seed_root = v1._inside(root, "dev_seed")
            if (seed_root / "dev_evidence.json").is_file():
                stores, artifacts = [seed_root / "source_memory"], [seed_root / "dev_evidence.json"]
            elif args.mode == "mock":
                stores, artifacts = v1._mock_memory(runs, common, suite)
        if not stores or not artifacts:
            raise ValueError("m35v2_requires_authorized_dev_sources")
        dream_root = v1._inside(root, "runs/dream")
        store = dream_root / "memory"
        dream = auto_dream(source_stores=stores, dev_artifacts=artifacts, output_store=store, output_dir=dream_root)
        memory = {"path": "runs/dream/memory", "sha256": v1._store_digest(store),
                  "merged_kb": _promote_merged_base_plus_dev_kb(root, dream, base)}
        if memory["sha256"] == EMPTY_STORE_SHA256:
            raise ValueError("m35v2_empty_dream_store")
        forks = {}
        for seed in seeds:
            order = list(ARMS)
            random.Random(seed).shuffle(order)
            forks[str(seed)] = atomic_write_json(v1._inside(root, f"runs/{seed}/{FORK}"), {
                "schema_version": "m35v2-common-start/v1", "seed": seed, "agent": settings,
                "kb": base, "memory": memory, "arms": _arm_specs(base, memory), "arm_launch_order": order,
                "common_start": common, "common_start_sha256": v1._digest(common),
            })
        atomic_write_json(runs / ROSTER, {"schema_version": "m35v2-fork-roster/v1", "mode": args.mode, "forks": forks,
                                          "dev_shortlist_size": SHORTLIST_SIZE, "selection_suite": SELECT[0]})
    v1._emit({"fork_roster": str(runs / ROSTER), "seeds": seeds})
    return 0


def _forks(root: Path) -> dict[int, dict[str, Any]]:
    roster = v1._json(v1._inside(root, f"runs/{ROSTER}"))
    entries = roster["forks"]
    mode = roster["mode"]
    allowed = {str(seed) for seed in SEEDS}
    if (roster.get("schema_version") != "m35v2-fork-roster/v1" or not entries or not set(entries) <= allowed
            or mode not in {"live", "mock"} or (mode == "live" and set(entries) != allowed)
            or roster["dev_shortlist_size"] != SHORTLIST_SIZE or roster["selection_suite"] != SELECT[0]):
        raise ValueError("m35v2_invalid_fork_roster")
    base = _base_pin()
    _verify_pin(base)
    forks = {}
    shared = None
    for raw_seed, digest in entries.items():
        seed = int(raw_seed)
        path = v1._inside(root, f"runs/{seed}/{FORK}")
        fork = v1._json(path)
        memory, agent = fork["memory"], fork["agent"]
        if (sha256_file(path) != digest or fork.get("schema_version") != "m35v2-common-start/v1"
                or fork["seed"] != seed or fork["kb"] != base or fork["arms"] != _arm_specs(base, memory)
                or sorted(fork["arm_launch_order"]) != sorted(ARMS) or memory["path"] != "runs/dream/memory"
                or fork["common_start_sha256"] != v1._digest(fork["common_start"])
                or any(agent.get(key) != value for key, value in {
                    "mode": mode, "planner_model": MODEL, "eoh_model": MODEL, "total_request_cap": REQUEST_CAP,
                    "checkpoint_budgets": [REQUEST_CAP], "strict_checkpoint_barriers": True,
                    "instance_time_budget_ms": SOLVE_MS, "problem_family": "cvrp", "use_benchmark_dev_suite": True,
                    "dev_suite_id": v1.DEV[0], "dev_split": v1.DEV[1], "dev_instance_count": 24,
                }.items()) or agent.get("strict_checkpoint_barriers") is not True
                or agent.get("use_benchmark_dev_suite") is not True):
            raise ValueError(f"m35v2_invalid_fork_manifest:{seed}")
        identity = (memory, agent, fork["common_start_sha256"])
        if shared is None:
            shared = identity
            pin = memory["merged_kb"]
            release = v1._inside(root, f"{MERGED_ROOT}/{pin['release_id']}")
            if release.parent != root / MERGED_ROOT or str(release) != pin["release_dir"]:
                raise ValueError("m35v2_merged_kb_outside_fork")
            manifest = v1._json(_verify_pin(pin) / "manifest.json")
            dream = root / "runs" / "dream"
            candidates_sha = sha256_file(dream / "l3_promotion_candidates.json")
            if (manifest["base_manifest_sha256"] != base["manifest_sha256"] or manifest["source_split"] != "dev"
                    or manifest["auto_dream_manifest_sha256"] != sha256_file(dream / "auto_dream_manifest.json")
                    or manifest["l3_promotion_candidates_sha256"] != candidates_sha
                    or pin["release_id"] != f"m35v2-m4-dev-{v1._digest([base['manifest_sha256'], candidates_sha])[:24]}"
                    or v1._store_digest(v1._inside(root, memory["path"])) != memory["sha256"]):
                raise ValueError("m35v2_fork_seed_evidence_mismatch")
        elif shared != identity:
            raise ValueError("m35v2_cross_seed_fork_mismatch")
        forks[seed] = fork
    return forks


def cmd_emit_mux(args: argparse.Namespace) -> int:
    root = v1._output(args)
    panes = [{"id": f"{arm}_s{seed}", "cwd": str(REPO),
              "command": [sys.executable, str(Path(__file__).resolve()), "--output-dir", str(root), "run-cell",
                          "--seed", str(seed), "--arm", arm, "--resume"]}
             for seed, fork in _forks(root).items() for arm in fork["arm_launch_order"]]
    path = root / "mux_m35_pure_kb.json"
    atomic_write_json(path, {"panes": panes})
    v1._emit({"manifest_path": str(path), "pane_count": len(panes)})
    return 0


def _install_memory(root: Path, fork: Mapping, config: AgentConfig) -> None:
    if not config.memory_enabled:
        return
    run = Path(config.output_dir)
    store = Path(config.memory_store_path)
    card_sha = fork["arms"][config.arm_id]["initial_memory_sha256"]
    expected = {"sha256": card_sha, "common_start_sha256": fork["common_start_sha256"]}
    receipt = run / "initial_memory_receipt.json"
    if receipt.is_file() and v1._json(receipt) != expected:
        raise ValueError("m35v2_initial_memory_receipt_mismatch")
    if store.resolve() != store:
        raise ValueError("m35v2_private_memory_store_link")
    if (run / "agent_checkpoint.json").is_file():
        if not receipt.is_file() or not store.is_dir():
            raise ValueError("m35v2_initial_memory_receipt_required_on_resume")
        if not config.memory_online_writeback_enabled and v1._store_digest(store) != card_sha:
            raise ValueError("m35v2_offline_store_changed")
        return
    store.mkdir(parents=True, exist_ok=True)
    if config.arm_id in (ARM_2, ARM_3):
        source = v1._inside(root, fork["memory"]["path"])
        for path in v1._store_card_files(source):
            destination = v1._inside(store, path.relative_to(source).as_posix())
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and sha256_file(destination) != sha256_file(path):
                raise ValueError("m35v2_existing_initial_card_mismatch")
            if not destination.exists():
                pending = destination.with_suffix(destination.suffix + ".installing")
                if pending.resolve() != pending:
                    raise ValueError("m35v2_initial_card_staging_link")
                shutil.copyfile(path, pending)
                pending.replace(destination)
    if v1._store_digest(store) != card_sha:
        raise ValueError("m35v2_initial_memory_digest_mismatch")
    atomic_write_json(receipt, expected)


def cmd_run_cell(args: argparse.Namespace) -> int:
    load_local_env()
    root = v1._output(args)
    fork = _forks(root)[args.seed]
    config = _arm_configuration(root, fork, args.arm)
    if config.mode == "live" and (v1._endpoint("live") != config.endpoint or not os.environ.get(v1.API_KEY_ENV, "").strip()
                                  or os.environ.get("AGENT_SKILL_M2_MOCK") == "1"):
        raise ValueError("m35v2_live_environment_mismatch")
    run = Path(config.output_dir)
    initial = fork["arms"][args.arm]["initial_memory_sha256"]
    with exclusive_file_lock(run / "run_cell.lock", busy="m35v2_cell_busy"):
        if (root / "runs" / SHORTLIST).exists():
            raise ValueError("m35v2_dev_shortlist_already_frozen")
        resume = (run / "agent_config.json").is_file() or (run / "agent_checkpoint.json").is_file()
        if resume and not args.resume:
            raise FileExistsError("m35v2_existing_run_requires_resume")
        _install_memory(root, fork, config)
        try:
            summary = run_research_agent(config, resume=resume, common_start=fork["common_start"])
        except ProviderFailure as exc:
            if args.arm == ARM_2 and v1._store_digest(Path(config.memory_store_path)) != initial:
                raise ValueError("m35v2_offline_store_changed") from exc
            atomic_write_json(run / "run_interrupt_status.json", {"status": "resumable", "reason": exc.error_code})
            v1._emit({"run_id": config.run_id, "status": "resumable", "reason": exc.error_code})
            return 75
        audit_cell(config, initial_store_sha256=initial)
    v1._emit({"run_id": config.run_id, "status": summary["final_phase"]})
    return 0


def _dev_shortlist(config: AgentConfig, common: Mapping, suite: Mapping) -> tuple[int, list[dict[str, Any]]]:
    run = Path(config.output_dir)
    v1._check_ordinal_zero(run, config.run_id, common)
    with closing(_open_ledger(run / "agent_budget.sqlite3")) as con:
        requests = con.execute("SELECT COUNT(*) FROM budget_requests WHERE run_id=?", (config.run_id,)).fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM candidate_provenance WHERE run_id=? AND generation_status='pending'",
                              (config.run_id,)).fetchone()[0]
        rows = con.execute(
            """SELECT p.*, b.idx AS request_ordinal, b.state AS request_state
               FROM candidate_provenance p
               LEFT JOIN budget_requests b ON b.request_id=p.physical_request_id AND b.run_id=p.run_id
               WHERE p.run_id=? AND p.eligible=1 AND p.generation_status IN ('baseline_seed', 'valid_candidate')""",
            (config.run_id,),
        ).fetchall()
    if pending or not 0 <= requests <= REQUEST_CAP:
        raise ValueError(f"m35v2_unsettled_or_over_budget_cell:{config.run_id}")
    if requests == REQUEST_CAP:
        v1._read_arm_champion(run, config.run_id, config.arm_id, config.search_seed, REQUEST_CAP)
    candidates = []
    for row in rows:
        ordinal = row["global_ordinal"]
        is_base = row["generation_status"] == "baseline_seed"
        completion, objective = row["dev_completion_rate"], row["dev_penalized_mean"]
        if (row["validation_passed"] != 1 or (ordinal == 0) != is_base or not 0 <= ordinal <= requests
                or (not is_base and (row["request_ordinal"] != ordinal or row["request_state"] != "complete"))
                or row["dev_suite_hash"] != (common["dev_suite_hash"] if is_base else suite["content_hash"])
                or row["solve_budget_ms"] != SOLVE_MS or completion is None or not 0 < completion <= 1
                or objective is None or not math.isfinite(objective)):
            raise ValueError(f"m35v2_bad_dev_provenance:{config.run_id}:{ordinal}")
        solver = FrozenInterfaceSolver.from_dict(json.loads(row["solver_manifest_json"]))
        if (solver.problem_family != config.problem_family or solver.template_id not in config.allowed_templates
                or (not is_base and (solver.origin_run != config.run_id or solver.kb_release_id != config.pinned_kb_release_id))
                or row["bundle_hash"] != solver.bundle_hash):
            raise ValueError(f"m35v2_bad_candidate_identity:{config.run_id}:{ordinal}")
        payload = solver.to_dict()
        candidates.append({"ordinal": ordinal, "completion_rate": completion, "penalized_mean": objective,
                           "solver": payload, "digest": v1._digest(payload)})
    seen = set()
    shortlist = []
    for candidate in sorted(candidates, key=lambda row: (-row["completion_rate"], row["penalized_mean"],
                                                         row["ordinal"], row["digest"])):
        solver = candidate["solver"]
        identity = v1._digest([solver.get(key) for key in (
            "protocol_id", "template_id", "template_source_sha256", "postprocess_mode", "template_options",
            "bundle_hash", "hook_code_sha256",
        )])
        if identity not in seen:
            seen.add(identity)
            shortlist.append(candidate)
        if len(shortlist) == SHORTLIST_SIZE:
            break
    if not shortlist:
        raise ValueError(f"m35v2_empty_dev_shortlist:{config.run_id}")
    return requests, shortlist


def _configs(root: Path, forks: Mapping[int, Any]) -> dict[str, AgentConfig]:
    return {f"{seed}:{arm}": _arm_configuration(root, fork, arm) for seed, fork in forks.items() for arm in ARMS}


def _freeze_shortlist(root: Path, forks: Mapping[int, Any]) -> None:
    runs = root / "runs"
    path = runs / SHORTLIST
    if path.is_file():
        return
    configs = _configs(root, forks)
    with ExitStack() as locks:
        for config in configs.values():
            locks.enter_context(exclusive_file_lock(Path(config.output_dir) / "run_cell.lock", busy="m35v2_cell_busy"))
        cells = {}
        suite = v1._suite(v1.DEV)
        for key, config in configs.items():
            summary_path = Path(config.output_dir) / "research_summary.json"
            summary = v1._json(summary_path)
            if summary["run_id"] != config.run_id or summary["final_phase"] not in TERMINAL_PHASES:
                raise ValueError(f"m35v2_cell_not_terminal:{key}")
            fork = forks[config.search_seed]
            audit = audit_cell(config, initial_store_sha256=fork["arms"][config.arm_id]["initial_memory_sha256"])
            requests, candidates = _dev_shortlist(config, fork["common_start"], suite)
            cells[key] = {"summary_sha256": sha256_file(summary_path), "attempted_requests": requests,
                          "outcome": summary["final_phase"], "audit": audit, "candidates": candidates}
        atomic_write_json(path, {"schema_version": "m35v2-dev-shortlist/v1", "fork_sha256": sha256_file(runs / ROSTER),
                                 "cells": cells})


def _load_shortlist(root: Path, forks: Mapping[int, Any]) -> dict[str, Any]:
    runs = root / "runs"
    shortlist = v1._json(runs / SHORTLIST)
    configs = _configs(root, forks)
    if (shortlist.get("schema_version") != "m35v2-dev-shortlist/v1"
            or shortlist["fork_sha256"] != sha256_file(runs / ROSTER) or set(shortlist["cells"]) != set(configs)):
        raise ValueError("m35v2_shortlist_fork_binding_mismatch")
    for key, cell in shortlist["cells"].items():
        if sha256_file(Path(configs[key].output_dir) / "research_summary.json") != cell["summary_sha256"]:
            raise ValueError(f"m35v2_frozen_summary_changed:{key}")
        candidates = cell["candidates"]
        digests = {row["digest"] for row in candidates}
        if (not 0 < len(candidates) <= SHORTLIST_SIZE or len(digests) != len(candidates)
                or any(row["digest"] != v1._digest(row["solver"]) for row in candidates)):
            raise ValueError(f"m35v2_frozen_shortlist_invalid:{key}")
    return shortlist["cells"]


def _evaluation_inputs(spec: tuple[str, str, str], *, mock: bool) -> tuple[dict, Sequence, dict]:
    suite = v1._suite(spec)
    instances = suite["instances"]
    if len(instances) != SUITE_COUNTS[spec[0]]:
        raise ValueError(f"m35v2_unexpected_suite_count:{spec[0]}")
    if mock:
        instances = instances[:3]
    return suite, instances, {"suite_id": spec[0], "split": spec[1], "role": spec[2],
                               "instance_count": len(instances), "instance_set_sha256": v1._digest(instances),
                               "vehicle_limit_policy": suite["vehicle_limit_policy"]}


def _evaluate(solver: FrozenInterfaceSolver, instance: Mapping, suite: Mapping) -> dict[str, Any]:
    row = v1._evaluate(solver, instance, suite)
    if suite["vehicle_limit_policy"] == "free_fleet_min_k_lb":
        # CVRPLIB X supplies a lower bound on fleet size from demand and capacity.
        row.update(exact_k_applicable=False, exact_k_feasible=None)
    return row


def _select_key(rows: Sequence[dict[str, Any]], *, ordinal: int, digest: str) -> tuple[int, float, int, str]:
    return (-sum(_completed(row) for row in rows), sum(_penalized(row) for row in rows) / len(rows), ordinal, digest)


def _load_selection(runs: Path, cells: Mapping, *, mock: bool) -> dict:
    evaluation = v1._json(runs / SELECT_EVAL)
    expected_count = 3 if mock else SUITE_COUNTS[SELECT[0]]
    if (evaluation.get("schema_version") != "m35v2-selection/v1" or evaluation["suite_id"] != SELECT[0]
            or evaluation["split"] != SELECT[1] or evaluation["role"] != SELECT[2]
            or evaluation["instance_count"] != expected_count or set(evaluation["cells"]) != set(cells)
            or evaluation["shortlist_sha256"] != sha256_file(runs / SHORTLIST)
            or evaluation["records_sha256"] != v1._digest(evaluation["cells"])):
        raise ValueError("m35v2_select_binding_mismatch")
    for key, cell in cells.items():
        records = evaluation["cells"][key]
        if set(records) != {row["digest"] for row in cell["candidates"]} or any(
            len(rows) != expected_count for rows in records.values()
        ):
            raise ValueError(f"m35v2_select_candidate_set_mismatch:{key}")
    return evaluation


def _select_winner(candidates: Sequence[dict], records: Mapping) -> dict:
    return min(candidates, key=lambda row: _select_key(records[row["digest"]], ordinal=row["ordinal"], digest=row["digest"]))


def _champion_ref(cell: str) -> str:
    seed, arm = cell.split(":")
    return f"runs/{seed}/{arm}/selected_champion.json"


def _load_champions(root: Path, forks: Mapping[int, Any]) -> tuple[dict, dict[str, FrozenInterfaceSolver]]:
    runs = root / "runs"
    roster = v1._json(runs / CHAMPIONS)
    cells = _load_shortlist(root, forks)
    select = _load_selection(runs, cells, mock=next(iter(forks.values()))["agent"]["mode"] == "mock")
    if (roster.get("schema_version") != "m35v2-frozen-champions/v1" or set(roster["cells"]) != set(cells)
            or roster["selection_sha256"] != sha256_file(runs / SELECT_EVAL)):
        raise ValueError("m35v2_champion_roster_selection_binding_mismatch")
    solvers = {}
    for key, cell in roster["cells"].items():
        expected = _select_winner(cells[key]["candidates"], select["cells"][key])
        winner = cell["winner"]
        path = v1._inside(root, _champion_ref(key))
        payload = v1._json(path)
        if (winner["ref"] != _champion_ref(key) or winner["sha256"] != sha256_file(path)
                or winner["ordinal"] != expected["ordinal"] or payload != expected["solver"]):
            raise ValueError(f"m35v2_frozen_champion_mismatch:{key}")
        solvers[key] = FrozenInterfaceSolver.from_dict(payload)
    return roster, solvers


def cmd_select_and_freeze(args: argparse.Namespace) -> int:
    root = v1._output(args)
    forks = _forks(root)
    runs = root / "runs"
    mock = next(iter(forks.values()))["agent"]["mode"] == "mock"
    with exclusive_file_lock(runs / "selection.lock", busy="m35v2_selection_busy"):
        if (runs / CHAMPIONS).is_file():
            _load_champions(root, forks)
        else:
            _freeze_shortlist(root, forks)
            cells = _load_shortlist(root, forks)
            if not (runs / SELECT_EVAL).is_file():
                suite, instances, info = _evaluation_inputs(SELECT, mock=mock)
                evaluated = {}
                for key, cell in cells.items():
                    evaluated[key] = {}
                    for row in cell["candidates"]:
                        solver = FrozenInterfaceSolver.from_dict(row["solver"])
                        evaluated[key][row["digest"]] = [_evaluate(solver, item, suite) for item in instances]
                atomic_write_json(runs / SELECT_EVAL, {"schema_version": "m35v2-selection/v1", **info,
                                                       "shortlist_sha256": sha256_file(runs / SHORTLIST),
                                                       "cells": evaluated, "records_sha256": v1._digest(evaluated)})
            selection = _load_selection(runs, cells, mock=mock)
            champions = {}
            for key, cell in cells.items():
                winner = _select_winner(cell["candidates"], selection["cells"][key])
                ref = _champion_ref(key)
                digest = atomic_write_json(v1._inside(root, ref), winner["solver"])
                champions[key] = {"winner": {"ref": ref, "sha256": digest, "ordinal": winner["ordinal"]}}
            atomic_write_json(runs / CHAMPIONS, {"schema_version": "m35v2-frozen-champions/v1", "cells": champions,
                                                  "selection_sha256": sha256_file(runs / SELECT_EVAL)})
    v1._emit({"frozen_champions": str(runs / CHAMPIONS)})
    return 0


def _load_independent(runs: Path, *, mock: bool) -> dict:
    evaluation = v1._json(runs / INDEPENDENT_EVAL)
    suites = evaluation["suites"]
    if (evaluation.get("schema_version") != "m35v2-independent-evaluation/v1"
            or evaluation["champions_sha256"] != sha256_file(runs / CHAMPIONS)
            or evaluation["suites_sha256"] != v1._digest(suites) or set(suites) != {spec[0] for spec in INDEPENDENT}):
        raise ValueError("m35v2_independent_evaluation_binding_mismatch")
    for suite_id, split, role in INDEPENDENT:
        suite = suites[suite_id]
        if (suite["suite_id"] != suite_id or suite["split"] != split or suite["role"] != role
                or suite["instance_count"] != (3 if mock else SUITE_COUNTS[suite_id])):
            raise ValueError(f"m35v2_independent_suite_mismatch:{suite_id}")
    return suites


def cmd_eval_independent(args: argparse.Namespace) -> int:
    root = v1._output(args)
    forks = _forks(root)
    runs = root / "runs"
    _, solvers = _load_champions(root, forks)
    mock = next(iter(forks.values()))["agent"]["mode"] == "mock"
    path = runs / INDEPENDENT_EVAL
    with exclusive_file_lock(path.with_suffix(".lock"), busy="m35v2_independent_evaluation_busy"):
        if path.is_file():
            _load_independent(runs, mock=mock)
        else:
            suites = {}
            for spec in INDEPENDENT:
                suite, instances, info = _evaluation_inputs(spec, mock=mock)
                suites[spec[0]] = {**info, "records": {key: [_evaluate(solver, item, suite) for item in instances]
                                                      for key, solver in solvers.items()}}
            atomic_write_json(path, {"schema_version": "m35v2-independent-evaluation/v1",
                                     "champions_sha256": sha256_file(runs / CHAMPIONS),
                                     "suites": suites, "suites_sha256": v1._digest(suites)})
    v1._emit({"independent_evaluation": str(path)})
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    root = v1._output(args)
    forks = _forks(root)
    runs = root / "runs"
    roster, _ = _load_champions(root, forks)
    first = next(iter(forks.values()))
    mode = first["agent"]["mode"]
    suites = _load_independent(runs, mock=mode == "mock")
    wiring = {}
    for key, config in _configs(root, forks).items():
        arm = forks[config.search_seed]["arms"][config.arm_id]
        wiring[key] = audit_cell(config, initial_store_sha256=arm["initial_memory_sha256"])
    path = runs / REPORT
    atomic_write_json(path, {
        "schema_version": "m35v2-report/v1", "mode": mode, "seeds": list(forks), "arms": first["arms"],
        "model": MODEL, "request_cap": REQUEST_CAP, "solve_budget_ms": SOLVE_MS,
        "champions_sha256": sha256_file(runs / CHAMPIONS), "champions": roster["cells"], "arm_wiring": wiring,
        "independent_evaluation_sha256": sha256_file(runs / INDEPENDENT_EVAL),
        "analysis_plan": {"bootstrap_replicates": v1.BOOTSTRAPS, "confidence_level": 0.95, "seed_pooling": False,
                          "overall_failure_penalty_multiplier": 2,
                          "holm_family": "contrasts within each suite, seed, fleet, and denominator"},
        "suites": {name: suite_report(suite, seeds=list(forks), arms=list(ARMS), contrasts=CONTRASTS)
                   for name, suite in suites.items()},
    })
    v1._emit({"report": str(path)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    commands = parser.add_subparsers(dest="command", required=True)
    dev = commands.add_parser("build-dev-seed", help="measure and publish dev-only seed evidence")
    dev.add_argument("--instance-limit", type=int, choices=range(1, 25))
    dev.set_defaults(handler=cmd_build_dev_seed)
    freeze = commands.add_parser("freeze-fork", help="freeze the common start, Dream store and all arm pins")
    freeze.add_argument("--mode", choices=("mock", "live"), default="mock")
    freeze.add_argument("--seed", type=int, choices=SEEDS, action="append", help="optional mock seed subset")
    freeze.add_argument("--source-store", type=Path, action="append")
    freeze.add_argument("--dev-artifact", type=Path, action="append")
    freeze.set_defaults(handler=cmd_freeze_fork)
    commands.add_parser("emit-mux").set_defaults(handler=cmd_emit_mux)
    run = commands.add_parser("run-cell")
    run.add_argument("--seed", type=int, choices=SEEDS, required=True)
    run.add_argument("--arm", choices=ARMS, required=True)
    run.add_argument("--resume", action="store_true")
    run.set_defaults(handler=cmd_run_cell)
    commands.add_parser("select-and-freeze").set_defaults(handler=cmd_select_and_freeze)
    commands.add_parser("eval-independent").set_defaults(handler=cmd_eval_independent)
    commands.add_parser("report").set_defaults(handler=cmd_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
