"""Command-line entrypoint for running or resuming the Milestone 3 Research Agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_agent.contracts import AgentConfig
from research_agent.loop import run_research_agent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autonomous CO Research Agent CLI (Milestone 3).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Start a new autonomous research run.")
    p_run.add_argument("--output-dir", type=Path, required=True)
    p_run.add_argument("--run-id", default="m3_agent_run")
    p_run.add_argument("--arm-id", default="arm_m3_3_full_dynamic")
    p_run.add_argument("--mode", choices=("mock", "live"), default="mock")
    p_run.add_argument("--max-rounds", type=int, default=3)
    p_run.add_argument("--total-request-cap", type=int, default=36)
    p_run.add_argument("--time-budget-ms", type=float, default=500.0)
    p_run.add_argument("--planner-model", default="deepseek-chat")
    p_run.add_argument("--eoh-model", default="deepseek-chat")
    p_run.add_argument("--endpoint", default="https://api.deepseek.com/v1/chat/completions")
    p_run.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    p_run.add_argument("--search-seed", type=int, default=20261124)
    p_run.add_argument("--disable-tools", action="store_true")
    p_run.add_argument("--no-agent-guidance", action="store_true")
    p_run.add_argument("--use-benchmark-dev-suite", action="store_true")
    p_run.add_argument("--kb-store", type=Path, default=None)

    p_res = sub.add_parser("resume", help="Resume an interrupted autonomous research run.")
    p_res.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "run":
        cfg = AgentConfig(
            run_id=args.run_id,
            output_dir=str(args.output_dir.resolve()),
            arm_id=args.arm_id,
            mode=args.mode,
            max_rounds=args.max_rounds,
            total_request_cap=args.total_request_cap,
            instance_time_budget_ms=args.time_budget_ms,
            planner_model=args.planner_model,
            eoh_model=args.eoh_model,
            endpoint=args.endpoint,
            api_key_env=args.api_key_env,
            search_seed=args.search_seed,
            tools_enabled=not args.disable_tools,
            agent_guidance=not args.no_agent_guidance,
            use_benchmark_dev_suite=bool(args.use_benchmark_dev_suite),
            kb_store_path=str(args.kb_store.resolve()) if args.kb_store else None,
        )
        res = run_research_agent(cfg, resume=False)
    else:
        cfg_path = args.output_dir.resolve() / "agent_config.json"
        cfg = AgentConfig.from_dict(json.loads(cfg_path.read_text(encoding="utf-8")))
        res = run_research_agent(cfg, resume=True)

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0
