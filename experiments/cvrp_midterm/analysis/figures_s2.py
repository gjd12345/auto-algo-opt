"""Render publication-grade hand-written SVG figures for Stage 2 CVRP research.

Outputs (under experiments/cvrp_midterm/analysis/figures_s2/):
1. s2_alpha_boundary.svg           : Alpha=1 phase transition + counterfactual depot-start swaps
2. s2_search_trajectory.svg        : 8-round autonomous vs control trajectory + 120-instance P0 held-out
3. s2_multiscale_complementarity.svg : Scale contraction of VBS-SBS gap + gap-to-CW across n=50/100/200
4. s2_selector_protocols.svg       : Out-of-fold selector gains & 95% Bootstrap CIs (cv12 / loro48 / loso3)

Pure Python + SVG (zero matplotlib dependency). Verified by check_figures_s2.py.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ANA = REPO / "experiments/cvrp_midterm/analysis"
SEL = REPO / "experiments/cvrp_midterm/selection_s2"
FIG_DIR = ANA / "figures_s2"

PALETTE = {
    "bg": "#ffffff",
    "ink": "#1f2937",
    "muted": "#6b7280",
    "grid": "#e5e7eb",
    "blue": "#2563eb",
    "teal": "#0d9488",
    "orange": "#ea580c",
    "red": "#dc2626",
    "purple": "#7c3aed",
    "slate": "#64748b",
    "light_blue": "#dbeafe",
    "light_teal": "#ccfbf1",
    "light_orange": "#ffedd5",
}


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def svg_wrap(w: int, h: int, body: list[str], title: str) -> str:
    header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">',
        "<style>",
        "text { font-family: 'Segoe UI', Arial, sans-serif; fill: #1f2937; }",
        ".title { font-size: 15px; font-weight: 700; }",
        ".sub { font-size: 11px; fill: #4b5563; }",
        ".axis { font-size: 10.5px; fill: #4b5563; }",
        ".lbl { font-size: 10.5px; font-weight: 600; }",
        ".val { font-size: 10px; fill: #111827; }",
        "</style>",
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="#ffffff"/>',
    ]
    return "\n".join(header + body + ["</svg>"]) + "\n"


def render_alpha_boundary() -> Path:
    data = json.loads((ANA / "boundary_analysis.json").read_text(encoding="utf-8"))
    sweep = data["alpha_sweep"]
    swaps = data["counterfactual_swaps"]

    w, h = 980, 400
    body: list[str] = [
        '<text x="24" y="28" class="title">H-003: Depot-Start Phase Transition (alpha=1) &amp; Counterfactual Depot-Start Swaps (72 multi-scale instances)</text>',
        '<text x="24" y="45" class="sub">Left: s_alpha(i,j) = d(i,j) - alpha*d(0,j) flips sign at i=0 (alpha=1), dropping route length -6.82% discontinuously. Right: swapping ONLY i=0 on frozen rules.</text>',
    ]

    # Left panel: alpha sweep curve
    lx0, lx1, ly0, ly1 = 72, 468, 78, 336
    body.append(f'<rect x="{lx0}" y="{ly0}" width="{lx1-lx0}" height="{ly1-ly0}" fill="#f9fafb" stroke="#d1d5db"/>')
    pts = [
        (0.0, sweep["alpha=0.00"]["overall_mean_obj"]),
        (0.3, sweep["alpha=0.30"]["overall_mean_obj"]),
        (0.6, sweep["alpha=0.60"]["overall_mean_obj"]),
        (0.8, sweep["alpha=0.80"]["overall_mean_obj"]),
        (0.99, sweep["alpha=0.99"]["overall_mean_obj"]),
        (1.00, sweep["alpha=1.00_tie_far"]["overall_mean_obj"]),
        (1.01, sweep["alpha=1.01"]["overall_mean_obj"]),
        (1.2, sweep["alpha=1.20"]["overall_mean_obj"]),
        (1.5, sweep["alpha=1.50"]["overall_mean_obj"]),
        (2.0, sweep["alpha=2.00"]["overall_mean_obj"]),
    ]
    y_min, y_max = 18.4, 21.0
    def sx(a: float) -> float:
        return lx0 + (a / 2.0) * (lx1 - lx0)
    def sy(v: float) -> float:
        return ly1 - ((v - y_min) / (y_max - y_min)) * (ly1 - ly0)

    for yv in (18.5, 19.0, 19.5, 20.0, 20.5, 21.0):
        yy = sy(yv)
        body.append(f'<line x1="{lx0}" y1="{yy:.1f}" x2="{lx1}" y2="{yy:.1f}" stroke="#e5e7eb"/>')
        body.append(f'<text x="{lx0-8}" y="{yy+3.5:.1f}" text-anchor="end" class="axis">{yv:.1f}</text>')
    for av in (0.0, 0.5, 1.0, 1.5, 2.0):
        xx = sx(av)
        body.append(f'<line x1="{xx:.1f}" y1="{ly0}" x2="{xx:.1f}" y2="{ly1}" stroke="#e5e7eb"/>')
        body.append(f'<text x="{xx:.1f}" y="{ly1+16}" text-anchor="middle" class="axis">{av:.1f}</text>')
    body.append(f'<text x="{(lx0+lx1)/2:.1f}" y="{ly1+36}" text-anchor="middle" class="lbl">Depot pull coefficient alpha</text>')
    body.append(f'<text x="20" y="{(ly0+ly1)/2:.1f}" text-anchor="middle" transform="rotate(-90 20 {(ly0+ly1)/2:.1f})" class="lbl">Mean route length (72 instances)</text>')

    # Vertical transition marker at alpha=1.0
    x1 = sx(1.0)
    body.append(f'<line x1="{x1:.1f}" y1="{ly0}" x2="{x1:.1f}" y2="{ly1}" stroke="{PALETTE["red"]}" stroke-dasharray="5,4" stroke-width="1.5"/>')
    body.append(f'<text x="{x1+6:.1f}" y="{ly0+16}" class="val" fill="{PALETTE["red"]}">alpha=1 sign flip</text>')
    body.append(f'<text x="{x1+6:.1f}" y="{ly0+30}" class="val" fill="{PALETTE["red"]}">20.32 -&gt; 18.91 (-6.9%)</text>')

    # Split polyline at discontinuity (alpha<=0.99 vs alpha>=1.00)
    left_pts = " ".join(f"{sx(a):.1f},{sy(v):.1f}" for a, v in pts[:5])
    right_pts = " ".join(f"{sx(a):.1f},{sy(v):.1f}" for a, v in pts[5:])
    body.append(f'<polyline points="{left_pts}" fill="none" stroke="{PALETTE["orange"]}" stroke-width="2.4"/>')
    body.append(f'<polyline points="{right_pts}" fill="none" stroke="{PALETTE["blue"]}" stroke-width="2.4"/>')
    for a, v in pts:
        col = PALETTE["orange"] if a < 1.0 else PALETTE["blue"]
        body.append(f'<circle cx="{sx(a):.1f}" cy="{sy(v):.1f}" r="3.6" fill="{col}"/>')
    # Also mark alpha=1.00_tie_near
    v_near = sweep["alpha=1.00_tie_near"]["overall_mean_obj"]
    body.append(f'<circle cx="{sx(1.0):.1f}" cy="{sy(v_near):.1f}" r="4.0" fill="#ffffff" stroke="{PALETTE["orange"]}" stroke-width="2"/>')
    body.append(f'<text x="{sx(0.45):.1f}" y="{sy(20.72):.1f}" text-anchor="middle" class="axis">Inside-out (near start)</text>')
    body.append(f'<text x="{sx(1.55):.1f}" y="{sy(18.62):.1f}" text-anchor="middle" class="axis">Outside-in (far start)</text>')

    # Right panel: counterfactual depot-start swap bars (native vs heavy_far)
    rx0, rx1, ry0, ry1 = 550, 956, 78, 336
    body.append(f'<rect x="{rx0}" y="{ry0}" width="{rx1-rx0}" height="{ry1-ry0}" fill="#f9fafb" stroke="#d1d5db"/>')
    rules = [("v0", "V0"), ("c", "C"), ("b", "B"), ("savings", "savings"), ("a", "A")]
    by_min, by_max = 18.0, 20.8
    def rsy(v: float) -> float:
        return ry1 - ((v - by_min) / (by_max - by_min)) * (ry1 - ry0)

    for yv in (18.0, 18.5, 19.0, 19.5, 20.0, 20.5):
        yy = rsy(yv)
        body.append(f'<line x1="{rx0}" y1="{yy:.1f}" x2="{rx1}" y2="{yy:.1f}" stroke="#e5e7eb"/>')
        body.append(f'<text x="{rx0-8}" y="{yy+3.5:.1f}" text-anchor="end" class="axis">{yv:.1f}</text>')

    group_w = (rx1 - rx0) / len(rules)
    bw = 26
    for idx, (rk, rlbl) in enumerate(rules):
        cx = rx0 + (idx + 0.5) * group_w
        v_nat = swaps[rk]["native"]["overall_mean_obj"]
        v_hf = swaps[rk]["heavy_far"]["overall_mean_obj"]
        y_nat = rsy(v_nat)
        y_hf = rsy(v_hf)
        body.append(f'<rect x="{cx-bw-2:.1f}" y="{y_nat:.1f}" width="{bw}" height="{ry1-y_nat:.1f}" fill="{PALETTE["slate"]}"/>')
        body.append(f'<rect x="{cx+2:.1f}" y="{y_hf:.1f}" width="{bw}" height="{ry1-y_hf:.1f}" fill="{PALETTE["teal"]}"/>')
        body.append(f'<text x="{cx-bw/2-2:.1f}" y="{y_nat-5:.1f}" text-anchor="middle" class="val">{v_nat:.2f}</text>')
        body.append(f'<text x="{cx+bw/2+2:.1f}" y="{y_hf-5:.1f}" text-anchor="middle" class="val">{v_hf:.2f}</text>')
        body.append(f'<text x="{cx:.1f}" y="{ry1+16}" text-anchor="middle" class="lbl">{esc(rlbl)}</text>')

    # Legend right panel
    body.append(f'<rect x="{rx0+12}" y="{ry0+10}" width="12" height="10" fill="{PALETTE["slate"]}"/>')
    body.append(f'<text x="{rx0+28}" y="{ry0+19}" class="axis">Native depot-start</text>')
    body.append(f'<rect x="{rx0+155}" y="{ry0+10}" width="12" height="10" fill="{PALETTE["teal"]}"/>')
    body.append(f'<text x="{rx0+171}" y="{ry0+19}" class="axis">Swapped to heavy_far (i=0 only)</text>')
    body.append(f'<text x="{(rx0+rx1)/2:.1f}" y="{ry1+36}" text-anchor="middle" class="lbl">Frozen rule (mid-route steps unchanged)</text>')

    out = FIG_DIR / "s2_alpha_boundary.svg"
    out.write_text(svg_wrap(w, h, body, "Depot-start phase transition and counterfactual swaps"), encoding="utf-8")
    return out


def render_search_trajectory() -> Path:
    data = json.loads((ANA / "s2_holdout_eval.json").read_text(encoding="utf-8"))
    auto_tr = data["auto_arm"]["trajectory"]
    ctrl_tr = data["ctrl_arm"]["trajectory"]
    res = data["results"]

    w, h = 1000, 420
    body: list[str] = [
        '<text x="24" y="28" class="title">Stage 2 Track A: 8-Round Autonomous Math Search vs Paired Control &amp; 120-Instance P0 Held-Out</text>',
        '<text x="24" y="45" class="sub">Identical explicit seeds [C,A,B,V0], budget (48 req/arm), model (deepseek-flash). Left: dev4 gap trajectory. Right: unseen P0 multi-scale mean (n=50/100/200).</text>',
    ]

    # Left panel: 8-round trajectory (incumbent & best generated per round)
    lx0, lx1, ly0, ly1 = 72, 475, 80, 348
    body.append(f'<rect x="{lx0}" y="{ly0}" width="{lx1-lx0}" height="{ly1-ly0}" fill="#f9fafb" stroke="#d1d5db"/>')
    y_min, y_max = -17.0, -4.0  # percent vs NN baseline
    def sx(r: int) -> float:
        return lx0 + ((r - 1) / 7.0) * (lx1 - lx0)
    def sy(pct: float) -> float:
        return ly1 - ((pct - y_min) / (y_max - y_min)) * (ly1 - ly0)

    for pv in (-16, -14, -12, -10, -8, -6, -4):
        yy = sy(pv)
        body.append(f'<line x1="{lx0}" y1="{yy:.1f}" x2="{lx1}" y2="{yy:.1f}" stroke="#e5e7eb"/>')
        body.append(f'<text x="{lx0-8}" y="{yy+3.5:.1f}" text-anchor="end" class="axis">{pv}%</text>')
    for r in range(1, 9):
        xx = sx(r)
        body.append(f'<line x1="{xx:.1f}" y1="{ly0}" x2="{xx:.1f}" y2="{ly1}" stroke="#e5e7eb"/>')
        body.append(f'<text x="{xx:.1f}" y="{ly1+16}" text-anchor="middle" class="axis">R{r}</text>')

    # Frozen C reference line (-10.89%)
    yc = sy(-10.89)
    body.append(f'<line x1="{lx0}" y1="{yc:.1f}" x2="{lx1}" y2="{yc:.1f}" stroke="{PALETTE["red"]}" stroke-dasharray="5,4" stroke-width="1.4"/>')
    body.append(f'<text x="{lx1-4}" y="{yc-5:.1f}" text-anchor="end" class="val" fill="{PALETTE["red"]}">Frozen C seed (-10.89%)</text>')

    # Incumbent curves
    a_inc_pts = " ".join(f"{sx(t['round_id']):.1f},{sy(t['incumbent_gap']*100.0):.1f}" for t in auto_tr)
    c_inc_pts = " ".join(f"{sx(t['round_id']):.1f},{sy(t['incumbent_gap']*100.0):.1f}" for t in ctrl_tr)
    body.append(f'<polyline points="{c_inc_pts}" fill="none" stroke="{PALETTE["slate"]}" stroke-width="2.2" stroke-dasharray="4,3"/>')
    body.append(f'<polyline points="{a_inc_pts}" fill="none" stroke="{PALETTE["blue"]}" stroke-width="2.6"/>')

    # Best generated per round dots (auto = teal circles, ctrl = gray squares)
    for t in auto_tr:
        bg = t.get("best_generated_gap")
        if bg is not None:
            pct = max(y_min, min(y_max, bg * 100.0))
            body.append(f'<circle cx="{sx(t["round_id"]):.1f}" cy="{sy(pct):.1f}" r="4.0" fill="{PALETTE["teal"]}"/>')
        else:
            # Round 6 AST fail marker
            body.append(f'<text x="{sx(t["round_id"]):.1f}" y="{ly0+16}" text-anchor="middle" class="val" fill="{PALETTE["orange"]}">R6 AST 0/5</text>')
    for t in ctrl_tr:
        bg = t.get("best_generated_gap")
        if bg is not None:
            pct = max(y_min, min(y_max, bg * 100.0))
            x, y = sx(t["round_id"]), sy(pct)
            body.append(f'<rect x="{x-3.2:.1f}" y="{y-3.2:.1f}" width="6.4" height="6.4" fill="{PALETTE["slate"]}"/>')

    # Key annotations on left panel
    body.append(f'<text x="{sx(3):.1f}" y="{sy(-15.76)+15:.1f}" text-anchor="middle" class="val" fill="{PALETTE["blue"]}">-15.76% (R3)</text>')
    body.append(f'<text x="{sx(7):.1f}" y="{sy(-15.27)+15:.1f}" text-anchor="middle" class="val" fill="{PALETTE["teal"]}">-15.27% (R7)</text>')

    # Legend left panel
    body.append(f'<line x1="{lx0+10}" y1="{ly0+16}" x2="{lx0+30}" y2="{ly0+16}" stroke="{PALETTE["blue"]}" stroke-width="2.6"/>')
    body.append(f'<text x="{lx0+35}" y="{ly0+20}" class="axis">Auto math incumbent</text>')
    body.append(f'<circle cx="{lx0+20}" cy="{ly0+33}" r="3.8" fill="{PALETTE["teal"]}"/>')
    body.append(f'<text x="{lx0+35}" y="{ly0+37}" class="axis">Auto round best generated</text>')
    body.append(f'<rect x="{lx0+17}" y="{ly0+46}" width="6.4" height="6.4" fill="{PALETTE["slate"]}"/>')
    body.append(f'<text x="{lx0+35}" y="{ly0+53}" class="axis">Control round best (never beats C)</text>')
    body.append(f'<text x="{(lx0+lx1)/2:.1f}" y="{ly1+38}" text-anchor="middle" class="lbl">Search Round (6 requests/round, 48 total)</text>')
    body.append(f'<text x="20" y="{(ly0+ly1)/2:.1f}" text-anchor="middle" transform="rotate(-90 20 {(ly0+ly1)/2:.1f})" class="lbl">dev4 gap vs NN (lower is better)</text>')

    # Right panel: 120-instance unseen P0 held-out horizontal bars
    rx0, rx1, ry0, ry1 = 625, 965, 80, 348
    body.append(f'<rect x="{rx0}" y="{ry0}" width="{rx1-rx0}" height="{ry1-ry0}" fill="#f9fafb" stroke="#d1d5db"/>')

    auto_dev = data["auto_dev_best"]
    auto_ana = data["auto_ana_best"]
    ctrl_dev = data["ctrl_dev_best"]
    ctrl_ana = data["ctrl_ana_best"]
    bar_keys = [
        ("cw_merge_ref", "CW merge (ref)", PALETTE["purple"]),
        (auto_ana, f"Auto ana72 ({auto_ana})", PALETTE["teal"]),
        ("V0_decoupled_theory", "V0 decoupled (H-003)", PALETTE["blue"]),
        (auto_dev, f"Auto dev4 ({auto_dev})", PALETTE["blue"]),
        (ctrl_ana, f"Ctrl ana72 ({ctrl_ana})", PALETTE["slate"]),
        ("savings", "savings (pointwise)", PALETTE["slate"]),
        ("A", "Frozen A", PALETTE["slate"]),
        ("B", "Frozen B", PALETTE["slate"]),
        ("C", "Frozen C", PALETTE["orange"]),
        ("NN", "NN baseline", "#9ca3af"),
    ]
    # Deduplicate if auto_ana == auto_dev or ctrl_ana == ctrl_dev
    seen_k: set[str] = set()
    bars = []
    for k, lbl, col in bar_keys:
        if k and k in res and k not in seen_k:
            seen_k.add(k)
            bars.append((k, lbl, col, float(res[k]["p0_120_mean"])))

    xmin, xmax = 17.0, 24.5
    def rsx(v: float) -> float:
        return rx0 + ((v - xmin) / (xmax - xmin)) * (rx1 - rx0)

    for xv in (18, 19, 20, 21, 22, 23, 24):
        xx = rsx(xv)
        body.append(f'<line x1="{xx:.1f}" y1="{ry0}" x2="{xx:.1f}" y2="{ry1}" stroke="#e5e7eb"/>')
        body.append(f'<text x="{xx:.1f}" y="{ry1+16}" text-anchor="middle" class="axis">{xv}</text>')

    row_h = (ry1 - ry0) / len(bars)
    for idx, (k, lbl, col, val) in enumerate(bars):
        yy = ry0 + idx * row_h + 4
        bh = max(12.0, row_h - 8)
        bw = max(2.0, rsx(val) - rx0)
        body.append(f'<rect x="{rx0}" y="{yy:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{col}"/>')
        body.append(f'<text x="{rx0-6}" y="{yy+bh*0.72:.1f}" text-anchor="end" class="axis">{esc(lbl)}</text>')
        body.append(f'<text x="{rx0+bw+4:.1f}" y="{yy+bh*0.72:.1f}" class="val">{val:.2f}</text>')

    body.append(f'<text x="{(rx0+rx1)/2:.1f}" y="{ry1+38}" text-anchor="middle" class="lbl">Mean tour length on 120 unseen P0 instances (lower is better)</text>')

    out = FIG_DIR / "s2_search_trajectory.svg"
    out.write_text(svg_wrap(w, h, body, "Stage 2 autonomous search trajectory and P0 held-out results"), encoding="utf-8")
    return out


def render_multiscale_complementarity() -> Path:
    summary = json.loads((SEL / "summary_s2.json").read_text(encoding="utf-8"))
    by_scale = summary["by_scale"]
    has_plus = "pointwise_plus_s2" in summary["overall"]["portfolios"]

    w, h = 980, 390
    body: list[str] = [
        '<text x="24" y="28" class="title">Stage 2 Track B: Multi-Scale Complementarity Contraction &amp; Gap to Clarke-Wright Merge (288 instances)</text>',
        '<text x="24" y="45" class="sub">Left: VBS-SBS complementarity gap shrinks strongly with problem size n=50-&gt;100-&gt;200. Right: % gap above parallel Clarke-Wright merge.</text>',
    ]

    # Left panel: VBS-SBS gap (%) by scale
    lx0, lx1, ly0, ly1 = 72, 445, 80, 326
    body.append(f'<rect x="{lx0}" y="{ly0}" width="{lx1-lx0}" height="{ly1-ly0}" fill="#f9fafb" stroke="#d1d5db"/>')
    scales = ("50", "100", "200")
    max_gap = max(
        by_scale[s]["portfolios"][p]["sbs_gap_to_vbs"] * 100.0
        for s in scales
        for p in by_scale[s]["portfolios"]
    )
    y_max = max(4.5, round(max_gap + 0.8, 1))
    def sy(v: float) -> float:
        return ly1 - (v / y_max) * (ly1 - ly0)

    for yv in (0.0, 1.0, 2.0, 3.0, 4.0):
        if yv <= y_max:
            yy = sy(yv)
            body.append(f'<line x1="{lx0}" y1="{yy:.1f}" x2="{lx1}" y2="{yy:.1f}" stroke="#e5e7eb"/>')
            body.append(f'<text x="{lx0-8}" y="{yy+3.5:.1f}" text-anchor="end" class="axis">{yv:.1f}%</text>')

    gw = (lx1 - lx0) / 3.0
    bw = 34 if has_plus else 48
    for idx, sz in enumerate(scales):
        cx = lx0 + (idx + 0.5) * gw
        g_base = by_scale[sz]["portfolios"]["pointwise_base"]["sbs_gap_to_vbs"] * 100.0
        if has_plus:
            g_plus = by_scale[sz]["portfolios"]["pointwise_plus_s2"]["sbs_gap_to_vbs"] * 100.0
            yb, yp = sy(g_base), sy(g_plus)
            body.append(f'<rect x="{cx-bw-3:.1f}" y="{yb:.1f}" width="{bw}" height="{ly1-yb:.1f}" fill="{PALETTE["slate"]}"/>')
            body.append(f'<rect x="{cx+3:.1f}" y="{yp:.1f}" width="{bw}" height="{ly1-yp:.1f}" fill="{PALETTE["teal"]}"/>')
            body.append(f'<text x="{cx-bw/2-3:.1f}" y="{yb-5:.1f}" text-anchor="middle" class="val">{g_base:.2f}%</text>')
            body.append(f'<text x="{cx+bw/2+3:.1f}" y="{yp-5:.1f}" text-anchor="middle" class="val">{g_plus:.2f}%</text>')
        else:
            yb = sy(g_base)
            body.append(f'<rect x="{cx-bw/2:.1f}" y="{yb:.1f}" width="{bw}" height="{ly1-yb:.1f}" fill="{PALETTE["blue"]}"/>')
            body.append(f'<text x="{cx:.1f}" y="{yb-5:.1f}" text-anchor="middle" class="val">{g_base:.2f}%</text>')
        body.append(f'<text x="{cx:.1f}" y="{ly1+18}" text-anchor="middle" class="lbl">n = {sz}</text>')

    if has_plus:
        body.append(f'<rect x="{lx0+12}" y="{ly0+10}" width="12" height="10" fill="{PALETTE["slate"]}"/>')
        body.append(f'<text x="{lx0+28}" y="{ly0+19}" class="axis">Base pool (8 rules)</text>')
        body.append(f'<rect x="{lx0+150}" y="{ly0+10}" width="12" height="10" fill="{PALETTE["teal"]}"/>')
        body.append(f'<text x="{lx0+166}" y="{ly0+19}" class="axis">+ Stage 2 rules</text>')
    body.append(f'<text x="{(lx0+lx1)/2:.1f}" y="{ly1+40}" text-anchor="middle" class="lbl">Problem size (96 instances per scale)</text>')
    body.append(f'<text x="20" y="{(ly0+ly1)/2:.1f}" text-anchor="middle" transform="rotate(-90 20 {(ly0+ly1)/2:.1f})" class="lbl">SBS gap to VBS (%)</text>')

    # Right panel: % gap above parallel Clarke-Wright merge across n=50, 100, 200
    rx0, rx1, ry0, ry1 = 530, 956, 80, 326
    body.append(f'<rect x="{rx0}" y="{ry0}" width="{rx1-rx0}" height="{ry1-ry0}" fill="#f9fafb" stroke="#d1d5db"/>')

    extra = summary.get("extra_members") or []
    show_rules = [("c", "Frozen C", PALETTE["orange"]), ("b", "Frozen B", PALETTE["slate"]), ("savings", "savings", PALETTE["blue"])]
    if extra:
        # Pick best overall extra rule from summary
        best_extra = min(extra, key=lambda n: summary["overall"]["rule_mean"][n])
        show_rules.append((best_extra, f"Stage 2 ({best_extra})", PALETTE["teal"]))

    # Compute % excess over cw_merge
    series_vals: dict[str, list[float]] = {}
    max_exc = 0.0
    for rk, _, _ in show_rules:
        vals = []
        for sz in scales:
            cw = by_scale[sz]["cw_merge_mean"]
            rm = by_scale[sz]["rule_mean"][rk]
            exc = (rm - cw) / cw * 100.0
            vals.append(exc)
            max_exc = max(max_exc, exc)
        series_vals[rk] = vals

    ry_max = max(25.0, round(max_exc + 3.0, 0))
    def rsy(v: float) -> float:
        return ry1 - (v / ry_max) * (ry1 - ry0)
    def rsx(idx: int) -> float:
        return rx0 + 45 + idx * ((rx1 - rx0 - 90) / 2.0)

    for yv in (0, 5, 10, 15, 20, 25):
        if yv <= ry_max:
            yy = rsy(yv)
            body.append(f'<line x1="{rx0}" y1="{yy:.1f}" x2="{rx1}" y2="{yy:.1f}" stroke="#e5e7eb"/>')
            body.append(f'<text x="{rx0-8}" y="{yy+3.5:.1f}" text-anchor="end" class="axis">+{yv}%</text>')
    for idx, sz in enumerate(scales):
        xx = rsx(idx)
        body.append(f'<text x="{xx:.1f}" y="{ry1+18}" text-anchor="middle" class="lbl">n = {sz}</text>')

    for idx_r, (rk, rlbl, col) in enumerate(show_rules):
        vals = series_vals[rk]
        pts = " ".join(f"{rsx(i):.1f},{rsy(v):.1f}" for i, v in enumerate(vals))
        body.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.4"/>')
        for i, v in enumerate(vals):
            body.append(f'<circle cx="{rsx(i):.1f}" cy="{rsy(v):.1f}" r="3.8" fill="{col}"/>')
            dy = -7 if idx_r != 1 else 13
            body.append(f'<text x="{rsx(i):.1f}" y="{rsy(v)+dy:.1f}" text-anchor="middle" class="val" fill="{col}">+{v:.1f}%</text>')
        ly_leg = ry0 + 14 + idx_r * 15
        body.append(f'<line x1="{rx0+12}" y1="{ly_leg}" x2="{rx0+30}" y2="{ly_leg}" stroke="{col}" stroke-width="2.4"/>')
        body.append(f'<text x="{rx0+35}" y="{ly_leg+3.5}" class="axis">{esc(rlbl)}</text>')

    body.append(f'<text x="{(rx0+rx1)/2:.1f}" y="{ry1+40}" text-anchor="middle" class="lbl">% route length above parallel Clarke-Wright merge</text>')

    out = FIG_DIR / "s2_multiscale_complementarity.svg"
    out.write_text(svg_wrap(w, h, body, "Multi-scale complementarity contraction and Clarke-Wright gap"), encoding="utf-8")
    return out


def render_selector_protocols() -> Path:
    data = json.loads((SEL / "selectors_s2.json").read_text(encoding="utf-8"))
    pname = "pointwise_plus_s2" if "pointwise_plus_s2" in data["portfolios"] else "pointwise_base"
    pdata = data["portfolios"][pname]
    protos = pdata["protocols"]

    w, h = 960, 420
    body: list[str] = [
        f'<text x="24" y="28" class="title">Stage 2 Track B: Out-of-Fold Selector Gain vs SBS with 95% Paired Bootstrap CIs ({esc(pname)}, 288 inst)</text>',
        f'<text x="24" y="45" class="sub">Global SBS = {esc(pdata["global_sbs_rule"])} (gap to VBS = {pdata["global_sbs_gap_to_vbs"]*100:.2f}%). Positive gain = shorter routes than in-fold SBS across cv12, loro48, loso3.</text>',
    ]

    x0, x1, y0, y1 = 155, 920, 76, 354
    body.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="#f9fafb" stroke="#d1d5db"/>')

    sels = ["ridge", "pairwise_cs", "pairwise_plain", "rf_reg", "rf_pairwise_cs", "knn5", "stump_1d"]
    p_styles = [
        ("cv12", "12-fold CV (within-dist)", PALETTE["blue"], -10),
        ("loro48", "48-fold LORO (unseen cell)", PALETTE["teal"], 0),
        ("loso3", "3-fold LOSO (unseen scale)", PALETTE["orange"], 10),
    ]

    all_vals = []
    for s in sels:
        for pk, _, _, _ in p_styles:
            m = protos[pk][s]
            all_vals.extend([m["gain_vs_fixed"] * 100.0, m["gain_ci95"][0] * 100.0, m["gain_ci95"][1] * 100.0])
    xmin = min(-1.2, round(min(all_vals) - 0.25, 1))
    xmax = max(1.0, round(max(all_vals) + 0.35, 1))
    def sx(v: float) -> float:
        return x0 + ((v - xmin) / (xmax - xmin)) * (x1 - x0)

    # Grid & zero line
    step = 0.5
    v_cur = round(xmin * 2) / 2
    while v_cur <= xmax + 1e-9:
        xx = sx(v_cur)
        if x0 <= xx <= x1:
            is_zero = abs(v_cur) < 1e-9
            stroke = "#374151" if is_zero else "#e5e7eb"
            sw = "1.5" if is_zero else "1.0"
            dash = ' stroke-dasharray="4,3"' if is_zero else ""
            body.append(f'<line x1="{xx:.1f}" y1="{y0}" x2="{xx:.1f}" y2="{y1}" stroke="{stroke}" stroke-width="{sw}"{dash}/>')
            body.append(f'<text x="{xx:.1f}" y="{y1+16}" text-anchor="middle" class="axis">{v_cur:+.1f}%</text>')
        v_cur += step

    row_h = (y1 - y0) / len(sels)
    for idx, sel in enumerate(sels):
        cy = y0 + (idx + 0.5) * row_h
        if idx > 0:
            body.append(f'<line x1="{x0}" y1="{y0 + idx*row_h:.1f}" x2="{x1}" y2="{y0 + idx*row_h:.1f}" stroke="#eef2f7"/>')
        body.append(f'<text x="{x0-10}" y="{cy+4:.1f}" text-anchor="end" class="lbl">{esc(sel)}</text>')
        for pk, _, col, dy in p_styles:
            m = protos[pk][sel]
            g = m["gain_vs_fixed"] * 100.0
            lo = m["gain_ci95"][0] * 100.0
            hi = m["gain_ci95"][1] * 100.0
            yy = cy + dy
            body.append(f'<line x1="{sx(lo):.1f}" y1="{yy:.1f}" x2="{sx(hi):.1f}" y2="{yy:.1f}" stroke="{col}" stroke-width="1.8"/>')
            body.append(f'<line x1="{sx(lo):.1f}" y1="{yy-3:.1f}" x2="{sx(lo):.1f}" y2="{yy+3:.1f}" stroke="{col}" stroke-width="1.5"/>')
            body.append(f'<line x1="{sx(hi):.1f}" y1="{yy-3:.1f}" x2="{sx(hi):.1f}" y2="{yy+3:.1f}" stroke="{col}" stroke-width="1.5"/>')
            body.append(f'<circle cx="{sx(g):.1f}" cy="{yy:.1f}" r="3.6" fill="{col}"/>')
            body.append(f'<text x="{sx(hi)+5:.1f}" y="{yy+3.2:.1f}" class="val" fill="{col}">{g:+.2f}%</text>')

    # Legend
    lx = x0 + 12
    for pk, plbl, col, _ in p_styles:
        body.append(f'<circle cx="{lx}" cy="395" r="4.0" fill="{col}"/>')
        body.append(f'<text x="{lx+9}" y="399" class="axis">{esc(plbl)}</text>')
        lx += 230
    body.append(f'<text x="{(x0+x1)/2:.1f}" y="{y1+34}" text-anchor="middle" class="lbl">Gain vs In-Fold Single Best Solver (%) with 95% Bootstrap CI</text>')

    out = FIG_DIR / "s2_selector_protocols.svg"
    out.write_text(svg_wrap(w, h, body, "Out-of-fold selector gain across cv12, loro48, and loso3"), encoding="utf-8")
    return out


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        render_alpha_boundary(),
        render_search_trajectory(),
        render_multiscale_complementarity(),
        render_selector_protocols(),
    ]
    print(json.dumps({"rendered": [str(p.relative_to(REPO)).replace("\\", "/") for p in outputs]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
