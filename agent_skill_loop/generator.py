"""Prompt construction and code extraction.

i1/e1/m1 templates are written for this loop. They are not the official EoH
_build_prompt strings (those treat m1 as 'repair the incumbent' and e1 as
multi-parent crossover, and the FME-aware i1 asks for a mechanism hypothesis).

Extraction helpers follow the MIT-licensed EoH approach of locating a fenced
Python block, then a brace description. Copied extraction logic is marked below.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from agent_skill_loop.problems.base import ProblemSpec, get_problem
from agent_skill_loop.problems.cvrp import PROBLEM_NAME

_EXECUTION_CONTRACT = (
    "NUMERIC EXECUTION CONTRACT: numpy/math only; no files, network, reflection "
    "or imports of other modules. Basic ndarray indexing and reductions are allowed; "
    "helpers such as np.ix_ are not."
)
_INTERFACE_BOUNDARY = (
    "INTERFACE BOUNDARY: only select_next_node is evolved. Route construction, "
    "capacity filtering, and objective computation stay in the evaluator."
)
_REPAIR_HINT = "returns a feasible node index (or 0 for an early depot return)"
_STAGNATION_HINT = (
    "Change one structural element (scoring combination, capacity remainder, "
    "candidate ordering, or early depot return). Do not emit a near-copy."
)


@dataclass
class PromptFeedback:
    incumbent_id: str | None = None
    incumbent_code: str | None = None
    incumbent_objective: float | None = None
    incumbent_instances: tuple[float, ...] = ()
    last_attempt_id: int | None = None
    last_code: str | None = None
    last_code_hash: str | None = None
    last_valid: bool | None = None
    last_objective: float | None = None
    last_instances: tuple[float, ...] = ()
    delta_vs_incumbent: float | None = None
    accepted: bool | None = None
    accept_reason: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    raw_reply: str | None = None
    edit_target: str = "incumbent"
    structural_explore: bool = False
    failed_code: str | None = None


def _fmt_nums(values: tuple[float, ...] | list[float]) -> str:
    return "[" + ", ".join(str(v) for v in values) + "]"


def _incumbent_block(feedback: PromptFeedback) -> str:
    return (
        "INCUMBENT:\n"
        f"version_id: {feedback.incumbent_id}\n"
        f"mean_objective: {feedback.incumbent_objective} (lower is better).\n"
        f"instance_objectives: {_fmt_nums(feedback.incumbent_instances)}\n"
        f"code:\n{feedback.incumbent_code}\n"
    )


def _last_block(feedback: PromptFeedback) -> str:
    lines = [
        "LAST CANDIDATE:",
        f"attempt_id: {feedback.last_attempt_id}",
        f"code_hash: {feedback.last_code_hash}",
        f"valid: {feedback.last_valid}",
        f"mean_objective: {feedback.last_objective}",
        f"instance_objectives: {_fmt_nums(feedback.last_instances)}",
        f"delta_vs_incumbent: {feedback.delta_vs_incumbent} (candidate minus incumbent; negative is better).",
        f"accepted: {feedback.accepted}",
        f"accept_reason: {feedback.accept_reason}",
    ]
    if feedback.error_code:
        lines.append(f"error_code: {feedback.error_code}")
    if feedback.error_detail:
        lines.append(f"error_detail: {feedback.error_detail}")
    if feedback.last_code:
        lines.append(f"code:\n{feedback.last_code}")
    elif feedback.raw_reply:
        lines.append("Previous model reply (no executable code extracted):")
        lines.append(feedback.raw_reply)
    elif feedback.failed_code:
        lines.append(f"Failed code:\n{feedback.failed_code}")
    return "\n".join(lines) + "\n"


def _function_spec(spec: ProblemSpec) -> str:
    return (
        "implement the following Python function:\n"
        f"```python\n{spec.template_program.strip()}\n```\n"
        "Do not give additional explanations."
    )


def build_prompt(operator: str, feedback: PromptFeedback | None = None, spec: ProblemSpec | None = None) -> str:
    spec = spec or get_problem(PROBLEM_NAME)
    program_spec = _function_spec(spec)
    boundary = spec.interface_boundary or _INTERFACE_BOUNDARY
    header = f"{spec.task_description}\n{boundary}\n"
    if operator == "i1":
        if feedback is not None:
            raise ValueError("i1_must_not_carry_parent_or_failure")
        return (
            f"{header}"
            "First, describe your new algorithm and main steps in one sentence. "
            f"The description must be inside a brace. Next, {program_spec}\n"
            f"{_EXECUTION_CONTRACT}\n"
        )
    if operator == "e1":
        if feedback is None or not feedback.incumbent_code or feedback.incumbent_objective is None:
            raise ValueError("e1_requires_single_parent")
        if feedback.error_code or feedback.failed_code:
            raise ValueError("e1_must_not_carry_failure")
        last_block = ""
        if (
            feedback.last_code
            and feedback.last_objective is not None
            and feedback.last_code != feedback.incumbent_code
        ):
            last_block = _last_block(feedback)
        explore = (
            "STAGNATION: previous measured e1 steps did not improve the incumbent. "
            f"{spec.stagnation_hint or _STAGNATION_HINT}\n"
            if feedback.structural_explore
            else ""
        )
        return (
            f"{header}"
            f"{_incumbent_block(feedback)}"
            f"{last_block}"
            f"EDIT TARGET: {feedback.edit_target}\n"
            f"{explore}"
            "Use the measured values as feedback. Preserve effective parts of the edit target, "
            "then introduce one clear alternative. Do not reset to a generic default.\n"
            "First, describe your new algorithm and main steps in one sentence. "
            f"The description must be inside a brace. Next, {program_spec}\n"
            f"{_EXECUTION_CONTRACT}\n"
        )
    if operator == "m1":
        if feedback is None or not feedback.error_code:
            raise ValueError("m1_requires_failed_code_and_error")
        body = _last_block(feedback)
        incumbent = ""
        if feedback.incumbent_code and feedback.incumbent_objective is not None:
            incumbent = (
                "A currently legal incumbent (do not treat it as the code to repair):\n"
                f"{_incumbent_block(feedback)}"
            )
        return (
            f"{header}"
            "Repair the failed candidate. Do not invent a score for it.\n"
            f"{body}"
            f"{incumbent}"
            f"EDIT TARGET: {feedback.edit_target}\n"
            "Change the failed program so it satisfies the function contract and "
            f"{spec.repair_hint or _REPAIR_HINT}.\n"
            "First, describe your repaired algorithm and main steps in one sentence. "
            f"The description must be inside a brace. Next, {program_spec}\n"
            f"{_EXECUTION_CONTRACT}\n"
        )
    raise ValueError(f"unknown_operator:{operator}")


# --- extraction: adapted from Fei Liu et al., EoH, MIT License ---
def extract(response: str) -> tuple[str, str]:
    """Return (description, code). Empty code means parse failure."""
    if not response:
        return "", ""

    code = re.findall(r"```(?:python)?\n(.*?)```", response, re.DOTALL)
    if not code:
        start = re.search(r"^(?:import |from |def |class |@)", response, re.MULTILINE)
        if start:
            candidate = response[start.start():].strip()
            lines = candidate.splitlines()
            for trim in range(len(lines)):
                snippet = "\n".join(lines[: len(lines) - trim]).strip()
                if not snippet:
                    break
                try:
                    ast.parse(snippet)
                    code = [snippet]
                    break
                except SyntaxError:
                    continue
    code = [re.sub(r"^\s*\{[^}]*\}\s*\n+", "", item, flags=re.DOTALL).strip() for item in code]
    code = [item for item in code if item]

    if "```" in response:
        pre_code = response[: response.find("```")].strip()
    elif code:
        idx = response.find(code[0][:60]) if code[0] else -1
        pre_code = response[:idx].strip() if idx > 0 else response.strip()
    else:
        pre_code = response.strip()
    algorithm = re.findall(r"\{([^{}]{8,})\}", pre_code)
    if not algorithm and pre_code:
        algorithm = [pre_code]
    description = algorithm[0].strip() if algorithm else ""
    extracted = prepend_imports(code[0]) if code else ""
    return description, extracted


def prepend_imports(code: str) -> str:
    prefix = "import numpy as np"
    if prefix in code:
        return code
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    has_numpy = any(
        isinstance(node, ast.Import) and any(alias.name == "numpy" for alias in node.names)
        for node in tree.body
    )
    if has_numpy:
        return code
    return prefix + "\n" + code
