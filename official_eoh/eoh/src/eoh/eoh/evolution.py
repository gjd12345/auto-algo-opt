# Copyright (c) 2026 Fei Liu. MIT License.
# Project: https://github.com/FeiLiu36/EoH
# Citation: Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang, Zhichao Lu,
#           Qingfu Zhang, Evolution of Heuristics: Towards Efficient Automatic Algorithm Design
#           Using Large Language Model, Forty-first International Conference on Machine Learning
#           (ICML), 2024.

import ast
import os
import random
import re
import sys
import signal
import logging
import threading
import warnings
import multiprocessing

import numpy as np

# joblib powers only the legacy generation-batch path (get_algorithm) and
# parallel seed evaluation. The async pipeline in eoh.py does not use it, so the
# dependency is optional — import lazily and fall back to sequential if absent.
try:
    from joblib import Parallel, delayed
except ImportError:  # pragma: no cover
    Parallel = delayed = None

# spawn: safe on all platforms, no background server started at import time.
# forkserver would start a server process at module import, which breaks when
# evolution.py is re-imported inside joblib's loky worker processes.
_MP_CTX = multiprocessing.get_context('spawn')

# Serialises the (rare) global set_start_method call below so concurrent eval
# threads can never race on it. In the async pipeline the start method is set
# once in the main thread, so this branch is normally never taken; the lock only
# matters for the legacy joblib/loky seed path.
_START_METHOD_LOCK = threading.Lock()

logger = logging.getLogger('eoh')


def _is_mutable_numeric_constant(value) -> bool:
    """只选择适合做局部搜索的数值常量，跳过布尔值和常见稳定项。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return abs(float(value)) > 1e-8 and abs(float(value)) != 1.0


def _numeric_neighbors(value) -> list[int | float]:
    """生成保持原数值类型的小邻域，避免整数参数被改成浮点后破坏接口。"""
    if isinstance(value, int):
        neighbors = [value + step for step in (-2, -1, 1, 2)]
        if value > 0:
            neighbors = [candidate for candidate in neighbors if candidate > 0]
        return neighbors
    factors = (0.8, 0.9, 0.95, 1.05, 1.1, 1.2)
    return [float(f"{value * factor:.12g}") for factor in factors]


class _NumericConstantRewriter(ast.NodeTransformer):
    """按 AST 遍历序号替换指定数值常量。"""

    def __init__(self, replacements: dict[int, int | float]):
        self.replacements = replacements
        self.current_index = 0

    def visit_Constant(self, node):
        if not _is_mutable_numeric_constant(node.value):
            return node
        index = self.current_index
        self.current_index += 1
        if index not in self.replacements:
            return node
        return ast.copy_location(ast.Constant(value=self.replacements[index]), node)


def _rewrite_numeric_constants(code: str, replacements: dict[int, int | float]) -> str:
    candidate_tree = ast.parse(code)
    candidate_tree = _NumericConstantRewriter(replacements).visit(candidate_tree)
    ast.fix_missing_locations(candidate_tree)
    return ast.unparse(candidate_tree).strip()


def numeric_constant_mutations(code: str) -> list[tuple[str, str]]:
    """生成一次只改一个数值常量的确定性邻域，并按代码文本去重。"""
    tree = ast.parse(code)
    values = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and _is_mutable_numeric_constant(node.value)
    ]
    mutations = []
    seen = {code.strip()}
    for target_index, value in enumerate(values):
        for replacement in _numeric_neighbors(value):
            candidate_code = _rewrite_numeric_constants(code, {target_index: replacement})
            if candidate_code in seen:
                continue
            seen.add(candidate_code)
            description = f"Numeric neighborhood mutation: {value!r} -> {replacement!r}."
            mutations.append((candidate_code, description))
    return mutations


def numeric_constant_pair_mutations(code: str) -> list[tuple[str, str]]:
    """生成同时改变两个不同数值常量的确定性补偿邻域。"""
    tree = ast.parse(code)
    values = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and _is_mutable_numeric_constant(node.value)
    ]
    mutations = []
    seen = {code.strip()}
    for first_index, first_value in enumerate(values):
        for second_index in range(first_index + 1, len(values)):
            second_value = values[second_index]
            for first_replacement in _numeric_neighbors(first_value):
                for second_replacement in _numeric_neighbors(second_value):
                    replacements = {
                        first_index: first_replacement,
                        second_index: second_replacement,
                    }
                    candidate_code = _rewrite_numeric_constants(code, replacements)
                    if candidate_code in seen:
                        continue
                    seen.add(candidate_code)
                    description = (
                        "Numeric pair mutation: "
                        f"{first_value!r} -> {first_replacement!r}; "
                        f"{second_value!r} -> {second_replacement!r}."
                    )
                    mutations.append((candidate_code, description))
    return mutations


def _eval_worker(queue, problem, code):
    """Subprocess entry point — must be module-level for pickling.

    Calls os.setsid() on Unix to create a new process group, so that any
    child processes spawned here (e.g. a Java/C++ compiler or runner) belong
    to the same group and are killed together on timeout.
    """
    if sys.platform != 'win32':
        os.setsid()
    try:
        queue.put(problem.evaluate(code))
    except Exception:
        queue.put(None)


def _kill_process_tree(p):
    """Hard-stop a timed-out eval process and any children, escalating to SIGKILL.

    On Unix _eval_worker called os.setsid(), so the eval and any compiler/runner
    children share a process group we can signal as a unit. We try SIGTERM first,
    then escalate to SIGKILL, and bound every join so a subprocess that ignores
    SIGTERM can never hang the calling eval thread indefinitely.
    """
    pid = p.pid

    def _signal_group(sig):
        if sys.platform != 'win32' and pid is not None:
            try:
                os.killpg(os.getpgid(pid), sig)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    _signal_group(signal.SIGTERM)
    p.terminate()
    p.join(5)
    if p.is_alive():
        _signal_group(signal.SIGKILL)
        p.kill()
        p.join(5)


def _eval_with_timeout(problem, code, timeout):
    """Run evaluate() in a subprocess and enforce a hard per-eval timeout.

    Module-level so it can be pickled by joblib/loky when called from a
    parallel worker. Returns the fitness value or None on timeout/error.
    """
    # joblib's loky backend registers 'loky' as the global multiprocessing
    # start method inside its worker processes.  spawn.py's get_preparation_data
    # reads this global and embeds it in the child's prep data, so the spawned
    # child calls set_start_method('loky', force=True) — which fails in a fresh
    # interpreter where loky is not registered.  Force 'spawn' before creating
    # the subprocess; each loky worker is an isolated OS process so this only
    # affects the current worker, not the main process or other workers.  The
    # lock makes the (rare) global mutation safe under the threaded eval pool.
    with _START_METHOD_LOCK:
        if multiprocessing.get_start_method(allow_none=False) != 'spawn':
            multiprocessing.set_start_method('spawn', force=True)
    q = _MP_CTX.Queue()
    p = _MP_CTX.Process(target=_eval_worker, args=(q, problem, code))
    p.start()
    p.join(timeout)
    if p.is_alive():
        _kill_process_tree(p)
        return None
    try:
        return q.get_nowait()
    except Exception:
        return None


def _normalize_evaluation_result(result):
    """兼容旧 float 与带结构化反馈的新评价结果。"""
    feedback = None
    raw_objective = result
    if isinstance(result, dict):
        raw_objective = result.get("objective")
        candidate_feedback = result.get("feedback")
        if isinstance(candidate_feedback, dict):
            feedback = candidate_feedback
    if raw_objective is None:
        return None, feedback
    try:
        rounded = float(np.round(raw_objective, 5))
    except (TypeError, ValueError):
        return None, feedback
    if not np.isfinite(rounded):
        return None, feedback
    return rounded, feedback


from ..llm.interface_LLM import InterfaceLLM
from ..problem import _get_entry_name, _detect_template_kind, _extract_import_lines


def parent_selection(pop, m, feedback_policy="legacy"):
    if not pop:
        raise ValueError("Cannot select parents from an empty population.")
    if feedback_policy == "fme_aware":
        # 先保留质量最好的父代，再优先选择不同的行为格，避免源码不同但行为塌缩。
        ranked = sorted(pop, key=lambda item: float(item["objective"]))
        selected = [ranked[0]]
        selected_profiles = {
            (ranked[0].get("other_inf") or {}).get("behavior_profile_hash")
        }
        for candidate in ranked[1:]:
            profile_hash = (candidate.get("other_inf") or {}).get(
                "behavior_profile_hash"
            )
            if profile_hash not in selected_profiles:
                selected.append(candidate)
                selected_profiles.add(profile_hash)
            if len(selected) >= m:
                return selected
        while len(selected) < m:
            selected.append(ranked[min(len(selected), len(ranked) - 1)])
        return selected
    if feedback_policy in {
        "objective_aware",
        "scale_aware",
        "robust_aware",
        "router_aware",
        "confirmation_aware",
        "confirmation_observe_only",
        "confirmation_gate_only",
    }:
        # 评价反馈模式始终保留当前精英；多父代算子再配一个不同个体，兼顾利用与探索。
        ranked = sorted(pop, key=lambda item: float(item["objective"]))
        if m == 1:
            return [ranked[0]]
        selected = [ranked[0]]
        remaining = ranked[1:]
        while len(selected) < m:
            if not remaining:
                selected.append(ranked[0])
                continue
            weights = [1 / (rank + 2) for rank in range(len(remaining))]
            chosen = random.choices(remaining, weights=weights, k=1)[0]
            selected.append(chosen)
            remaining.remove(chosen)
        return selected
    ranks = list(range(len(pop)))
    probs = [1 / (rank + 1 + len(pop)) for rank in ranks]
    return random.choices(pop, weights=probs, k=m)


class Evolution:
    """Prompt building, LLM calls, code extraction, and offspring generation."""

    def __init__(self, config, problem):
        self.task = problem.task_description
        self.template = problem.template_program
        self.func_name = _get_entry_name(problem.template_program)
        self._template_kind = _detect_template_kind(problem.template_program)
        self._template_import_prefix = _extract_import_lines(problem.template_program)

        self.interface_eval = problem
        self.debug = config.debug
        self.n_processes = problem.n_processes
        self.timeout = problem.timeout
        self.n_parents = config.n_parents
        self.feedback_policy = config.feedback_policy
        # 离线算子不调用 LLM；独立游标让同一 run 依次覆盖邻域，锁避免多线程重复领取。
        self._numeric_mutation_cursors = {"n1": 0, "n2": 0}
        self._numeric_mutation_lock = threading.Lock()

        if not self.debug:
            warnings.filterwarnings("ignore")

        # 纯离线算子不应因为缺少 Provider 而无法跨设备运行；混合算子列表仍照常初始化 LLM。
        offline_only = bool(config.operators) and set(config.operators) <= {"n1", "n2"}
        self.llm = None if offline_only else InterfaceLLM(
            config.llm.api_endpoint,
            config.llm.api_key,
            config.llm.model,
            config.llm.use_local,
            config.llm.local_url,
            timeout=config.llm.timeout,
        )

    # ── prompt builders ───────────────────────────────────────────────────────

    def _func_spec(self) -> str:
        if self._template_kind == 'class':
            verb = "implement the following Python class"
        elif self._template_kind == 'multi_function':
            verb = "implement the following Python functions"
        else:
            verb = "implement the following Python function"
        return (
            f"{verb}:\n"
            f"```python\n{self.template.strip()}\n```\n"
            "Do not give additional explanations."
        )

    def _parent_block(self, parents: list) -> str:
        if self.feedback_policy in {
            "objective_aware",
            "scale_aware",
            "robust_aware",
            "fme_aware",
            "router_aware",
            "confirmation_aware",
            "confirmation_observe_only",
            "confirmation_gate_only",
        }:
            return "\n".join(
                f"No.{i+1} dev objective={p['objective']} (lower is better).\n"
                f"{self._structured_feedback_line(p)}"
                f"Algorithm description: {p['algorithm']}\nCode:\n{p['code']}"
                for i, p in enumerate(parents)
            )
        return "\n".join(
            f"No.{i+1} algorithm and the corresponding code are:\n{p['algorithm']}\n{p['code']}"
            for i, p in enumerate(parents)
        )

    def _structured_feedback_line(self, parent: dict) -> str:
        """把分尺度 gap 转成直白反馈；缺少详情时安全回退为空。"""
        if self.feedback_policy not in {
            "scale_aware",
            "robust_aware",
            "fme_aware",
            "router_aware",
            "confirmation_aware",
        }:
            return ""
        feedback = parent.get("other_inf")
        if not isinstance(feedback, dict):
            return "Structured feedback unavailable for this parent.\n"
        if self.feedback_policy == "fme_aware":
            gaps = feedback.get("per_distribution_relative_gap")
            if not isinstance(gaps, dict) or not gaps:
                return "FME behavior feedback unavailable for this parent.\n"
            gap_text = ", ".join(
                f"{name}={float(value):.6f}%"
                for name, value in sorted(gaps.items())
            )
            counterexamples = feedback.get("distinguishing_counterexample_ids") or []
            claim_state = feedback.get("mechanism_claim_state", "proposed")
            return (
                f"Development distribution gaps (lower is better): {gap_text}. "
                f"Worst distribution: {feedback.get('worst_distribution', 'unknown')}. "
                f"Distinguishing counterexamples: {counterexamples}. "
                f"Mechanism claim state: {claim_state}.\n"
            )
        if self.feedback_policy == "router_aware":
            environments = feedback.get("environment_relative_cost_vs_n2")
            counts = feedback.get("expert_selection_counts")
            if not isinstance(environments, dict) or not isinstance(counts, dict):
                return "Router feedback unavailable for this parent.\n"
            environment_text = ", ".join(
                f"{name}={float(value):.6f}"
                for name, value in sorted(environments.items())
            )
            count_text = ", ".join(
                f"{name}={int(value)}"
                for name, value in sorted(counts.items())
            )
            return (
                f"Environment relative cost versus n2 (lower is better): {environment_text}. "
                f"Expert selections: {count_text}. "
                f"Invalid outputs: {int(feedback.get('selector_invalid_outputs', 0))}; "
                f"fallbacks: {int(feedback.get('expert_fallback_count', 0))}.\n"
            )
        scale_gaps = feedback.get("scale_gap_pct")
        if not isinstance(scale_gaps, dict) or not scale_gaps:
            if self.feedback_policy == "confirmation_aware":
                confirm_objective = feedback.get("confirm_objective")
                if confirm_objective is not None:
                    search_confirm_gap = feedback.get("search_confirm_gap")
                    gap_text = (
                        f" Search-confirm difference: {float(search_confirm_gap):.6f}."
                        if search_confirm_gap is not None else ""
                    )
                    line = (
                        f"Independent confirmation objective: {float(confirm_objective):.6f}."
                        f"{gap_text}\n"
                    )
                    search_environments = feedback.get("search_environment_objectives")
                    confirm_environments = feedback.get("confirm_environment_objectives")
                    if isinstance(search_environments, dict) and isinstance(confirm_environments, dict):
                        names = sorted(set(search_environments) & set(confirm_environments))
                        environment_text = ", ".join(
                            f"{name}: search={float(search_environments[name]):.6f}, "
                            f"confirm={float(confirm_environments[name]):.6f}"
                            for name in names
                        )
                        line += f"Environment objectives (lower is better): {environment_text}.\n"
                    return line
            return "Scale feedback unavailable for this parent.\n"
        ordered = sorted(
            scale_gaps.items(),
            key=lambda item: (
                0 if str(item[0]).isdigit() else 1,
                int(item[0]) if str(item[0]).isdigit() else str(item[0]),
            ),
        )
        gap_text = ", ".join(f"{scale} items={float(gap):.6f}%" for scale, gap in ordered)
        worst_scale = feedback.get("worst_scale", "unknown")
        line = f"Scale gaps (lower is better): {gap_text}. Worst scale: {worst_scale} items.\n"
        if self.feedback_policy == "confirmation_aware":
            confirm_gaps = feedback.get("confirm_scale_gap_pct")
            if not isinstance(confirm_gaps, dict) or not confirm_gaps:
                return line + "Independent confirmation feedback unavailable for this parent.\n"
            confirm_text = ", ".join(
                f"{scale} items={float(confirm_gaps.get(scale, 0.0)):.6f}%"
                for scale, _ in ordered
            )
            confirm_objective = feedback.get("confirm_objective", "unknown")
            return (
                line
                + f"Independent confirmation gaps: {confirm_text}. "
                + f"Confirmation objective: {confirm_objective}.\n"
            )
        if self.feedback_policy != "robust_aware":
            return line
        scale_std = feedback.get("scale_std_pct")
        if not isinstance(scale_std, dict) or not scale_std:
            return line + "Fold stability feedback unavailable for this parent.\n"
        std_text = ", ".join(
            f"{scale} items std={float(scale_std.get(scale, 0.0)):.6f}%"
            for scale, _ in ordered
        )
        return line + f"Fold variation (lower is more stable): {std_text}.\n"

    def _operator_request(self, operator: str) -> str:
        """按反馈策略生成算子要求；legacy 文本保持原实现不变。"""

        legacy = {
            "e1": "Please help me create a new algorithm that has a totally different form from the given ones.\n",
            "e2": (
                "Please help me create a new algorithm that has a totally different form from the given ones "
                "but can be motivated from them.\n"
                "Firstly, identify the common backbone idea in the provided algorithms. "
            ),
            "m1": (
                "Please assist me in creating a new algorithm that has a different form but can be a "
                "modified version of the algorithm provided.\n"
            ),
            "m2": (
                "Please identify the main algorithm parameters and assist me in creating a new algorithm "
                "that has different parameter settings.\n"
            ),
        }
        if self.feedback_policy == "legacy":
            return legacy[operator]
        if self.feedback_policy == "scale_aware":
            scale_feedback = {
                "e1": (
                    "Use the per-scale gaps as feedback. Preserve the best backbone, then make one structural "
                    "change aimed at the worst scale without sacrificing the other scales.\n"
                ),
                "e2": (
                    "Use the per-scale gaps as feedback. Combine ideas that reduce the worst-scale gap while "
                    "keeping the stronger scale behavior from the best parent. "
                ),
                "m1": (
                    "Preserve the current best structure and make one purposeful modification aimed at its "
                    "worst scale. Do not trade a large regression on another scale for a small average gain.\n"
                ),
                "m2": (
                    "Change only one or two parameters to reduce the worst-scale gap while keeping the other "
                    "reported scale gaps stable.\n"
                ),
            }
            return scale_feedback[operator]
        if self.feedback_policy == "robust_aware":
            robust_feedback = {
                "e1": (
                    "Use both scale means and fold variation as feedback. Make one structural change that helps "
                    "across repeated folds; ignore tiny gains that are smaller than the reported variation.\n"
                ),
                "e2": (
                    "Combine only ideas whose gains are repeated across folds. Preserve the stable behavior of "
                    "the best parent and avoid a trade that helps one fold but hurts the others. "
                ),
                "m1": (
                    "Make one purposeful modification that reduces a repeated weakness across folds. Prefer "
                    "simple changes with a margin larger than the reported fold variation.\n"
                ),
                "m2": (
                    "Change only one parameter when the direction is supported across folds. Avoid tuning to a "
                    "small aggregate difference that is within the reported fold variation.\n"
                ),
            }
            return robust_feedback[operator]
        if self.feedback_policy == "fme_aware":
            mechanism_feedback = {
                "e1": (
                    "Use the behavior profile and recorded counterexamples to propose one falsifiable mechanism "
                    "hypothesis, then create a structurally different algorithm that should occupy a new behavior cell. "
                    "State the cheapest development-only observation that would refute the hypothesis.\n"
                ),
                "e2": (
                    "Combine only mechanisms that survived their recorded counterexamples. Preserve the stronger "
                    "distribution behavior of each parent and state which new counterexample would distinguish the combination. "
                ),
                "m1": (
                    "Repair the mechanism weakened by the listed counterexample. Change one causal rule, preserve the "
                    "unbroken behavior, and state what result would refute the repair.\n"
                ),
                "m2": (
                    "Alter one or two parameters only when the behavior profile suggests a monotone mechanism. "
                    "State the expected distribution shift and the cheapest observation that would refute it.\n"
                ),
            }
            return mechanism_feedback[operator]
        if self.feedback_policy == "router_aware":
            router_feedback = {
                "e1": (
                    "Use the per-environment relative costs and expert-use counts as feedback. "
                    "Introduce one deterministic feature-based routing rule that can improve the weakest "
                    "environment without reading hidden costs or collapsing all instances to one expert.\n"
                ),
                "e2": (
                    "Combine only routing ideas supported by lower development relative cost. Preserve valid "
                    "feature-only decisions and keep more than one expert reachable. "
                ),
                "m1": (
                    "Preserve the current selector and make one purposeful feature-threshold or interaction "
                    "change aimed at its weakest environment. Do not use environment labels or hidden costs.\n"
                ),
                "m2": (
                    "Change only one or two numeric thresholds in the selector. Keep deterministic behavior, "
                    "valid expert ids, and the feature-only information boundary.\n"
                ),
            }
            return router_feedback[operator]
        if self.feedback_policy == "confirmation_aware":
            confirmation_feedback = {
                "e1": (
                    "Use both search and independent confirmation gaps as feedback. Make one structural change "
                    "expected to improve the search objective without harming confirmation behavior.\n"
                ),
                "e2": (
                    "Combine only ideas supported by both search and independent confirmation feedback. Preserve "
                    "the parent behavior that transfers across the two batches. "
                ),
                "m1": (
                    "Make one purposeful modification aimed at a weakness repeated in both search and independent "
                    "confirmation batches. Avoid tuning to a search-only difference.\n"
                ),
                "m2": (
                    "Change only one parameter when its direction is supported by both search and independent "
                    "confirmation gaps. Avoid a change that merely improves the fixed search batch.\n"
                ),
            }
            return confirmation_feedback[operator]
        feedback = {
            "e1": (
                "Use the dev objectives as feedback. Preserve effective parts of the best parent, "
                "then introduce one clear structural alternative. Do not reset to a generic default.\n"
            ),
            "e2": (
                "Use the dev objectives as feedback. Identify ideas associated with lower objectives, "
                "keep the best backbone, and combine it with one useful difference from another parent. "
            ),
            "m1": (
                "The parent is the current best by dev objective. Preserve its strongest structure and "
                "make one purposeful modification that could lower the objective.\n"
            ),
            "m2": (
                "The parent is the current best by dev objective. Change only one or two parameters; "
                "do not reset its full structure or ordering.\n"
            ),
        }
        return feedback[operator]

    def _single_parent_request(self, parent: dict, operator: str) -> str:
        request = self._operator_request(operator)
        if self.feedback_policy == "legacy":
            return request
        return (
            f"Dev objective: {parent['objective']} (lower is better).\n"
            f"{self._structured_feedback_line(parent)}{request}"
        )

    def _build_prompt(self, operator: str, parents=None) -> str:
        spec = self._func_spec()
        if operator == "i1":
            mechanism_request = (
                "First, state a falsifiable mechanism hypothesis and its cheapest development-only refutation in one sentence. "
                if self.feedback_policy == "fme_aware"
                else "First, describe your new algorithm and main steps in one sentence. "
            )
            return (
                f"{self.task}\n"
                f"{mechanism_request}"
                f"The description must be inside a brace. Next, {spec}"
            )
        if operator == "e1":
            block = self._parent_block(parents)
            return (
                f"{self.task}\n"
                f"I have {len(parents)} existing algorithms with their codes as follows:\n{block}\n"
                f"{self._operator_request(operator)}"
                "First, describe your new algorithm and main steps in one sentence. "
                f"The description must be inside a brace. Next, {spec}"
            )
        if operator == "e2":
            block = self._parent_block(parents)
            return (
                f"{self.task}\n"
                f"I have {len(parents)} existing algorithms with their codes as follows:\n{block}\n"
                f"{self._operator_request(operator)}"
                "Secondly, based on the backbone idea describe your new algorithm in one sentence. "
                f"The description must be inside a brace. Thirdly, {spec}"
            )
        if operator == "m1":
            return (
                f"{self.task}\n"
                f"I have one algorithm with its code as follows.\n"
                f"Algorithm description: {parents['algorithm']}\nCode:\n{parents['code']}\n"
                f"{self._single_parent_request(parents, operator)}"
                "First, describe your new algorithm and main steps in one sentence. "
                f"The description must be inside a brace. Next, {spec}"
            )
        if operator == "m2":
            return (
                f"{self.task}\n"
                f"I have one algorithm with its code as follows.\n"
                f"Algorithm description: {parents['algorithm']}\nCode:\n{parents['code']}\n"
                f"{self._single_parent_request(parents, operator)}"
                "First, describe your new algorithm and main steps in one sentence. "
                f"The description must be inside a brace. Next, {spec}"
            )
        if operator == "m3":
            return (
                f"{self.task}\n"
                f"I have one algorithm with its code as follows.\n"
                f"Algorithm description: {parents['algorithm']}\nCode:\n{parents['code']}\n"
                "Please identify the main components, analyze whether any are overfit to "
                "in-distribution instances, and create a simplified version that improves "
                "generalization to out-of-distribution instances.\n"
                "First, describe your new algorithm and main steps in one sentence. "
                f"The description must be inside a brace. Next, {spec}"
            )
        raise ValueError(f"Unknown operator: {operator}")

    # ── LLM call + extraction ─────────────────────────────────────────────────

    def _extract(self, response: str):
        if not response:
            return [], []

        # ── code ──────────────────────────────────────────────────────────────
        # 1. Fenced code blocks (most reliable)
        code = re.findall(r'```(?:python)?\n(.*?)```', response, re.DOTALL)

        if not code:
            # 2. Locate the first top-level Python statement at the start of a line
            #    (import / from / def / class / decorator), then trim trailing prose
            #    by iteratively removing the last line until the snippet parses.
            start = re.search(r'^(?:import |from |def |class |@)', response, re.MULTILINE)
            if start:
                candidate = response[start.start():].strip()
                lines = candidate.splitlines()
                for trim in range(len(lines)):
                    snippet = '\n'.join(lines[:len(lines) - trim]).strip()
                    if not snippet:
                        break
                    try:
                        ast.parse(snippet)
                        code = [snippet]
                        break
                    except SyntaxError:
                        continue

        # Strip any leading {description} line the LLM sometimes puts inside the code block
        code = [re.sub(r'^\s*\{[^}]*\}\s*\n+', '', c, flags=re.DOTALL).strip() for c in code]
        code = [c for c in code if c]

        # ── algorithm description ──────────────────────────────────────────────
        # Search only in text BEFORE the code to avoid matching Python dict literals.
        if '```' in response:
            pre_code = response[:response.find('```')].strip()
        elif code:
            # Find where the extracted code begins in the original response
            idx = response.find(code[0][:60]) if code[0] else -1
            pre_code = response[:idx].strip() if idx > 0 else response.strip()
        else:
            pre_code = response.strip()

        # Require at least 8 chars to skip empty {}, single-letter vars, dict snippets
        algorithm = re.findall(r'\{([^{}]{8,})\}', pre_code)

        if not algorithm and pre_code:
            # Fall back: everything before the code is treated as the description
            algorithm = [pre_code]

        return algorithm, code

    def _prepend_imports(self, code: str) -> str:
        """Prepend any template import line not already present in code."""
        if not self._template_import_prefix:
            return code
        missing = [
            line for line in self._template_import_prefix.splitlines()
            if line and line not in code
        ]
        if not missing:
            return code
        return "\n".join(missing) + "\n" + code

    def _call_llm(self, prompt: str):
        for attempt in range(4):
            response = self.llm.get_response(prompt)
            if response:
                logger.debug("  [response] attempt %d/4: %.500s", attempt + 1, response)
            algorithm, code = self._extract(response)
            if algorithm and code:
                break
            logger.debug("  [extract] attempt %d/4 failed — no algorithm or code found.", attempt + 1)

        if not algorithm or not code:
            return None, None

        return self._prepend_imports(code[0]), algorithm[0]

    # ── operator dispatch ─────────────────────────────────────────────────────

    def _generate(self, population: list, operator: str):
        if operator == "i1":
            parents = None
            prompt = self._build_prompt("i1")
        elif operator in {"n1", "n2"}:
            if not population:
                raise ValueError(f"Operator '{operator}' requires a non-empty population.")
            parents = parent_selection(population, 1, self.feedback_policy)[0]
            mutations = (
                numeric_constant_mutations(parents["code"])
                if operator == "n1"
                else numeric_constant_pair_mutations(parents["code"])
            )
            if not mutations:
                return parents, None, None
            with self._numeric_mutation_lock:
                index = self._numeric_mutation_cursors[operator] % len(mutations)
                self._numeric_mutation_cursors[operator] += 1
            code, algorithm = mutations[index]
            logger.debug("  [%s] candidate %d/%d: %s", operator, index + 1, len(mutations), algorithm)
            return parents, code, algorithm
        elif operator in ("e1", "e2"):
            if not population:
                raise ValueError(f"Operator '{operator}' requires a non-empty population.")
            parents = parent_selection(population, self.n_parents, self.feedback_policy)
            prompt = self._build_prompt(operator, parents)
        elif operator in ("m1", "m2", "m3"):
            if not population:
                raise ValueError(f"Operator '{operator}' requires a non-empty population.")
            parents = parent_selection(population, 1, self.feedback_policy)[0]
            prompt = self._build_prompt(operator, parents)
        else:
            raise ValueError(f"Unknown operator: {operator}")

        logger.debug("  [prompt/%s] %d chars: %.400s", operator, len(prompt), prompt)
        code, algorithm = self._call_llm(prompt)

        if code:
            logger.debug("  [extract] algorithm: %.120r", algorithm)
            logger.debug("  [extract] code (%d chars): %.400s", len(code), code)
        else:
            logger.debug("  [extract] failed — no code extracted.")

        return parents, code, algorithm

    # ── code generation (no evaluation) ───────────────────────────────────────

    def generate_code(self, population: list, operator: str):
        """LLM generation + duplicate-retry, WITHOUT evaluation.

        Returns (parents, code, algorithm), or (None, None, None) on failure.
        This is the producer half used by the async pipeline: evaluation is run
        separately on the evaluation pool so LLM I/O and CPU-bound evaluation
        scale independently of each other and of pop_size.
        """
        parents, code, algorithm = self._generate(population, operator)
        if code is None:
            return None, None, None

        n_retry = 0
        while self._is_duplicate(population, code) and n_retry < 2:
            logger.debug("  [offspring] duplicate — retrying...")
            _, code, algorithm = self._generate(population, operator)
            if code is None:
                return None, None, None
            n_retry += 1

        return parents, code, algorithm

    # ── single offspring ──────────────────────────────────────────────────────

    def get_offspring(self, population: list, operator: str):
        try:
            parents, code, algorithm = self.generate_code(population, operator)
            if code is None:
                return None, None

            # Always isolate evaluation in a subprocess so a per-eval hard timeout
            # applies consistently in both sequential and parallel modes.
            # In parallel mode this function already runs inside a joblib worker
            # process, so the nested subprocess is safe (spawn context, no
            # inherited lock state). os.setsid() in _eval_worker creates a new
            # process group so compiler/interpreter children are killed too.
            fitness = _eval_with_timeout(self.interface_eval, code, self.timeout)
            if fitness is None:
                logger.debug("  [eval] timed out or returned None after %ds", self.timeout)

            objective, feedback = _normalize_evaluation_result(fitness)
            offspring = {
                'algorithm': algorithm,
                'code': code,
                'objective': objective,
                'other_inf': feedback,
            }
            return parents, offspring

        except Exception as e:
            logger.debug("  [offspring] %s: %s", type(e).__name__, e)
            return None, None

    # ── parallel batch ────────────────────────────────────────────────────────

    def get_algorithm(self, population: list, operators: list):
        """Generate one offspring per entry in operators, optionally in parallel.

        Each eval runs in its own subprocess (see _eval_with_timeout), so per-job
        timeouts are enforced without a batch-level timeout. On any Parallel()
        failure the call falls back to sequential so no offspring are silently lost.
        """
        if self.n_processes == 1 or Parallel is None:
            results = [self.get_offspring(population, op) for op in operators]
        else:
            try:
                results = Parallel(n_jobs=self.n_processes)(
                    delayed(self.get_offspring)(population, op) for op in operators
                )
            except Exception as e:
                logger.warning("  [parallel] %s: %s — falling back to sequential", type(e).__name__, e)
                results = [self.get_offspring(population, op) for op in operators]

        parents = [p for p, _ in results]
        offspring = [o for _, o in results]
        return parents, offspring

    # ── seed evaluation ───────────────────────────────────────────────────────

    def evaluate_seeds(self, seeds: list) -> list:
        _timeout = self.timeout
        _problem = self.interface_eval
        if self.n_processes == 1 or Parallel is None:
            fitness_list = [
                _eval_with_timeout(_problem, s['code'], _timeout) for s in seeds
            ]
        else:
            try:
                fitness_list = Parallel(n_jobs=self.n_processes)(
                    delayed(_eval_with_timeout)(_problem, s['code'], _timeout)
                    for s in seeds
                )
            except Exception as e:
                logger.warning("  [seed parallel] %s — falling back to sequential", e)
                fitness_list = [
                    _eval_with_timeout(_problem, s['code'], _timeout) for s in seeds
                ]
        population = []
        for seed, fitness in zip(seeds, fitness_list):
            objective, feedback = _normalize_evaluation_result(fitness)
            if objective is not None:
                population.append({
                    'algorithm': seed['algorithm'],
                    'code': seed['code'],
                    'objective': objective,
                    'other_inf': feedback,
                })
        logger.info("Seeds: %d/%d valid.", len(population), len(seeds))
        return population

    # ── helpers ───────────────────────────────────────────────────────────────

    def _is_duplicate(self, population: list, code: str) -> bool:
        return any(ind['code'] == code for ind in population)
