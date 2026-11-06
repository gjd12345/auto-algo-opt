"""Render a verified public round summary; no model calls or private reasoning."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skill_loop import session_actions as actions, session_runtime as db


def render(run):
    run = Path(run).resolve()
    state = db.read_state(run=run)
    con = sqlite3.connect((run / "session.sqlite3").as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rounds = [dict(r) for r in con.execute("SELECT * FROM rounds ORDER BY round_id")]
        requests = Counter(r[0] for r in con.execute("SELECT round_id FROM requests"))
        solver = Counter(r[0] for r in con.execute("SELECT round_id FROM solver_calls"))
        terminal = {r[0]: r[1] for r in con.execute("SELECT round_id,terminal_reason FROM tasks")}
    finally:
        con.close()
    rows = []
    candidate_details = []
    cumulative = 0
    for row in rounds:
        number = row["round_id"]
        cumulative += requests[number]
        if not row.get("evaluation_facts_ref") or row["state"] not in {"ROUND_COMPLETED", "FAILED", "STOPPED"}:
            continue
        facts = actions.read_evaluation(run=run, round_id=number)["result"]
        plan_path = (run / row["normalized_plan_ref"]).resolve()
        if not plan_path.is_relative_to(run):
            raise ValueError("plan_path_escape")
        raw = plan_path.read_text(encoding="utf-8")
        if hashlib.sha256(raw.encode()).hexdigest() != row["normalized_plan_sha256"]:
            raise ValueError("plan_hash_mismatch")
        plan = json.loads(raw)
        generated = [c for c in facts.get("candidates", []) if c.get("origin") in {"generated", "generated_repair"}]
        valid = [c for c in generated if c.get("valid") is True]
        before = (facts.get("incumbent_before") or {}).get("objective")
        after = (facts.get("incumbent_after") or {}).get("objective")
        reason = terminal.get(number)
        status = "all-invalid" if generated and not valid else (
            "seed-insufficient" if reason == "insufficient_valid_seeds" else
            "budget-limited" if reason and ("BUDGET" in reason or "DEADLINE" in reason) else
            "improved" if before is not None and after is not None and after < before else
            "stagnated" if before is not None and after == before else "—")
        mechanism = "; ".join(op["mechanism"] for op in plan["operations"])
        objectives = Counter(str(c.get("objective")) if c.get("valid") else "invalid:" + str(c.get("error_code")) for c in generated)
        candidate_details.append({"round_id": number, "candidates": [
            {k: c.get(k) for k in ("candidate_id", "code_sha256", "evaluation_ref", "objective", "valid", "error_code")}
            for c in generated]})
        row_values = [number, mechanism, f"{requests[number]} / {cumulative}; {solver[number]}",
                      f"{len(valid)} / {len(generated)}", "; ".join(f"{k} × {v}" for k, v in objectives.items()),
                      f"{before if before is not None else '—'} → {after if after is not None else '—'}",
                      "OFF" if not state["memory"]["enabled"] else "—", status]
        rows.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in row_values) + " |")
    path = run / "round_progress.md"
    if path.exists():
        old = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("| ")][1:]
        if rows[:len(old)] != old:
            raise ValueError("previous_round_progress_changed")
    header = "# Round Progress\n\n| Round | Plan mechanism | Requests Δ / Σ; solver | Valid / generated | Objectives (identity list: round_candidates.json) | Incumbent before → after | Memory | Status |\n|---|---|---|---|---|---|---|---|\n"
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    (run / "round_candidates.json").write_text(json.dumps(candidate_details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"rounds": len(rows), "path": str(path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    print(json.dumps(render(parser.parse_args().run)))
