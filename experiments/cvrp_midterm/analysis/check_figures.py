"""Structural self-check for the hand-written SVGs.

A picture cannot be inspected from here, so the geometry is checked instead:
every coordinate must sit inside the viewBox, no number may be NaN, and the
series values quoted in the labels must equal the numbers in the source JSON.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FIG = REPO / "experiments/cvrp_midterm/analysis/figures"
SELECTION = REPO / "experiments/cvrp_midterm/selection"
AUDIT = REPO / "experiments/cvrp_midterm/analysis/scale_term_audit.json"

NUM = re.compile(r"-?\d+(?:\.\d+)?")


def check(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    if "nan" in text.lower() or "inf" in text.lower():
        problems.append(f"{path.name}: contains nan/inf")
    head = re.search(r'width="(\d+)" height="(\d+)"', text)
    if not head:
        return problems + [f"{path.name}: no size"]
    width, height = int(head.group(1)), int(head.group(2))
    for tag in re.findall(r"<(?:rect|line|circle|text|path)[^>]*>", text):
        for attr in ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy"):
            match = re.search(rf'\s{attr}="(-?\d+(?:\.\d+)?)"', tag)
            if not match:
                continue
            value = float(match.group(1))
            limit = width if attr.startswith("x") or attr == "cx" else height
            if value < -1 or value > limit + 1:
                problems.append(f"{path.name}: {attr}={value} outside 0..{limit}")
    for match in re.finditer(r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="(-?[\d.]+)" height="(-?[\d.]+)"', text):
        x, y, w, h = (float(v) for v in match.groups())
        if w < 0 or h < 0:
            problems.append(f"{path.name}: negative rect size {w}x{h}")
    return problems


def numbers_match() -> list[str]:
    problems: list[str] = []
    summary = json.loads((SELECTION / "summary.json").read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))

    svg = (FIG / "portfolio_vbs_sbs.svg").read_text(encoding="utf-8")
    labels = {v for v in NUM.findall(svg)}
    for pool, block in summary["portfolios"].items():
        for key in ("vbs", "sbs"):
            value = f"{block[key]:.1f}"
            if value not in labels:
                problems.append(f"portfolio_vbs_sbs.svg: {pool}.{key}={value} not rendered")

    svg = (FIG / "scale_term_growth.svg").read_text(encoding="utf-8")
    for key in ("band_total_vs_base", "demand_term_vs_base", "cap_term_vs_base"):
        value = f"{audit['exponents'][key]:+.2f}"
        if value not in svg:
            problems.append(f"scale_term_growth.svg: exponent {key}={value} not in subtitle")

    svg = (FIG / "rule_mean_runtime.svg").read_text(encoding="utf-8")
    for rule, value in summary["mean_runtime_s"].items():
        text = f"{value*1000:.2f} ms"
        if text not in svg:
            problems.append(f"rule_mean_runtime.svg: {rule} runtime {text} missing")
    return problems


def main() -> int:
    figures = sorted(FIG.glob("*.svg"))
    if not figures:
        print("no figures")
        return 1
    problems: list[str] = []
    for path in figures:
        problems += check(path)
    problems += numbers_match()
    if problems:
        for item in problems:
            print("FAIL", item)
        return 1
    print(f"ok: {len(figures)} svg files, geometry and label/number agreement verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
