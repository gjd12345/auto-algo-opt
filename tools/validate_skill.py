#!/usr/bin/env python3
"""Validate a packaged Codex Skill using the standard Skill schema checks."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


MAX_SKILL_NAME_LENGTH = 64
ALLOWED_FRONTMATTER = {"name", "description", "license", "allowed-tools", "metadata"}


def validate_skill(skill_path: str | Path) -> tuple[bool, str]:
    root = Path(skill_path)
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        return False, "SKILL.md not found"

    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return False, f"Invalid YAML in frontmatter: {exc}"
    if not isinstance(frontmatter, dict):
        return False, "Frontmatter must be a YAML dictionary"

    unexpected = set(frontmatter) - ALLOWED_FRONTMATTER
    if unexpected:
        return False, f"Unexpected frontmatter key(s): {', '.join(sorted(unexpected))}"
    if "name" not in frontmatter or "description" not in frontmatter:
        return False, "Missing 'name' or 'description' in frontmatter"

    name = frontmatter["name"]
    if not isinstance(name, str):
        return False, "Name must be a string"
    name = name.strip()
    if not re.fullmatch(r"[a-z0-9-]+", name):
        return False, "Name must use lowercase hyphen-case"
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return False, "Name cannot start/end with hyphen or contain consecutive hyphens"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, "Name is too long"

    description = frontmatter["description"]
    if not isinstance(description, str):
        return False, "Description must be a string"
    description = description.strip()
    if not description or len(description) > 1024 or "<" in description or ">" in description:
        return False, "Description is empty, too long, or contains angle brackets"
    if description.startswith("[TODO:"):
        return False, "Description contains an unfinished TODO placeholder"

    body = content[match.end() :]
    fence_marker: str | None = None
    fence_length = 0
    for line in body.splitlines():
        fence = re.match(r"^[ \t]*(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})(.*)$", line)
        if fence:
            marker = fence.group(1)
            if fence_marker is None:
                fence_marker, fence_length = marker[0], len(marker)
            elif marker[0] == fence_marker and len(marker) >= fence_length and not fence.group(2).strip():
                fence_marker, fence_length = None, 0
            continue
        if fence_marker is None and re.fullmatch(r"[ ]{0,3}\[TODO:[^\n]*\][ \t]*", line):
            return False, "Skill instructions contain an unfinished TODO placeholder"
    if fence_marker is not None:
        return False, "Unclosed fenced code block"
    # Validate local Markdown references without fetching any external URL.
    for document in root.rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            relative = target.split("#", 1)[0]
            resolved = (document.parent / relative).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                return False, f"Invalid local Skill reference: {document.name} -> {target}"
    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/validate_skill.py <skill_directory>")
        raise SystemExit(1)
    valid, message = validate_skill(sys.argv[1])
    print(message)
    raise SystemExit(0 if valid else 1)
