"""
模块：eoh_single_runner（EoH 单次进化实验运行器）
功能：以子进程方式启动一次官方 EoH 启发式进化实验，采集结果并生成 JSON / Markdown 报告。
职责：
    - 组装并写出一份自包含的子进程运行脚本（内含 LLM 调用改写、问题加载、上下文注入、种群初始化）。
    - 按实验分支（arm）决定是否为提示词注入额外参考上下文（纯 EoH / API 规则 / RAG 检索上下文）。
    - 检查必需的 API 环境变量，拼装命令行并执行子进程，超时与失败均有兜底记录。
    - 解析最新一代种群，选出目标值最优的候选，汇总为运行摘要。
    - 将日志中的接口地址与密钥做脱敏后落盘。
接口：
    - normalize_api_endpoint(endpoint) -> str：从 URL 中提取纯主机名。
    - redact_log_tail(text) -> str：对日志尾部做接口/密钥脱敏。
    - summarize_run(run_dir) -> dict：解析一次运行目录，产出结果摘要。
    - run_official_eoh(args) -> dict：主流程，执行一次实验并返回结果 payload。
    - main() -> None：命令行入口，解析参数并打印结果 payload。
输入：
    - 命令行参数（问题类型、实验分支、种群规模、代数、RAG 参数、超时等）。
    - 环境变量：EOH_OFFICIAL_ROOT、EOH_OFFICIAL_PYTHON、以及 API key/endpoint/model 三组变量。
    - 依赖官方 EoH 代码根目录及其 examples 下的各问题定义。
输出：
    - 输出目录下的 official_eoh_run_summary.json 与 official_eoh_run_summary.md。
    - 每次运行独立目录下的种群、样本、RAG 上下文等中间产物。
示例：
    python -m eoh_rag.experiments.eoh_single_runner \
        --official-root /path/to/eoh --python /path/to/python \
        --problem bp_online --arm pure_eoh --pop-size 2 --generations 1
"""

from __future__ import annotations

import argparse
import ast
import hashlib
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
from eoh_rag.experiments.problem_registry import RUNNABLE_PROBLEMS
from eoh_rag.rag.card_outcomes import load_outcomes, summarize_all_cards
from eoh_rag.rag.features import load_population_features


DEFAULT_OFFICIAL_ROOT = os.environ.get("EOH_OFFICIAL_ROOT", "") or str(Path(__file__).resolve().parents[2] / "official_eoh")
DEFAULT_OFFICIAL_PYTHON = os.environ.get("EOH_OFFICIAL_PYTHON", "")


def normalize_api_endpoint(endpoint: str) -> str:
    """从接口地址中提取纯主机名，去掉协议前缀和路径部分。

    入参 endpoint 可为完整 URL；返回仅保留 host（如 "api.example.com"），空值返回空串。
    """
    value = (endpoint or "").strip()
    value = re.sub(r"^https?://", "", value)  # 去掉 http:// 或 https:// 前缀
    value = value.split("/", 1)[0]  # 仅保留第一个斜杠前的 host 段
    return value.strip()


def _natural_generation(path: Path) -> int:
    """从种群文件名中解析代数编号。

    文件名形如 population_generation_3.json 时返回 3；不匹配则返回 -1（用于排序兜底）。
    """
    match = re.search(r"population_generation_(\d+)\.json$", path.name)
    return int(match.group(1)) if match else -1


def _load_json(path: Path) -> Any:
    """以 UTF-8 读取并解析一个 JSON 文件，返回其反序列化结果。"""
    return json.loads(path.read_text(encoding="utf-8"))


def redact_log_tail(text: str) -> str:
    """对日志文本做脱敏，隐藏接口地址与密钥后再落盘。

    分别把 URL、endpoint=... 值、以及 Bearer 令牌替换为占位符。
    """
    redacted = re.sub(r"https?://\S+", "[api-endpoint-redacted]", text or "")  # 屏蔽完整 URL
    redacted = re.sub(r"(endpoint=)[^,\s)]+", r"\1[api-endpoint-redacted]", redacted)  # 屏蔽 endpoint= 后的值
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[api-key-redacted]", redacted)  # 屏蔽 Bearer 令牌
    return redacted


def _tail_text(value: str | bytes | None, max_lines: int = 80) -> str:
    """返回文本的末尾若干行，用于截取子进程日志尾部。

    支持传入字节串（按 UTF-8 容错解码）；默认最多保留最后 80 行。
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", "replace")
    else:
        text = value
    return "\n".join(text.splitlines()[-max_lines:])


def summarize_run(run_dir: Path) -> dict[str, Any]:
    """解析一次运行目录，汇总最新一代种群并选出最优候选。

    在 results/pops 下按代数找到最新种群文件，筛出带有效目标值（objective）的候选，
    取目标值最小者为最优（各支持问题均为最小化）。
    返回包含是否成功、失败原因、最新代数、种群规模、有效候选数及最优代码/描述/目标值的摘要字典。
    """
    pop_dir = run_dir / "results" / "pops"
    # 按解析出的代数编号升序排列历代种群文件
    populations = sorted(pop_dir.glob("population_generation_*.json"), key=_natural_generation)
    samples = sorted((run_dir / "results" / "samples").glob("samples_*.json"))
    best_sample = run_dir / "results" / "samples" / "samples_best.json"
    held_out_report_path = run_dir / "held_out_report.json"
    held_out_report: dict[str, Any] = {}
    if held_out_report_path.is_file():
        try:
            loaded_report = _load_json(held_out_report_path)
            if isinstance(loaded_report, dict):
                held_out_report = loaded_report
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # held-out 报告属于补充指标；文件损坏时保留主摘要，并显式标记为不可用。
            held_out_report = {}
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
        "held_out_report": held_out_report,
        "held_out_report_path": str(held_out_report_path) if held_out_report_path.is_file() else None,
        "population_diversity": [],
    }
    if not populations:
        # 没有任何种群文件，说明进化未产出结果
        summary["failure_reason"] = "missing_population"
        return summary

    # AST 节点类型序列比原始文本更稳健，可忽略变量名与格式差异。
    for population_path in populations:
        items = _load_json(population_path)
        if not isinstance(items, list):
            continue
        hashes: set[str] = set()
        parse_failures = 0
        parseable = 0
        for item in items:
            code = item.get("code") if isinstance(item, dict) else None
            if not isinstance(code, str) or not code.strip():
                continue
            try:
                tree = ast.parse(code)
            except SyntaxError:
                parse_failures += 1
                continue
            parseable += 1
            signature = ",".join(type(node).__name__ for node in ast.walk(tree))
            hashes.add(hashlib.sha256(signature.encode("utf-8")).hexdigest())
        summary["population_diversity"].append({
            "generation": _natural_generation(population_path),
            "population_size": len(items),
            "unique_ast_count": len(hashes),
            "unique_ast_ratio": round(len(hashes) / parseable, 6) if parseable else 0.0,
            "ast_parse_failure_count": parse_failures,
        })

    latest = populations[-1]  # 取最后一代作为结果来源
    population = _load_json(latest)
    if not isinstance(population, list):
        summary["failure_reason"] = "population_not_list"
        return summary
    # 只保留目标值非空的候选，视为有效个体
    valid = [item for item in population if isinstance(item, dict) and item.get("objective") is not None]
    best = min(valid, key=lambda item: item["objective"]) if valid else None  # 目标值最小者最优
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
    """按问题类型返回一段接口约束说明（API RULES），注入到提示词中约束生成代码。

    覆盖 bp_online、tsp_construct、cvrp_construct 三类问题，各自说明需实现的函数及返回值约定；
    未知问题抛出 ValueError。
    """
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
    """返回一段自包含的子进程运行脚本源码（字符串）。

    该脚本会被写入运行目录后由官方 EoH 使用的 Python 解释器独立执行，内部负责：
    补丁化 LLM 接口调用（统一请求格式与重试）、构造接口地址、按问题注入 API 约束或参考上下文、
    加载对应问题并启动一次进化。此处仅返回脚本文本，不在当前进程内执行。
    """
    return textwrap.dedent(
        r'''
        from __future__ import annotations

        import argparse
        import json
        import logging
        import os
        import random
        import re
        import sys
        import time
        import urllib.request
        import numpy as np
        from pathlib import Path

        logger = logging.getLogger(__name__)


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
            if problem == "tsp_search_controller":
                return (
                    "API RULES: implement build_search_plan(problem_size, total_budget). Return only a list of "
                    "(primitive, budget, minimum_relative_gain) tuples using the documented whitelist and budget."
                )
            raise ValueError(f"unknown problem: {problem}")


        def load_problem(problem: str, official_root: Path, eval_timeout_s: int, n_processes: int,
                         broad_training: bool = False, n_train: int = 128, held_out_set: list | None = None,
                         controller_budget_policy: str = "strict"):
            sys.path.insert(0, str(official_root / "eoh" / "src"))
            example_root = official_root / "examples" / problem
            sys.path.insert(0, str(example_root))
            if problem == "bp_online":
                if broad_training:
                    from prob import BPONLINEBroad
                    return BPONLINEBroad(capacity=100, timeout=eval_timeout_s, n_processes=n_processes,
                                         n_train=n_train, held_out_set=held_out_set)
                from prob import BPONLINE
                return BPONLINE(capacity=100, timeout=eval_timeout_s, n_processes=n_processes)
            if problem == "tsp_construct":
                if broad_training:
                    from prob_broad import TSPCONSTBroad
                    return TSPCONSTBroad(problem_size=50, timeout=eval_timeout_s, n_processes=n_processes,
                                         n_train=n_train, held_out_set=held_out_set)
                from prob import TSPCONST
                return TSPCONST(problem_size=50, n_instance=8, timeout=eval_timeout_s, n_processes=n_processes)
            if problem == "cvrp_construct":
                if broad_training:
                    from prob_broad import CVRPCONSTBroad
                    return CVRPCONSTBroad(n_customers=50, capacity=40, timeout=eval_timeout_s, n_processes=n_processes,
                                          n_train=n_train, held_out_set=held_out_set)
                from prob import CVRPCONST
                return CVRPCONST(n_customers=50, capacity=40, n_instance=16, timeout=eval_timeout_s, n_processes=n_processes)
            if problem == "tsp_search_controller":
                from prob import TSPSEARCHCONTROLLER
                return TSPSEARCHCONTROLLER(
                    timeout=eval_timeout_s,
                    n_processes=n_processes,
                    budget_policy=controller_budget_policy,
                )
            raise ValueError(f"unknown problem: {problem}")


        def persist_best_held_out_report(task, output_dir: Path) -> None:
            """复算最终种群的最佳候选，并把 held-out 指标原子写入运行目录。"""

            if not hasattr(task, "held_out_report"):
                return

            def generation_number(path: Path) -> int:
                match = re.search(r"population_generation_(\d+)\.json$", path.name)
                return int(match.group(1)) if match else -1

            population_paths = sorted(
                (output_dir / "results" / "pops").glob("population_generation_*.json"),
                key=generation_number,
            )
            if not population_paths:
                logger.warning("No final population found; held-out report was not generated")
                return

            try:
                population = json.loads(population_paths[-1].read_text(encoding="utf-8"))
                valid_candidates = [
                    item
                    for item in population
                    if isinstance(item, dict)
                    and item.get("objective") is not None
                    and item.get("code")
                ]
                best_candidate = min(valid_candidates, key=lambda item: item["objective"])
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning("Cannot select the best candidate for held-out reporting: %s", exc)
                return

            # 常规评估在隔离进程中执行，对 task 字段的修改不会回传。这里仅对已经通过
            # 评估的最佳候选复算一次，确保报告对应最终选择，而不是并发结束顺序。
            # 演化阶段只计算训练适应度；此处显式开启 held-out，并且只复算最终最佳候选一次。
            task.report_held_out = True
            try:
                if task.evaluate(best_candidate["code"]) is None:
                    logger.warning("Best candidate could not be re-evaluated for held-out reporting")
                    return
            finally:
                task.report_held_out = False

            report = getattr(task, "held_out_report", None)
            if not isinstance(report, dict):
                logger.warning("Held-out report has an unexpected type: %s", type(report).__name__)
                return

            report_path = output_dir / "held_out_report.json"
            temporary_path = report_path.with_suffix(".json.tmp")
            temporary_path.write_text(
                json.dumps(report, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary_path, report_path)


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
            parser.add_argument(
                "--problem",
                required=True,
                choices=["bp_online", "tsp_construct", "cvrp_construct", "tsp_search_controller"],
            )
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
            parser.add_argument("--seed", type=int, default=2024)
            parser.add_argument("--provider", choices=["opencode-go", "deepseek"], default="opencode-go")
            parser.add_argument("--temperature-schedule", choices=["fixed", "linear", "step-down"], default="fixed")
            parser.add_argument("--controller-budget-policy", choices=["strict", "clip"], default="strict")
            parser.add_argument("--seed-codes", default="")
            parser.add_argument("--adaptive-stop", action="store_true")
            parser.add_argument("--stop-window", type=int, default=5)
            parser.add_argument("--stop-min-gap", type=float, default=0.0)
            parser.add_argument("--broad-training", action="store_true", help="启用广训练池(128 Weibull 实例)+ held-out 报告(opt-in)")
            parser.add_argument("--n-train", type=int, default=128, help="广训练池实例数(仅 broad-training 有效)")
            parser.add_argument("--held-out-set", default="", help="held-out pkl 路径 JSON 数组,如 '[path1,path2]'")
            args = parser.parse_args()

            # 同一配对共享本地随机 seed；远端 LLM 文本不承诺逐字一致。
            random.seed(args.seed)
            np.random.seed(args.seed)

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

            # 解析 held_out_set JSON 数组
            held_out_set = json.loads(args.held_out_set) if args.held_out_set else None
            task = load_problem(args.problem, official_root, args.eval_timeout_s, args.n_processes,
                                broad_training=args.broad_training, n_train=args.n_train,
                                held_out_set=held_out_set,
                                controller_budget_policy=args.controller_budget_policy)
            apply_arm_context(task, args.problem, args.arm, args.context_file)
            operators = [item.strip() for item in args.operators.split(",") if item.strip()]
            install_api_url_patch()
            llm = LLMConfig(api_endpoint=endpoint, api_key=api_key, model=model, timeout=args.llm_timeout_s)
            # 种子来源:精英代码优先,否则用官方初始种群。精英代码规整成引擎
            # evaluate_seeds 认可的 {algorithm, code} 列表,经 use_seed/seed_path 注入为初始种群。
            use_seed = args.use_official_seed
            example_root = official_root / "examples" / args.problem
            curated_seed_path = example_root / "seeds" / "controller_seeds.json"
            legacy_seed_path = example_root / "results" / "pops" / "population_generation_0.json"
            # 控制器种子是冻结输入，不应放进被忽略的 results 目录。旧问题继续读取
            # 官方 population_generation_0.json，保持既有实验完全兼容。
            seed_path = curated_seed_path if curated_seed_path.is_file() else legacy_seed_path
            if args.seed_codes and Path(args.seed_codes).exists():
                try:
                    raw_seeds = json.loads(Path(args.seed_codes).read_text(encoding="utf-8"))
                    seeds = [
                        {"algorithm": s.get("algorithm") or "elite seed", "code": s["code"]}
                        for s in raw_seeds
                        if isinstance(s, dict) and s.get("code")
                    ]
                    if seeds:
                        elite_path = Path(args.output_dir) / "_elite_seeds.json"
                        elite_path.write_text(json.dumps(seeds, ensure_ascii=False), encoding="utf-8")
                        use_seed = True
                        seed_path = elite_path
                        logger.info("注入 %d 份精英代码作为初始种群", len(seeds))
                except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    logger.warning("精英种子加载失败,回退默认初始化: %s", exc)
            eoh = EoH(
                llm=llm,
                problem=task,
                pop_size=args.pop_size,
                n_pop=args.generations,
                operators=operators,
                output_dir=args.output_dir,
                n_processes=args.n_processes,
                use_seed=use_seed,
                seed_path=str(seed_path),
                adaptive_stop=args.adaptive_stop,
                stop_window=args.stop_window,
                stop_min_gap=args.stop_min_gap,
            )
            eoh.run()
            persist_best_held_out_report(task, Path(args.output_dir))


        if __name__ == "__main__":
            main()
        '''
    ).strip()


def run_official_eoh(args: argparse.Namespace) -> dict[str, Any]:
    """执行一次完整的 EoH 进化实验并返回结果 payload（同时落盘 JSON/Markdown）。

    主要步骤：
        1. 依据问题、实验分支和时间戳建立独立运行目录，并写出子进程运行脚本。
        2. 若分支为检索类（literature_rag / history_rag / mixed_rag），构造参考上下文并写入
           rag_context.txt，同时记录检索轨迹（rag_trace）。
        3. 校验 API key / endpoint / model 三项环境变量，任一缺失则提前返回带 failure_reason 的结果。
        4. 拼装命令行、以受控超时运行子进程，采集并脱敏其 stdout/stderr 尾部。
        5. 解析运行摘要，综合返回码与摘要结果判定失败原因。

    关键入参（取自 argparse）：official_root/python 指定官方代码根与解释器，problem/arm 决定问题与分支，
    pop_size/generations 控制进化规模，rag_* 系列控制检索行为，*_env 指定环境变量名，run_timeout_s 为总超时。
    返回：包含运行配置、环境就绪标志、返回码、耗时、日志尾部、检索轨迹与运行摘要的 payload 字典。
    """
    official_root = Path(args.official_root).resolve()
    python_exe = Path(args.python)
    output_root = Path(args.output_dir).resolve()
    # 运行目录按 <问题>/<分支>/run_<时间戳> 分层，避免多次运行相互覆盖
    # batch_runner 已为每个 RunSpec 分配隔离目录；精确模式避免再嵌套 problem/arm/time，
    # 使 resume、run index 与 summary 契约指向同一位置。
    run_dir = output_root if getattr(args, "exact_output_dir", False) else output_root / args.problem / args.arm / f"run_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    runner_path = run_dir / "_run_official_eoh.py"
    runner_path.write_text(_runner_script(), encoding="utf-8")  # 将子进程脚本写入运行目录
    context_file = args.context_file
    rag_trace: dict[str, Any] | None = None
    # 预先探测三项 API 环境是否就绪（endpoint 需能解析出 host）
    endpoint_present = bool(normalize_api_endpoint(os.environ.get(args.api_endpoint_env, "")))
    # 实际解析出的模型名(非密钥,可安全落盘):写进 summary 以便追溯每个 run 究竟用了哪个模型。
    resolved_model = args.llm_model or os.environ.get(args.model_env, "")
    model_present = bool(resolved_model)
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
        "seed": getattr(args, "seed", 2024),
        "provider": getattr(args, "provider", "opencode-go"),
        "temperature_schedule": getattr(args, "temperature_schedule", "fixed"),
        "controller_budget_policy": getattr(args, "controller_budget_policy", "strict"),
        "adaptive_stop": args.adaptive_stop,
        "stop_window": args.stop_window,
        "stop_min_gap": args.stop_min_gap,
        "broad_training": args.broad_training,
        "n_train": args.n_train,
        "held_out_set": args.held_out_set,
        "api_key_present": api_key_present,
        "api_endpoint_present": endpoint_present,
        "model_present": model_present,
        "model": resolved_model,
        "return_code": None,
        "runtime_seconds": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "rag_trace": None,
    }
    # 检索类分支：构造并注入参考上下文，同时记录检索轨迹
    if args.arm in {"literature_rag", "history_rag", "mixed_rag"}:
        selected_ids = [sid.strip() for sid in args.selected_card_ids.split(",") if sid.strip()] if args.selected_card_ids else None
        candidate_source = getattr(args, "candidate_card_source", "selected_card_ids" if selected_ids else "none")
        population_features: set[str] | None = None
        # 若提供上一轮运行目录，则从其最新种群抽取特征，供检索时做偏好加权
        if args.prev_run_dir:
            prev_pop_dir = Path(args.prev_run_dir) / "results" / "pops"
            if not prev_pop_dir.exists():
                # 官方 EoH 输出为嵌套结构：<problem>/<arm>/run_<ts>/results/pops/，此处向下递归定位
                candidates = sorted(Path(args.prev_run_dir).rglob("results/pops"))
                if candidates:
                    prev_pop_dir = candidates[-1]
            prev_pops = sorted(prev_pop_dir.glob("population_generation_*.json"), key=_natural_generation) if prev_pop_dir.exists() else []
            if prev_pops:
                prev_population = _load_json(prev_pops[-1])
                if isinstance(prev_population, list):
                    population_features = load_population_features(prev_population, top_fraction=args.rag_top_fraction) or None
        outcome_summaries: dict[str, object] | None = None
        # 若指定了历史结果文件，用于把过往卡片的实验结论纳入上下文
        if getattr(args, "outcome_file", ""):
            outcome_path = Path(args.outcome_file)
            if not outcome_path.exists():
                # 结果文件缺失：直接记录轨迹并提前返回失败
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
        # 依据候选来源字段，把选定卡片 id 放入对应参数槽（三者互斥）
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
            extra_corpus_paths=tuple(getattr(args, "rag_extra_corpus", []) or []),
            **candidate_kwargs,
        )
        context_path = run_dir / "rag_context.txt"
        context_path.write_text(context, encoding="utf-8")  # 落盘检索上下文供子进程读取与复核
        context_file = str(context_path)
        # 补全检索轨迹中的路径与来源信息，便于事后审计
        rag_trace["rag_context_path"] = str(context_path)
        rag_trace["rag_prev_run_dir"] = args.prev_run_dir or ""
        rag_trace["rag_outcome_file"] = args.outcome_file or ""
        rag_trace["rag_outcome_file_exists"] = True if args.outcome_file else None
        rag_trace["rag_population_feature_count"] = len(population_features) if population_features else 0
    payload["rag_trace"] = rag_trace
    # 三项环境变量逐一校验，缺失即记录具体缺哪一项并提前返回
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

    # 拼装子进程命令行；检索类分支统一以 context_file 方式传入上下文
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
        "--seed",
        str(getattr(args, "seed", 2024)),
        "--provider",
        getattr(args, "provider", "opencode-go"),
        "--temperature-schedule",
        getattr(args, "temperature_schedule", "fixed"),
        "--controller-budget-policy",
        getattr(args, "controller_budget_policy", "strict"),
    ]
    # 以下均为可选项，仅在对应参数存在时追加
    if args.llm_model:
        cmd.extend(["--llm-model", args.llm_model])
    if args.adaptive_stop:
        cmd.extend([
            "--adaptive-stop",
            "--stop-window", str(args.stop_window),
            "--stop-min-gap", str(args.stop_min_gap),
        ])
    if args.broad_training:
        cmd.extend(["--broad-training", "--n-train", str(args.n_train)])
        if args.held_out_set:
            # CLI 参数已经是 JSON 数组字符串；再次序列化会让内部 runner 得到字符串而不是路径列表。
            cmd.extend(["--held-out-set", args.held_out_set])
    if context_file:
        cmd.extend(["--context-file", context_file])
    if args.use_official_seed:
        cmd.append("--use-official-seed")
    if args.seed_codes:
        cmd.extend(["--seed-codes", args.seed_codes])

    started = time.time()
    return_code: int | None = None
    try:
        # 运行子进程并捕获输出，run_timeout_s 为整体墙钟超时上限
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
        # 日志尾部先截断再脱敏后保存
        payload["stdout_tail"] = redact_log_tail(_tail_text(proc.stdout))
        payload["stderr_tail"] = redact_log_tail(_tail_text(proc.stderr))
    except subprocess.TimeoutExpired as exc:
        # 超时：标记失败原因，并尽量保留已产生的部分日志
        payload["return_code"] = None
        payload["failure_reason"] = "timeout"
        payload["stdout_tail"] = redact_log_tail(_tail_text(exc.stdout))
        payload["stderr_tail"] = redact_log_tail(_tail_text(exc.stderr))
    payload["runtime_seconds"] = round(time.time() - started, 3)

    summary = summarize_run(run_dir)
    payload["run_summary"] = summary
    # 综合判定失败原因：非零返回码优先，其次是运行摘要判定的失败
    if payload.get("failure_reason") is None and return_code not in (None, 0):
        payload["failure_reason"] = f"return_code_{return_code}"
    if payload.get("failure_reason") is None and not summary.get("ok"):
        payload["failure_reason"] = summary.get("failure_reason")
    _write_outputs(output_root, payload)
    return payload


def _write_outputs(output_root: Path, payload: dict[str, Any]) -> None:
    """把运行结果同时写为 JSON 与 Markdown 两份摘要文件到输出根目录。"""
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "official_eoh_run_summary.json"
    md_path = output_root / "official_eoh_run_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    _write_markdown(md_path, payload)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    """将运行结果 payload 渲染为可读的 Markdown 报告并写入 path。

    报告分为配置、结果、最优代码、最优算法描述四部分；不写入任何密钥信息。
    """
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
    """命令行入口：解析全部参数，运行一次实验，并以 JSON 打印结果 payload。

    实验分支（--arm）取值：pure_eoh（纯 EoH）、api_only（仅注入接口约束）、
    literature_rag / history_rag / mixed_rag（三类检索上下文）、context_file（直接读取给定上下文文件）。
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-root", default=DEFAULT_OFFICIAL_ROOT)
    parser.add_argument("--python", default=DEFAULT_OFFICIAL_PYTHON)
    parser.add_argument("--output-dir", default="eoh_rag_workspace/reports/official_eoh_runs")
    parser.add_argument("--problem", choices=sorted(RUNNABLE_PROBLEMS), default="bp_online")
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
    parser.add_argument(
        "--rag-extra-corpus",
        action="append",
        default=[],
        help="Additional experiment-specific CorpusItem JSONL; may be repeated",
    )
    parser.add_argument("--seed-codes", default="", help="JSON file with seed codes for population init")
    parser.add_argument("--pop-size", type=int, default=2)
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--operators", default="i1")
    parser.add_argument("--n-processes", type=int, default=1)
    parser.add_argument("--eval-timeout-s", type=int, default=40)
    parser.add_argument("--llm-timeout-s", type=int, default=180)
    parser.add_argument("--run-timeout-s", type=int, default=900)
    parser.add_argument("--use-official-seed", action="store_true")
    parser.add_argument("--adaptive-stop", action="store_true", help="启用自适应早停:平台时提前结束进化")
    parser.add_argument("--stop-window", type=int, default=5, help="早停观察窗口(代数)")
    parser.add_argument("--stop-min-gap", type=float, default=0.0, help="窗口内 best 相对改进低于此值则停")
    parser.add_argument("--broad-training", action="store_true", help="启用广训练池(128 Weibull 实例)+ held-out 报告(opt-in)")
    parser.add_argument("--n-train", type=int, default=128, help="广训练池实例数")
    parser.add_argument("--held-out-set", default="", help="held-out pkl 路径 JSON 数组")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--api-endpoint-env", default="DEEPSEEK_API_ENDPOINT")
    parser.add_argument("--model-env", default="DEEPSEEK_MODEL")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--provider", choices=["opencode-go", "deepseek"], default="opencode-go")
    parser.add_argument("--temperature-schedule", choices=["fixed", "linear", "step-down"], default="fixed")
    parser.add_argument("--controller-budget-policy", choices=["strict", "clip"], default="strict")
    parser.add_argument("--exact-output-dir", action="store_true")
    payload = run_official_eoh(parser.parse_args())
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    if payload.get("failure_reason") == "outcome_file_not_found":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
