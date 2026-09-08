"""Immutable skill versions: code.py + skill.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent_skill_loop.contracts import SKILL_SCHEMA, SkillVersion
from agent_skill_loop.evaluator import evaluator_source_hash


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_skill(directory: Path, skill: SkillVersion) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    code_path = directory / "code.py"
    meta_path = directory / "skill.json"
    if sha256_text(skill.code) != skill.code_sha256:
        raise ValueError("code_hash_mismatch")
    if skill.evaluator_hash != evaluator_source_hash():
        raise ValueError("evaluator_hash_mismatch")
    code_path.write_text(skill.code, encoding="utf-8")
    meta_path.write_text(json.dumps(skill.metadata(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return directory


def load_skill(directory: Path) -> SkillVersion:
    code = (directory / "code.py").read_text(encoding="utf-8")
    meta = json.loads((directory / "skill.json").read_text(encoding="utf-8"))
    if meta.get("schema_version") != SKILL_SCHEMA:
        raise ValueError("skill_schema_mismatch")
    if sha256_text(code) != meta.get("code_sha256"):
        raise ValueError("code_hash_mismatch")
    return SkillVersion(
        version_id=str(meta["version_id"]),
        problem=str(meta["problem"]),
        entrypoint=str(meta["entrypoint"]),
        code=code,
        code_sha256=str(meta["code_sha256"]),
        parent_version_id=meta.get("parent_version_id"),
        suite_hash=str(meta["suite_hash"]),
        evaluator_hash=str(meta["evaluator_hash"]),
        valid=bool(meta["valid"]),
        mean_objective=meta.get("mean_objective"),
        instance_objectives=tuple(meta.get("instance_objectives") or ()),
        source_attempt_id=meta.get("source_attempt_id"),
        description=str(meta.get("description") or ""),
    )


def make_skill(
    *,
    version_id: str,
    code: str,
    suite_hash: str,
    valid: bool,
    mean_objective: float | None,
    instance_objectives: tuple[float, ...],
    parent_version_id: str | None,
    source_attempt_id: int | None,
    description: str = "",
    problem: str,
    entrypoint: str,
) -> SkillVersion:
    return SkillVersion(
        version_id=version_id,
        problem=problem,
        entrypoint=entrypoint,
        code=code,
        code_sha256=sha256_text(code),
        parent_version_id=parent_version_id,
        suite_hash=suite_hash,
        evaluator_hash=evaluator_source_hash(),
        valid=valid,
        mean_objective=mean_objective,
        instance_objectives=instance_objectives,
        source_attempt_id=source_attempt_id,
        description=description,
    )
