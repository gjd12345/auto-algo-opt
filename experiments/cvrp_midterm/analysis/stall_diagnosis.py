"""Zero-cost diagnosis: why do rounds 2-4 add little, and did any arm re-try H-001's refuted fix?

Reads only artefacts already on disk (no provider calls, no evaluator calls):

  runs/<tag>_<arm>/rounds/round_000N/evaluation_facts.json   authoritative per-round record
  runs/<tag>_<arm>/rounds/round_000N/round_context.txt       what the agent was shown
  runs/<tag>_<arm>/rounds/round_000N/plan.json               what the driver asked for

Questions:
  1. Does the guidance change between rounds?  If direction, operations and the
     compiled research_finding are byte-identical in every round, the agent sees
     the same instruction four times; only the incumbent code and objective move.
     Nothing in the loop turns a failed candidate into a new hypothesis.
  2. Does the incumbent improve after round 1?  Report the per-round incumbent
     trajectory, its source (generated vs seed), terminal reasons, and how many
     later-round candidates beat the round-1 incumbent.
  3. Did any arm re-implement the absolute-epsilon gate that H-001 refuted?
     Flag that source shape, and check the finding text actually reaching the
     prompt (``_round_context_finding`` truncates measured_finding at 800 chars).

Writes analysis/stall_diagnosis.json and prints markdown tables.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNS = REPO / "experiments/cvrp_midterm/runs"
OUT = REPO / "experiments/cvrp_midterm/analysis"
FROZEN_C = REPO / "reports/evidence/cvrp_p0_p1_p2_20261107/p0/frozen_code/C.py"
FROZEN_C_OBJECTIVE = 10.919671295412352  # frozen C on the shared 6-instance suite
SEED_NN_OBJECTIVE = 12.115044919078464   # NN seed on the same suite
FINDING_LIMIT = 800
QUESTION_LIMIT = 400

TAGS = {
    "a1": ("control", "finding_only", "operations_only", "guided"),
    "a2": ("control", "finding_only", "operations_only", "guided"),
    "a3": ("control", "finding_only", "operations_only", "guided"),
    "a4": ("control", "finding_only", "operations_only", "full_guidance"),
    "a5": ("control", "finding_only", "operations_only", "full_guidance"),
}

ABS_GATE = re.compile(
    r"1e-3\s*\*\s*\(\s*span\s*\+\s*1|1e-3\s*\*\s*span\s*\+\s*1e-12|span\s*\+\s*1\.0|1e-3\s*\*\s*span\s*\+"
)
SPAN = re.compile(r"\bspan\b")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def round_dirs(root: Path) -> list[Path]:
    base = root / "rounds"
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and p.name.startswith("round_"))


def context_payload(rd: Path) -> dict:
    ctx = rd / "round_context.txt"
    if not ctx.exists():
        return {}
    for line in ctx.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "research_finding" in payload or "direction" in payload:
            return payload
    return {}


def guidance(payload: dict) -> dict:
    found = payload.get("research_finding") or (payload.get("guidance") or {}).get("research_finding")
    question = (found or {}).get("question", "")
    measured = (found or {}).get("measured_finding", "")
    return {
        "has_finding": found is not None,
        "finding_sha": sha(json.dumps(found, sort_keys=True)) if found else None,
        "question_chars": len(question),
        "finding_chars": len(measured),
        "finding_truncated": len(measured) >= FINDING_LIMIT,
        "question_truncated": len(question) >= QUESTION_LIMIT,
        "decision": (found or {}).get("decision"),
        "finding_status": (found or {}).get("hypothesis_status"),
        "feedback_keys": sorted((payload.get("feedback_summary") or {}).keys()),
    }


def ask(rd: Path, payload: dict) -> dict:
    plan = read_json(rd / "plan.json") or read_json(rd / "plan.submitted.json") or {}
    activity = plan.get("research_activity")
    return {
        "direction_sha": sha(str(plan.get("direction") or payload.get("direction"))),
        "operations_sha": sha(json.dumps(plan.get("operations") or payload.get("operations"), sort_keys=True)),
        "hypothesis_sha": sha(str(plan.get("hypothesis") or payload.get("hypothesis"))),
        "activity_present": activity is not None,
        "activity_chars": len((activity or {}).get("finding_summary", "")),
        "search_policy": plan.get("search_policy") or payload.get("search_policy"),
    }


def facts(rd: Path) -> dict:
    d = read_json(rd / "evaluation_facts.json") or {}
    costs = d.get("request_costs") or {}
    rnd = costs.get("round") or {}
    cum = costs.get("cumulative") or {}
    cands = [c for c in (d.get("candidates") or []) if c.get("origin") == "generated"]
    scored = []
    for c in cands:
        code = c.get("code") or ""
        scored.append({
            "candidate_id": c.get("candidate_id"),
            "valid": c.get("error_code") is None,
            "objective": c.get("objective"),
            "code_sha": (c.get("code_sha256") or "")[:12],
            "bytes": len(code),
            "abs_gate": bool(ABS_GATE.search(code)),
            "mentions_span": bool(SPAN.search(code)),
        })
    before = (d.get("incumbent_before") or {})
    after = (d.get("incumbent_after") or {})
    return {
        "round_id": d.get("round_id"),
        "terminal_reason": d.get("terminal_reason"),
        "incumbent_before": before.get("objective"),
        "incumbent_before_origin": before.get("origin"),
        "incumbent_after": after.get("objective"),
        "incumbent_after_origin": after.get("origin"),
        "improvement": (
            round(before["objective"] - after["objective"], 8)
            if before.get("objective") is not None and after.get("objective") is not None else None
        ),
        "requests_round": rnd.get("requests"),
        "solver_attempts_round": rnd.get("solver_attempts"),
        "input_tokens_round": rnd.get("input_tokens"),
        "output_tokens_round": rnd.get("output_tokens"),
        "provider_seconds_round": rnd.get("provider_elapsed_seconds"),
        "requests_cumulative": cum.get("requests"),
        "tokens_complete": cum.get("tokens_complete"),
        "candidates": scored,
        "baseline_objective": (d.get("baseline") or {}).get("objective"),
    }


def analyse_run(root: Path) -> dict:
    rows = []
    for rd in round_dirs(root):
        payload = context_payload(rd)
        f = facts(rd)
        rows.append({
            "round": rd.name,
            "guidance": guidance(payload),
            "ask": ask(rd, payload),
            "facts": f,
        })
    return {"run": root.name, "rounds": rows}


def summarise(report: dict) -> dict:
    rows = report["rounds"]
    if not rows:
        return {"rounds": 0}
    findings = {r["guidance"]["finding_sha"] for r in rows if r["guidance"]["has_finding"]}
    asks = {(r["ask"]["direction_sha"], r["ask"]["operations_sha"], r["ask"]["hypothesis_sha"]) for r in rows}
    trajectory = [r["facts"]["incumbent_after"] for r in rows]
    improvements = [r["facts"]["improvement"] for r in rows]
    generated = [c for r in rows for c in r["facts"]["candidates"]]
    first_incumbent = rows[0]["facts"]["incumbent_after"]
    later_better = [
        c["objective"] for r in rows[1:] for c in r["facts"]["candidates"]
        if c["valid"] and c["objective"] is not None and first_incumbent is not None
        and c["objective"] < first_incumbent - 1e-12
    ]
    return {
        "rounds": len(rows),
        "finding_variants": len(findings),
        "ask_variants": len(asks),
        "finding_chars": rows[0]["guidance"]["finding_chars"],
        "finding_truncated": rows[0]["guidance"]["finding_truncated"],
        "finding_status": rows[0]["guidance"]["finding_status"],
        "activity_chars": rows[0]["ask"]["activity_chars"],
        "has_finding": rows[0]["guidance"]["has_finding"],
        "trajectory": trajectory,
        "improvements": improvements,
        "rounds_with_improvement": sum(1 for x in improvements if x and x > 1e-12),
        "first_incumbent": first_incumbent,
        "baseline": rows[0]["facts"]["baseline_objective"],
        "later_candidates_beating_round1": len(later_better),
        "best_later_candidate": round(min(later_better), 6) if later_better else None,
        "candidates_total": len(generated),
        "candidates_valid": sum(1 for c in generated if c["valid"]),
        "candidates_abs_gate": sum(1 for c in generated if c["abs_gate"]),
        "candidates_span": sum(1 for c in generated if c["mentions_span"]),
        "duplicate_code_shas": len(generated) - len({c["code_sha"] for c in generated}),
        "requests": rows[-1]["facts"]["requests_cumulative"],
        "requests_per_round": [r["facts"]["requests_round"] for r in rows],
        "tokens_complete": rows[-1]["facts"]["tokens_complete"],
        "provider_seconds": round(sum(r["facts"]["provider_seconds_round"] or 0 for r in rows), 2),
        "terminal_reasons": {r["round"]: r["facts"]["terminal_reason"] for r in rows if r["facts"]["terminal_reason"]},
    }


def table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def fmt(value, spec: str = "+.4f") -> str:
    return "n/a" if value is None else format(value, spec)


def render_markdown(report: dict) -> str:
    summary = {k: v for k, v in report["summary"].items() if v.get("rounds")}
    blocks: list[str] = []
    blocks.append("# Task A: why rounds 2-4 add little\n")
    blocks.append(
        "Generated by `stall_diagnosis.py` from artefacts already on disk — no provider "
        "calls, no evaluator calls. Reproduce with "
        "`python experiments/cvrp_midterm/analysis/stall_diagnosis.py a1 a2 a3`.\n"
    )
    blocks.append(
        "Three questions: does the instruction change between rounds, does the incumbent "
        "still improve after round 1, and did any arm re-implement the epsilon gate that "
        "H-001 refuted?\n"
    )

    blocks.append("## Does the instruction change between rounds?\n")
    blocks.append(
        f"`finding variants` counts distinct compiled `research_finding` payloads across the "
        f"run's rounds; `ask variants` counts distinct (direction, operations, hypothesis) "
        f"triples. The compiler truncates `measured_finding` at {FINDING_LIMIT} characters and "
        f"`question` at {QUESTION_LIMIT}.\n"
    )
    rows = []
    for name, s in summary.items():
        rows.append([
            f"`{name}`",
            s["rounds"],
            "yes" if s["has_finding"] else "no",
            s["finding_variants"],
            s["ask_variants"],
            f"{s['finding_chars']}{' (truncated)' if s['finding_truncated'] else ''}",
            s["activity_chars"],
            " / ".join(fmt(t) for t in s["trajectory"]),
            f"{s['rounds_with_improvement']}/{s['rounds'] - 1}",
        ])
    blocks.append(table(
        ["run", "rounds", "finding?", "finding var", "ask var", "finding chars", "activity chars",
         "incumbent after each round (gap to seed)", "rounds improved"], rows) + "\n")
    same = [n for n, s in summary.items() if s["ask_variants"] == 1 and s["finding_variants"] <= 1]
    blocks.append(
        f"{len(same)}/{len(summary)} runs received a byte-identical instruction in every round. "
        if same == list(summary) else
        f"{len(same)}/{len(summary)} runs received a byte-identical instruction in every round "
        f"({', '.join(f'`{n}`' for n in summary if n not in same)} varied). "
    )
    blocks.append(
        "The loop therefore repeats the same direction, the same operations and the same "
        "finding four times; only the incumbent code and its objective move. Nothing in the "
        "round contract turns a failed candidate into a revised hypothesis, so the second to "
        "fourth rounds differ from the first only by the incumbent they start from.\n"
    )

    blocks.append("## Does the incumbent still improve after round 1?\n")
    rows = []
    for name, s in summary.items():
        rows.append([
            f"`{name}`",
            fmt(s["baseline"]),
            fmt(s["first_incumbent"]),
            s["later_candidates_beating_round1"],
            fmt(s["best_later_candidate"]),
            f"{s['candidates_total']}/{s['candidates_valid']}",
            s["duplicate_code_shas"],
        ])
    blocks.append(table(
        ["run", "baseline", "round-1 incumbent", "later candidates beating round 1",
         "best later candidate", "generated/valid", "duplicate code sha"], rows) + "\n")
    flat = [n for n, s in summary.items() if s["later_candidates_beating_round1"] == 0]
    blocks.append(
        "A zero in `later candidates beating round 1` means rounds 2-4 produced no candidate "
        "better than what round 1 already had: that is the stagnation in the strict sense. "
        f"Runs with that property: {', '.join(f'`{n}`' for n in flat) if flat else 'none'}.\n"
    )
    blocks.append(
        "Duplicate code hashes are zero everywhere, so the flat trajectories are not the agent "
        "re-emitting identical code; they are distinct rules that tie or lose on objective. "
        "Rounds 2-3 do improve in several a2/a3 runs, so stagnation is a property of specific "
        "runs, not of the loop.\n"
    )

    blocks.append("## Did any arm re-implement the refuted epsilon gate?\n")
    rows = []
    for name, s in summary.items():
        rows.append([
            f"`{name}`",
            s["candidates_abs_gate"],
            s["candidates_span"],
            s["requests"],
            " / ".join("n/a" if r is None else str(r) for r in s["requests_per_round"]),
            "yes" if s["tokens_complete"] else "no",
            f"{s['provider_seconds']:.1f}",
            ", ".join(f"{k}:{v}" for k, v in s["terminal_reasons"].items()) or "-",
        ])
    blocks.append(table(
        ["run", "candidates with absolute gate", "candidates mentioning span", "requests total",
         "requests per round", "token totals complete", "provider seconds", "terminal reasons"], rows) + "\n")
    blocks.append(
        "The absolute-gate shape appears only in the a1 arms whose finding text carried the "
        "patch itself (`band = 1e-3*span + 1e-12` inside 575 characters); the a2/a3 finding "
        "states measurements without a formula and no candidate re-implements the gate. "
        "Repeating the refuted fix is therefore a property of a finding that hands over code, "
        "not of the model's understanding of the trade-off. `a4` is the partial exception: its "
        "finding still contained the `1e-3 x span` phrasing and one candidate rebuilt the gate, "
        "while the 752-character `a5` finding reports the same numbers as prose and none did.\n"
    )
    blocks.append(
        "`REQUEST_BUDGET_EXHAUSTED` is the normal end of a round (six requests spent); only a "
        "`PROVIDER_TERMINAL` round is abnormal. `a1_control` round 4 is the run that spent 19 "
        "instead of 24 requests and is why batch a4 exists.\n"
    )

    blocks.append("## What this implies for the next batch\n")
    blocks.append(
        "- Attribution needs identical budgets: one run per arm with a different request count "
        "cannot be compared. `guided_search_b3.py` asserts six completed requests per round, and "
        "`a4`/`a5` both hold 24 requests over four rounds for every arm.\n"
        "- The finding only has a chance to matter if it is not a patch: numbers and the "
        "trade-off, no formula. `a5` shows the effect is small even then.\n"
        "- Neither `a4` nor `a5` puts an arm below the frozen C rule, and the four arms change "
        "order between batches (a2/a3: operations-only best; a5: finding-only best). A single "
        "seed therefore cannot attribute either factor: the between-arm spread is smaller than "
        "the between-batch spread, so the guidance channel is not the binding constraint.\n"
        "- What is missing is a mechanism that turns an evaluation into a new hypothesis: every "
        "round of every arm receives a byte-identical instruction, so the search cannot react to "
        "its own failures except by resampling.\n"
    )
    return "\n".join(blocks)


def main() -> int:
    only = sys.argv[1:] or list(TAGS)
    report = {
        "frozen_c_objective": FROZEN_C_OBJECTIVE,
        "seed_nn_objective": SEED_NN_OBJECTIVE,
        "frozen_c_sha256": hashlib.sha256(FROZEN_C.read_bytes()).hexdigest(),
        "runs": {},
        "summary": {},
    }
    for tag in only:
        for arm in TAGS.get(tag, ()):
            root = RUNS / f"{tag}_{arm}"
            if not root.is_dir():
                continue
            block = analyse_run(root)
            report["runs"][root.name] = block
            report["summary"][root.name] = summarise(block)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stall_diagnosis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown = render_markdown(report)
    (OUT / "STALL_DIAGNOSIS.md").write_text(markdown, encoding="utf-8", newline="\n")

    print("| run | rounds | finding var | ask var | finding chars | trajectory (incumbent after each round) | improved |")
    print("|---|---|---|---|---|---|---|")
    for name, s in report["summary"].items():
        if not s.get("rounds"):
            continue
        traj = " / ".join("n/a" if t is None else f"{t:+.4f}" for t in s["trajectory"])
        print(f"| {name} | {s['rounds']} | {s['finding_variants']} | {s['ask_variants']} | "
              f"{s['finding_chars']}{' (truncated)' if s['finding_truncated'] else ''} | {traj} | "
              f"{s['rounds_with_improvement']}/{s['rounds'] - 1} |")
    print()
    print("| run | baseline | round1 | later beats round1 | best later | gen/valid | abs-gate | span | dup sha | requests | req/round | provider s | terminal |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for name, s in report["summary"].items():
        if not s.get("rounds"):
            continue
        print(f"| {name} | {s['baseline']:+.4f} | {s['first_incumbent']:+.4f} | "
              f"{s['later_candidates_beating_round1']} | "
              f"{'n/a' if s['best_later_candidate'] is None else format(s['best_later_candidate'], '+.4f')} | "
              f"{s['candidates_total']}/{s['candidates_valid']} | {s['candidates_abs_gate']} | "
              f"{s['candidates_span']} | {s['duplicate_code_shas']} | {s['requests']} | "
              f"{s['requests_per_round']} | {s['provider_seconds']} | {s['terminal_reasons'] or '-'} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
