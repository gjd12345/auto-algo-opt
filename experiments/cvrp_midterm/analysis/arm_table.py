"""Assemble the 2x2 comparison across batches into one table.

Sources, all on disk and produced by earlier zero-provider steps:

* ``runs/compare_{batch}.json``      run-level rounds (incumbent vs the NN seed)
* ``runs/per_instance_table_{batch}.json``  every arm rescored on the shared suite
* ``runs/{batch}_{arm}/budget_ledger.json``  requests, tokens, solver seconds

The table is what the report quotes for "strictly aligned 2x2": same model, same
seed, same six requests per round, four rounds, and every arm rescored by the
same evaluator on the same six instances as the frozen rules.

Usage:
    python experiments/cvrp_midterm/analysis/arm_table.py a5 a4 a2 a3
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

FROZEN_C = 10.919671295412352
FROZEN_NN = 12.115044919078464
ARMS = ("control", "finding_only", "operations_only", "full_guidance", "guided")

LABEL = {
    "control": "Control",
    "finding_only": "Finding-only",
    "operations_only": "Operations-only",
    "full_guidance": "Full-guidance",
    "guided": "Full-guidance",
}


def arm_dirs(batch: str) -> list[str]:
    found = [
        path.name[len(batch) + 1:]
        for path in sorted(RUNS.glob(f"{batch}_*"))
        if path.is_dir() and not path.name.startswith("_")
    ]
    lead = [arm for arm in ARMS if arm in found]
    return lead + [arm for arm in found if arm not in lead]


def run_level(batch: str, arm: str) -> dict:
    path = RUNS / f"compare_{batch}.json"
    if not path.exists():
        return {}
    rounds = json.loads(path.read_text(encoding="utf-8")).get(arm) or []
    if not rounds:
        return {}
    improving = sum(
        1
        for prev, cur in zip(rounds, rounds[1:])
        if cur["incumbent_after"] < prev["incumbent_after"] - 1e-12
    )
    best = min(r["best"]["objective"] for r in rounds if r.get("best"))
    return {
        "rounds": len(rounds),
        "improving": improving,
        "final_incumbent": rounds[-1]["incumbent_after"],
        "best_candidate": best,
    }


def budget(batch: str, arm: str) -> dict:
    """Requests and tokens per arm.

    The a4/a5 driver writes ``budget_ledger.json``; the earlier batches did not,
    so fall back to summing the engine's own ``requests.jsonl`` per round.
    """
    root = RUNS / f"{batch}_{arm}"
    path = root / "budget_ledger.json"
    if path.exists():
        rounds = json.loads(path.read_text(encoding="utf-8")).get("rounds") or []
        if rounds:
            return {
                "requests": sum(r["requests_completed"] for r in rounds),
                "input_tokens": sum(r["input_tokens"] for r in rounds),
                "output_tokens": sum(r["output_tokens"] for r in rounds),
                "solver_seconds": sum(r["solver_seconds"] for r in rounds),
            }
    requests = input_tokens = output_tokens = 0
    if not root.exists():
        return {}
    seen: set[str] = set()
    for path in sorted(root.glob("rounds/round_*/eoh_run/results/requests.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("state") != "complete":
                continue
            key = rec.get("request_id") or f"{path}:{rec.get('index')}"
            if key in seen:
                continue
            seen.add(key)
            requests += 1
            input_tokens += int(rec.get("input_tokens") or 0)
            output_tokens += int(rec.get("output_tokens") or 0)
    if not requests:
        return {}
    return {"requests": requests, "input_tokens": input_tokens, "output_tokens": output_tokens}


def suite(batch: str, arm: str) -> dict:
    path = RUNS / f"per_instance_table_{batch}.json"
    if not path.exists():
        return {}
    table = json.loads(path.read_text(encoding="utf-8"))
    objectives = table["objectives"].get(arm)
    if not objectives:
        return {}
    frozen = table["objectives"]["frozen_C"]
    mean = sum(objectives) / len(objectives)
    c_mean = sum(frozen) / len(frozen)
    c_first4 = sum(frozen[:4]) / 4
    return {
        "mean": mean,
        "vs_c": mean / c_mean - 1.0,
        "first4_vs_c": (sum(objectives[:4]) / 4) / c_first4 - 1.0,
    }


def table(batches: list[str]) -> str:
    head = (
        "| batch | arm | rounds | improving | requests | input tok | output tok "
        "| solver s | run best (vs NN) | suite mean | vs frozen C |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = []
    for batch in batches:
        for arm in arm_dirs(batch):
            run = run_level(batch, arm)
            bud = budget(batch, arm)
            sut = suite(batch, arm)
            body.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    batch,
                    LABEL.get(arm, arm),
                    run.get("rounds", "-"),
                    run.get("improving", "-"),
                    bud.get("requests", "-"),
                    bud.get("input_tokens", "-"),
                    bud.get("output_tokens", "-"),
                    ("{:.1f}".format(bud["solver_seconds"]))
                    if "solver_seconds" in bud else "-",
                    ("{:+.2%}".format(run["best_candidate"] / FROZEN_NN - 1))
                    if run else "-",
                    ("{:.3f}".format(sut["mean"])) if sut else "-",
                    ("{:+.2%}".format(sut["vs_c"])) if sut else "-",
                )
            )
    return head + "\n".join(body) + "\n"


def main() -> None:
    import sys

    batches = sys.argv[1:] or ["a5", "a4", "a2", "a3"]
    text = table(batches)
    out = ROOT / "analysis" / "arm_table.md"
    out.write_text(
        "# 2x2 arm comparison (shared suite, frozen C = {:.4f})\n\n".format(FROZEN_C)
        + text,
        encoding="utf-8",
        newline="\n",
    )
    print(text)
    print("written", out)


if __name__ == "__main__":
    main()
