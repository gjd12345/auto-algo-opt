"""Audit closure checks that require the optional pinned EoH dependency."""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

pytest.importorskip("eoh")

from agent_skill_loop.problems.base import get_problem
from agent_skill_loop.skill_store import sha256_text
from eoh_frozen.problem import FrozenProblem
from eoh_frozen.repair import RepairingEOH, is_repairable


def test_missing_repair_evidence_never_accepts_scalar_fitness():
    engine = object.__new__(RepairingEOH)
    engine._repair_lock = threading.Lock()
    engine.max_repairs_per_candidate = engine.max_repair_requests_total = 1
    for name in ("repair_triggered", "repair_attempted", "repair_succeeded", "repair_failed", "repair_skipped"):
        setattr(engine, name, 0)
    spec = get_problem("cvrp_construct")
    engine.problem = SimpleNamespace(
        spec=spec,
        task_description=spec.task_description,
        template_program=spec.template_program,
        suite={"content_hash": "suite"},
        timeout=20,
        set_evaluation_context=lambda _: None,
        evaluation_for_identity=lambda *_: None,
    )
    engine.repair_request = lambda *a, **k: json.dumps(
        {"algorithm": "fixed", "code": spec.baseline_code, "repair_summary": "fixed"}
    )
    engine._eval_executor = SimpleNamespace(submit=lambda *a: SimpleNamespace(result=lambda: 1.0))
    events = []
    engine._append_repair_event = events.append
    offspring = engine._repair_one(
        offspring={"code": "def broken(): pass", "objective": None},
        operator="i1",
        candidate_id="candidate_1",
        diagnostic={"error_code": "missing_entrypoint"},
    )
    assert offspring["objective"] is None and events[-1]["state"] == "failed"
    assert engine.repair_succeeded == 0


def test_frozen_problem_rejects_mismatched_evaluation_identity(tmp_path):
    from agent_skill_loop.problems.cvrp import build_suite

    spec = get_problem("cvrp_construct")
    suite = build_suite(1, count=1, size=6)
    code = spec.baseline_code
    row = {
        "code": code,
        "code_sha256": sha256_text(code),
        "problem": spec.problem_id,
        "entrypoint": spec.entrypoint,
        "suite_hash": suite["content_hash"],
        "evaluator_hash": "not-the-current-evaluator",
        "candidate_id": "candidate_1",
        "revision": "repair_1",
        "evaluation_id": "evaluation_1",
        "evaluation": {"valid": True, "objective": 1.0},
    }
    log = tmp_path / "results/evaluations.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps(row) + "\n", encoding="utf-8")
    problem = FrozenProblem(suite, spec=spec, evaluation_log=log)
    assert problem.evaluation_for_identity(
        code,
        {"candidate_id": "candidate_1", "revision": "repair_1", "evaluation_id": "evaluation_1"},
    ) is None


def test_repair_policy_is_closed():
    for code, detail in [
        ("forbidden_rebinding", "np"),
        ("forbidden_attribute", "read_text"),
        ("candidate_exception", "UnknownError"),
        ("timeout", ""),
        ("unknown", ""),
    ]:
        assert not is_repairable({"error_code": code, "error_detail": detail})
    assert is_repairable({"error_code": "forbidden_attribute", "error_detail": "ix_"})
    assert is_repairable({"error_code": "candidate_exception", "error_detail": "NameError:line_3"})
