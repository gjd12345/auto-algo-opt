"""CLI for the Algorithm Optimization Skill and its Session runtime."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from agent_skill_loop.contracts import (
    DEFAULT_COUNT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    PROBLEM_CVRP,
)
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.importer import import_skill
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.session_runtime import (
    SessionError,
    error_envelope,
    initialize_session,
    read_state,
    stop_session,
)
from agent_skill_loop.skill_store import load_skill, validate_skill_for_suite


def _require_new_dir(path: Path) -> Path:
    if path.exists():
        raise SystemExit(f"output directory must be new: {path}")
    return path


def cmd_prepare(args: argparse.Namespace) -> int:
    from eoh_frozen.__main__ import prepare_output
    path = _require_new_dir(Path(args.output))
    prepare_output(path, problem_id=args.problem, seed=args.seed, count=args.count, size=args.size)
    print(path / "config_frozen.json")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    from eoh_frozen.smoke import run_smoke
    return run_smoke(args.problem, Path(args.output))


def cmd_run(args: argparse.Namespace) -> int:
    from eoh_frozen.__main__ import cmd_run as official_cmd_run
    return official_cmd_run(args)


def cmd_evaluate_skill(args: argparse.Namespace) -> int:
    skill = load_skill(Path(args.skill))
    suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
    mismatch = validate_skill_for_suite(skill, suite)
    if mismatch:
        print(json.dumps({
            "valid": False,
            "objective": None,
            "instance_objectives": [],
            "suite_hash": suite.get("content_hash") if isinstance(suite, dict) else None,
            "error_code": mismatch,
            "error_detail": None,
            "elapsed_seconds": 0.0,
        }, indent=2))
        return 1
    result = SubprocessEvaluator().evaluate(skill.code, suite)
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.valid else 1


def cmd_import_skill(args: argparse.Namespace) -> int:
    path = _require_new_dir(Path(args.output))
    has_git = bool(args.git_repo or args.git_ref or args.git_path)
    if args.file and has_git:
        raise SystemExit("choose either --file or --git-repo/--git-ref/--git-path")
    if args.file:
        source = {"kind": "file", "path": args.file}
    elif args.git_repo and args.git_ref and args.git_path:
        source = {"kind": "git", "repo": args.git_repo, "ref": args.git_ref, "path": args.git_path}
    else:
        raise SystemExit("provide --file or --git-repo/--git-ref/--git-path")
    record = import_skill(
        problem_id=args.problem,
        output_dir=path,
        source=source,
        license=args.license,
        seed=args.seed,
        size=args.size,
        count=args.count,
        solver_timeout=args.solver_timeout,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if record["accepted"] else 1


def cmd_workflow(args: argparse.Namespace) -> int:
    # Keep the parser for one transition release so old invocations fail with
    # an actionable, machine-readable response.  In particular, do not load
    # the environment or instantiate the removed legacy outer workflow.
    print(json.dumps({
        "ok": False,
        "error": {
            "code": "WORKFLOW_DEPRECATED",
            "message": "Use session init and the algorithm-optimization Coding Agent Skill.",
        },
    }, ensure_ascii=False, indent=2))
    return 2


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Run only offline benchmark operations; never creates provider traffic."""
    from agent_skill_loop.benchmark import cli as benchmark_cli
    handlers = {
        "audit": benchmark_cli.cmd_audit,
        "calibrate-obp": benchmark_cli.cmd_calibrate,
        "evaluate": benchmark_cli.cmd_evaluate,
        "evaluate-set": benchmark_cli.cmd_evaluate_set,
        "evaluate-selection": benchmark_cli.cmd_evaluate_selection,
        "archive": benchmark_cli.cmd_archive,
        "snapshot": benchmark_cli.cmd_snapshot,
        "freeze-selection": benchmark_cli.cmd_freeze_selection,
        "manifest": benchmark_cli.cmd_manifest,
        "pilot-config": benchmark_cli.cmd_pilot_config,
        "report": benchmark_cli.cmd_report,
    }
    return int(handlers[args.benchmark_action](args))


def _print_session(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_session_init(args: argparse.Namespace) -> int:
    experiment_manifest = None
    if args.experiment_manifest:
        experiment_manifest = json.loads(Path(args.experiment_manifest).read_text(encoding="utf-8"))
        if not isinstance(experiment_manifest, dict):
            raise SystemExit("experiment manifest must be a JSON object")
    explicit_seed_set = None
    if args.seed_set:
        try:
            explicit_seed_set = json.loads(Path(args.seed_set).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise SystemExit("explicit seed set is invalid") from None
    if args.benchmark_id and (args.count is not None or args.size is not None):
        raise SystemExit("benchmark sessions use their frozen suite; --count/--size are forbidden")
    manifest_population = experiment_manifest.get("population_size") if experiment_manifest else None
    manifest_round_budget = experiment_manifest.get("round_budget") if experiment_manifest else None
    manifest_extra = experiment_manifest.get("extra") if isinstance(experiment_manifest, dict) else None
    manifest_search_defaults = manifest_extra.get("search_policy_defaults") if isinstance(manifest_extra, dict) else None
    manifest_search_limits = manifest_extra.get("search_policy_limits") if isinstance(manifest_extra, dict) else None
    inheritance_mode = (
        args.inheritance_mode
        if args.inheritance_mode is not None
        else experiment_manifest.get("inheritance_mode", "incumbent_only")
        if experiment_manifest
        else "incumbent_only"
    )
    feedback_mode = (
        args.feedback_mode
        if args.feedback_mode is not None
        else experiment_manifest.get("feedback_mode", "runtime_facts")
        if experiment_manifest
        else "runtime_facts"
    )
    agent_guidance = (
        args.agent_guidance
        if args.agent_guidance is not None
        else bool(experiment_manifest.get("agent_guidance", True))
        if experiment_manifest
        else True
    )
    if experiment_manifest and all(value is None for value in (args.default_pop_size, args.default_n_pop, args.default_max_sample_nums)):
        default_search = dict(manifest_search_defaults) if isinstance(manifest_search_defaults, dict) else {
            "pop_size": manifest_population,
            "n_pop": 2,
            "max_sample_nums": 8,
        }
    elif any(value is not None for value in (args.default_pop_size, args.default_n_pop, args.default_max_sample_nums)):
        default_search = {
            "pop_size": args.default_pop_size if args.default_pop_size is not None else 4,
            "n_pop": args.default_n_pop if args.default_n_pop is not None else 2,
            "max_sample_nums": args.default_max_sample_nums if args.default_max_sample_nums is not None else 8,
        }
    else:
        default_search = None
    if experiment_manifest and isinstance(manifest_search_limits, dict):
        search_limits = manifest_search_limits
    else:
        max_pop_size = max(args.max_pop_size, int(manifest_population)) if manifest_population is not None else args.max_pop_size
        search_limits = {
            "pop_size": [2, max_pop_size],
            "n_pop": [1, args.max_n_pop],
            "max_sample_nums": [1, args.max_sample_nums_per_round],
        }
    effective_round_budget = args.round_budget if args.round_budget is not None else manifest_round_budget
    return _print_session(initialize_session(
        output=Path(args.output),
        operation_id=args.operation_id,
        problem=args.problem,
        eoh_model=args.eoh_model,
        eoh_endpoint=args.eoh_endpoint,
        eoh_api_key_env=args.eoh_api_key_env,
        eoh_max_requests=args.eoh_max_requests,
        eoh_round_max_requests=args.eoh_round_max_requests,
        engine_wall_seconds=args.engine_wall_seconds,
        round_wall_seconds=args.round_wall_seconds,
        max_solver_calls=args.max_solver_calls,
        repair_mode=args.repair_mode,
        repair_max_requests=args.repair_max_requests,
        memory_store=args.memory_store,
        memory_enabled=args.memory_enabled,
        solution_threshold=args.solution_min_relative_improvement,
        seed=args.seed,
        size=args.size if args.size is not None else DEFAULT_SIZE,
        count=args.count if args.count is not None else DEFAULT_COUNT,
        search_policy_defaults=default_search,
        search_policy_limits=search_limits,
        solver_timeout=args.solver_timeout,
        request_timeout=args.request_timeout,
        eoh_thinking=args.eoh_thinking,
        benchmark_id=args.benchmark_id,
        benchmark_profile_name=args.benchmark_profile,
        inheritance_mode=inheritance_mode,
        feedback_mode=feedback_mode,
        agent_guidance=agent_guidance,
        experiment_manifest=experiment_manifest,
        max_rounds=args.max_rounds,
        round_budget=effective_round_budget,
        explicit_seed_set=explicit_seed_set,
    ))


def cmd_session_state(args: argparse.Namespace) -> int:
    return _print_session(read_state(run=Path(args.run), expected_run_id=args.run_id))


def cmd_session_stop(args: argparse.Namespace) -> int:
    return _print_session(stop_session(
        run=Path(args.run),
        operation_id=args.operation_id,
        expected_state_version=args.expected_state_version,
        reason=args.reason,
        expected_run_id=args.run_id,
    ))


def cmd_session_action(args: argparse.Namespace) -> int:
    from agent_skill_loop import session_actions
    values = vars(args).copy()
    function = getattr(session_actions, values.pop("session_function"))
    for key in ("command", "session_action", "memory_action", "func"):
        values.pop(key, None)
    values["expected_run_id"] = values.pop("run_id", None)
    try:
        return _print_session(function(**values))
    except SessionError:
        raise
    except sqlite3.Error as exc:
        raise SessionError("SQLITE_ERROR", str(exc), action=args.session_action, retryable=True) from exc
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SessionError("STORAGE_FAILED" if isinstance(exc, OSError) else "INVALID_ARGUMENT",
                           str(exc), action=args.session_action) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_skill_loop")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--problem", default=PROBLEM_CVRP)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--seed", type=int, default=DEFAULT_SEED)
    prepare.add_argument("--size", type=int, default=DEFAULT_SIZE)
    prepare.add_argument("--count", type=int, default=DEFAULT_COUNT)
    prepare.set_defaults(func=cmd_prepare)

    smoke = sub.add_parser("smoke")
    smoke.add_argument("--problem", default=PROBLEM_CVRP)
    smoke.add_argument("--output", required=True)
    smoke.set_defaults(func=cmd_smoke)

    from eoh_frozen.__main__ import add_run_arguments
    run = sub.add_parser("run")
    add_run_arguments(run)
    run.set_defaults(func=cmd_run)

    evaluate = sub.add_parser("evaluate-skill")
    evaluate.add_argument("--skill", required=True)
    evaluate.add_argument("--suite", required=True)
    evaluate.set_defaults(func=cmd_evaluate_skill)

    benchmark = sub.add_parser("benchmark", help="Offline benchmark contracts, calibration, and reports")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_action", required=True)
    audit = benchmark_sub.add_parser("audit", help="Verify tracked benchmark assets and provenance hashes")
    audit.add_argument("--registry")
    audit.add_argument("--output")
    audit.set_defaults(func=cmd_benchmark)

    calibrate = benchmark_sub.add_parser("calibrate-obp", help="Run the independent zero-provider OBP calibration")
    calibrate.add_argument("--suite")
    calibrate.add_argument("--gold")
    calibrate.add_argument("--output")
    calibrate.add_argument("--benchmark-id", default="eohs_v1")
    calibrate.add_argument("--profile", default="obp_mini")
    calibrate.add_argument("--split", default="dev_train")
    calibrate.set_defaults(func=cmd_benchmark)

    bench_eval = benchmark_sub.add_parser("evaluate", help="Isolated offline evaluation of one benchmark candidate")
    bench_eval.add_argument("--suite")
    bench_eval.add_argument("--code", required=True)
    bench_eval.add_argument("--timeout", type=float, default=20.0)
    bench_eval.add_argument("--output")
    bench_eval.add_argument("--benchmark-id", default="eohs_v1")
    bench_eval.add_argument("--profile", default="obp_mini")
    bench_eval.add_argument("--split", default="dev_train")
    bench_eval.set_defaults(func=cmd_benchmark)

    bench_set_eval = benchmark_sub.add_parser("evaluate-set", help="Evaluate a heuristic set and aggregate the best member per instance")
    bench_set_eval.add_argument("--suite")
    bench_set_eval.add_argument("--candidates", required=True, help="JSON object {candidate_id: code} or list of candidate objects")
    bench_set_eval.add_argument("--timeout", type=float, default=20.0)
    bench_set_eval.add_argument("--output")
    bench_set_eval.add_argument("--benchmark-id", default="eohs_v1")
    bench_set_eval.add_argument("--profile", default="obp_mini")
    bench_set_eval.add_argument("--split", default="dev_train")
    bench_set_eval.set_defaults(func=cmd_benchmark)

    bench_selection_eval = benchmark_sub.add_parser("evaluate-selection", help="Evaluate every member of a locked selection on a benchmark split")
    bench_selection_eval.add_argument("--suite")
    bench_selection_eval.add_argument("--selection", required=True)
    bench_selection_eval.add_argument("--timeout", type=float, default=20.0)
    bench_selection_eval.add_argument("--output")
    bench_selection_eval.add_argument("--benchmark-id", default="eohs_v1")
    bench_selection_eval.add_argument("--profile", default="obp_mini")
    bench_selection_eval.add_argument("--split", default="heldout")
    bench_selection_eval.set_defaults(func=cmd_benchmark)

    archive = benchmark_sub.add_parser(
        "archive",
        help="Build a validated training archive from completed Session evidence",
    )
    archive.add_argument("--run", required=True)
    archive.add_argument("--run-id")
    archive.add_argument("--output")
    archive.set_defaults(func=cmd_benchmark)

    snapshot = benchmark_sub.add_parser("snapshot", help="Serialize an ordered official final-population snapshot")
    snapshot.add_argument("--population", required=True)
    snapshot.add_argument("--generation", type=int, required=True)
    snapshot.add_argument("--metric-spec-hash", required=True)
    snapshot.add_argument("--problem-spec-hash")
    snapshot.add_argument("--data-manifest-hash")
    snapshot.add_argument("--evaluator-hash")
    snapshot.add_argument("--output")
    snapshot.set_defaults(func=cmd_benchmark)

    freeze = benchmark_sub.add_parser("freeze-selection", help="Persist a locked benchmark selection before test evaluation")
    freeze.add_argument("--kind", choices=["incumbent_top1", "archive_topk", "final_population_set"], required=True)
    freeze.add_argument("--metric-spec-hash", required=True)
    freeze.add_argument("--archive", help="JSON list of validated ArchiveEntry objects")
    freeze.add_argument("--population-snapshot", help="Faithful official final-population snapshot")
    freeze.add_argument("--source-ref")
    freeze.add_argument("--k", type=int)
    freeze.add_argument("--output")
    freeze.set_defaults(func=cmd_benchmark)

    manifest = benchmark_sub.add_parser("manifest", help="Hash an ExperimentManifest JSON config")
    manifest.add_argument("--config", required=True)
    manifest.add_argument("--output")
    manifest.set_defaults(func=cmd_benchmark)

    pilot_config = benchmark_sub.add_parser(
        "pilot-config",
        help="Expand one frozen manifest into the zero-provider A/B/C/D pilot configs",
    )
    pilot_config.add_argument("--config", required=True, help="Base ExperimentManifest JSON")
    pilot_config.add_argument("--output")
    pilot_config.set_defaults(func=cmd_benchmark)

    report = benchmark_sub.add_parser(
        "report",
        help="Build a deterministic report from a locked selection and offline facts",
    )
    report.add_argument("--manifest", required=True)
    report.add_argument("--selection", required=True)
    report.add_argument("--metrics", required=True)
    report.add_argument("--budget", required=True)
    report.add_argument("--test-result", help="Verified locked-selection test evaluation JSON")
    report.add_argument("--source", choices=["published_reported", "artifact_reevaluated", "search_rerun"], default="artifact_reevaluated")
    report.add_argument("--output")
    report.set_defaults(func=cmd_benchmark)

    imp = sub.add_parser("import-skill")
    imp.add_argument("--problem", default=PROBLEM_CVRP)
    imp.add_argument("--output", required=True)
    imp.add_argument("--file")
    imp.add_argument("--git-repo")
    imp.add_argument("--git-ref")
    imp.add_argument("--git-path")
    imp.add_argument("--license", default="unspecified")
    imp.add_argument("--seed", type=int, default=DEFAULT_SEED)
    imp.add_argument("--size", type=int, default=DEFAULT_SIZE)
    imp.add_argument("--count", type=int, default=DEFAULT_COUNT)
    imp.add_argument("--solver-timeout", type=float, default=DEFAULT_SOLVER_TIMEOUT)
    imp.set_defaults(func=cmd_import_skill)

    workflow = sub.add_parser("workflow", help="Deprecated legacy workflow command (use session + Skill)")
    workflow.add_argument("--problem", default=PROBLEM_CVRP)
    workflow.add_argument("--model", default="deepseek-flash")
    workflow.add_argument("--output", required=True)
    workflow.add_argument("--endpoint", default="https://api.deepseek.com/v1/chat/completions")
    workflow.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    workflow.add_argument("--rounds", type=int, default=1)
    workflow.add_argument("--max-requests", type=int, default=16)
    workflow.add_argument("--wall-seconds", type=float, default=420.0)
    workflow.add_argument("--seed", type=int, default=DEFAULT_SEED)
    workflow.add_argument("--size", type=int, default=DEFAULT_SIZE)
    workflow.add_argument("--count", type=int, default=DEFAULT_COUNT)
    workflow.add_argument("--pop-size", type=int, default=2)
    workflow.add_argument("--n-pop", type=int, default=1)
    workflow.add_argument("--max-sample-nums", type=int, default=2)
    workflow.add_argument("--solver-timeout", type=float, default=DEFAULT_SOLVER_TIMEOUT)
    workflow.add_argument("--request-timeout", type=float, default=90.0)
    workflow.add_argument("--memory-store")
    workflow.add_argument("--solution-min-relative-improvement", type=float, default=None)
    workflow.add_argument("--repair-mode", choices=["off", "bounded"], default="off")
    workflow.add_argument("--max-repairs-per-candidate", type=int, default=1)
    workflow.add_argument("--max-repair-requests-total", type=int, default=None)
    workflow.set_defaults(func=cmd_workflow)

    session = sub.add_parser("session", help="Manage a recoverable Algorithm Optimization session")
    session_sub = session.add_subparsers(dest="session_action", required=True)

    session_init = session_sub.add_parser("init", help="Create a SQLite-backed session without external effects")
    session_init.add_argument("--output", required=True)
    session_init.add_argument("--operation-id", required=True)
    session_init.add_argument("--problem", default=PROBLEM_CVRP)
    session_init.add_argument("--benchmark", dest="benchmark_id", help="Benchmark registry id, e.g. eohs_v1")
    session_init.add_argument("--benchmark-profile", default="obp_mini")
    session_init.add_argument("--inheritance-mode", choices=["incumbent_only", "population_seeds", "explicit_seeds"], default=None)
    session_init.add_argument("--feedback-mode", choices=["off", "runtime_facts"], default=None)
    session_init.add_argument("--no-agent-guidance", dest="agent_guidance", action="store_false", default=None)
    session_init.add_argument("--experiment-manifest")
    session_init.add_argument("--seed-set", help="JSON list/object of explicit seed code members")
    session_init.add_argument("--eoh-model", required=True)
    session_init.add_argument("--eoh-thinking", choices=["provider-default", "enabled", "disabled"], default="provider-default")
    session_init.add_argument("--eoh-endpoint", default="https://api.deepseek.com/v1/chat/completions")
    session_init.add_argument("--eoh-api-key-env", default="DEEPSEEK_API_KEY")
    session_init.add_argument("--eoh-max-requests", type=int, default=32)
    session_init.add_argument("--eoh-round-max-requests", type=int, default=None)
    session_init.add_argument("--engine-wall-seconds", type=float, default=420.0)
    session_init.add_argument("--round-wall-seconds", type=float, default=None)
    session_init.add_argument("--max-solver-calls", type=int, default=None)
    session_init.add_argument("--repair-mode", choices=["off", "bounded"], default="off")
    session_init.add_argument("--repair-max-requests", type=int, default=None)
    memory_group = session_init.add_mutually_exclusive_group()
    memory_group.add_argument("--memory-store", help="Enable Memory with this store (ordinary Sessions use the user default when omitted)")
    memory_group.add_argument("--no-memory", dest="memory_enabled", action="store_false",
                              help="Disable Memory for this Session")
    session_init.set_defaults(memory_enabled=None)
    session_init.add_argument("--solution-min-relative-improvement", type=float, default=None)
    session_init.add_argument("--seed", type=int, default=DEFAULT_SEED)
    session_init.add_argument("--size", type=int, default=None)
    session_init.add_argument("--count", type=int, default=None)
    session_init.add_argument("--default-pop-size", type=int, default=None)
    session_init.add_argument("--default-n-pop", type=int, default=None)
    session_init.add_argument("--default-max-sample-nums", type=int, default=None)
    session_init.add_argument("--max-pop-size", type=int, default=8)
    session_init.add_argument("--max-n-pop", type=int, default=5)
    session_init.add_argument("--max-sample-nums-per-round", type=int, default=16)
    session_init.add_argument("--solver-timeout", type=float, default=DEFAULT_SOLVER_TIMEOUT)
    session_init.add_argument("--request-timeout", type=float, default=180.0)
    session_init.add_argument("--rounds", dest="max_rounds", type=int, default=None)
    session_init.add_argument("--round-budget", type=int, default=None)
    session_init.set_defaults(func=cmd_session_init)

    session_state = session_sub.add_parser("state", help="Read session state without external effects")
    session_state.add_argument("--run", required=True)
    session_state.add_argument("--run-id")
    session_state.set_defaults(func=cmd_session_state)

    session_stop = session_sub.add_parser("stop", help="Stop a session with an idempotent mutation")
    session_stop.add_argument("--run", required=True)
    session_stop.add_argument("--run-id")
    session_stop.add_argument("--operation-id", required=True)
    session_stop.add_argument("--expected-state-version", type=int, required=True)
    session_stop.add_argument("--reason", default="user_requested")
    session_stop.set_defaults(func=cmd_session_stop)

    for name, function in (("submit-plan", "submit_plan"), ("execute", "execute"), ("collect", "collect"),
                           ("read-evaluation", "read_evaluation"), ("submit-evaluation", "submit_evaluation"), ("memory-revise", "memory_revise"), ("finish-round", "finish_round")):
        command = session_sub.add_parser(name)
        command.add_argument("--run", required=True)
        command.add_argument("--run-id")
        if name != "read-evaluation":
            command.add_argument("--operation-id", required=True)
            command.add_argument("--expected-state-version", type=int, required=True)
        if name in {"submit-plan", "submit-evaluation", "memory-revise"}: command.add_argument("--file", required=True)
        if name == "finish-round": command.add_argument("--decision", choices=["continue", "complete"], required=True)
        if name == "read-evaluation":
            command.add_argument("--round", dest="round_id", type=int)
            command.add_argument("--candidate")
            command.add_argument("--include-diff", action="store_true")
        command.set_defaults(func=cmd_session_action, session_function=function)
    memory = session_sub.add_parser("memory")
    memory_sub = memory.add_subparsers(dest="memory_action", required=True)
    for name in ("search", "read"):
        command = memory_sub.add_parser(name)
        command.add_argument("--run", required=True)
        command.add_argument("--run-id")
        if name == "search":
            command.add_argument("--query", default="")
            command.add_argument("--type", dest="memory_type", choices=["insight", "solution"])
            command.add_argument("--scene")
            command.add_argument("--limit", type=int, default=8)
            command.add_argument("--include-shared", action="store_true")
            command.add_argument("--include-cross-project", action="store_true")
            command.add_argument("--cursor")
        else:
            command.add_argument("--reference", required=True)
            command.add_argument("--offset", type=int, default=0)
            command.add_argument("--limit", type=int, default=4096)
        command.set_defaults(func=cmd_session_action, session_function="memory_" + name)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"session", "benchmark"}:
            return int(args.func(args))
        problem_id = getattr(args, "problem", PROBLEM_CVRP)
        # Resolve from the spec registry so the CLI and the loop agree on identity.
        get_problem(problem_id)
        return int(args.func(args))
    except ValueError as exc:
        if args.command == "benchmark":
            print(json.dumps({
                "ok": False,
                "action": getattr(args, "benchmark_action", "benchmark"),
                "error": {"code": str(exc) or "INVALID_ARGUMENT", "message": str(exc)},
            }, ensure_ascii=False, indent=2))
            return 3
        problem_id = getattr(args, "problem", PROBLEM_CVRP)
        raise SystemExit(f"unknown problem: {problem_id}") from None
    except SessionError as exc:
        print(json.dumps(error_envelope(exc), ensure_ascii=False, indent=2))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
