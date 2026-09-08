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

from agent_skill_loop.problems.cvrp import TASK_DESCRIPTION, TEMPLATE_PROGRAM

_EXECUTION_CONTRACT = (
    "NUMERIC EXECUTION CONTRACT: numpy/math only; no files, network, reflection "
    "or imports of other modules."
)


def _function_spec() -> str:
    return (
        "implement the following Python function:\n"
        f"```python\n{TEMPLATE_PROGRAM.strip()}\n```\n"
        "Do not give additional explanations."
    )


def build_prompt(
    operator: str,
    *,
    parent_code: str | None = None,
    parent_objective: float | None = None,
    last_code: str | None = None,
    last_objective: float | None = None,
    failed_code: str | None = None,
    error_code: str | None = None,
    raw_reply: str | None = None,
    incumbent_code: str | None = None,
    incumbent_objective: float | None = None,
) -> str:
    spec = _function_spec()
    if operator == "i1":
        if parent_code or failed_code:
            raise ValueError("i1_must_not_carry_parent_or_failure")
        return (
            f"{TASK_DESCRIPTION}\n"
            "First, describe your new algorithm and main steps in one sentence. "
            f"The description must be inside a brace. Next, {spec}\n"
            f"{_EXECUTION_CONTRACT}\n"
        )
    if operator == "e1":
        if not parent_code or parent_objective is None:
            raise ValueError("e1_requires_single_parent")
        if failed_code:
            raise ValueError("e1_must_not_carry_failure")
        last_block = ""
        if last_code and last_objective is not None:
            last_block = (
                "A later measured candidate was valid but not accepted as incumbent. "
                "Keep this measurement as additional feedback; do not ignore it.\n"
                f"Last candidate objective: {last_objective} (lower is better).\n"
                f"Last candidate code:\n{last_code}\n"
            )
        return (
            f"{TASK_DESCRIPTION}\n"
            "I have one existing algorithm with its measured development objective.\n"
            f"Dev objective: {parent_objective} (lower is better).\n"
            f"Code:\n{parent_code}\n"
            f"{last_block}"
            "Use the measured objective as feedback. Preserve effective parts of this parent, "
            "then introduce one clear structural alternative. Do not reset to a generic default.\n"
            "First, describe your new algorithm and main steps in one sentence. "
            f"The description must be inside a brace. Next, {spec}\n"
            f"{_EXECUTION_CONTRACT}\n"
        )
    if operator == "m1":
        if not error_code:
            raise ValueError("m1_requires_failed_code_and_error")
        if failed_code:
            failed_section = f"Failed code:\n{failed_code}\n"
        else:
            reply = raw_reply if raw_reply else "# no code extracted"
            failed_section = (
                "Previous model reply (no executable code extracted):\n"
                f"{reply}\n"
            )
        incumbent = ""
        if incumbent_code and incumbent_objective is not None:
            incumbent = (
                "A currently legal incumbent (do not treat it as the code to repair):\n"
                f"Incumbent objective: {incumbent_objective} (lower is better).\n"
                f"Incumbent code:\n{incumbent_code}\n"
            )
        return (
            f"{TASK_DESCRIPTION}\n"
            "I have one algorithm that failed evaluation. Repair THAT failed code. "
            "Do not invent a score for the failed candidate.\n"
            f"Error code: {error_code}\n"
            f"{failed_section}"
            f"{incumbent}"
            "Change the failed program so it satisfies the function contract and returns a "
            "feasible node index (or 0 for an early depot return).\n"
            "First, describe your repaired algorithm and main steps in one sentence. "
            f"The description must be inside a brace. Next, {spec}\n"
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
