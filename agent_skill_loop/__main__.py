"""CLI: prepare / smoke / run / evaluate-skill. No research-protocol flags."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_skill_loop.client import FixtureTransport, LiveTransport, load_local_env
from agent_skill_loop.contracts import (
    DEFAULT_COUNT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SPLIT,
    PROBLEM_CVRP,
)
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.loop import AgentLoop, prepare_output
from agent_skill_loop.problems.cvrp import BASELINE_CODE
from agent_skill_loop.skill_store import load_skill


def _require_new_dir(path: Path) -> Path:
    if path.exists():
        raise SystemExit(f"output directory must be new: {path}")
    return path


def _valid_fixture_response() -> str:
    farthest = BASELINE_CODE.replace("argmin", "argmax")
    return (
        "{Farthest-neighbor constructive heuristic for CVRP}\n"
        "```python\n"
        f"{farthest.strip()}\n"
        "```\n"
    )


def _invalid_fixture_response() -> str:
    return (
        "{Broken return type}\n"
        "```python\n"
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    return 'nope'\n"
        "```\n"
    )


def cmd_prepare(args: argparse.Namespace) -> int:
    path = _require_new_dir(Path(args.output))
    prepare_output(path, seed=args.seed, split=DEFAULT_SPLIT, count=args.count, size=args.size)
    print(path / "config_frozen.json")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    path = _require_new_dir(Path(args.output))
    path.mkdir(parents=True)
    transport = FixtureTransport([_valid_fixture_response(), _invalid_fixture_response(), _valid_fixture_response()])
    loop = AgentLoop(path, transport=transport, execution_mode="fixture")
    summary = loop.run()
    print(json.dumps(summary.as_dict(), indent=2))
    return 0 if summary.loop_completed else 1


def cmd_run(args: argparse.Namespace) -> int:
    load_local_env()
    path = _require_new_dir(Path(args.output))
    path.mkdir(parents=True)
    parent = load_skill(Path(args.parent_skill)) if args.parent_skill else None
    transport = LiveTransport(args.model)
    loop = AgentLoop(path, transport=transport, parent_skill=parent, execution_mode="live")
    summary = loop.run()
    print(json.dumps(summary.as_dict(), indent=2))
    return 0 if summary.status != "provider_failed" else 2


def cmd_evaluate_skill(args: argparse.Namespace) -> int:
    skill = load_skill(Path(args.skill))
    suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
    result = SubprocessEvaluator().evaluate(skill.code, suite)
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.valid else 1


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
    run.set_defaults(func=cmd_run)

    evaluate = sub.add_parser("evaluate-skill")
    evaluate.add_argument("--skill", required=True)
    evaluate.add_argument("--suite", required=True)
    evaluate.set_defaults(func=cmd_evaluate_skill)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "problem", PROBLEM_CVRP) != PROBLEM_CVRP:
        raise SystemExit("first version supports only cvrp_construct")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
