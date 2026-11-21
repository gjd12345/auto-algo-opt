"""Draw the report figures as hand-written SVG (the venv has no matplotlib).

Every number is read from the artefacts the pipeline already wrote, so the
figures cannot drift from the tables:

* ``selection/summary.json``      -> portfolio VBS/SBS, rule means and runtimes
* ``selection/selectors.json``    -> selector gains against the fixed baseline
* ``analysis/scale_term_audit.json`` -> per-term scale exponents and magnitudes

Run:  python experiments/cvrp_midterm/analysis/figures.py
Out:  experiments/cvrp_midterm/analysis/figures/*.svg
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable, Sequence

REPO = Path(__file__).resolve().parents[3]
ANALYSIS = REPO / "experiments/cvrp_midterm/analysis"
SELECTION = REPO / "experiments/cvrp_midterm/selection"
OUT = ANALYSIS / "figures"

INK = "#1c2530"
MUTED = "#6a7480"
GRID = "#dfe4ea"
PALETTE = ("#2f6fd0", "#e0803a", "#3f9d6a", "#a3579e", "#c0392b", "#7b8794")


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Svg:
    def __init__(self, width: int, height: int, title: str, subtitle: str = "") -> None:
        self.width, self.height = width, height
        self.parts: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
            f'<text x="{width/2}" y="30" text-anchor="middle" font-size="17" font-weight="600" '
            f'fill="{INK}">{esc(title)}</text>',
        ]
        if subtitle:
            self.parts.append(
                f'<text x="{width/2}" y="50" text-anchor="middle" font-size="11.5" fill="{MUTED}">'
                f"{esc(subtitle)}</text>")

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = GRID,
             width: float = 1.0, dash: str | None = None) -> None:
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{color}" stroke-width="{width}"{extra}/>')

    def rect(self, x: float, y: float, w: float, h: float, fill: str, opacity: float = 1.0) -> None:
        self.parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(w, 0.5):.2f}" height="{max(h, 0.5):.2f}" '
            f'fill="{fill}" fill-opacity="{opacity}"/>')

    def text(self, x: float, y: float, content: str, size: float = 11, color: str = INK,
             anchor: str = "start", weight: str = "400", rotate: float | None = None) -> None:
        transform = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate else ""
        self.parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" font-weight="{weight}"{transform}>{esc(content)}</text>')

    def path(self, points: Sequence[tuple[float, float]], color: str, width: float = 2.0) -> None:
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}" for i, (x, y) in enumerate(points))
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"/>')

    def circle(self, x: float, y: float, r: float, fill: str) -> None:
        self.parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="{fill}"/>')

    def save(self, path: Path) -> None:
        self.parts.append("</svg>")
        path.write_bytes(("\n".join(self.parts) + "\n").encode("utf-8"))


def nice_bounds(values: Iterable[float], pad: float = 0.08) -> tuple[float, float]:
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi):
        return lo - 1.0, hi + 1.0
    span = hi - lo
    return lo - span * pad, hi + span * pad


def bar_chart(path: Path, title: str, subtitle: str, groups: Sequence[str],
              series: Sequence[tuple[str, Sequence[float]]], y_label: str,
              fmt: str = "{:.1f}", zero_line: bool = False,
              footnotes: Sequence[str] | None = None) -> None:
    width, height = 860, 470
    left, right, top, bottom = 78.0, 24.0, 86.0, 92.0
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for _, vals in series for v in vals]
    lo, hi = nice_bounds(values)
    if zero_line:
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    span = hi - lo
    svg = Svg(width, height, title, subtitle)

    def y_of(value: float) -> float:
        return top + plot_h * (1.0 - (value - lo) / span)

    ticks = 6
    for i in range(ticks + 1):
        value = lo + span * i / ticks
        y = y_of(value)
        svg.line(left, y, left + plot_w, y)
        svg.text(left - 10, y + 4, fmt.format(value), size=10.5, color=MUTED, anchor="end")
    if zero_line and lo < 0 < hi:
        svg.line(left, y_of(0.0), left + plot_w, y_of(0.0), color=INK, width=1.2)
    svg.line(left, top + plot_h, left + plot_w, top + plot_h, color=INK, width=1.2)
    svg.text(left + plot_w / 2, top - 16, y_label, size=11.5, color=MUTED, anchor="middle")

    n_groups = len(groups)
    group_w = plot_w / n_groups
    bar_w = group_w * 0.72 / len(series)
    for gi, group in enumerate(groups):
        base_x = left + gi * group_w + group_w * 0.14
        for si, (_, vals) in enumerate(series):
            value = vals[gi]
            x = base_x + si * bar_w
            y_value, y_zero = y_of(value), y_of(0.0 if zero_line else lo)
            svg.rect(x, min(y_value, y_zero), bar_w * 0.9, abs(y_value - y_zero),
                     PALETTE[si % len(PALETTE)], 0.92)
            label = fmt.format(value)
            svg.text(x + bar_w * 0.45, (y_value - 5) if value >= (0.0 if zero_line else lo) else (y_value + 13),
                     label, size=9.5, color=INK, anchor="middle")
        for li, text in enumerate(group.split("\n")):
            svg.text(left + gi * group_w + group_w / 2, top + plot_h + 18 + li * 13, text,
                     size=10.5, color=INK, anchor="middle")
    legend_y = height - 46
    x_cursor = left
    for si, (name, _) in enumerate(series):
        estimate = 26 + 6.9 * len(name)
        if x_cursor + estimate > width - right and x_cursor > left:
            legend_y -= 17
            x_cursor = left
        svg.rect(x_cursor, legend_y - 9, 12, 12, PALETTE[si % len(PALETTE)])
        svg.text(x_cursor + 18, legend_y + 1, name, size=11, color=INK)
        x_cursor += estimate
    if footnotes:
        for fi, note in enumerate(footnotes):
            svg.text(left, height - 16 - fi * 14, note, size=10, color=MUTED)
    svg.save(path)


def log_line_chart(path: Path, title: str, subtitle: str, scales: Sequence[float],
                   series: Sequence[tuple[str, Sequence[float]]], y_label: str,
                   floor: float = 1e-6) -> None:
    width, height = 820, 470
    left, right, top, bottom = 92.0, 132.0, 86.0, 74.0
    plot_w, plot_h = width - left - right, height - top - bottom
    order = sorted(range(len(scales)), key=lambda i: math.log10(scales[i]))
    scales = [scales[i] for i in order]
    series = [(name, [vals[i] for i in order]) for name, vals in series]
    xs = [math.log10(s) for s in scales]
    log_values = [math.log10(max(v, floor)) for _, vals in series for v in vals]
    lo, hi = nice_bounds(log_values, 0.06)
    svg = Svg(width, height, title, subtitle)

    def x_of(log_scale: float) -> float:
        return left + plot_w * (log_scale - xs[0]) / (xs[-1] - xs[0])

    def y_of(log_value: float) -> float:
        return top + plot_h * (1.0 - (log_value - lo) / (hi - lo))

    for i in range(6):
        value = lo + (hi - lo) * i / 5
        y = y_of(value)
        svg.line(left, y, left + plot_w, y)
        svg.text(left - 10, y + 4, f"1e{value:.1f}", size=10.5, color=MUTED, anchor="end")
    for scale in scales:
        x = x_of(math.log10(scale))
        svg.line(x, top, x, top + plot_h)
        svg.text(x, top + plot_h + 18, f"s={scale:g}", size=10.5, color=INK, anchor="middle")
    svg.line(left, top + plot_h, left + plot_w, top + plot_h, color=INK, width=1.2)
    svg.text(left + plot_w / 2, top - 16, y_label, size=11.5, color=MUTED, anchor="middle")

    for si, (name, vals) in enumerate(series):
        points = [(x_of(math.log10(s)), y_of(math.log10(max(v, floor)))) for s, v in zip(scales, vals)]
        svg.path(points, PALETTE[si % len(PALETTE)], 2.2)
        for x, y in points:
            svg.circle(x, y, 3.4, PALETTE[si % len(PALETTE)])
        lx, ly = width - right + 10, top + 18 + si * 20
        svg.line(lx, ly - 4, lx + 18, ly - 4, PALETTE[si % len(PALETTE)], 2.2)
        svg.text(lx + 24, ly, name, size=10.5, color=INK)
    svg.save(path)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = json.loads((SELECTION / "summary.json").read_text(encoding="utf-8"))
    selectors = json.loads((SELECTION / "selectors.json").read_text(encoding="utf-8"))
    audit = json.loads((ANALYSIS / "scale_term_audit.json").read_text(encoding="utf-8"))

    portfolios = list(summary["portfolios"])
    order = ["core", "with_c", "extended_c", "core_abc", "full_pool"]
    portfolios = [p for p in order if p in portfolios] + [p for p in portfolios if p not in order]

    bar_chart(
        OUT / "portfolio_vbs_sbs.svg",
        "Portfolio complementarity on 96 factorised instances",
        "VBS = per-instance best member, SBS = single best fixed rule; gap is the price of committing to one rule",
        portfolios,
        [("VBS", [summary["portfolios"][p]["vbs"] for p in portfolios]),
         ("SBS", [summary["portfolios"][p]["sbs"] for p in portfolios])],
        "total construction objective (lower is better)", fmt="{:.1f}")

    pools = [p for p in ("core", "extended_c", "full_pool") if p in selectors["portfolios"]]
    names = [row["selector"] for row in selectors["portfolios"][pools[0]]["selectors"]]
    gains = []
    for name in names:
        row_gains = []
        for pool in pools:
            match = [r for r in selectors["portfolios"][pool]["selectors"] if r["selector"] == name]
            row_gains.append(100.0 * match[0]["gain_vs_fixed"] if match else 0.0)
        gains.append((name, row_gains))

    width_groups = [f"{pool}\nVBS {selectors['portfolios'][pool]['vbs_total']:.1f}" for pool in pools]
    bar_chart(
        OUT / "selector_gain.svg",
        "Selector gain over the best fixed rule",
        "positive = the learned selector beats committing to one rule; negative = the fixed rule wins",
        width_groups, gains, "gain vs fixed best SBS (%)", fmt="{:+.2f}", zero_line=True)

    scales = [float(k) for k in audit["pooled_by_scale"]]
    keys = [f"{s:g}" for s in scales]
    log_line_chart(
        OUT / "scale_term_growth.svg",
        "How fast each non-equivariant term grows as the instance shrinks",
        "ratio of term magnitude to the base score it competes with, double-log axes",
        scales,
        [("band (relative + absolute)", [audit["pooled_by_scale"][k]["band_total_vs_base_median"] for k in keys]),
         ("-1e-6 * demand", [audit["pooled_by_scale"][k]["demand_term_vs_base_median"] for k in keys]),
         ("cap_term (capacity gap / distance)", [audit["pooled_by_scale"][k]["cap_term_vs_base_median"] for k in keys])],
        "term magnitude / median |base|  (fitted exponents "
        f"band {audit['exponents']['band_total_vs_base']:+.2f}, "
        f"demand {audit['exponents']['demand_term_vs_base']:+.2f}, "
        f"cap {audit['exponents']['cap_term_vs_base']:+.2f})")

    rules = sorted(summary["portfolio_mean"], key=lambda r: summary["portfolio_mean"][r])
    runtime = summary["mean_runtime_s"]
    bar_chart(
        OUT / "rule_mean_runtime.svg",
        "Mean objective and mean evaluation cost per rule",
        "bars = mean objective over 96 instances (lower is better); the second line under each rule is its mean seconds per evaluation",
        [f"{rule}\n{runtime[rule]*1000:.2f} ms" for rule in rules],
        [("mean objective", [summary["portfolio_mean"][r] for r in rules])],
        "mean objective", fmt="{:.2f}",
        footnotes=[
            "Frozen rules: a (2.22 ms), b (2.33 ms), c (2.62 ms) -- C is the slowest and only 6th on objective.",
            "Runtime is the wall clock of one frozen evaluation call, suite construction included.",
        ])

    index = OUT / "index.html"
    figures = sorted(p.name for p in OUT.glob("*.svg"))
    cards = "\n".join(
        f'<figure><img src="{name}" alt="{name}"><figcaption>{name}</figcaption></figure>'
        for name in figures)
    index.write_bytes(
        ("<!doctype html><meta charset=\"utf-8\"><title>cvrp midterm figures</title>"
         "<style>body{font-family:Segoe UI,sans-serif;margin:24px;color:#1c2530}"
         "figure{margin:0 0 28px}img{max-width:100%;border:1px solid #dfe4ea}"
         "figcaption{font-size:12px;color:#6a7480}</style>"
         f"<h1>cvrp midterm figures</h1>{cards}\n").encode("utf-8"))
    print("wrote", ", ".join(figures), "and index.html in", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
