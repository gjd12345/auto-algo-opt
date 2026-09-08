"""运行时指针必须停在已复核的 RQ1b 终态，且没有剩余批准实验。"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "agent_records" / "runtime" / "research_state.json"
AUDIT_PATH = (
    ROOT
    / "agent_records"
    / "calibrations"
    / "rq1b_online_20260831_v2_resume_v1_audit.json"
)


def test_research_state_points_at_rq1b_resume_and_blocks_new_runs() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    assert state["branch"] == "Refactor0830"
    assert state["run_budget"]["remaining_approved_additional_llm_runs"] == 0
    assert state["provider_policy"]["mix_cohorts"] is False
    assert state["blocked_reason"] == "no_authorized_additional_llm_runs"
    assert "execute" in state["next_action"]
    assert state["last_handoff"]["path"] == AUDIT_PATH.relative_to(ROOT).as_posix()
    assert state["last_handoff"]["sha256"] == (
        "b3e05c46a74b93f51fdbc3c686734d8340c6cb6f9ec14e9b805d36afbbdab54e"
    )
    assert audit["status"] == "evidence_integrity_verified"
    assert audit["study_status"] == "pilot_completed"
