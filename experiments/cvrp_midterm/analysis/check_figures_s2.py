"""Structural and numeric consistency self-check for Stage 2 SVG figures."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ANA = REPO / "experiments/cvrp_midterm/analysis"
SEL = REPO / "experiments/cvrp_midterm/selection_s2"
FIG_DIR = ANA / "figures_s2"


def check_svg_xml(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    w = float(root.attrib["width"])
    h = float(root.attrib["height"])
    assert w > 0 and h > 0, f"bad dims in {path}"
    for elem in root.iter():
        tag = elem.tag.split("}")[-1]
        if tag == "rect":
            rw = float(elem.attrib.get("width", 0))
            rh = float(elem.attrib.get("height", 0))
            assert rw >= 0 and rh >= 0, f"negative rect in {path}"
        elif tag == "circle":
            cx = float(elem.attrib.get("cx", 0))
            cy = float(elem.attrib.get("cy", 0))
            assert -5 <= cx <= w + 5 and -5 <= cy <= h + 5, f"circle OOB in {path}: ({cx},{cy})"
    return text


def main() -> int:
    bdata = json.loads((ANA / "boundary_analysis.json").read_text(encoding="utf-8"))
    hdata = json.loads((ANA / "s2_holdout_eval.json").read_text(encoding="utf-8"))
    sdata = json.loads((SEL / "summary_s2.json").read_text(encoding="utf-8"))
    seldata = json.loads((SEL / "selectors_s2.json").read_text(encoding="utf-8"))

    # 1. s2_alpha_boundary.svg
    t1 = check_svg_xml(FIG_DIR / "s2_alpha_boundary.svg")
    v0_nat = f'{bdata["counterfactual_swaps"]["v0"]["native"]["overall_mean_obj"]:.2f}'
    v0_hf = f'{bdata["counterfactual_swaps"]["v0"]["heavy_far"]["overall_mean_obj"]:.2f}'
    assert v0_nat in t1 and v0_hf in t1, f"missing V0 swap values {v0_nat}/{v0_hf}"

    # 2. s2_search_trajectory.svg
    t2 = check_svg_xml(FIG_DIR / "s2_search_trajectory.svg")
    cw_p0 = f'{hdata["results"]["cw_merge_ref"]["p0_120_mean"]:.2f}'
    a_p0 = f'{hdata["results"]["A"]["p0_120_mean"]:.2f}'
    assert cw_p0 in t2 and a_p0 in t2, f"missing P0 means {cw_p0}/{a_p0}"

    # 3. s2_multiscale_complementarity.svg
    t3 = check_svg_xml(FIG_DIR / "s2_multiscale_complementarity.svg")
    g50 = f'{sdata["by_scale"]["50"]["portfolios"]["pointwise_base"]["sbs_gap_to_vbs"]*100:.2f}%'
    g200 = f'{sdata["by_scale"]["200"]["portfolios"]["pointwise_base"]["sbs_gap_to_vbs"]*100:.2f}%'
    assert g50 in t3 and g200 in t3, f"missing scale gaps {g50}/{g200}"

    # 4. s2_selector_protocols.svg
    t4 = check_svg_xml(FIG_DIR / "s2_selector_protocols.svg")
    pname = "pointwise_plus_s2" if "pointwise_plus_s2" in seldata["portfolios"] else "pointwise_base"
    r_cv = f'{seldata["portfolios"][pname]["protocols"]["cv12"]["ridge"]["gain_vs_fixed"]*100:+.2f}%'
    r_loso = f'{seldata["portfolios"][pname]["protocols"]["loso3"]["ridge"]["gain_vs_fixed"]*100:+.2f}%'
    assert r_cv in t4 and r_loso in t4, f"missing selector gains {r_cv}/{r_loso}"

    print(json.dumps({
        "ok": True,
        "checked": [
            "s2_alpha_boundary.svg",
            "s2_search_trajectory.svg",
            "s2_multiscale_complementarity.svg",
            "s2_selector_protocols.svg",
        ],
        "verified_numbers": {
            "v0_native_vs_hf": [v0_nat, v0_hf],
            "p0_cw_vs_A": [cw_p0, a_p0],
            "gap_n50_vs_n200": [g50, g200],
            "ridge_cv12_vs_loso3": [r_cv, r_loso],
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
