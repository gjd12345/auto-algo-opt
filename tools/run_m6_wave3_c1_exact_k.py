"""Build, evolve, and evaluate the Wave 3 C1 exact-fleet solver."""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import ExitStack, closing, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent_skill_loop import benchmark, session_actions, session_runner, session_runtime, session_supervisor
from agent_skill_loop.client import ProviderFailure, load_local_env
from agent_skill_loop.cvrp_workbench.baselines_2026 import solve_pyvrp
from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance
from agent_skill_loop.cvrp_workbench.suites import BENCHMARK_ID
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.evidence import report as evidence_report
from agent_skill_loop.file_lock import exclusive_file_lock
from agent_skill_loop.interface_design import session_baseline, session_bridge
from agent_skill_loop.interface_design.blind_eval import paired_bootstrap_comparison
from agent_skill_loop.interface_design.blind_eval_m3 import holm_bonferroni_adjust
from agent_skill_loop.interface_design.blind_eval_m32 import read_verified_milestone_blind_payload
from agent_skill_loop.interface_design.blind_eval_m5 import M5_BLIND_COMMITMENT_PATH, M5_BLIND_SUITE_ID, _m5_custody_dir
from agent_skill_loop.interface_design.contracts import FrozenInterfaceSolver, sha256_text
from agent_skill_loop.interface_design.planner import build_interface_design, parse_hook_candidate
from agent_skill_loop.interface_design.runtime import evaluate_frozen_interface_solver
from agent_skill_loop.interface_design.templates import get_template_spec
from agent_skill_loop.milestone_checkpoint import _champion_sort_key
from agent_skill_loop.problems.base import get_problem
from eoh_frozen.identity import loaded_identity
from research_agent import loop as research_loop
from research_agent.contracts import AgentConfig, atomic_write_json, atomic_write_text, sha256_file
from research_agent.loop import run_research_agent
from research_agent.tools.session_tools import SessionRunnerTool
from tools.run_external_baselines_2026 import (
    BUDGETS, DEV, EXTERNAL_COUNTS, MODEL, PARATERA_ENDPOINT, SEEDS, _load_external, _score, _summary, _target_instances,
)

TEMPLATE_ID = "cvrp_fleet_aware_exact_k"
TEMPLATE_VERSION = "v1"
REQUEST_CAP = 36
MAX_ROUNDS = 12
LIVE_BUDGET_MS = 500
BOOTSTRAP_SAMPLES = 10_000
DEFAULT_OUTPUT = REPO / "experiments" / "milestone6_wave3_c1_exact_k"
M5_LEGACY = REPO / "experiments/milestone5_paratera/roster_snapshots/legacy_baseline_500ms_20261128.json"
A1_AUDIT = REPO / "experiments/milestone6_wave1_clean_audit/a1_baselines_2026_clean_audit.json"
OFFICIAL_OR = ("cvrp_ext_cvrplib_abp_74", "cvrp_ext_cvrplib_x_100")
CW = "cw_relocate_2opt"
V2 = "m5_ds_legacy_v2"
PYVRP = "PyVRP"
STATIC_HOOK = "score_merge_static"
ADJUSTMENT_HOOK = "score_fleet_adjustment"
DEV_TARGET_SOURCE = "dev_train_first_fit_decreasing"
TERMINAL_PHASES = {"completed", "budget_stopped"}
PRIVATE_FIELDS = frozenset({
    "depot", "coordinates", "customer_coordinates", "demands", "distance_matrix", "sealed_seed_token",
    "seed_token", "items", "item_sizes", "routes", "route_loads", "customer_ids",
})


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(payload) -> str:
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))


def _check_public(value) -> None:
    if isinstance(value, Mapping):
        if PRIVATE_FIELDS.intersection(value):
            raise ValueError("private_instance_fields_in_c1_output")
        for child in value.values():
            _check_public(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            _check_public(child)


def _write_public(path: Path, payload: Mapping) -> None:
    _check_public(payload)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _output_path(out_dir: Path) -> Path:
    path = out_dir.resolve()
    if path.is_relative_to(REPO) and not (path.is_relative_to(DEFAULT_OUTPUT) or path.is_relative_to(REPO / "build")):
        raise ValueError("c1_output_must_use_wave3_or_build_directory")
    if any(part.casefold() == ".secrets" or part.casefold().startswith(".agent_skill_custody") for part in path.parts):
        raise ValueError("c1_output_cannot_use_custody_directory")
    return path


def _m5_v2() -> FrozenInterfaceSolver:
    raw = _read_json(M5_LEGACY)
    source = FrozenInterfaceSolver.from_dict(raw.get("frozen_solver", raw))
    old = get_template_spec("cvrp_parallel_merge_static", "v1")
    new = get_template_spec("cvrp_parallel_merge_static", "v2")
    if (
        (source.template_id, source.template_version, source.template_source_sha256)
        != (old.template_id, old.template_version, old.template_source_sha256)
        or source.hook_name != old.hook_name or source.hook_specs != old.hook_specs
    ):
        raise ValueError("c1_m5_static_source_identity_mismatch")
    design = build_interface_design(new.template_id, new.template_version, postprocess_mode=source.postprocess_mode)
    design = replace(design, template_options=dict(source.template_options))
    return replace(
        source, solver_id=V2, template_version=new.template_version, template_source_sha256=new.template_source_sha256,
        design_sha256=design.design_sha256, display_name="M5 DeepSeek legacy static v2",
    )


def _solver(label: str, static: str, adjustment: str, *, repair: bool, origin: str = "m6_c1") -> FrozenInterfaceSolver:
    template = get_template_spec(TEMPLATE_ID, TEMPLATE_VERSION)
    hooks = parse_hook_candidate(TEMPLATE_ID, TEMPLATE_VERSION, {STATIC_HOOK: static, ADJUSTMENT_HOOK: adjustment})
    design = replace(
        build_interface_design(TEMPLATE_ID, TEMPLATE_VERSION, postprocess_mode="relocate_2opt"),
        template_options={"fleet_repair_enabled": repair},
    )
    return FrozenInterfaceSolver(
        solver_id=label,
        display_name=label,
        problem_family=template.problem_family,
        paradigm=template.paradigm,
        template_id=template.template_id,
        template_version=template.template_version,
        template_source_sha256=template.template_source_sha256,
        postprocess_mode=design.postprocess_mode,
        template_options=design.template_options,
        hook_name=STATIC_HOOK,
        hook_code=static,
        hook_code_sha256=sha256_text(static),
        design_sha256=design.design_sha256,
        origin_run=origin,
        kb_release_id="m6_c1",
        protocol_id=template.effective_protocol_id,
        hook_specs=template.hook_specs,
        hook_implementations=hooks,
    )


def _baseline_sources() -> tuple[str, str]:
    hooks = get_template_spec(TEMPLATE_ID, TEMPLATE_VERSION).baseline_implementations()
    return hooks[STATIC_HOOK], hooks[ADJUSTMENT_HOOK]


def _target_dev_suite(suite: Mapping) -> dict:
    """Derive feasible targets using only demand data from the permitted train split."""
    rows = []
    for instance in suite["instances"]:
        if "k_vehicles" in instance:
            rows.append(dict(instance))
            continue
        capacity = float(instance["capacity"])
        residuals = []
        for demand in sorted(map(float, instance["demands"]), reverse=True):
            if demand < 0 or demand > capacity:
                raise ValueError("c1_invalid_dev_instance_demand")
            for idx, residual in enumerate(residuals):
                if residual + 1e-12 >= demand:
                    residuals[idx] -= demand
                    break
            else:
                residuals.append(capacity - demand)
        rows.append({**instance, "k_vehicles": len(residuals), "exact_k_target_source": DEV_TARGET_SOURCE})
    return {
        **suite,
        "instances": rows,
        "content_hash": get_problem(suite["problem"]).suite_hash(suite["problem"], suite["split"], rows),
        "c1_target_profile": DEV_TARGET_SOURCE,
    }


def _dev_suite() -> dict:
    return _target_dev_suite(session_baseline.load_dev_or_public_suite(DEV, split="dev_train", role="diagnostic_interactive"))


def _run_id(seed: int) -> str:
    return f"m6_c1_s{seed}"


def _config(root: Path, seed: int, *, mode: str, endpoint: str, api_key_env: str) -> AgentConfig:
    live = mode == "live"
    run_id = _run_id(seed) if live else "m6_c1_mock"
    budget = REQUEST_CAP if live else 16
    return AgentConfig(
        run_id=run_id, output_dir=str(root / run_id), arm_id="m6_c1", search_seed=seed,
        initial_template_id=TEMPLATE_ID, template_version=TEMPLATE_VERSION, allowed_templates=(TEMPLATE_ID,),
        allowed_postprocess_modes=("relocate_2opt",), initial_postprocess_mode="relocate_2opt",
        use_benchmark_dev_suite=True, dev_suite_id=DEV, dev_split="dev_train", dev_instance_count=24,
        instance_time_budget_ms=LIVE_BUDGET_MS, total_request_cap=budget, max_rounds=MAX_ROUNDS if live else 1,
        outer_requests_per_round_cap=1, outer_reflect_cap=1, eoh_pop_size=2, eoh_n_pop=1, eoh_max_sample_nums=4,
        strict_checkpoint_barriers=True, checkpoint_budgets=(budget,), planner_model=MODEL, eoh_model=MODEL,
        endpoint=endpoint, api_key_env=api_key_env, mode=mode, request_timeout_s=240.0 if live else 5.0,
        wall_seconds=14400.0 if live else 600.0, kb_enabled=False, archive_feedback_enabled=False, tools_enabled=False,
    )


class _C1Session(SessionRunnerTool):
    def _memory_basis(self, query: str, selection: Mapping) -> list[str]:
        selection["template_options"]["frozen_static_hook_code"] = _m5_v2().hook_code
        return super()._memory_basis(query, selection)


def _json_skill(directory: Path, skill, *, evidence=None) -> Path:
    """Session skill assets need the validated executable and JSON metadata only."""
    if sha256_text(skill.code) != skill.code_sha256 or skill.evaluator_hash != evaluator_source_hash():
        raise ValueError("c1_generated_skill_identity_mismatch")
    if directory.exists():
        raise ValueError("skill_directory_exists")
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory.parent) as staging:
        artifact = Path(staging) / "artifact"
        artifact.mkdir()
        (artifact / "code.py").write_text(skill.code, encoding="utf-8")
        atomic_write_json(artifact / "skill.json", skill.metadata())
        if evidence is not None:
            atomic_write_json(artifact / "evidence.json", evidence)
        os.replace(artifact, directory)
    return directory


class _C1SessionProcesses:
    """Propagate the C1 session profile through supervised Python boundaries."""

    def __getattr__(self, name: str):
        return getattr(subprocess, name)

    def Popen(self, argv, *args, **kwargs):
        modes = {
            "agent_skill_loop.session_supervisor": "supervisor",
            "agent_skill_loop.session_runner": "runner",
        }
        if len(argv) >= 3 and argv[1] == "-m" and argv[2] in modes:
            argv = [argv[0], str(Path(__file__).resolve()), "--c1-session-process", modes[argv[2]], *argv[3:]]
        elif len(argv) == 4 and argv[1] == "-c" and "from eoh_frozen.identity import loaded_identity" in argv[2]:
            argv = [argv[0], str(Path(__file__).resolve()), "--c1-session-process", "identity", argv[3]]
        return subprocess.Popen(argv, *args, **kwargs)


@contextmanager
def _c1_session_profile():
    """Keep the existing Session machinery and constrain its C1 I/O to code and JSON.

    The legacy Session APIs have fixed Markdown artifacts and elide CVRP fleet
    fields. Scope the adapters to this CLI and its supervised child processes.
    """
    load_profile = benchmark.load_profile_suite
    normalize = session_bridge._normalize_session_suite_instances
    policy_writer = research_loop.atomic_write_text

    def load_targeted(benchmark_id, profile, *, split="dev_train"):
        suite = load_profile(benchmark_id, profile, split=split)
        if benchmark_id == BENCHMARK_ID and profile == DEV and split in {"train", "dev_train"}:
            return _target_dev_suite(suite)
        return suite

    def normalize_targeted(suite, *, problem_family):
        rows = normalize(suite, problem_family=problem_family)
        if problem_family == "cvrp" and suite.get("c1_target_profile") == DEV_TARGET_SOURCE:
            for row, original in zip(rows, suite["instances"], strict=True):
                row["k_vehicles"] = original["k_vehicles"]
        return rows

    def json_policy(path, text):
        if path.name == "research_policy.md":
            atomic_write_json(path.with_suffix(".json"), {"policy": text, "profile": "m6-c1-json-session/v1"})
        else:
            policy_writer(path, text)

    def policy_hash():
        return _digest({"profile": "m6-c1-json-session/v1", "policy": research_loop.RESEARCH_POLICY_MD,
                        "profile_source_sha256": sha256_file(Path(__file__))})

    def kb_off(config=None, *, session_root=None, **_kwargs):
        # C1 has no KB access; bind return manifests to an explicit empty KB identity.
        return "m6_c1_kb_disabled", sha256_text("m6_c1_kb_disabled")

    with ExitStack() as stack:
        for module, attribute, implementation in (
            (benchmark, "load_profile_suite", load_targeted),
            (session_baseline, "load_profile_suite", load_targeted),
            (session_bridge, "_normalize_session_suite_instances", normalize_targeted),
            (session_bridge, "resolve_session_kb_release", kb_off),
            (session_bridge, "save_skill", _json_skill),
            (session_runtime, "_skill_content_hash", policy_hash),
            (session_actions, "subprocess", _C1SessionProcesses()),
            (session_supervisor, "subprocess", _C1SessionProcesses()),
            (research_loop, "atomic_write_text", json_policy),
        ):
            stack.enter_context(patch.object(module, attribute, implementation))
        stack.enter_context(patch.object(evidence_report, "write_round_progress", lambda root: root / "session.sqlite3"))
        yield


def _session_process(mode: str, args: Sequence[str]) -> int:
    with _c1_session_profile():
        if mode == "supervisor":
            session_supervisor.run_task(Path(args[0]), args[1])
        elif mode == "runner":
            sys.argv = [sys.argv[0], *args]
            session_runner.main()
        elif mode == "identity":
            print(json.dumps(loaded_identity(args[0] or None), sort_keys=True))
        else:
            raise ValueError("invalid_c1_session_process")
    return 0


def _strict_row(instance: Mapping, result: Mapping, budget: int) -> dict:
    row = _score(instance, result, "free_fleet_min_k_lb", budget)
    completed = row["completed"] and row["returned_before_deadline"] and row["solve_ms"] < budget
    strict = {
        **row, "completed": completed, "strict_completed_before_deadline": completed,
        "returned_before_deadline": completed,
        "scored_objective": row["objective"] if completed else 2 * row["reference_objective"],
    }
    diagnostics = result.get("fleet_diagnostics") or {}
    strict.update({key: diagnostics[key] for key in (
        "pre_repair_exact_k", "pre_repair_route_count", "pre_repair_cost", "exact_source", "target_k_status",
    ) if key in diagnostics})
    return strict


def _physical_length(instance: Mapping, result: Mapping) -> float | None:
    length = result.get("tour_length_euc_2d_float")
    if length is not None:
        return float(length)
    if not result.get("valid"):
        return None
    points = (instance["depot"], *instance["customer_coordinates"])
    return math.fsum(math.dist(points[a], points[b]) for route in result["routes"] for a, b in zip(route, route[1:]))


def _evaluate_rows(label, solver, suite, budget, cache_dir, *, seed=SEEDS[0], pyvrp_exact=False):
    suite_id = suite["suite_id"]
    ids = [row["instance_id"] for row in suite["instances"]]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError(f"c1_invalid_evaluation_suite:{suite_id}")
    cache_key = f"{label}__{suite_id}__{budget}"
    if solver == PYVRP:
        cache_key += f"__{seed}__{'exact' if pyvrp_exact else 'free'}"
    identity = {
        "source_sha256": [
            sha256_file(Path(__file__)), sha256_file(REPO / "agent_skill_loop/interface_design/runtime.py"),
            sha256_file(REPO / "agent_skill_loop/cvrp_workbench/solvers.py"),
            sha256_file(REPO / "agent_skill_loop/cvrp_workbench/baselines_2026.py"),
        ],
        "solver_sha256": _digest(solver.to_dict() if isinstance(solver, FrozenInterfaceSolver) else solver),
        "instances_sha256": _digest(suite["instances"]),
        "distance_convention": suite["distance_convention"],
        "budget_ms": budget, "workers": 1,
    }
    path = cache_dir / f"{cache_key}.json"
    if path.is_file():
        cache = _read_json(path)
        _check_public(cache)
        if cache["identity"] == identity and [r["instance_id"] for r in cache["rows"]] == ids:
            return cache["rows"]

    rows = []
    policy = "strict_max_vehicles" if pyvrp_exact else "free_fleet_min_k_lb"
    kwargs = {"distance_convention": suite["distance_convention"], "vehicle_limit_policy": policy}
    for instance in suite["instances"]:
        if isinstance(solver, FrozenInterfaceSolver):
            result = evaluate_frozen_interface_solver(solver, instance, solve_deadline_ms=budget, **kwargs)
        elif solver == PYVRP:
            result = solve_pyvrp(instance, budget_ms=budget, seed=seed, **kwargs)
        else:
            result = evaluate_algorithm_on_instance(solver, instance, time_budget_ms=budget, record_trace=False, **kwargs)
        row = _strict_row(instance, result, budget)
        row["tour_length_euc_2d_float"] = _physical_length(instance, result)
        rows.append(row)
    _write_public(path, {"identity": identity, "rows": rows})
    return rows


def _exact_projection(rows):
    return [
        {
            **row,
            "completed": row["completed"] and row["exact_vehicle_count"] is True,
            "feasible": row["feasible"] and row["exact_vehicle_count"] is True,
            "returned_before_deadline": row["returned_before_deadline"] and row["exact_vehicle_count"] is True,
            "feasible_before_deadline": row["feasible_before_deadline"] and row["exact_vehicle_count"] is True,
            "scored_objective": (
                row["objective"] if row["completed"] and row["exact_vehicle_count"] is True
                else 2 * row["reference_objective"]
            ),
        }
        for row in rows
    ]


def _paired(xs, ys, *, seed):
    if not xs:
        return {"n_instances": 0, "wilcoxon_signed_rank": None, "p_holm_wilcoxon": None}
    return paired_bootstrap_comparison(xs, ys, n_boot=BOOTSTRAP_SAMPLES, seed=seed)


def _contrasts(rows, comparisons, *, seed):
    result = {}
    for label, (left, right) in comparisons.items():
        names = (*left, *right)
        paired_rows = list(zip(*(rows[name] for name in names), strict=True))
        if any(len({r["instance_id"] for r in pair}) != 1 for pair in paired_rows):
            raise ValueError("unaligned_c1_paired_observations")
        result[label] = {}
        for sample in ("overall", "common_completed"):
            selected = [pair for pair in paired_rows if sample == "overall" or all(r["completed"] for r in pair)]
            entry = _paired(
                [sum(r["scored_objective"] for r in pair[:len(left)]) for pair in selected],
                [sum(r["scored_objective"] for r in pair[len(left):]) for pair in selected],
                seed=seed,
            )
            result[label][sample] = entry
    for sample in ("overall", "common_completed"):
        entries = [item[sample] for item in result.values()]
        p_values = [item["wilcoxon_signed_rank"]["p_two_sided"] if item["wilcoxon_signed_rank"] else 1.0 for item in entries]
        for item, p_value in zip(entries, holm_bonferroni_adjust(p_values), strict=True):
            item["p_holm_wilcoxon"] = p_value if item["wilcoxon_signed_rank"] else None
    return result


def _ratio(rows, control):
    pairs = [(row["tour_length_euc_2d_float"], base["tour_length_euc_2d_float"])
             for row, base in zip(rows, control, strict=True)
             if row["completed"] and base["completed"]
             and row["tour_length_euc_2d_float"] is not None and base["tour_length_euc_2d_float"] is not None]
    denominator = math.fsum(b for _, b in pairs)
    return {
        "L_new / L_v2": math.fsum(a for a, _ in pairs) / denominator if denominator > 0 else None,
        "common_completed_count": len(pairs), "n_instances": len(rows),
    }


def _report_group(rows, contrasts, *, seed, pyvrp_exact=None):
    exact = {label: _exact_projection(values) for label, values in rows.items()}
    if pyvrp_exact is not None:
        exact[PYVRP] = _exact_projection(pyvrp_exact)
    summaries = {}
    for lane, data in (("free_fleet", rows), ("exact_k", exact)):
        summaries[lane] = {
            "solvers": {label: _summary(values) for label, values in data.items()},
            "paired": _contrasts(data, contrasts, seed=seed),
        }
    summaries["strict_returns"] = {
        label: sum(row["returned_before_deadline"] for row in values) for label, values in rows.items()
    }
    summaries["L_new / L_v2"] = {label: _ratio(values, rows[V2]) for label, values in rows.items() if label != V2}
    return summaries


def _external_suites():
    return {suite["suite_id"]: {**suite, "instances": _target_instances(suite)} for suite in _load_external()}


def _groups(suites):
    return {**{key: (key,) for key in suites}, "official_or_174": OFFICIAL_OR, "full_430": tuple(suites)}


def _a1_pyvrp_reference():
    audit = _read_json(A1_AUDIT)
    by_run = {}
    for key, run in audit["runs"].items():
        modes = {}
        for endpoint, source in (
            ("feasible_before_deadline", "anytime_feasible_before_deadline"),
            ("returned_before_deadline", "strict_returned_before_deadline"),
        ):
            mode = run["modes"][source]
            modes[endpoint] = {
                "suites": {
                    suite: {lane: values["overall"][PYVRP] for lane, values in lanes.items()}
                    for suite, lanes in mode["suites"].items()
                },
                "aggregates": {name: values["overall"][PYVRP] for name, values in mode["aggregates"].items()},
            }
        by_run[key] = {"seed": run["seed"], "budget_ms": run["budget_ms"], **modes}
    return {"source": A1_AUDIT.name, "source_sha256": sha256_file(A1_AUDIT), "runs": by_run}


def _all_rows(solvers, suites, budget, cache_dir, *, seed=SEEDS[0]):
    return {
        key: {label: _evaluate_rows(label, solver, suite, budget, cache_dir, seed=seed) for label, solver in solvers.items()}
        for key, suite in suites.items()
    }


def _aggregate(data, suite_ids):
    return {label: [row for suite_id in suite_ids for row in data[suite_id][label]] for label in data[suite_ids[0]]}


def _acceptance(groups, budget, label):
    official = groups["official_or_174"]
    full = groups["full_430"]
    exact = official["exact_k"]["solvers"][label]["completed_count"]
    goal, stretch = {500: (155, 162), 2000: (162, 168)}[budget]
    physical = {suite: groups[suite]["L_new / L_v2"][label] for suite in EXTERNAL_COUNTS}
    quality = all(item["common_completed_count"] == item["n_instances"]
                  and item["L_new / L_v2"] is not None and item["L_new / L_v2"] <= 1.03
                  for item in physical.values())
    strict = official["strict_returns"][label] == 174 and full["strict_returns"][label] == 430
    return {"arm": label, "strict_returns_passed": strict, "official_exact_k": exact, "official_exact_k_target": goal,
            "official_exact_k_stretch_target": stretch, "official_exact_k_passed": exact >= goal,
            "official_exact_k_stretch_passed": exact >= stretch, "physical_quality_passed": quality,
            "passed": strict and exact >= goal and quality}


def run_c1_offline(out_dir: Path = DEFAULT_OUTPUT) -> dict:
    directory = _output_path(out_dir) / "c1_offline"
    legacy = _m5_v2()
    classic, zero = _baseline_sources()
    solvers = {CW: CW, V2: legacy}
    for name, static in (("cw", classic), ("m5", legacy.hook_code)):
        for quadrant, repair in (("y00", False), ("y01", True)):
            label = f"c1_{quadrant}_{name}_{'repair' if repair else 'norepair'}"
            solvers[label] = _solver(label, static, zero, repair=repair)
    contrasts = {f"{label}_vs_v2": ((label,), (V2,)) for label in solvers if label != V2}
    for static in ("cw", "m5"):
        contrasts[f"template_repair_gain_{static}"] = ((f"c1_y01_{static}_repair",), (f"c1_y00_{static}_norepair",))
    suites = _external_suites()
    report = {
        "schema_version": "m6-c1-offline-430/v1", "workers": 1, "suite_counts": EXTERNAL_COUNTS,
        "official_or_174_suites": list(OFFICIAL_OR), "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "pyvrp_dual_endpoint_reference": _a1_pyvrp_reference(), "budgets_ms": {},
    }
    for budget in BUDGETS:
        data = _all_rows(solvers, suites, budget, directory / "cache")
        groups = {
            name: _report_group(_aggregate(data, keys), contrasts, seed=SEEDS[0])
            for name, keys in _groups(suites).items()
        }
        for group in groups.values():
            group["template_repair_gain"] = {
                name: group["exact_k"]["solvers"][f"c1_y01_{name}_repair"]["completed_count"]
                - group["exact_k"]["solvers"][f"c1_y00_{name}_norepair"]["completed_count"] for name in ("cw", "m5")
            }
        report["budgets_ms"][str(budget)] = {
            "groups": groups, "acceptance": _acceptance(groups, budget, "c1_y01_m5_repair"),
        }
    report["passed"] = all(item["acceptance"]["passed"] for item in report["budgets_ms"].values())
    _write_public(directory / "c1_offline_430_report.json", report)
    return report


def _seed_common_start(live_dir: Path, seed: int, *, endpoint: str, api_key_env: str) -> dict:
    config = _config(live_dir, seed, mode="live", endpoint=endpoint, api_key_env=api_key_env)
    path = live_dir / f"common_start_s{seed}.json"
    with exclusive_file_lock(live_dir / f".common_start_s{seed}.lock", busy=f"c1_common_start_busy:{seed}"):
        suite = _dev_suite()
        _, zero = _baseline_sources()
        baseline = _solver(f"{config.run_id}_baseline_0", _m5_v2().hook_code, zero, repair=True, origin=config.run_id)
        identity = {
            "schema_version": "m6-c1-common-start/v1", "seed": seed, "dev_suite_id": DEV,
            "dev_target_source": DEV_TARGET_SOURCE, "solve_budget_ms": LIVE_BUDGET_MS,
            "dev_suite_hash": _digest(suite["instances"]), "session_suite_hash": suite["content_hash"],
            "frozen_solver": baseline.to_dict(),
        }
        if path.is_file():
            previous = _read_json(path)
            _check_public(previous)
            if any(previous.get(key) != val for key, val in identity.items()):
                raise ValueError(f"c1_common_start_identity_mismatch:{seed}")
            return previous
        rows = _evaluate_rows(baseline.solver_id, baseline, suite, LIVE_BUDGET_MS, live_dir / "dev_cache")
        n = len(rows)
        completed = [row for row in rows if row["completed"]]
        valid_mean = math.fsum(r["objective"] for r in completed) / len(completed) if completed else None
        mean = math.fsum(row["scored_objective"] for row in rows) / n
        payload = {
            **identity,
            "baseline_dev_eval": {
                "suite_id": DEV, "protocol_id": baseline.protocol_id, "valid_count": len(completed), "instance_count": n,
                "completion_rate": len(completed) / n, "all_feasible": len(completed) == n,
                "exact_k_count": sum(row["exact_vehicle_count"] is True and row["completed"] for row in rows),
                "failure_penalty_policy": "2x_reference_objective",
                "valid_only_mean_objective": valid_mean, "penalized_mean_objective": mean, "mean_objective": mean,
                "valid_only_mean_tour_length": valid_mean, "penalized_mean_tour_length": mean, "mean_tour_length": mean,
                "records": rows,
            },
        }
        _write_public(path, payload)
        return payload


def build_mux_manifest(
    out_dir: Path = DEFAULT_OUTPUT, *, endpoint: str = PARATERA_ENDPOINT, api_key_env: str = "PARATERA_API_KEY",
) -> dict:
    root = _output_path(out_dir)
    return {
        "schema_version": "m6-c1-live-mux/v1", "model": MODEL, "request_cap": REQUEST_CAP, "max_rounds": MAX_ROUNDS,
        "template_id": TEMPLATE_ID, "template_version": TEMPLATE_VERSION, "postprocess_mode": "relocate_2opt",
        "dev_suite_id": DEV, "dev_target_source": DEV_TARGET_SOURCE, "frozen_static_hook_sha256": _m5_v2().hook_code_sha256,
        "panes": [
            {
                "id": _run_id(seed), "cwd": str(REPO),
                "command": [
                    sys.executable, str(Path(__file__).resolve()), "--stage", "c1_cell", "--output-dir", str(root),
                    "--seed", str(seed), "--endpoint", endpoint, "--api-key-env", api_key_env, "--resume",
                ],
            }
            for seed in SEEDS
        ],
    }


def run_c1_mux(
    out_dir: Path = DEFAULT_OUTPUT, *, endpoint: str = PARATERA_ENDPOINT, api_key_env: str = "PARATERA_API_KEY",
) -> dict:
    live_dir = _output_path(out_dir) / "c1_live"
    manifest = build_mux_manifest(out_dir, endpoint=endpoint, api_key_env=api_key_env)
    manifest["common_starts"] = {}
    for seed in SEEDS:
        start = _seed_common_start(live_dir, seed, endpoint=endpoint, api_key_env=api_key_env)
        manifest["common_starts"][str(seed)] = {
            "name": f"common_start_s{seed}.json", "sha256": sha256_file(live_dir / f"common_start_s{seed}.json"),
            "dev_suite_hash": start["dev_suite_hash"],
        }
    _write_public(live_dir / "mux_m6_c1.json", manifest)
    return manifest


def run_c1_cell(
    out_dir: Path, seed: int, *, endpoint: str = PARATERA_ENDPOINT, api_key_env: str = "PARATERA_API_KEY",
    resume: bool = False,
) -> int:
    load_local_env()
    if endpoint.startswith("mock://") or os.environ.get("AGENT_SKILL_M2_MOCK") == "1":
        raise ValueError("c1_cell_requires_live_provider")
    live_dir = _output_path(out_dir) / "c1_live"
    config = _config(live_dir, seed, mode="live", endpoint=endpoint, api_key_env=api_key_env)
    run_dir = Path(config.output_dir)
    with exclusive_file_lock(run_dir / ".cell.lock", busy=f"c1_cell_busy:{config.run_id}"):
        common_start = _seed_common_start(live_dir, seed, endpoint=endpoint, api_key_env=api_key_env)
        try:
            with _c1_session_profile():
                summary = run_research_agent(config, session_factory=_C1Session, resume=resume, common_start=common_start)
        except ProviderFailure as exc:
            _write_public(run_dir / "run_interrupt_status.json", {"status": "resumable", "reason": exc.error_code})
            return 75
        print(json.dumps({key: summary[key] for key in ("run_id", "final_phase", "realized_request_spend")}))
        return 0 if summary["final_phase"] in TERMINAL_PHASES else 2


def _generated_champion(config: AgentConfig, summary: Mapping, *, session_suite_hash: str):
    """Select the strongest validated evolved hook under the frozen dev-only ranking."""
    spent = summary["realized_request_spend"]
    run_dir = Path(config.output_dir)
    if summary["run_id"] != config.run_id or summary["final_phase"] not in TERMINAL_PHASES:
        raise ValueError(f"c1_run_not_terminal:{config.run_id}")
    uri = (run_dir / "agent_budget.sqlite3").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        requests = db.execute("SELECT idx,state FROM budget_requests WHERE run_id=? ORDER BY idx", (config.run_id,)).fetchall()
        if not 0 < spent <= config.total_request_cap or len(requests) != spent or any(
            ordinal != expected or state in {"reserved", "sent"}
            for expected, (ordinal, state) in enumerate(requests, 1)
        ):
            raise ValueError(f"c1_run_ledger_mismatch:{config.run_id}")
        if spent == config.total_request_cap:
            checkpoint = run_dir / "checkpoints" / f"frozen_checkpoint_{spent}.json"
            sealed = db.execute(
                "SELECT state,payload_sha256,settled_through_ordinal FROM milestone_checkpoints WHERE run_id=? AND ckpt_budget=?",
                (config.run_id, spent),
            ).fetchone()
            if sealed is None or tuple(sealed) != ("sealed", sha256_file(checkpoint), spent):
                raise ValueError(f"c1_run_checkpoint_unsealed:{config.run_id}")
        candidates = db.execute(
            "SELECT * FROM candidate_provenance WHERE run_id=? AND global_ordinal BETWEEN 1 AND ?"
            " AND eligible=1 AND validation_passed=1 AND generation_status='valid_candidate'"
            " AND dev_suite_hash=? AND solve_budget_ms=? AND solver_manifest_json IS NOT NULL",
            (config.run_id, spent, session_suite_hash, LIVE_BUDGET_MS),
        ).fetchall()
    template = get_template_spec(TEMPLATE_ID, TEMPLATE_VERSION)
    m5 = _m5_v2()
    _, zero = _baseline_sources()
    for row in sorted(candidates, key=_champion_sort_key):
        solver = FrozenInterfaceSolver.from_dict(json.loads(row["solver_manifest_json"]))
        if (
            (solver.template_id, solver.template_version, solver.template_source_sha256)
            != (TEMPLATE_ID, TEMPLATE_VERSION, template.template_source_sha256)
            or solver.hook_specs != template.hook_specs or solver.postprocess_mode != "relocate_2opt"
            or solver.hook_code_sha256 != m5.hook_code_sha256
        ):
            raise ValueError(f"c1_champion_template_mismatch:{config.run_id}")
        if solver.hook_implementations[ADJUSTMENT_HOOK].strip() == zero.strip():
            continue
        return solver, {
            "requests_used": spent, "phase": summary["final_phase"], "candidate_ordinal": row["global_ordinal"],
            "dev_penalized_mean": row["dev_penalized_mean"], "session_suite_hash": session_suite_hash,
            "champion_bundle_sha256": solver.bundle_hash, "champion_manifest_sha256": _digest(solver.to_dict()),
        }
    raise ValueError(f"c1_no_valid_evolved_champion:{config.run_id}")


def _verify_mock_isolation(run_dir: Path):
    disallowed_suites = {M5_BLIND_SUITE_ID, "cvrp_select_multiscale_64"}

    def check(payload):
        if isinstance(payload, Mapping):
            if {"sealed_seed_token", "seed_token"}.intersection(payload) or any(
                payload.get(key) in disallowed_suites for key in ("suite_id", "profile", "benchmark_profile")
                if isinstance(payload.get(key), str)
            ):
                raise ValueError("c1_mock_private_or_selection_leakage")
            for child in payload.values():
                check(child)
        elif isinstance(payload, list):
            for child in payload:
                check(child)

    for path in run_dir.rglob("*.json*"):
        if path.suffix == ".json" and path.is_file():
            check(_read_json(path))
        elif path.suffix == ".jsonl" and path.is_file():
            with path.open(encoding="utf-8") as journal:
                for line in journal:
                    if line.strip():
                        check(json.loads(line))
    if any(path.is_file() for path in run_dir.rglob("*.md")):
        raise ValueError("c1_mock_markdown_artifact")


def run_c1_mock(out_dir: Path = DEFAULT_OUTPUT) -> dict:
    mock_dir = _output_path(out_dir) / "c1_mock"
    config = _config(mock_dir, SEEDS[0], mode="mock", endpoint="mock://local", api_key_env="PARATERA_API_KEY")
    run_dir = Path(config.output_dir)
    with exclusive_file_lock(run_dir / ".cell.lock", busy=f"c1_mock_busy:{config.run_id}"):
        with _c1_session_profile():
            summary = run_research_agent(
                config, session_factory=_C1Session, resume=(run_dir / "agent_checkpoint.json").is_file(),
            )
        _verify_mock_isolation(run_dir)
        solver, metadata = _generated_champion(config, summary, session_suite_hash=_dev_suite()["content_hash"])
        champion = "c1_evolved_champion.json"
        _write_public(run_dir / champion, solver.to_dict())
        report = {
            "schema_version": "m6-c1-mock/v1", "seed": SEEDS[0], "request_cap": config.total_request_cap,
            "passed": True, "no_private_leakage": True, "completed_rounds": summary["completed_rounds"],
            "best_solver_manifest_ref": f"{run_dir.name}/{champion}", **metadata,
        }
        _write_public(mock_dir / "c1_mock_report.json", report)
    return report


def _historical_pyvrp(suites, budget, seed):
    path = REPO / "experiments" / "baselines_2026" / f"dual_timing_s{seed}_b{budget}.json"
    source = _read_json(path)
    if (source["seed"], source["budget_ms"]) != (seed, budget):
        raise ValueError("c1_historical_pyvrp_identity_mismatch")
    lanes = {}
    for suite_id, suite in suites.items():
        recorded = source["suites"][suite_id]
        if any(recorded[key] != suite[key] for key in ("distance_convention", "data_manifest_hash", "reference_manifest_hash")):
            raise ValueError(f"c1_historical_pyvrp_suite_mismatch:{suite_id}")
        by_lane = {}
        for lane in ("free_fleet", "exact-k"):
            records = {r["instance_id"]: r for r in recorded[lane]["rows"] if r["algorithm_id"] == PYVRP}
            if len(records) != len(suite["instances"]):
                raise ValueError(f"c1_historical_pyvrp_incomplete:{suite_id}:{lane}")
            rows = []
            for instance in suite["instances"]:
                row = records[instance["instance_id"]]
                if row["target_vehicles"] != instance["k_vehicles"] or row["reference_objective"] != instance["reference_objective"]:
                    raise ValueError(f"c1_historical_pyvrp_instance_mismatch:{suite_id}")
                rows.append(_strict_row(instance, row, budget))
            by_lane[lane] = rows
        lanes[suite_id] = by_lane
    return lanes, {"source": path.name, "source_sha256": sha256_file(path)}


def _pyvrp_endpoints(rows):
    return {
        "feasible_before_deadline": sum(row["feasible_before_deadline"] is True for row in rows),
        "returned_before_deadline": sum(row["returned_before_deadline"] is True for row in rows),
        "feasible_incumbent_mean_length": (
            math.fsum(row["objective"] for row in rows if row["feasible_before_deadline"] and row["objective"] is not None)
            / sum(row["feasible_before_deadline"] and row["objective"] is not None for row in rows)
        ) if any(row["feasible_before_deadline"] and row["objective"] is not None for row in rows) else None,
    }


def _attribution_group(rows, pyvrp_exact, *, seed):
    comparisons = {
        "template_repair_gain": (("Y_01",), ("Y_00",)),
        "adjustment_gain": (("Y_10",), ("Y_00",)),
        "repair_with_evolution": (("Y_11",), ("Y_10",)),
        "adjustment_with_repair": (("Y_11",), ("Y_01",)),
        "interaction": (("Y_11", "Y_00"), ("Y_01", "Y_10")),
        **{f"{label}_vs_v2": ((label,), (V2,)) for label in rows if label != V2},
    }
    result = _report_group(rows, comparisons, seed=seed, pyvrp_exact=pyvrp_exact)
    counts = {arm: result["exact_k"]["solvers"][arm]["completed_count"] for arm in ("Y_00", "Y_01", "Y_10", "Y_11")}
    result["attribution_matrix"] = {
        arm: {
            "adjustment_evolved": arm[2] == "1", "fleet_repair_enabled": arm[3] == "1",
            "exact_k": counts[arm], "strict_returns": result["strict_returns"][arm],
            "physical_return_quality": result["L_new / L_v2"][arm],
        }
        for arm in counts
    }
    result["exact_k_attribution_effects"] = {
        name: sum(counts[arm] for arm in left) - sum(counts[arm] for arm in right)
        for name, (left, right) in comparisons.items() if all(arm in counts for arm in (*left, *right))
    }
    result["pyvrp_dual_endpoints"] = {
        "free_fleet": _pyvrp_endpoints(rows[PYVRP]),
        "exact_k": _pyvrp_endpoints(_exact_projection(pyvrp_exact)),
    }
    return result


def run_eval(out_dir: Path = DEFAULT_OUTPUT, *, custody_dir: Path | None = None) -> dict:
    root = _output_path(out_dir)
    live_dir, directory = root / "c1_live", root / "eval"
    session_suite_hash = _dev_suite()["content_hash"]
    champions = {}
    provenance = {}
    for seed in SEEDS:
        run_dir = live_dir / _run_id(seed)
        persisted = AgentConfig.from_dict(_read_json(run_dir / "agent_config.json"))
        expected = _config(live_dir, seed, mode="live", endpoint=persisted.endpoint, api_key_env=persisted.api_key_env)
        if persisted != expected or persisted.endpoint.startswith("mock://"):
            raise ValueError(f"c1_invalid_live_config:{seed}")
        champions[seed], provenance[str(seed)] = _generated_champion(
            persisted, _read_json(run_dir / "research_summary.json"), session_suite_hash=session_suite_hash,
        )

    commitment_sha = sha256_file(M5_BLIND_COMMITMENT_PATH)
    roster = {"champions": provenance, "blind_commitment_sha256": commitment_sha, "seeds": list(SEEDS)}
    roster_path = directory / "c1_eval_roster_lock.json"
    with exclusive_file_lock(directory / ".eval.lock", busy="c1_eval_busy"):
        if not roster_path.is_file():
            _write_public(roster_path, roster)
        elif _read_json(roster_path) != roster:
            raise ValueError("c1_eval_roster_already_locked")

        custody = _m5_custody_dir(custody_dir, REPO)
        sealed, _, verification = read_verified_milestone_blind_payload(
            sealed_path=custody / f"{M5_BLIND_SUITE_ID}_sealed.json", commitment_path=M5_BLIND_COMMITMENT_PATH,
            expected_commitment_sha256=commitment_sha, expected_suite_id=M5_BLIND_SUITE_ID,
        )
        if verification["instance_count"] != 120:
            raise ValueError("c1_blind_suite_count_mismatch")
        blind = {"suite_id": M5_BLIND_SUITE_ID, "distance_convention": sealed["distance_convention"],
                 "instances": _target_instances(sealed)}
        suites = _external_suites()
        legacy = _m5_v2()
        _, zero = _baseline_sources()
        report = {
            "schema_version": "m6-c1-evaluation/v1", "workers": 1, "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "suite_counts": EXTERNAL_COUNTS, "official_or_174_suites": list(OFFICIAL_OR),
            "blind_suite_verification": verification, "roster": roster, "by_seed": {},
        }
        cache = directory / "cache"
        for seed, champion in champions.items():
            evolved = champion.hook_implementations[ADJUSTMENT_HOOK]
            solvers = {
                CW: CW, V2: legacy,
                **{
                    arm: _solver(
                        f"{arm}_s{seed}" if arm[2] == "1" else arm, legacy.hook_code,
                        evolved if arm[2] == "1" else zero, repair=arm[3] == "1",
                        origin=champion.solver_id if arm[2] == "1" else "m6_c1",
                    )
                    for arm in ("Y_00", "Y_01", "Y_10", "Y_11")
                },
            }
            by_budget = {}
            for budget in BUDGETS:
                data = {name: {
                    arm: _evaluate_rows(getattr(solver, "solver_id", arm), solver, suite, budget, cache, seed=seed)
                    for arm, solver in solvers.items()
                } for name, suite in suites.items()}
                historical, pyvrp_source = _historical_pyvrp(suites, budget, seed)
                for name in suites:
                    data[name][PYVRP] = historical[name]["free_fleet"]
                groups = {
                    name: _attribution_group(
                        _aggregate(data, keys), [row for key in keys for row in historical[key]["exact-k"]], seed=seed,
                    )
                    for name, keys in _groups(suites).items()
                }
                by_budget[str(budget)] = {
                    "groups": groups, "acceptance": _acceptance(groups, budget, "Y_11"), "pyvrp_source": pyvrp_source,
                }
            try:
                blind_rows = {
                    arm: _evaluate_rows(getattr(solver, "solver_id", arm), solver, blind, LIVE_BUDGET_MS, cache, seed=seed)
                    for arm, solver in {**solvers, PYVRP: PYVRP}.items()
                }
                blind_exact = _evaluate_rows(PYVRP, PYVRP, blind, LIVE_BUDGET_MS, cache, seed=seed, pyvrp_exact=True)
            except Exception:
                raise RuntimeError(f"c1_blind_evaluation_failed:{seed}") from None
            report["by_seed"][str(seed)] = {
                "budgets_ms": by_budget, "blind_120": {
                    "budget_ms": LIVE_BUDGET_MS, **_attribution_group(blind_rows, blind_exact, seed=seed),
                },
            }
        report["passed"] = all(
            value["acceptance"]["passed"] for result in report["by_seed"].values() for value in result["budgets_ms"].values()
        )
        _write_public(directory / "c1_eval_report.json", report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--c1-session-process"]:
        return _session_process(argv[1], argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("c1_offline", "c1_mock", "c1_mux", "c1_cell", "eval"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--endpoint", default=PARATERA_ENDPOINT)
    parser.add_argument("--api-key-env", default="PARATERA_API_KEY")
    parser.add_argument("--custody-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    root = _output_path(args.output_dir)
    if args.stage == "c1_cell":
        if args.seed is None:
            parser.error("--stage c1_cell requires --seed")
        return run_c1_cell(root, args.seed, endpoint=args.endpoint, api_key_env=args.api_key_env, resume=args.resume)
    if args.stage == "c1_offline":
        report = run_c1_offline(root)
        path = root / "c1_offline" / "c1_offline_430_report.json"
    elif args.stage == "c1_mock":
        report = run_c1_mock(root)
        path = root / "c1_mock" / "c1_mock_report.json"
    elif args.stage == "c1_mux":
        report = run_c1_mux(root, endpoint=args.endpoint, api_key_env=args.api_key_env)
        path = root / "c1_live" / "mux_m6_c1.json"
    else:
        report = run_eval(root, custody_dir=args.custody_dir)
        path = root / "eval" / "c1_eval_report.json"
    print(path)
    return 0 if report.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
