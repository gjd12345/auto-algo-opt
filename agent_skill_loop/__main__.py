"""CLI: prepare / smoke / run / evaluate-skill / import-skill. No research-protocol flags."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_skill_loop.client import FixtureTransport, LiveTransport, load_local_env
from agent_skill_loop.contracts import (
    DEFAULT_CANDIDATE_ATTEMPTS,
    DEFAULT_COUNT,
    DEFAULT_MAX_LLM_REQUESTS,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    DEFAULT_SPLIT,
    DEFAULT_WALL_SECONDS,
    PROBLEM_CVRP,
)
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.importer import import_skill
from agent_skill_loop.loop import AgentLoop, prepare_output
from agent_skill_loop.problems.base import ProblemSpec, get_problem
from agent_skill_loop.skill_store import load_skill


def _require_new_dir(path: Path) -> Path:
    if path.exists():
        raise SystemExit(f"output directory must be new: {path}")
    return path


def _valid_fixture_response(spec: ProblemSpec) -> str:
    farthest = spec.baseline_code.replace("argmin", "argmax")
    return (
        "{Farthest-neighbor constructive heuristic}\n"
        "```python\n"
        f"{farthest.strip()}\n"
        "```\n"
    )


def _invalid_fixture_response(spec: ProblemSpec) -> str:
    return (
        "{Broken return type}\n"
        "```python\n"
        f"def {spec.entrypoint}(*args, **kwargs):\n"
        "    return 'nope'\n"
        "```\n"
    )


def cmd_prepare(args: argparse.Namespace) -> int:
    path = _require_new_dir(Path(args.output))
    prepare_output(
        path,
        problem_id=args.problem,
        seed=args.seed,
        split=DEFAULT_SPLIT,
        count=args.count,
        size=args.size,
    )
    print(path / "config_frozen.json")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    spec = get_problem(args.problem)
    path = _require_new_dir(Path(args.output))
    path.mkdir(parents=True)
    transport = FixtureTransport([
        _valid_fixture_response(spec),
        _invalid_fixture_response(spec),
        _valid_fixture_response(spec),
    ])
    loop = AgentLoop(path, transport=transport, execution_mode="fixture", problem_spec=spec)
    summary = loop.run()
    print(json.dumps(summary.as_dict(), indent=2))
    return 0 if summary.loop_completed else 1


def cmd_run(args: argparse.Namespace) -> int:
    load_local_env()
    spec = get_problem(args.problem)
    path = _require_new_dir(Path(args.output))
    path.mkdir(parents=True)
    parent = load_skill(Path(args.parent_skill)) if args.parent_skill else None
    transport = LiveTransport(
        args.model,
        timeout=args.request_timeout,
        endpoint=args.endpoint,
        api_key_env=args.api_key_env,
    )
    loop = AgentLoop(
        path,
        transport=transport,
        parent_skill=parent,
        execution_mode="live",
        candidate_attempts=args.candidate_attempts,
        max_llm_requests=args.max_llm_requests,
        wall_seconds=args.wall_seconds,
        request_timeout=args.request_timeout,
        model=args.model,
        problem_spec=spec,
    )
    summary = loop.run()
    print(json.dumps(summary.as_dict(), indent=2))
    return 0 if summary.status != "provider_failed" else 2


def cmd_evaluate_skill(args: argparse.Namespace) -> int:
    skill = load_skill(Path(args.skill))
    suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
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

    run = sub.add_parser("run")
    run.add_argument("--problem", default=PROBLEM_CVRP)
    run.add_argument("--model", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--parent-skill")
    run.add_argument("--endpoint")
    run.add_argument("--api-key-env", default="MODEL_ROUTER_API_KEY")
    run.add_argument("--request-timeout", type=float, default=max(DEFAULT_REQUEST_TIMEOUT, 180.0))
    run.add_argument("--candidate-attempts", type=int, default=DEFAULT_CANDIDATE_ATTEMPTS)
    run.add_argument("--max-llm-requests", type=int, default=DEFAULT_MAX_LLM_REQUESTS)
    run.add_argument("--wall-seconds", type=float, default=DEFAULT_WALL_SECONDS)
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
