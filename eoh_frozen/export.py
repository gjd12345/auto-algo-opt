"""Export official EoH population-best code as an algorithm skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_skill_loop.contracts import ENTRYPOINT_CVRP, PROBLEM_CVRP
from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.skill_store import make_skill, save_skill


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


def export_best_skill(output_dir: Path, suite: dict[str, Any], *, timeout: float = 20.0) -> Path | None:
    individual = load_best_individual(output_dir)
    if not individual or not individual.get("code"):
        return None
    code = str(individual["code"])
    evaluation = SubprocessEvaluator(timeout=timeout).evaluate(code, suite)
    skill = make_skill(
        version_id="eoh_best",
        code=code,
        suite_hash=str(suite["content_hash"]),
        valid=evaluation.valid,
        mean_objective=evaluation.objective,
        instance_objectives=evaluation.instance_objectives,
        parent_version_id=None,
        source_attempt_id=None,
        description=str(individual.get("algorithm") or ""),
        problem=PROBLEM_CVRP,
        entrypoint=ENTRYPOINT_CVRP,
    )
    save_skill(Path(output_dir) / "exported_skill", skill, overwrite=True)
    return Path(output_dir) / "exported_skill"
