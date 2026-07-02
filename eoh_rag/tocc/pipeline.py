"""TOCC V2 Pipeline — orchestrates agent → gatekeeper → manifest runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_tocc_v2_cycle(
    trace_path: str,
    *,
    problem: str | None = None,
    output_dir: str | None = None,
    available_cards: list[str] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Full V2 cycle: read trace → agent propose → gatekeeper validate.

    Does NOT execute runs — only produces validated proposal.
    Returns full audit dict for review.
    """
    from eoh_rag.tocc.agent import propose
    from eoh_rag.tocc.gatekeeper import validate_proposal

    result: dict[str, Any] = {
        "trace_path": trace_path,
        "proposal": None,
        "gatekeeper": None,
        "accepted": False,
        "safe_arm": None,
        "error": None,
    }

    agent_result = propose(trace_path)
    if agent_result.get("error"):
        result["error"] = agent_result["error"]
        return result

    proposal = agent_result["proposal"]
    result["proposal"] = proposal

    if not problem:
        payload = json.loads(Path(trace_path).read_text(encoding="utf-8"))
        problem = payload.get("problem", "")

    gk = validate_proposal(proposal, problem=problem, available_card_ids=available_cards)
    result["gatekeeper"] = gk
    result["accepted"] = gk["accepted"]
    result["safe_arm"] = gk["safe_arm"]

    return result


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="TOCC V2 pipeline — agent propose + gatekeeper validate")
    parser.add_argument("--trace", required=True, help="Path to official_eoh_run_summary.json")
    parser.add_argument("--problem", help="Problem name (auto-detected if omitted)")
    parser.add_argument("--output", default="-", help="Output path (default: stdout)")
    parser.add_argument("--available-cards", help="Comma-separated valid card IDs")
    args = parser.parse_args()

    cards = [c.strip() for c in args.available_cards.split(",")] if args.available_cards else None

    result = run_tocc_v2_cycle(args.trace, problem=args.problem, available_cards=cards)

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output_text)
    else:
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")

    if result.get("error") or not result.get("accepted"):
        sys.exit(1)


if __name__ == "__main__":
    main()
