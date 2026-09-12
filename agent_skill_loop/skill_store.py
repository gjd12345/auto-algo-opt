"""Immutable skill versions: code.py + skill.json. Export is a pointer, not a copy."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from agent_skill_loop.contracts import SKILL_SCHEMA, SkillVersion
from agent_skill_loop.evaluator import evaluator_source_hash
from agent_skill_loop.problems.base import get_problem

SKILL_REF_SCHEMA = "algorithm-skill-ref/v2"
POLICY_ID = "unspecified"
POLICY_VERSION = "unknown"


def validate_skill_for_suite(skill: SkillVersion, suite: Mapping[str, Any]) -> str | None:
    """Return an error code when a skill does not match the suite's problem/interface.

    Identity is explicit: a skill is only evaluable against a suite of the same
    problem and the same entrypoint. Re-labelling a skill to fit another
    interface is never allowed.
    """
    problem_id = suite.get("problem") if isinstance(suite, Mapping) else None
    if skill.problem != problem_id:
        return "skill_problem_mismatch"
    try:
        spec = get_problem(problem_id)
    except ValueError:
        return "unsupported_problem"
    if skill.entrypoint != spec.entrypoint:
        return "skill_entrypoint_mismatch"
    return None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


def save_skill(directory: Path, skill: SkillVersion, *, evidence: Mapping[str, Any] | None = None) -> Path:
    directory = Path(directory)
    if sha256_text(skill.code) != skill.code_sha256:
        raise ValueError("code_hash_mismatch")
    if skill.evaluator_hash != evaluator_source_hash():
        raise ValueError("evaluator_hash_mismatch")
    if directory.exists():
        raise ValueError("skill_directory_exists")
    directory.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=directory.name + ".", dir=str(directory.parent)))
    try:
        (tmp / "code.py").write_text(skill.code, encoding="utf-8")
        (tmp / "skill.json").write_text(
            json.dumps(skill.metadata(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (tmp / "SKILL.md").write_text(
            "# Executable algorithm skill\n\n"
            f"Problem: `{skill.problem}`  \n"
            f"Entrypoint: `{skill.entrypoint}`  \n"
            f"Version: `{skill.version_id}`  \n\n"
            f"{skill.description or 'No algorithm description was supplied.'}\n\n"
            "The executable source is `code.py`. Re-evaluate it on the target "
            "suite before reuse; the stored score is evidence for its recorded "
            "suite only.\n",
            encoding="utf-8",
        )
        if evidence is not None:
            (tmp / "evidence.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
        os.replace(tmp, directory)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return directory


def _load_materialized(directory: Path) -> SkillVersion:
    code = (directory / "code.py").read_text(encoding="utf-8")
    meta = json.loads((directory / "skill.json").read_text(encoding="utf-8"))
    if meta.get("schema_version") != SKILL_SCHEMA:
        raise ValueError("skill_schema_mismatch")
    if sha256_text(code) != meta.get("code_sha256"):
        raise ValueError("code_hash_mismatch")
    if not isinstance(meta.get("valid"), bool):
        raise ValueError("skill_valid_type_mismatch")
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
        repair_of_attempt_id=meta.get("repair_of_attempt_id"),
        search_policy_id=str((meta.get("search_policy") or {}).get("id") or POLICY_ID),
        search_policy_version=str((meta.get("search_policy") or {}).get("version") or POLICY_VERSION),
        origin=meta.get("origin"),
        official_objective=meta.get("official_objective"),
        legacy_unverified=bool(meta.get("legacy_unverified", False)),
        search_policy_fixture_only=bool((meta.get("search_policy") or {}).get("fixture_only", False)),
    )


def _validate_ref_identity(payload: Mapping[str, Any], skill: SkillVersion) -> None:
    """Ensure an export pointer cannot silently relabel its target asset."""
    checks = {
        "version_id": skill.version_id,
        "problem": skill.problem,
        "entrypoint": skill.entrypoint,
        "code_sha256": skill.code_sha256,
        "suite_hash": skill.suite_hash,
        "evaluator_hash": skill.evaluator_hash,
    }
    for key, actual in checks.items():
        # Original v1 pointers did not duplicate problem/interface. The target
        # supplies both; all fields present in a v1 ref are still checked.
        if payload.get("schema_version") == "algorithm-skill-ref/v1" and key in {"problem", "entrypoint"} and key not in payload:
            continue
        if key not in payload:
            raise ValueError(f"skill_ref_{key}_missing")
        declared = payload[key]
        if str(declared) != str(actual):
            raise ValueError(f"skill_ref_{key}_mismatch")


def _resolve_ref_payload(payload: Mapping[str, Any], *, anchor: Path) -> Path:
    if payload.get("schema_version") not in {SKILL_REF_SCHEMA, "algorithm-skill-ref/v1"}:
        raise ValueError("skill_ref_schema_mismatch")
    relative = payload.get("skill_dir")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("skill_ref_invalid")
    target = (anchor / relative).resolve()
    if not target.is_relative_to(anchor.resolve()):
        raise ValueError("skill_ref_invalid")
    return target


def load_skill(directory: Path, *, _seen: frozenset[Path] = frozenset()) -> SkillVersion:
    directory = Path(directory)
    resolved = directory.resolve()
    if resolved in _seen or len(_seen) >= 32:
        raise ValueError("skill_ref_cycle")
    _seen = _seen | {resolved}
    if directory.is_file():
        payload = json.loads(directory.read_text(encoding="utf-8"))
        anchor = directory.parent.parent if directory.name == "ref.json" else directory.parent
        skill = load_skill(_resolve_ref_payload(payload, anchor=anchor), _seen=_seen)
        _validate_ref_identity(payload, skill)
        return skill
    skill_json = directory / "skill.json"
    ref_json = directory / "ref.json"
    if skill_json.is_file():
        return _load_materialized(directory)
    if ref_json.is_file():
        payload = json.loads(ref_json.read_text(encoding="utf-8"))
        skill = load_skill(_resolve_ref_payload(payload, anchor=directory.parent), _seen=_seen)
        _validate_ref_identity(payload, skill)
        return skill
    raise ValueError("skill_not_found")


def publish_export_ref(run_dir: Path, skill_dir: Path) -> Path:
    run_dir = Path(run_dir).resolve()
    skill_dir = Path(skill_dir).resolve()
    if not skill_dir.is_relative_to(run_dir):
        raise ValueError("skill_ref_invalid")
    skill = load_skill(skill_dir)
    if not skill.valid:
        raise ValueError("invalid_skill_not_exported")
    payload = {
        "schema_version": SKILL_REF_SCHEMA,
        "version_id": skill.version_id,
        "problem": skill.problem,
        "entrypoint": skill.entrypoint,
        "skill_dir": skill_dir.relative_to(run_dir).as_posix(),
        "code_sha256": skill.code_sha256,
        "suite_hash": skill.suite_hash,
        "evaluator_hash": skill.evaluator_hash,
    }
    export_dir = run_dir / "exported_skill"
    if (export_dir / "skill.json").is_file():
        raise ValueError("export_materialized_exists")
    _atomic_write_text(export_dir / "ref.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return export_dir


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
    repair_of_attempt_id: int | None = None,
    search_policy_id: str = POLICY_ID,
    search_policy_version: str = POLICY_VERSION,
    origin: str | None = None,
    official_objective: float | None = None,
    search_policy_fixture_only: bool = False,
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
        repair_of_attempt_id=repair_of_attempt_id,
        search_policy_id=search_policy_id,
        search_policy_version=search_policy_version,
        origin=origin,
        official_objective=official_objective,
        search_policy_fixture_only=search_policy_fixture_only,
    )
