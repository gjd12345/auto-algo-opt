"""LLM response parsing utilities."""

from __future__ import annotations

import re


def extract_code_block(text: str, lang: str = "go") -> str | None:
    """Extract the first fenced code block matching the given language.

    Only extracts the raw code from ```lang ... ``` fences.
    Does NOT perform any function-name filtering (that is caller responsibility).
    """
    pattern = rf"```(?:{lang}|{lang}lang)?\s*\n(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None
