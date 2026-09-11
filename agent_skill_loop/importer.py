"""Explicit import of a historical candidate as a re-evaluated skill asset.

The caller names one source: a local file, or a path inside a local git
snapshot (ref + path). The importer records provenance (kind, ref, resolved
commit, path, source sha256, license), re-evaluates the code on the current
frozen suite with the current evaluator, and only stores it as a reusable
skill when the evaluation is valid. Incompatible code is rejected with a
diagnostic and is never rewritten or relabelled; historical scores never
migrate into the new evaluation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from agent_skill_loop.contracts import (
    DEFAULT_COUNT,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    DEFAULT_SOLVER_TIMEOUT,
    DEFAULT_SPLIT,
)
from agent_skill_loop.evaluator import SubprocessEvaluator, evaluator_source_hash
from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.skill_store import make_skill, publish_export_ref, save_skill, sha256_text

IMPORT_SCHEMA = "algorithm-skill-import/v1"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "unknown").strip().splitlines()
        raise ValueError(f"git_failed:{message[0][:200] if message else 'unknown'}")
    return proc.stdout


def _resolve_source(source: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    kind = source.get("kind")
    if kind == "file":
        path = Path(str(source.get("path", ""))).expanduser()
        if not path.is_file():
            raise ValueError(f"source_file_missing:{path}")
        try:
            code = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"source_file_not_utf8:{path}") from exc
        provenance: dict[str, Any] = {
            "kind": "file",
            "file": str(path.resolve()),
            "source_sha256": sha256_text(code),
        }
        return code, provenance
    if kind == "git":
        repo = Path(str(source.get("repo", ""))).expanduser()
        ref = str(source.get("ref", "")).strip()
        rel = str(source.get("path", "")).strip()
        if not repo.is_dir() or not ref or not rel:
            raise ValueError("invalid_git_source")
        commit = _git(repo, "rev-parse", ref).strip()
        code = _git(repo, "show", f"{commit}:{rel}")
        if not code.strip():
            raise ValueError("git_source_empty")
        provenance = {
            "kind": "git",
            "repo": str(repo.resolve()),
            "ref": ref,
            "commit": commit,
            "path": rel,
            "source_sha256": sha256_text(code),
        }
        return code, provenance
    raise ValueError("invalid_source")


def _source_label(provenance: Mapping[str, Any]) -> str:
    if provenance.get("kind") == "git":
        return f"{provenance.get('ref')}:{provenance.get('path')}"
    return str(provenance.get("file"))


def import_skill(
    *,
    problem_id: str,
    output_dir: Path,
    source: Mapping[str, Any],
    license: str = "unspecified",
    suite: Mapping[str, Any] | None = None,
    seed: int = DEFAULT_SEED,
    size: int = DEFAULT_SIZE,
    count: int = DEFAULT_COUNT,
    split: str = DEFAULT_SPLIT,
    solver_timeout: float = DEFAULT_SOLVER_TIMEOUT,
) -> dict[str, Any]:
    """Import one named candidate. Returns the import record (written to disk)."""
    spec = get_problem(problem_id)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError(f"output_directory_exists:{output_dir}")
    output_dir.mkdir(parents=True)
    suite_data = (
        dict(suite)
        if suite is not None
        else spec.build_suite(seed, split=split, count=count, size=size)
    )
    (output_dir / "dev_suite.json").write_text(
        json.dumps(suite_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    code, provenance = _resolve_source(source)
    provenance = {**provenance, "license": license}
    evaluation = SubprocessEvaluator(timeout=float(solver_timeout)).evaluate(code, suite_data)

    record: dict[str, Any] = {
        "schema": IMPORT_SCHEMA,
        "problem": spec.problem_id,
        "accepted": bool(evaluation.valid),
        "counts_as_generated": False,
        "source": provenance,
        "suite_hash": suite_data["content_hash"],
        "evaluator_hash": evaluator_source_hash(),
        "evaluation": evaluation.as_dict(),
        "skill_dir": None,
        "version_id": None,
        "note": (
            "Imported candidates are re-evaluated on the current suite with the "
            "current evaluator. Historical scores are not migrated and the import "
            "is not counted as generated in any run."
        ),
    }

    if evaluation.valid:
        version_id = f"imported_{sha256_text(code)[:12]}"
        skill = make_skill(
            version_id=version_id,
            code=code,
            suite_hash=str(suite_data["content_hash"]),
            valid=True,
            mean_objective=evaluation.objective,
            instance_objectives=evaluation.instance_objectives,
            parent_version_id=None,
            source_attempt_id=None,
            description=f"imported from {_source_label(provenance)}",
            problem=spec.problem_id,
            entrypoint=spec.entrypoint,
        )
        skill_dir = save_skill(output_dir / "skills" / version_id, skill)
        publish_export_ref(output_dir, skill_dir)
        record["skill_dir"] = f"skills/{version_id}"
        record["version_id"] = version_id

    (output_dir / "import_record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record
