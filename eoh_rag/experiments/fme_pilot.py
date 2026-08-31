"""显式的 FME online-pilot CLI；默认只冻结计划，不调用模型。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eoh_rag.fme.online_adapters import ROOT
from eoh_rag.fme.online_pilot import freeze_protocol, load_protocol, run_study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "eoh_rag_workspace/experiments/manifests/refactor0830_opencode_go_pilot_v7.json")
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing output is never overwritten.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="Preflight all model slots then execute the complete frozen cohort.")
    mode.add_argument("--preflight", action="store_true", help="Only check configured models; create no experiment cells.")
    mode.add_argument("--integration-smoke", action="store_true", help="Same pipeline with explicit fixture transport + real solvers; no API or scientific claims.")
    args = parser.parse_args()
    protocol = freeze_protocol(load_protocol(args.manifest.resolve(), smoke=args.integration_smoke))
    output = args.output.resolve()
    if not (args.execute or args.preflight or args.integration_smoke):
        output.mkdir(parents=True, exist_ok=False)
        (output / "protocol_frozen.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = {"status": "prepared_not_executed", "protocol_hash": protocol["protocol_hash"],
                   "expected_cells": len(protocol["problems"]) * len(protocol["seeds"]) * len(protocol["arms"])}
    else:
        summary = run_study(protocol, output, gate_only=args.preflight)
    print(json.dumps({key: value for key, value in summary.items() if key in {
        "status", "protocol_hash", "expected_cells", "completed_cells", "terminal_error", "gate", "scientific_claim_allowed"
    }}, ensure_ascii=False))
    return 0 if summary["status"] in {"prepared_not_executed", "integration_smoke_completed", "pilot_completed", "preflight_ready"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
