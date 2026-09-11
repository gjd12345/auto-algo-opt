"""Run official EoH on the frozen CVRP construct suite. Operators stay upstream."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from agent_skill_loop.client import load_local_env
from agent_skill_loop.contracts import (
    DEFAULT_COUNT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    DEFAULT_SPLIT,
)
from agent_skill_loop.problems.cvrp import build_suite
from agent_skill_loop.request_budget import RequestBudget
from eoh_frozen.export import export_best_skill, load_best_individual
from eoh_frozen.problem import FrozenCVRPConstruct

DEFAULT_EOH_WALL_SECONDS = 3600.0


def _require_new_dir(path: Path) -> Path:
    if path.exists():
        raise SystemExit(f"output directory must be new: {path}")
    return path


def _bridge_target(endpoint: str) -> str:
    """Normalise an endpoint to a full URL the bridge can POST to."""
    if "://" in endpoint:
        return endpoint
    return f"https://{endpoint}/v1/chat/completions"


def cmd_run(args: argparse.Namespace) -> int:
    from eoh import EoH, LLMConfig

    from eoh_frozen.llm_bridge import OpenAIPathBridge

    load_local_env()
    output = _require_new_dir(Path(args.output))
    output.mkdir(parents=True)
    suite = build_suite(args.seed, split=DEFAULT_SPLIT, count=args.count, size=args.size)
    (output / "dev_suite.json").write_text(
        json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        raise SystemExit(f"missing API key in {args.api_key_env}")
    if args.max_requests is None:
        max_requests = (2 * args.pop_size + args.pop_size * args.n_pop) * 6 + 20
    else:
        max_requests = args.max_requests
    budget = RequestBudget(max_requests)
    fail_log = output / "results" / "eval_failures.jsonl"
    fail_log.parent.mkdir(parents=True, exist_ok=True)
    task = FrozenCVRPConstruct(
        suite,
        timeout=int(args.solver_timeout),
        n_processes=1,
        fail_log=fail_log,
    )
    config = {
        "problem": "cvrp_construct",
        "suite_hash": suite["content_hash"],
        "seed": args.seed,
        "size": args.size,
        "count": args.count,
        "split": DEFAULT_SPLIT,
        "model": args.model,
        "endpoint": args.endpoint,
        "pop_size": args.pop_size,
        "n_pop": args.n_pop,
        "operators": args.operators,
        "max_sample_nums": args.max_sample_nums,
        "search": "official_eoh",
        "eoh_package": "FeiLiu36/EoH",
        "request_budget": max_requests,
        "wall_seconds": args.wall_seconds,
    }
    (output / "config_frozen.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    # Every outbound request goes through the bridge so the shared budget and
    # the total-deadline transport apply to the default endpoint too.
    bridge = OpenAIPathBridge(
        _bridge_target(args.endpoint),
        api_key,
        args.model,
        timeout=args.request_timeout,
        budget=budget,
        request_log=output / "results" / "requests.jsonl",
        wall_seconds=args.wall_seconds,
    )
    local_url = bridge.start()
    llm = LLMConfig(
        use_local=True,
        local_url=local_url,
        model=args.model,
        timeout=int(args.request_timeout),
    )

    summary: dict = {
        "search": "official_eoh",
        "suite_hash": suite["content_hash"],
        "model": args.model,
        "pop_size": args.pop_size,
        "n_pop": args.n_pop,
        "operators": args.operators,
        "request_budget": max_requests,
        "http_requests": 0,
        "request_rejected": 0,
    }
    exit_code = 0
    try:
        eoh = EoH(
            llm=llm,
            problem=task,
            pop_size=args.pop_size,
            n_pop=args.n_pop,
            operators=args.operators,
            num_samplers=1,
            num_evaluators=1,
            max_sample_nums=args.max_sample_nums,
            output_dir=str(output),
        )
        eoh.run()
        exported = export_best_skill(output, suite, timeout=float(args.solver_timeout))
        best = load_best_individual(output)
        rejected = output / "results" / "export_rejected.json"
        summary.update({
            "loop_completed": True,
            "status": "completed",
            "best_objective": None if best is None else best.get("objective"),
            "best_generated_path": None if exported is None else "skills/eoh_best",
            "exported_skill": None if exported is None else "exported_skill",
            "export_rejected": "results/export_rejected.json" if rejected.is_file() else None,
        })
    except Exception as exc:
        exit_code = 2
        summary.update({
            "loop_completed": False,
            "status": "provider_failed",
            "provider_error_code": bridge.last_error or type(exc).__name__,
        })
    finally:
        bridge.stop()
        summary["http_requests"] = budget.used
        summary["request_rejected"] = budget.rejected
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eoh_frozen")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--model", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--endpoint", default="api.deepseek.com")
    run.add_argument("--api-key-env", default="MODEL_ROUTER_API_KEY")
    run.add_argument("--request-timeout", type=float, default=180.0)
    run.add_argument("--solver-timeout", type=float, default=DEFAULT_SOLVER_TIMEOUT)
    run.add_argument("--seed", type=int, default=DEFAULT_SEED)
    run.add_argument("--size", type=int, default=DEFAULT_SIZE)
    run.add_argument("--count", type=int, default=DEFAULT_COUNT)
    run.add_argument("--pop-size", type=int, default=4)
    run.add_argument("--n-pop", type=int, default=5)
    run.add_argument("--max-sample-nums", type=int, default=None)
    run.add_argument("--max-requests", type=int, default=None)
    run.add_argument("--wall-seconds", type=float, default=DEFAULT_EOH_WALL_SECONDS)
    run.add_argument("--operators", nargs="+", default=["e1", "e2", "m1", "m2"])
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())