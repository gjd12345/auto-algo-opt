"""Export official EoH population-best code as an algorithm skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_skill_loop.contracts import ENTRYPOINT_CVRP, PROBLEM_CVRP
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.skill_store import make_skill, publish_export_ref, save_skill, sha256_text


def _generation_index(path: Path) -> int:
    stem = path.stem
    try:
        return int(stem.rsplit("_", 1)[-1])
    except ValueError:
        return -1


def load_best_individual(output_dir: Path) -> dict[str, Any] | None:
    best_dir = Path(output_dir) / "results" / "pops_best"
    if not best_dir.is_dir():
        samples = Path(output_dir) / "results" / "samples" / "samples_best.json"
        if samples.is_file():
            payload = json.loads(samples.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else None
        return None
    files = sorted(best_dir.glob("population_generation_*.json"), key=_generation_index)
    if not files:
        return None
    payload = json.loads(files[-1].read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _write_export_rejected(output_dir: Path, payload: dict[str, Any]) -> Path:
    path = Path(output_dir) / "results" / "export_rejected.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def export_best_skill(output_dir: Path, suite: dict[str, Any], *, timeout: float = 20.0) -> Path | None:
    output_dir = Path(output_dir)
    individual = load_best_individual(output_dir)
    if not individual or not individual.get("code"):
        _write_export_rejected(output_dir, {"reason": "missing_best_individual"})
        return None
    code = str(individual["code"])
    evaluation = SubprocessEvaluator(timeout=timeout).evaluate(code, suite)
    if not evaluation.valid or evaluation.objective is None:
        _write_export_rejected(
            output_dir,
            {
                "reason": "reeval_invalid",
                "error_code": evaluation.error_code,
                "error_detail": evaluation.error_detail,
                "official_objective": individual.get("objective"),
                "code_sha256": sha256_text(code),
                "suite_hash": suite.get("content_hash"),
            },
        )
        return None
    skill = make_skill(
        version_id="eoh_best",
        code=code,
        suite_hash=str(suite["content_hash"]),
        valid=True,
        mean_objective=evaluation.objective,
        instance_objectives=evaluation.instance_objectives,
        parent_version_id=None,
        source_attempt_id=None,
        description=str(individual.get("algorithm") or ""),
        problem=PROBLEM_CVRP,
        entrypoint=ENTRYPOINT_CVRP,
    )
    skill_dir = output_dir / "skills" / "eoh_best"
    save_skill(skill_dir, skill)
    publish_export_ref(output_dir, skill_dir)
    return skill_dir
