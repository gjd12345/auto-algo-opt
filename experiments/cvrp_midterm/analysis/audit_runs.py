"""Offline P1 audit reverification: Session SQLite request accounting, prompt field audit, and non-destructive replays.

Writes:
- `experiments/cvrp_midterm/analysis/reverification/<run>_replay.json`
- `experiments/cvrp_midterm/analysis/audit_reverification_p1.json`

Never modifies historical run directories, SQLite files, or original `hypotheses_state.json`.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments/cvrp_midterm/runs"))

import round_activity as ra  # noqa: E402

RUNS = REPO / "experiments/cvrp_midterm/runs"
ANA = REPO / "experiments/cvrp_midterm/analysis"
REVERIFY_DIR = ANA / "reverification"
OUT_JSON = ANA / "audit_reverification_p1.json"

_NUM_RE = re.compile(r"[+-]?\d+(?:\.\d+)?%?")


def strip_numbers(text: str | None) -> str:
    if not text:
        return ""
    return _NUM_RE.sub("<NUM>", " ".join(text.split()))


def audit_sqlite_requests(run_dir: Path) -> dict:
    """Reconcile all requests directly from session.sqlite3 (read-only) by run/round/task/request."""
    db_path = run_dir / "session.sqlite3"
    if not db_path.is_file():
        return {"present": False, "error": "missing session.sqlite3"}
    wal_path = db_path.with_name(db_path.name + "-wal")
    has_wal = wal_path.is_file() and wal_path.stat().st_size > 0
    query = "mode=ro" if has_wal else "mode=ro&immutable=1"
    uri = f"file:{db_path.resolve().as_posix()}?{query}"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        runs_rows = [dict(r) for r in con.execute("SELECT run_id, state, eoh_max_requests, eoh_round_max_requests FROM runs").fetchall()]
        tasks_rows = [dict(r) for r in con.execute(
            "SELECT run_id, round_id, task_id, state FROM tasks ORDER BY round_id, task_id"
        ).fetchall()]
        req_rows = [dict(r) for r in con.execute(
            "SELECT run_id, round_id, task_id, request_id, sequence, purpose, state, "
            "input_tokens, output_tokens, error_code "
            "FROM requests ORDER BY round_id, sequence, request_id"
        ).fetchall()]
    finally:
        con.close()

    by_round: dict[int, dict] = {}
    for t in tasks_rows:
        rid = int(t["round_id"])
        rec = by_round.setdefault(rid, {
            "round_id": rid,
            "tasks": [],
            "reserved_quota": 0,
            "completed": 0,
            "failed": 0,
            "unknown": 0,
            "recorded_input_tokens": 0,
            "recorded_output_tokens": 0,
            "usage_unknown_requests": 0,
            "request_ids": [],
        })
        rec["tasks"].append({"task_id": t["task_id"], "state": t["state"]})

    seen_req_ids: set[str] = set()
    for r in req_rows:
        req_id = str(r["request_id"])
        if req_id in seen_req_ids:
            continue
        seen_req_ids.add(req_id)
        rid = int(r["round_id"])
        rec = by_round.setdefault(rid, {
            "round_id": rid,
            "tasks": [],
            "reserved_quota": 0,
            "completed": 0,
            "failed": 0,
            "unknown": 0,
            "recorded_input_tokens": 0,
            "recorded_output_tokens": 0,
            "usage_unknown_requests": 0,
            "request_ids": [],
        })
        rec["reserved_quota"] += 1
        rec["request_ids"].append(req_id)
        st = str(r.get("state") or "unknown")
        if st == "complete":
            rec["completed"] += 1
        elif st == "failed":
            rec["failed"] += 1
        else:
            rec["unknown"] += 1
        in_tok = r.get("input_tokens")
        out_tok = r.get("output_tokens")
        if in_tok is None or out_tok is None:
            rec["usage_unknown_requests"] += 1
        else:
            rec["recorded_input_tokens"] += int(in_tok)
            rec["recorded_output_tokens"] += int(out_tok)

    rounds_list = []
    for rid in sorted(by_round):
        rec = by_round[rid]
        rounds_list.append({
            "round_id": rid,
            "task_count": len(rec["tasks"]),
            "task_ids": [t["task_id"] for t in rec["tasks"]],
            "reserved_quota": rec["reserved_quota"],
            "completed": rec["completed"],
            "failed": rec["failed"],
            "unknown": rec["unknown"],
            "recorded_input_tokens": rec["recorded_input_tokens"],
            "recorded_output_tokens": rec["recorded_output_tokens"],
            "usage_unknown_requests": rec["usage_unknown_requests"],
        })

    return {
        "present": True,
        "run_ids": [r["run_id"] for r in runs_rows],
        "run_states": [r["state"] for r in runs_rows],
        "totals": {
            "rounds_with_tasks": len(rounds_list),
            "tasks_total": sum(r["task_count"] for r in rounds_list),
            "reserved_quota": sum(r["reserved_quota"] for r in rounds_list),
            "completed": sum(r["completed"] for r in rounds_list),
            "failed": sum(r["failed"] for r in rounds_list),
            "unknown": sum(r["unknown"] for r in rounds_list),
            "recorded_input_tokens": sum(r["recorded_input_tokens"] for r in rounds_list),
            "recorded_output_tokens": sum(r["recorded_output_tokens"] for r in rounds_list),
            "usage_unknown_requests": sum(r["usage_unknown_requests"] for r in rounds_list),
        },
        "rounds": rounds_list,
    }


def _parse_round_context(round_dir: Path) -> dict | None:
    for fname in ("round_context.txt", "round_context.json"):
        p = round_dir / fname
        if not p.is_file():
            continue
        raw = p.read_text(encoding="utf-8").strip()
        if not raw:
            continue
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Some contexts have a header line followed by JSON body
            idx = raw.find("{")
            if idx >= 0:
                try:
                    return json.loads(raw[idx:])
                except json.JSONDecodeError:
                    pass
    return None


def audit_prompt_fields(run_dir: Path) -> dict:
    """Audit research_finding presence, measurement updates, decision_summary template stability, and truncation."""
    discovered = ra.discover_rounds(run_dir)
    rows = []
    prev_meas_raw: str | None = None
    prev_meas_tmpl: str | None = None
    prev_dec_raw: str | None = None
    prev_dec_tmpl: str | None = None
    unique_dec_raw: set[str] = set()
    unique_dec_tmpl: set[str] = set()
    unique_meas_raw: set[str] = set()

    for rid in discovered["complete_rounds"]:
        rd = run_dir / f"rounds/round_{rid:04d}"
        ctx = _parse_round_context(rd) or {}
        rf = ctx.get("research_finding") if isinstance(ctx, dict) else None
        present = isinstance(rf, dict) and bool(rf)
        meas_raw = str(rf.get("measured_finding") or "") if present else ""
        dec_raw = str(rf.get("decision_summary") or "") if present else ""
        meas_tmpl = strip_numbers(meas_raw)
        dec_tmpl = strip_numbers(dec_raw)
        trunc = list(ctx.get("research_finding_truncated") or []) if isinstance(ctx, dict) else []
        if present and isinstance(rf.get("truncated_fields"), list):
            for f in rf["truncated_fields"]:
                if f not in trunc:
                    trunc.append(f)

        if meas_raw:
            unique_meas_raw.add(meas_raw)
        if dec_raw:
            unique_dec_raw.add(dec_raw)
        if dec_tmpl:
            unique_dec_tmpl.add(dec_tmpl)

        rows.append({
            "round_id": rid,
            "research_finding_present": present,
            "measurement_changed_raw": (meas_raw != prev_meas_raw) if prev_meas_raw is not None else present,
            "measurement_changed_template": (meas_tmpl != prev_meas_tmpl) if prev_meas_tmpl is not None else present,
            "decision_summary_changed_raw": (dec_raw != prev_dec_raw) if prev_dec_raw is not None else present,
            "decision_summary_changed_template": (dec_tmpl != prev_dec_tmpl) if prev_dec_tmpl is not None else present,
            "truncated_fields": trunc,
            "decision_summary_template": dec_tmpl,
        })
        if present:
            prev_meas_raw, prev_meas_tmpl = meas_raw, meas_tmpl
            prev_dec_raw, prev_dec_tmpl = dec_raw, dec_tmpl

    return {
        "rounds_audited": len(rows),
        "rounds_with_research_finding": sum(1 for r in rows if r["research_finding_present"]),
        "distinct_measured_finding_raw": len(unique_meas_raw),
        "distinct_decision_summary_raw": len(unique_dec_raw),
        "distinct_decision_summary_template": len(unique_dec_tmpl),
        "truncated_rounds": sum(1 for r in rows if r["truncated_fields"]),
        "rounds": rows,
    }


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO)).decode().strip()
    except Exception:
        return "unknown"


def main() -> int:
    target_runs = [
        "a5_control",
        "a5_finding_only",
        "a5_operations_only",
        "a5_full_guidance",
        "b4_control",
        "b4_finding_only",
        "s2_control_r8",
        "s2_autonomous_math_r8",
    ]
    out: dict = {
        "code_version": _git_head(),
        "reverification_dir": str(REVERIFY_DIR.relative_to(REPO)).replace("\\", "/"),
        "runs": {},
    }
    for name in target_runs:
        rdir = RUNS / name
        if not rdir.is_dir():
            continue
        replay = ra.replay_run(rdir, out_dir=REVERIFY_DIR)
        sqlite_audit = audit_sqlite_requests(rdir)
        prompt_audit = audit_prompt_fields(rdir)
        out["runs"][name] = {
            "discovered": replay["discovered"],
            "sqlite_requests": sqlite_audit,
            "prompt_audit": prompt_audit,
            "replay_summary": {
                "rounds": [
                    {
                        "round_id": r["round_id"],
                        "candidate_count": r["candidate_count"],
                        "official_valid_count": r["official_valid_count"],
                        "official_rejected_count": r["official_rejected_count"],
                        "probe_failed_count": r["probe_failed_count"],
                        "included_count": r["included_count"],
                        "best_nominal": round(r["best_nominal"], 6) if r["best_nominal"] is not None else None,
                        "best_spread_pct": round(r["best_spread_pct"], 4) if r["best_spread_pct"] is not None else None,
                        "progress_status": r["progress_status"],
                        "exact_code_repeat_count": r["exact_code_repeat_count"],
                        "mechanism_repeat_count": r["mechanism_repeat_count"],
                    }
                    for r in replay["rounds"]
                ],
                "final_hypotheses": {
                    k: v["status"] for k, v in replay["state"]["hypotheses"].items()
                },
            },
        }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # Compact console check
    compact = {}
    for name in ("b4_finding_only", "b4_control", "s2_autonomous_math_r8", "s2_control_r8"):
        item = out["runs"][name]
        compact[name] = {
            "sqlite_totals": item["sqlite_requests"]["totals"],
            "distinct_dec_raw": item["prompt_audit"]["distinct_decision_summary_raw"],
            "distinct_dec_tmpl": item["prompt_audit"]["distinct_decision_summary_template"],
            "rounds_replayed": len(item["replay_summary"]["rounds"]),
        }
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
