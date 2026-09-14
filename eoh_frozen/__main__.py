"""One production entry: supervised, unmodified, pinned upstream EoH."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from agent_skill_loop.client import load_local_env
from agent_skill_loop.contracts import DEFAULT_SEED, DEFAULT_SIZE, DEFAULT_COUNT, DEFAULT_SPLIT, EOH_COMMIT
from agent_skill_loop.session_contracts import MAX_ROUND_CONTEXT_CHARS
from agent_skill_loop.evaluator import evaluator_source_hash, kill_process_tree
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.request_budget import RequestBudget
from agent_skill_loop.skill_store import _atomic_write_text, load_skill, validate_skill_for_suite
from eoh_frozen.export import export_run_evidence, finalize_evaluations


def _bridge_target(endpoint: str) -> str:
    value = endpoint if "://" in endpoint else f"https://{endpoint}"
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/") or "/v1/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _json(path: Path, data: object) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def prepare_output(path: Path, *, problem_id: str, seed=DEFAULT_SEED, count=DEFAULT_COUNT, size=DEFAULT_SIZE,
                   suite_override: dict | None = None) -> dict:
    path.mkdir(parents=True, exist_ok=False)
    spec = get_problem(problem_id)
    suite = suite_override if suite_override is not None else spec.build_suite(seed, split=DEFAULT_SPLIT, count=count, size=size)
    spec.validate_suite(suite)
    config = {"problem": problem_id, "suite_hash": suite["content_hash"],
              "entrypoint": spec.entrypoint, "interface_version": spec.interface_version,
              "evaluator_hash": evaluator_source_hash(), "search_policy": {"id": "official_eoh", "version": EOH_COMMIT},
              "purpose": "suite_preparation", "seed": seed, "count": count, "size": size}
    _json(path / "dev_suite.json", suite)
    _json(path / "config_frozen.json", config)
    return config


def cmd_run(args: argparse.Namespace) -> int:
    from eoh_frozen.identity import verify_upstream, adapter_source_hash
    from eoh_frozen.llm_bridge import OpenAIPathBridge
    from eoh_frozen.problem import FrozenProblem
    started = time.monotonic()
    deadline = started + args.wall_seconds
    if args.parent_skill and getattr(args, "seed_codes", None):
        raise SystemExit("--parent-skill and --seed-codes are mutually exclusive")
    if any(not math.isfinite(v) for v in (args.wall_seconds, args.solver_timeout, args.request_timeout)) or args.pop_size < 2 or args.n_pop < 0 or args.max_requests < 0 or args.wall_seconds < 0 or args.solver_timeout <= 1 or args.request_timeout <= 0 or (args.max_sample_nums is not None and args.max_sample_nums < 0) or args.max_repairs_per_candidate not in {0, 1} or (args.max_repair_requests_total is not None and args.max_repair_requests_total < 0):
        raise SystemExit("invalid_run_budget_or_population")
    upstream = verify_upstream()
    adapter_hash = adapter_source_hash()
    load_local_env()
    key = os.environ.get(args.api_key_env, "")
    if not key and args.max_requests > 0:
        raise SystemExit(f"missing API key in {args.api_key_env}")
    output = Path(args.output).resolve()
    if output.exists():
        raise SystemExit(f"output directory must be new: {output}")
    if args.round_context_file:
        context_path = Path(args.round_context_file).resolve()
        if not context_path.is_file():
            raise SystemExit(f"round context file not found: {context_path}")
        round_context = context_path.read_text(encoding="utf-8")
        if len(round_context) > MAX_ROUND_CONTEXT_CHARS:
            raise SystemExit("plan_context_too_large")
    else:
        round_context = None
    suite_override = None
    if getattr(args, "suite_file", None):
        suite_file = Path(args.suite_file).resolve()
        if not suite_file.is_file():
            raise SystemExit(f"suite file not found: {suite_file}")
        try:
            suite_override = json.loads(suite_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise SystemExit("suite file is invalid") from None
        if not isinstance(suite_override, dict) or suite_override.get("problem") != args.problem:
            raise SystemExit("suite file problem mismatch")
    config = prepare_output(output, problem_id=args.problem, seed=args.seed, count=args.count, size=args.size, suite_override=suite_override)
    spec = get_problem(args.problem)
    suite = json.loads((output / "dev_suite.json").read_text(encoding="utf-8"))
    session = getattr(args, "session", None)
    if session:
        from agent_skill_loop.session_ledger import SessionRequestBudget
        budget = SessionRequestBudget(session["root"], session["task_id"])
    else:
        budget = RequestBudget(args.max_requests)
    results = output / "results"
    results.mkdir()
    # ``EoH`` is instantiated directly below (the public ``run`` helper is
    # intentionally not used), so create the same checkpoint directories that
    # the upstream folder helper would create.  Without these, the search still
    # evaluates candidates but silently loses samples/population checkpoints.
    for subdir in ("samples", "pops", "pops_best", "evaluation_starts", "exchanges"):
        (results / subdir).mkdir(parents=True, exist_ok=True)
    parent = None
    seed_path = None
    seed_members = None
    if getattr(args, "seed_codes", None):
        seed_source = Path(args.seed_codes).resolve()
        if not seed_source.is_file():
            raise SystemExit(f"seed selection file not found: {seed_source}")
        try:
            seed_payload = json.loads(seed_source.read_text(encoding="utf-8"))
            seed_members = seed_payload.get("selected_members") if isinstance(seed_payload, dict) else seed_payload
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise SystemExit("seed selection file is invalid") from None
        if not isinstance(seed_members, list) or not seed_members or any(not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"].strip() for item in seed_members):
            raise SystemExit("seed selection contains no executable members")
        seed_path = output / "seeds" / "population_seeds.json"
        _json(seed_path, [{
            "algorithm": str(item.get("algorithm") or "Population seed"),
            "algorithm_text_sha256": item.get("algorithm_text_sha256"),
            "code": item["code"],
            "code_sha256": item.get("code_sha256") or hashlib.sha256(item["code"].encode("utf-8")).hexdigest(),
            "candidate_id": item.get("candidate_id"),
            "evaluation_id": item.get("evaluation_id"),
            "revision": item.get("revision", "original"),
            "source_ref": item.get("source_ref"),
        } for item in seed_members])
    config.update({"search": "official_eoh", "integration_mode": "bounded_repair" if args.repair_mode == "bounded" else "official_only",
                   "repair_mode": args.repair_mode,
                   "repair_policy_version": "bounded_v2" if args.repair_mode == "bounded" else None,
                   "max_repairs_per_candidate": args.max_repairs_per_candidate,
                   "max_repair_requests_total": args.max_repair_requests_total,
                   "eoh_commit": EOH_COMMIT, "upstream": upstream,
                   "adapter_source_hash": adapter_hash,
                   "execution_mode": getattr(args, "execution_mode", "live"),
                   "model": args.model, "endpoint": args.endpoint, "objective_direction": spec.objective_direction,
                   "pop_size": args.pop_size, "n_pop": args.n_pop, "operators": args.operators,
                   "max_sample_nums": args.max_sample_nums, "request_budget": args.max_requests,
                   "wall_seconds": args.wall_seconds, "solver_timeout": args.solver_timeout,
                   "initialization_samples": 0 if (args.parent_skill or seed_members) else 2 * args.pop_size,
                   "evolution_samples": args.max_sample_nums if args.max_sample_nums is not None else args.pop_size * args.n_pop,
                   "search_seed": getattr(args, "search_seed", None) if getattr(args, "search_seed", None) is not None else args.seed,
                   "probe_requests": 1, "num_samplers": 1, "num_evaluators": 1})
    config["metric_spec_hash"] = getattr(args, "metric_spec_hash", None)
    config["data_manifest_hash"] = getattr(args, "data_manifest_hash", None)
    config["problem_spec_hash"] = getattr(args, "problem_spec_hash", None)
    if round_context is not None:
        config.update({"context_mode": "round", "round_context_sha256": hashlib.sha256(round_context.encode("utf-8")).hexdigest()})
    summary = {"problem": args.problem, "search": "official_eoh", "integration_mode": "bounded_repair" if args.repair_mode == "bounded" else "official_only",
               "repair_mode": args.repair_mode, "eoh_commit": EOH_COMMIT,
               "adapter_source_hash": adapter_hash,
               "suite_hash": suite["content_hash"], "evaluator_hash": evaluator_source_hash(),
               "status": "completed", "stop_reason": "eoh_completed", "loop_completed": True,
               "best_generated_path": None, "exported_skill": None}
    bridge = None
    proc = None
    try:
        task = FrozenProblem(suite, spec=spec, timeout=args.solver_timeout, deadline=deadline,
                             origin="baseline", metric_spec_hash=getattr(args, "metric_spec_hash", None),
                             data_manifest_hash=getattr(args, "data_manifest_hash", None),
                             problem_spec_hash=getattr(args, "problem_spec_hash", None),
                             evaluation_log=results / "evaluations.jsonl", session=session)
        baseline = task.evaluate_result(spec.baseline_code)
        config["baseline"] = baseline.as_dict()
        summary["baseline"] = baseline.as_dict()
        if time.monotonic() >= deadline:
            summary.update(status="stopped", stop_reason="wall_time_limit")
        elif not baseline.valid:
            summary.update(status="evaluation_failed", stop_reason="baseline_invalid", loop_completed=False)
        else:
            if args.parent_skill:
                parent = load_skill(Path(args.parent_skill))
                mismatch = validate_skill_for_suite(parent, suite)
                if mismatch or not parent.valid:
                    raise ValueError(mismatch or "invalid_parent_skill")
                task.origin = "explicit_parent"
                checked = task.evaluate_result(parent.code)
                if not checked.valid:
                    if time.monotonic() >= deadline:
                        summary.update(status="stopped", stop_reason="wall_time_limit")
                    else:
                        raise ValueError("parent_reeval_invalid")
                else:
                    config["parent_skill"] = {"version_id": parent.version_id, "code_sha256": parent.code_sha256,
                                              "original_suite_hash": parent.suite_hash, "evaluation": checked.as_dict()}
                    _json(output / "seeds/parent_skill.json", [{"algorithm": parent.description or "Explicit parent", "code": parent.code}])
            if summary["status"] == "completed" and args.max_requests == 0:
                summary.update(status="stopped", stop_reason="request_limit")
            if summary["status"] == "completed":
                bridge = OpenAIPathBridge(_bridge_target(args.endpoint), key, args.model, timeout=args.request_timeout,
                                         budget=budget, request_log=results / "requests.jsonl",
                                         wall_seconds=max(0, deadline - time.monotonic()), problem=args.problem)
                bridge.thinking = getattr(args, "eoh_thinking", "provider-default")
                config["thinking"] = bridge.thinking
                local_url = bridge.start()
                worker_config = {**config, "deadline": deadline, "local_url": local_url,
                                  "session": session, "supervisor_pid": os.getpid() if session else None,
                                  "round_context": round_context,
                                  "use_seed": bool(parent is not None or seed_members),
                                  "seed_path": str(seed_path) if seed_path else str(output / "seeds" / "parent_skill.json"),
                                  "population_seed_count": len(seed_members or []),
                                  "request_timeout": args.request_timeout,
                                  "max_repairs_per_candidate": args.max_repairs_per_candidate,
                                  "max_repair_requests_total": args.max_repair_requests_total}
                _json(output / "worker_config.json", worker_config)
                env = {k: os.environ[k] for k in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG") if k in os.environ}
                env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
                with (results / "engine.log").open("wb") as log:
                    proc = subprocess.Popen([sys.executable, "-m", "eoh_frozen.worker", str(output)], env=env,
                                            stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                            start_new_session=os.name != "nt",
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                    while proc.poll() is None:
                        if session:
                            from agent_skill_loop.session_supervisor import stop_requested
                            if stop_requested(Path(session["root"]), session["task_id"]):
                                bridge.terminal = True
                                bridge.last_error = "session_stopped"
                        if time.monotonic() >= deadline or bridge.terminal:
                            reason = bridge.last_error if bridge.terminal else "wall_time_exhausted"
                            bridge.terminal = True
                            bridge.last_error = reason
                            kill_process_tree(proc)
                            break
                        try:
                            proc.wait(timeout=min(0.05, max(0.001, deadline - time.monotonic())))
                        except subprocess.TimeoutExpired:
                            pass
                if time.monotonic() >= deadline and bridge.last_error is None:
                    bridge.last_error = "wall_time_exhausted"
                error = bridge.last_error
                if error in {"request_budget_exhausted", "wall_time_exhausted", "solver_budget_exhausted", "round_budget_exhausted", "session_stopped"}:
                    summary.update(status="stopped", stop_reason={
                        "request_budget_exhausted": "request_limit",
                        "wall_time_exhausted": "wall_time_limit",
                        "solver_budget_exhausted": "solver_call_limit",
                        "round_budget_exhausted": "round_budget_limit",
                        "session_stopped": "user_requested",
                    }[error])
                elif error:
                    summary.update(status="storage_failed" if error == "evidence_storage_error" else "provider_failed",
                                   stop_reason="provider_error" if error != "evidence_storage_error" else "storage_error",
                                   provider_error_code=error, loop_completed=False)
                else:
                    result_path = output / "worker_result.json"
                    result = json.loads(result_path.read_text()) if result_path.is_file() else {"status": "engine_failed", "error_type": "WorkerExited"}
                    if result["status"] == "budget_exhausted":
                        summary.update(status="stopped", stop_reason=result.get("stop_reason", "budget_limit"),
                                       engine_error=result.get("error_type"), engine_error_code=result.get("error_code"),
                                       loop_completed=True)
                    elif result["status"] != "completed":
                        summary.update(status="engine_failed", stop_reason="engine_error", engine_error=result.get("error_type"), engine_error_code=result.get("error_code"), loop_completed=False)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        summary.update(status="invalid_input" if isinstance(exc, ValueError) else "storage_failed",
                       stop_reason="input_error" if isinstance(exc, ValueError) else "storage_error",
                       error_type=type(exc).__name__, error_detail=str(exc)[:200], loop_completed=False)
        if session and str(exc) in {"solver_budget_exhausted", "round_budget_exhausted", "session_stopped"}:
            summary.update(
                status="stopped",
                stop_reason=("solver_call_limit" if str(exc) == "solver_budget_exhausted"
                             else "round_budget_limit" if str(exc) == "round_budget_exhausted"
                             else "user_requested"),
                loop_completed=True,
            )
    finally:
        if proc is not None and proc.poll() is None:
            kill_process_tree(proc)
        if bridge is not None:
            bridge.stop()
        try:
            _json(output / "config_frozen.json", config)
            summary.update(finalize_evaluations(output, suite, stop_reason=summary["stop_reason"]))
            # Shutdown serializes completed evidence; never starts a new solver.
            summary.update(export_run_evidence(output, suite, parent=parent))
            repair_summary_path = output / "results" / "repair_summary.json"
            if repair_summary_path.is_file():
                summary["repair"] = json.loads(repair_summary_path.read_text(encoding="utf-8"))
            else:
                summary["repair"] = {
                    "mode": args.repair_mode,
                    "max_repairs_per_candidate": args.max_repairs_per_candidate,
                    "max_repair_requests_total": args.max_repair_requests_total,
                }
            if summary.get("engine_error_code") == "no_valid_initial_population" and summary.get("generated_valid_candidates", 0) == 0 and summary.get("generation_requests", 0) > 0:
                summary.update(status="no_valid_candidate", stop_reason="no_valid_candidate", loop_completed=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            summary.update(export_status="failed", export_error=type(exc).__name__)
            summary["prior_status"] = summary["status"]
            summary["prior_stop_reason"] = summary["stop_reason"]
            summary.update(status="export_failed", stop_reason="export_error", loop_completed=False)
        summary.update(http_requests=budget.used, request_rejected=budget.rejected,
                       wall_seconds=time.monotonic() - started)
        _json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["loop_completed"] else 2


def add_run_arguments(run: argparse.ArgumentParser) -> None:
    run.add_argument("--problem", default="cvrp_construct")
    run.add_argument("--eoh-model", "--model", dest="model", required=True,
                     help="Model used by the official EoH engine (legacy --model alias accepted)")
    run.add_argument("--output", required=True)
    run.add_argument("--eoh-endpoint", "--endpoint", dest="endpoint", default="https://api.deepseek.com/v1/chat/completions")
    run.add_argument("--eoh-api-key-env", "--api-key-env", dest="api_key_env", default="DEEPSEEK_API_KEY")
    run.add_argument("--request-timeout", type=float, default=180.0)
    run.add_argument("--solver-timeout", type=float, default=20.0)
    run.add_argument("--seed", type=int, default=DEFAULT_SEED)
    run.add_argument("--search-seed", type=int, default=None,
                     help="Seed for official EoH operator/search randomness; defaults to --seed")
    run.add_argument("--size", type=int, default=DEFAULT_SIZE)
    run.add_argument("--count", type=int, default=DEFAULT_COUNT)
    run.add_argument("--pop-size", type=int, default=4)
    run.add_argument("--n-pop", type=int, default=5)
    run.add_argument("--max-sample-nums", type=int, default=None, help="Evolution attempts AFTER initialization; excludes probe and retries")
    run.add_argument("--max-requests", type=int, default=32, help="Hard cap on ALL outbound HTTP attempts including probe and retries")
    run.add_argument("--wall-seconds", type=float, default=420.0)
    run.add_argument("--operators", nargs="+", choices=["e1", "e2", "m1", "m2"], default=["e1", "e2", "m1", "m2"])
    run.add_argument("--parent-skill")
    run.add_argument("--seed-codes", help="Frozen SeedSelection JSON with selected_members; mutually exclusive with --parent-skill")
    run.add_argument("--round-context-file", help="Bounded advisory Plan context for this EoH run")
    run.add_argument("--suite-file", help="Use an already frozen suite (Session adapter)")
    run.add_argument("--repair-mode", choices=["off", "bounded"], default="off")
    run.add_argument("--max-repairs-per-candidate", type=int, default=1)
    run.add_argument("--max-repair-requests-total", type=int, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eoh_frozen")
    run = parser.add_subparsers(dest="command", required=True).add_parser("run")
    add_run_arguments(run)
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
