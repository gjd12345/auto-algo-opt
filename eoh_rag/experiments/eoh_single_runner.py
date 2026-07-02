from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any

from eoh_rag.experiments.rag_context_builder import (
    OFFICIAL_RAG_PROBLEM_CONFIG,
    build_official_rag_context,
    history_card_gate_reasons,
    history_card_gate_warnings,
)
from eoh_rag.experiments.problem_registry import PROBLEMS
from eoh_rag.rag.card_outcomes import load_outcomes, summarize_all_cards
from eoh_rag.rag.features import load_population_features


DEFAULT_OFFICIAL_ROOT = os.environ.get("EOH_OFFICIAL_ROOT", "")
DEFAULT_OFFICIAL_PYTHON = os.environ.get("EOH_OFFICIAL_PYTHON", "")


def normalize_api_endpoint(endpoint: str) -> str:
    value = (endpoint or "").strip()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/", 1)[0]
    return value.strip()


def _natural_generation(path: Path) -> int:
    match = re.search(r"population_generation_(\d+)\.json$", path.name)
    return int(match.group(1)) if match else -1


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def redact_log_tail(text: str) -> str:
    redacted = re.sub(r"https?://\S+", "[api-endpoint-redacted]", text or "")
    redacted = re.sub(r"(endpoint=)[^,\s)]+", r"\1[api-endpoint-redacted]", redacted)
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[api-key-redacted]", redacted)
    return redacted


def _tail_text(value: str | bytes | None, max_lines: int = 80) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", "replace")
    else:
        text = value
    return "\n".join(text.splitlines()[-max_lines:])


def summarize_run(run_dir: Path) -> dict[str, Any]:
    pop_dir = run_dir / "results" / "pops"
    populations = sorted(pop_dir.glob("population_generation_*.json"), key=_natural_generation)
    samples = sorted((run_dir / "results" / "samples").glob("samples_*.json"))
    best_sample = run_dir / "results" / "samples" / "samples_best.json"
    summary: dict[str, Any] = {
        "run_dir": str(run_dir),
        "ok": False,
        "failure_reason": None,
        "latest_population_path": None,
        "latest_generation": None,
        "population_size": 0,
        "valid_candidates": 0,
        "best_objective": None,
        "best_algorithm": None,
        "best_code": None,
        "sample_file_count": len(samples),
        "best_sample_path": str(best_sample) if best_sample.exists() else None,
    }
    if not populations:
        summary["failure_reason"] = "missing_population"
        return summary

    latest = populations[-1]
    population = _load_json(latest)
    if not isinstance(population, list):
        summary["failure_reason"] = "population_not_list"
        return summary
    valid = [item for item in population if isinstance(item, dict) and item.get("objective") is not None]
    best = min(valid, key=lambda item: item["objective"]) if valid else None
    summary.update(
        {
            "ok": best is not None,
            "failure_reason": None if best is not None else "no_valid_candidates",
            "latest_population_path": str(latest),
            "latest_generation": _natural_generation(latest),
            "population_size": len(population),
            "valid_candidates": len(valid),
            "best_objective": best.get("objective") if best else None,
            "best_algorithm": best.get("algorithm") if best else None,
            "best_code": best.get("code") if best else None,
        }
    )
    return summary


def _api_context(problem: str) -> str:
    if problem == "bp_online":
        return (
            "API RULES: implement score(item, bins). Return a numeric numpy array with one score per feasible bin. "
            "Do not mutate bins. Prefer simple vectorized formulas over loops."
        )
    if problem == "tsp_construct":
        return (
            "API RULES: implement select_next_node(current_node, destination_node, unvisited_nodes, distance_matrix). "
            "Return one int from unvisited_nodes. Do not return a visited node or a new array."
        )
    if problem == "cvrp_construct":
        return (
            "API RULES: implement select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix). "
            "Return one int from unvisited_nodes, or depot only when intentionally ending the route."
        )
    raise ValueError(f"unknown problem: {problem}")


def _runner_script() -> str:
    return textwrap.dedent(
        r'''
        from __future__ import annotations

        import argparse
        import json
        import os
        import re
        import sys
        import time
        import urllib.request
        from pathlib import Path


        def normalize_api_endpoint(endpoint: str) -> str:
            value = (endpoint or "").strip()
            value = re.sub(r"^https?://", "", value)
            value = value.split("/", 1)[0]
            return value.strip()


        def api_url(endpoint: str) -> str:
            value = (endpoint or "").strip()
            if value.startswith(("http://", "https://")):
                if "/" in value.removeprefix("https://").removeprefix("http://"):
                    return value
                return value.rstrip("/") + "/v1/chat/completions"
            if "/" in value:
                return "https://" + value
            return "https://" + value.rstrip("/") + "/v1/chat/completions"


        def install_api_url_patch() -> None:
            from eoh.llm import api_general

            def get_response(self, prompt_content: str, max_retries: int = 5):
                payload = json.dumps({
                    "model": self.model_LLM,
                    "messages": [{"role": "user", "content": prompt_content}],
                    "thinking": {"type": "disabled"},
                }).encode("utf-8")
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "eoh-experiment/1.0",
                }
                url = api_url(self.api_endpoint)
                for attempt in range(max_retries):
                    try:
                        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                            parsed = json.loads(resp.read().decode("utf-8", "replace"))
                        choices = parsed.get("choices")
                        if not choices:
                            error_msg = parsed.get("error", {}).get("message", str(parsed))
                            raise ValueError(f"API returned no choices: {error_msg}")
                        return choices[0]["message"]["content"]
                    except Exception as exc:
                        api_general.logger.debug("API error (attempt %d/%d): %s", attempt + 1, max_retries, exc)
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                api_general.logger.warning(
                    "API call failed after %d attempts (endpoint=%s, model=%s).",
                    max_retries,
                    self.api_endpoint,
                    self.model_LLM,
                )
                return None

            api_general.InterfaceAPI.get_response = get_response


        def api_context(problem: str) -> str:
            if problem == "bp_online":
                return (
                    "API RULES: implement score(item, bins). Return a numeric numpy array with one score per feasible bin. "
                    "Do not mutate bins. Prefer simple vectorized formulas over loops."
                )
            if problem == "tsp_construct":
                return (
                    "API RULES: implement select_next_node(current_node, destination_node, unvisited_nodes, distance_matrix). "
                    "Return one int from unvisited_nodes. Do not return a visited node or a new array."
                )
            if problem == "cvrp_construct":
                return (
                    "API RULES: implement select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix). "
                    "Return one int from unvisited_nodes, or depot only when intentionally ending the route."
                )
            raise ValueError(f"unknown problem: {problem}")


        def load_problem(problem: str, official_root: Path, eval_timeout_s: int, n_processes: int):
            sys.path.insert(0, str(official_root / "eoh" / "src"))
            example_root = official_root / "examples" / problem
            sys.path.insert(0, str(example_root))
            if problem == "bp_online":
                from prob import BPONLINE
                return BPONLINE(capacity=100, timeout=eval_timeout_s, n_processes=n_processes)
            if problem == "tsp_construct":
                from prob import TSPCONST
                return TSPCONST(problem_size=50, n_instance=8, timeout=eval_timeout_s, n_processes=n_processes)
            if problem == "cvrp_construct":
                from prob import CVRPCONST
                return CVRPCONST(n_customers=50, capacity=40, n_instance=16, timeout=eval_timeout_s, n_processes=n_processes)
            raise ValueError(f"unknown problem: {problem}")


        def apply_arm_context(task, problem: str, arm: str, context_file: str) -> None:
            context = ""
            if arm == "api_only":
                context = api_context(problem)
            elif context_file:
                context = Path(context_file).read_text(encoding="utf-8").strip()
            if context:
                task.task_description = (
                    task.task_description
                    + "\n\nAdditional reference material. Treat it as constraints, not as text to explain.\n"
                    + "BEGIN CONTEXT\n"
                    + context
                    + "\nEND CONTEXT"
                )


        def main() -> None:
            parser = argparse.ArgumentParser()
            parser.add_argument("--official-root", required=True)
            parser.add_argument("--problem", required=True, choices=["bp_online", "tsp_construct", "cvrp_construct"])
            parser.add_argument("--arm", required=True, choices=["pure_eoh", "api_only", "context_file"])
            parser.add_argument("--context-file", default="")
            parser.add_argument("--output-dir", required=True)
            parser.add_argument("--pop-size", type=int, default=2)
            parser.add_argument("--generations", type=int, default=1)
            parser.add_argument("--n-processes", type=int, default=1)
            parser.add_argument("--eval-timeout-s", type=int, default=40)
            parser.add_argument("--llm-timeout-s", type=int, default=180)
            parser.add_argument("--operators", default="i1")
            parser.add_argument("--use-official-seed", action="store_true")
            parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
            parser.add_argument("--api-endpoint-env", default="DEEPSEEK_API_ENDPOINT")
            parser.add_argument("--model-env", default="DEEPSEEK_MODEL")
            parser.add_argument("--llm-model", default="")
            parser.add_argument("--seed-codes", default="")
            args = parser.parse_args()

            official_root = Path(args.official_root).resolve()
            sys.path.insert(0, str(official_root / "eoh" / "src"))
            from eoh import EoH, LLMConfig

            api_key = os.environ.get(args.api_key_env, "")
            endpoint = os.environ.get(args.api_endpoint_env, "").strip()
            model = args.llm_model or os.environ.get(args.model_env, "")
            if not api_key:
                raise RuntimeError(f"Missing API key env: {args.api_key_env}")
            if not endpoint:
                raise RuntimeError(f"Missing API endpoint env: {args.api_endpoint_env}")
            if not model:
                raise RuntimeError(f"Missing model env: {args.model_env}")

            task = load_problem(args.problem, official_root, args.eval_timeout_s, args.n_processes)
            apply_arm_context(task, args.problem, args.arm, args.context_file)
            operators = [item.strip() for item in args.operators.split(",") if item.strip()]
            install_api_url_patch()
            llm = LLMConfig(api_endpoint=endpoint, api_key=api_key, model=model, timeout=args.llm_timeout_s)
            seed_path = official_root / "examples" / args.problem / "results" / "pops" / "population_generation_0.json"
            eoh = EoH(
                llm=llm,
                problem=task,
                pop_size=args.pop_size,
                n_pop=args.generations,
                operators=operators,
                output_dir=args.output_dir,
                n_processes=args.n_processes,
                use_seed=args.use_official_seed,
                seed_path=str(seed_path),
            )
            # Seed codes injection: replace part of init population with elite codes
            if args.seed_codes and Path(args.seed_codes).exists():
                try:
                    seed_data = json.loads(Path(args.seed_codes).read_text())
                    if seed_data and hasattr(eoh, '_seed_elite_codes'):
                        eoh._seed_elite_codes(seed_data)
                except Exception:
                    pass
            eoh.run()


        if __name__ == "__main__":
            main()
        '''
    ).strip()


def run_official_eoh(args: argparse.Namespace) -> dict[str, Any]:
    official_root = Path(args.official_root).resolve()
    python_exe = Path(args.python)
    output_root = Path(args.output_dir).resolve()
    run_dir = output_root / args.problem / args.arm / f"run_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    runner_path = run_dir / "_run_official_eoh.py"
    runner_path.write_text(_runner_script(), encoding="utf-8")
    context_file = args.context_file
    rag_trace: dict[str, Any] | None = None
    endpoint_present = bool(normalize_api_endpoint(os.environ.get(args.api_endpoint_env, "")))
    model_present = bool(args.llm_model or os.environ.get(args.model_env, ""))
    api_key_present = bool(os.environ.get(args.api_key_env, ""))
    payload: dict[str, Any] = {
        "problem": args.problem,
        "arm": args.arm,
        "official_root": str(official_root),
        "python_exe": str(python_exe),
        "run_dir": str(run_dir),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pop_size": args.pop_size,
        "generations": args.generations,
        "operators": args.operators,
        "use_official_seed": args.use_official_seed,
        "api_key_present": api_key_present,
        "api_endpoint_present": endpoint_present,
        "model_present": model_present,
        "return_code": None,
        "runtime_seconds": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "rag_trace": None,
    }
    if args.arm in {"literature_rag", "history_rag", "mixed_rag"}:
        selected_ids = [sid.strip() for sid in args.selected_card_ids.split(",") if sid.strip()] if args.selected_card_ids else None
        candidate_source = getattr(args, "candidate_card_source", "selected_card_ids" if selected_ids else "none")
        population_features: set[str] | None = None
        if args.prev_run_dir:
            prev_pop_dir = Path(args.prev_run_dir) / "results" / "pops"
            if not prev_pop_dir.exists():
                # Official EoH nests output: <problem>/<arm>/run_<ts>/results/pops/
                candidates = sorted(Path(args.prev_run_dir).rglob("results/pops"))
                if candidates:
                    prev_pop_dir = candidates[-1]
            prev_pops = sorted(prev_pop_dir.glob("population_generation_*.json"), key=_natural_generation) if prev_pop_dir.exists() else []
            if prev_pops:
                prev_population = _load_json(prev_pops[-1])
                if isinstance(prev_population, list):
                    population_features = load_population_features(prev_population, top_fraction=args.rag_top_fraction) or None
        outcome_summaries: dict[str, object] | None = None
        if getattr(args, "outcome_file", ""):
            outcome_path = Path(args.outcome_file)
            if not outcome_path.exists():
                rag_trace = {
                    "rag_candidate_card_ids": selected_ids or [],
                    "rag_candidate_card_source": candidate_source,
                    "rag_outcome_file": str(outcome_path),
                    "rag_outcome_file_exists": False,
                }
                payload["rag_trace"] = rag_trace
                payload["failure_reason"] = "outcome_file_not_found"
                _write_outputs(output_root, payload)
                return payload
            outcome_summaries = summarize_all_cards(load_outcomes(outcome_path)) or None
        candidate_kwargs: dict[str, list[str] | None] = {
            "candidate_card_ids": selected_ids if candidate_source == "candidate_card_ids" else None,
            "selected_card_ids": selected_ids if candidate_source == "selected_card_ids" else None,
            "cards": selected_ids if candidate_source == "cards" else None,
        }
        context, rag_trace = build_official_rag_context(
            Path.cwd().resolve(),
            args.problem,
            args.arm,
            args.rag_top_k,
            args.rag_max_chars,
            args.rag_query or None,
            outcome_summaries=outcome_summaries,
            population_features=population_features,
            rerank_mode=args.rag_rerank,
            rerank_temperature=args.rag_rerank_temperature,
            **candidate_kwargs,
        )
        context_path = run_dir / "rag_context.txt"
        context_path.write_text(context, encoding="utf-8")
        context_file = str(context_path)
        rag_trace["rag_context_path"] = str(context_path)
        rag_trace["rag_prev_run_dir"] = args.prev_run_dir or ""
        rag_trace["rag_outcome_file"] = args.outcome_file or ""
        rag_trace["rag_outcome_file_exists"] = True if args.outcome_file else None
        rag_trace["rag_population_feature_count"] = len(population_features) if population_features else 0
    payload["rag_trace"] = rag_trace
    if not api_key_present:
        payload["failure_reason"] = f"missing_env_{args.api_key_env}"
        _write_outputs(output_root, payload)
        return payload
    if not endpoint_present:
        payload["failure_reason"] = f"missing_env_{args.api_endpoint_env}"
        _write_outputs(output_root, payload)
        return payload
    if not model_present:
        payload["failure_reason"] = f"missing_env_{args.model_env}"
        _write_outputs(output_root, payload)
        return payload

    cmd = [
        str(python_exe),
        str(runner_path),
        "--official-root",
        str(official_root),
        "--problem",
        args.problem,
        "--arm",
        "context_file" if args.arm in {"literature_rag", "history_rag", "mixed_rag"} else args.arm,
        "--output-dir",
        str(run_dir),
        "--pop-size",
        str(args.pop_size),
        "--generations",
        str(args.generations),
        "--n-processes",
        str(args.n_processes),
        "--eval-timeout-s",
        str(args.eval_timeout_s),
        "--llm-timeout-s",
        str(args.llm_timeout_s),
        "--operators",
        args.operators,
        "--api-key-env",
        args.api_key_env,
        "--api-endpoint-env",
        args.api_endpoint_env,
        "--model-env",
        args.model_env,
    ]
    if args.llm_model:
        cmd.extend(["--llm-model", args.llm_model])
    if context_file:
        cmd.extend(["--context-file", context_file])
    if args.use_official_seed:
        cmd.append("--use-official-seed")
    if args.seed_codes:
        cmd.extend(["--seed-codes", args.seed_codes])

    started = time.time()
    return_code: int | None = None
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.run_timeout_s,
            check=False,
        )
        return_code = proc.returncode
        payload["return_code"] = return_code
        payload["stdout_tail"] = redact_log_tail(_tail_text(proc.stdout))
        payload["stderr_tail"] = redact_log_tail(_tail_text(proc.stderr))
    except subprocess.TimeoutExpired as exc:
        payload["return_code"] = None
        payload["failure_reason"] = "timeout"
        payload["stdout_tail"] = redact_log_tail(_tail_text(exc.stdout))
        payload["stderr_tail"] = redact_log_tail(_tail_text(exc.stderr))
    payload["runtime_seconds"] = round(time.time() - started, 3)

    summary = summarize_run(run_dir)
    payload["run_summary"] = summary
    if payload.get("failure_reason") is None and return_code not in (None, 0):
        payload["failure_reason"] = f"return_code_{return_code}"
    if payload.get("failure_reason") is None and not summary.get("ok"):
        payload["failure_reason"] = summary.get("failure_reason")
    _write_outputs(output_root, payload)
    return payload


def _write_outputs(output_root: Path, payload: dict[str, Any]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "official_eoh_run_summary.json"
    md_path = output_root / "official_eoh_run_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    _write_markdown(md_path, payload)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload.get("run_summary") or {}
    lines = [
        "# 官方 EoH LLM Evolution Smoke",
        "",
        "本文记录官方 EoH benchmark 的最小 LLM evolution smoke。API key 不写入报告。",
        "",
        "## 配置",
        "",
        f"- problem: `{payload.get('problem')}`",
        f"- arm: `{payload.get('arm')}`",
        f"- pop_size: `{payload.get('pop_size')}`",
        f"- generations: `{payload.get('generations')}`",
        f"- operators: `{payload.get('operators')}`",
        f"- use_official_seed: `{payload.get('use_official_seed')}`",
        f"- run_dir: `{payload.get('run_dir')}`",
        f"- api_key_present: `{payload.get('api_key_present')}`",
        f"- api_endpoint_present: `{payload.get('api_endpoint_present')}`",
        f"- model_present: `{payload.get('model_present')}`",
        "",
        "## 结果",
        "",
        f"- return_code: `{payload.get('return_code')}`",
        f"- failure_reason: `{payload.get('failure_reason') or '-'}`",
        f"- runtime_seconds: `{payload.get('runtime_seconds')}`",
        f"- latest_generation: `{summary.get('latest_generation')}`",
        f"- population_size: `{summary.get('population_size')}`",
        f"- valid_candidates: `{summary.get('valid_candidates')}`",
        f"- best_objective: `{summary.get('best_objective')}`",
        "",
        "## 最优代码",
        "",
        "```python",
        (summary.get("best_code") or "").strip(),
        "```",
        "",
        "## 最优算法描述",
        "",
        str(summary.get("best_algorithm") or "").strip(),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-root", default=DEFAULT_OFFICIAL_ROOT)
    parser.add_argument("--python", default=DEFAULT_OFFICIAL_PYTHON)
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/official_eoh_runs")
    parser.add_argument("--problem", choices=sorted(PROBLEMS), default="bp_online")
    parser.add_argument(
        "--arm",
        choices=["pure_eoh", "api_only", "literature_rag", "history_rag", "mixed_rag", "context_file"],
        default="pure_eoh",
    )
    parser.add_argument("--context-file", default="")
    parser.add_argument("--rag-top-k", type=int, default=2)
    parser.add_argument("--rag-max-chars", type=int, default=1800)
    parser.add_argument("--rag-query", default="")
    parser.add_argument("--selected-card-ids", default="")
    parser.add_argument(
        "--candidate-card-source",
        choices=["candidate_card_ids", "selected_card_ids", "cards", "none"],
        default="selected_card_ids",
        help="Source field for the legacy --selected-card-ids allowlist",
    )
    parser.add_argument("--prev-run-dir", default="", help="Previous run dir to extract population features for rerank")
    parser.add_argument("--outcome-file", default="", help="Card outcome JSONL file used for outcome-aware rerank")
    parser.add_argument("--rag-rerank", default="feature_outcome", choices=["keyword", "feature_outcome", "llm"], help="Rerank mode")
    parser.add_argument("--rag-rerank-temperature", type=float, default=0.0, help="LLM rerank temperature (0=deterministic)")
    parser.add_argument("--rag-top-fraction", type=float, default=1.0, help="Population top fraction for feature extraction")
    parser.add_argument("--seed-codes", default="", help="JSON file with seed codes for population init")
    parser.add_argument("--pop-size", type=int, default=2)
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--operators", default="i1")
    parser.add_argument("--n-processes", type=int, default=1)
    parser.add_argument("--eval-timeout-s", type=int, default=40)
    parser.add_argument("--llm-timeout-s", type=int, default=180)
    parser.add_argument("--run-timeout-s", type=int, default=900)
    parser.add_argument("--use-official-seed", action="store_true")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--api-endpoint-env", default="DEEPSEEK_API_ENDPOINT")
    parser.add_argument("--model-env", default="DEEPSEEK_MODEL")
    parser.add_argument("--llm-model", default="")
    payload = run_official_eoh(parser.parse_args())
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    if payload.get("failure_reason") == "outcome_file_not_found":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
