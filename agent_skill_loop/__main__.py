"""CLI: prepare / smoke / run / evaluate-skill / import-skill. No research-protocol flags."""

from __future__ import annotations

import argparse
import json
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
    from agent_skill_loop.client import load_local_env
    from agent_skill_loop.memory import MemoryAPI
    from agent_skill_loop.workflow import WorkflowRunner
    load_local_env()
    memory = MemoryAPI(Path(args.memory_store)) if args.memory_store else None
    result = WorkflowRunner(
        Path(args.output), problem=args.problem, model=args.model, endpoint=args.endpoint,
        api_key_env=args.api_key_env, max_rounds=args.rounds, max_requests=args.max_requests,
        wall_seconds=args.wall_seconds, seed=args.seed, size=args.size, count=args.count,
        pop_size=args.pop_size, n_pop=args.n_pop, max_sample_nums=args.max_sample_nums,
        solver_timeout=args.solver_timeout, request_timeout=args.request_timeout, memory=memory,
        solution_min_relative_improvement=args.solution_min_relative_improvement,
        repair_mode=args.repair_mode,
        max_repairs_per_candidate=args.max_repairs_per_candidate,
        max_repair_requests_total=args.max_repair_requests_total,
    ).run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "completed" else 2


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

    workflow = sub.add_parser("workflow", help="Run bounded Plan → official EoH → Evaluate rounds")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    problem_id = getattr(args, "problem", PROBLEM_CVRP)
    try:
        # Resolve from the spec registry so the CLI and the loop agree on identity.
        get_problem(problem_id)
    except ValueError:
        raise SystemExit(f"unknown problem: {problem_id}") from None
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
