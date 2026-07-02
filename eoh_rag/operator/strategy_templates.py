"""
Bounded strategy templates for Smart EOH.

This module deliberately keeps the LLM/ReAct surface small: an agent may choose
a family and a few numeric knobs, but the executable Go code is rendered from
known-safe templates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_FAMILIES = {
    "sa_exact",
    "fast_nearest",
    "balanced_delta",
    "global_delta",
    "robust_first_feasible",
}


@dataclass(frozen=True)
class StrategySpec:
    family: str = "sa_exact"
    top_k: int = 4
    pickup_weight: float = 0.03
    fallback: str = "sa_exact"
    rationale: str = ""


def _density_value(density: str) -> int:
    text = str(density).lower().strip()
    if text.startswith("d"):
        text = text[1:]
    try:
        return int(text)
    except ValueError:
        return 25


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        val = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, val))


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, val))


def normalize_strategy_spec(raw: dict[str, Any] | StrategySpec) -> StrategySpec:
    """Normalize an agent decision into the bounded strategy DSL."""
    if isinstance(raw, StrategySpec):
        raw = raw.__dict__

    family = str(raw.get("family", "sa_exact")).strip()
    reset_knobs = False
    if family not in ALLOWED_FAMILIES:
        family = "sa_exact"
        reset_knobs = True

    fallback = str(raw.get("fallback", "sa_exact")).strip()
    if fallback not in ALLOWED_FAMILIES:
        fallback = "sa_exact"

    return StrategySpec(
        family=family,
        top_k=4 if reset_knobs else _clamp_int(raw.get("top_k"), 1, 6, 4),
        pickup_weight=(
            0.03
            if reset_knobs
            else _clamp_float(raw.get("pickup_weight"), 0.0, 1.0, 0.03)
        ),
        fallback=fallback,
        rationale=str(raw.get("rationale", "")).strip(),
    )


class BoundedReactPlanner:
    """First ReAct step: observe results and choose a bounded strategy spec.

    This is intentionally deterministic for now. Once the loop is stable, an LLM
    can produce the same JSON-shaped action and pass through normalize_strategy_spec.
    """

    def decide(self, observation: dict[str, Any]) -> StrategySpec:
        failures = {
            str(item).lower()
            for item in observation.get("active_failure_patterns", [])
        }
        density = _density_value(str(observation.get("density", "d25")))
        arrival_scale = float(observation.get("arrival_scale", 1.0) or 1.0)

        if any("timeout" in item for item in failures):
            return StrategySpec(
                family="fast_nearest",
                top_k=2,
                pickup_weight=0.0,
                rationale="ReAct: timeout observed, shrink insertion search to top-2 nearest vehicles.",
            )

        if any("negative" in item or "suspicious" in item for item in failures):
            return StrategySpec(
                family="robust_first_feasible",
                top_k=4,
                pickup_weight=0.0,
                rationale="ReAct: invalid-cost pattern observed, use conservative first-feasible insertion.",
            )

        if density >= 70:
            return StrategySpec(
                family="robust_first_feasible",
                top_k=4,
                pickup_weight=0.0,
                rationale="ReAct: high dynamic density favors robust feasible insertion.",
            )

        if density >= 45:
            return StrategySpec(
                family="balanced_delta",
                top_k=3 if arrival_scale >= 0.8 else 4,
                pickup_weight=0.03,
                rationale="ReAct: medium density favors bounded insertion-delta search.",
            )

        if arrival_scale >= 0.9:
            return StrategySpec(
                family="global_delta",
                top_k=6,
                pickup_weight=0.5,
                rationale="ReAct: guard-validated d25 runs favor all-vehicle insertion-delta search.",
            )

        return StrategySpec(
            family="fast_nearest",
            top_k=2,
            pickup_weight=0.0,
            rationale="ReAct: low density favors low-latency nearest insertion.",
        )


def _fmt_weight(value: float) -> str:
    return f"{value:.6g}"


def render_strategy(spec: StrategySpec | dict[str, Any]) -> str:
    spec = normalize_strategy_spec(spec)
    if spec.family == "fast_nearest":
        return _render_fast_nearest(spec.top_k)
    if spec.family == "balanced_delta":
        return _render_balanced_delta(spec.top_k, spec.pickup_weight)
    if spec.family == "global_delta":
        return _render_global_delta(spec.pickup_weight)
    if spec.family == "robust_first_feasible":
        return _render_robust_first_feasible()
    return _render_sa_exact()


def generate_template_candidates(observation: dict[str, Any], count: int) -> list[str]:
    """Generate a small, deduplicated candidate set from bounded templates."""
    planner = BoundedReactPlanner()
    primary = planner.decide(observation)
    density = _density_value(str(observation.get("density", "d25")))
    arrival_scale = float(observation.get("arrival_scale", 1.0) or 1.0)

    specs = [primary]
    if density <= 25 and arrival_scale >= 0.9 and primary.family != "global_delta":
        specs.append(StrategySpec(family="global_delta", top_k=6, pickup_weight=0.5))
    if primary.family != "sa_exact":
        specs.append(StrategySpec(family="sa_exact", rationale="Baseline safety candidate."))
    if primary.family != "robust_first_feasible":
        specs.append(StrategySpec(family="robust_first_feasible"))
    if primary.family != "balanced_delta":
        specs.append(StrategySpec(family="balanced_delta", top_k=3, pickup_weight=0.03))
    if density > 25 and primary.family != "global_delta":
        specs.append(StrategySpec(family="global_delta", top_k=6, pickup_weight=0.5))
    if primary.family != "fast_nearest":
        specs.append(StrategySpec(family="fast_nearest", top_k=2))
    if density >= 45:
        specs.append(StrategySpec(family="balanced_delta", top_k=4, pickup_weight=0.01))

    rendered: list[str] = []
    seen: set[str] = set()
    for item in specs:
        code = render_strategy(item)
        if code in seen:
            continue
        rendered.append(code)
        seen.add(code)
        if len(rendered) >= count:
            break
    return rendered


def _render_sa_exact() -> str:
    return """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
\tvar randRange [MAXASSIGNS]int
\trandLimit := 0

\tfor ii := range randRange {
\t\trandRange[ii] = ii
\t\tif ii < dispatch.AssignsLen && dispatch.Assigns[ii].StationsLen > 0 {
\t\t\trandRange[ii], randRange[randLimit] = randRange[randLimit], ii
\t\t\trandLimit++
\t\t}
\t}
\trand.Shuffle(randLimit, func(i, j int) {
\t\trandRange[i], randRange[j] = randRange[j], randRange[i]
\t})

\tfor jj := range oris {
\t\tinserted := false
\t\tfor _, ii := range randRange {
\t\t\tif ii >= MAXASSIGNS {
\t\t\t\tcontinue
\t\t\t}
\t\t\tif !dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {
\t\t\t\tcontinue
\t\t\t}
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\tif dispatch.Assigns[ii].Cost >= 0 {
\t\t\t\tif ii >= dispatch.AssignsLen {
\t\t\t\t\tdispatch.AssignsLen = ii + 1
\t\t\t\t}
\t\t\t\tinserted = true
\t\t\t\tbreak
\t\t\t}
\t\t\tdispatch.Assigns[ii].RemoveShip(total_ship + jj)
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\tif ii >= dispatch.AssignsLen {
\t\t\t\tbreak
\t\t\t}
\t\t}
\t\tif !inserted && dispatch.AssignsLen < MAXASSIGNS {
\t\t\tii := dispatch.AssignsLen
\t\t\tif dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {
\t\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\t\tif dispatch.Assigns[ii].Cost >= 0 {
\t\t\t\t\tdispatch.AssignsLen = ii + 1
\t\t\t\t}
\t\t\t}
\t\t}
\t}
\tdispatch.RenewnTotalCost()
\treturn dispatch
}"""


def _render_fast_nearest(top_k: int) -> str:
    return f"""func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {{
\tconst topK = {top_k}

\tfor jj := range oris {{
\t\tvar topIdx [topK]int
\t\tvar topDist [topK]float64
\t\ttopLen := 0

\t\tfor ii := 0; ii < dispatch.AssignsLen; ii++ {{
\t\t\tif dispatch.Assigns[ii].StationsLen <= 0 {{
\t\t\t\tcontinue
\t\t\t}}
\t\t\tdist := cal_dis(dispatch.Assigns[ii].StationCurrent, oris[jj])
\t\t\tpos := topLen
\t\t\tif pos >= topK {{
\t\t\t\tpos = topK - 1
\t\t\t\tif dist >= topDist[pos] {{
\t\t\t\t\tcontinue
\t\t\t\t}}
\t\t\t}} else {{
\t\t\t\ttopLen++
\t\t\t}}
\t\t\tfor pos > 0 && dist < topDist[pos-1] {{
\t\t\t\ttopIdx[pos] = topIdx[pos-1]
\t\t\t\ttopDist[pos] = topDist[pos-1]
\t\t\t\tpos--
\t\t\t}}
\t\t\ttopIdx[pos] = ii
\t\t\ttopDist[pos] = dist
\t\t}}

\t\tinserted := false
\t\tfor pos := 0; pos < topLen; pos++ {{
\t\t\tii := topIdx[pos]
\t\t\tif !dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {{
\t\t\t\tcontinue
\t\t\t}}
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\tif dispatch.Assigns[ii].Cost >= 0 {{
\t\t\t\tinserted = true
\t\t\t\tbreak
\t\t\t}}
\t\t\tdispatch.Assigns[ii].RemoveShip(total_ship + jj)
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t}}
\t\tif !inserted && dispatch.AssignsLen < MAXASSIGNS {{
\t\t\tii := dispatch.AssignsLen
\t\t\tif dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {{
\t\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\t\tif dispatch.Assigns[ii].Cost >= 0 {{
\t\t\t\t\tdispatch.AssignsLen = ii + 1
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
\tdispatch.RenewnTotalCost()
\treturn dispatch
}}"""


def _render_balanced_delta(top_k: int, pickup_weight: float) -> str:
    weight = _fmt_weight(pickup_weight)
    return f"""func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {{
\tconst topK = {top_k}
\tconst pickupWeight = {weight}

\tfor jj := range oris {{
\t\tvar topIdx [topK]int
\t\tvar topDist [topK]float64
\t\ttopLen := 0

\t\tfor ii := 0; ii < dispatch.AssignsLen; ii++ {{
\t\t\tif dispatch.Assigns[ii].StationsLen <= 0 {{
\t\t\t\tcontinue
\t\t\t}}
\t\t\tdist := cal_dis(dispatch.Assigns[ii].StationCurrent, oris[jj])
\t\t\tpos := topLen
\t\t\tif pos >= topK {{
\t\t\t\tpos = topK - 1
\t\t\t\tif dist >= topDist[pos] {{
\t\t\t\t\tcontinue
\t\t\t\t}}
\t\t\t}} else {{
\t\t\t\ttopLen++
\t\t\t}}
\t\t\tfor pos > 0 && dist < topDist[pos-1] {{
\t\t\t\ttopIdx[pos] = topIdx[pos-1]
\t\t\t\ttopDist[pos] = topDist[pos-1]
\t\t\t\tpos--
\t\t\t}}
\t\t\ttopIdx[pos] = ii
\t\t\ttopDist[pos] = dist
\t\t}}

\t\tbestIdx := -1
\t\tbestScore := 1e18
\t\tfor pos := 0; pos < topLen; pos++ {{
\t\t\tii := topIdx[pos]
\t\t\toldCost := dispatch.Assigns[ii].Cost
\t\t\tif !dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {{
\t\t\t\tcontinue
\t\t\t}}
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\tnewCost := dispatch.Assigns[ii].Cost
\t\t\tif newCost >= 0 {{
\t\t\t\tscore := (newCost - oldCost) + pickupWeight*topDist[pos]
\t\t\t\tif score < bestScore {{
\t\t\t\t\tbestScore = score
\t\t\t\t\tbestIdx = ii
\t\t\t\t}}
\t\t\t}}
\t\t\tdispatch.Assigns[ii].RemoveShip(total_ship + jj)
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t}}

\t\tif bestIdx >= 0 {{
\t\t\tdispatch.Assigns[bestIdx].AddShip(total_ship+jj, oris[jj], dess[jj])
\t\t\tdispatch.Assigns[bestIdx].GenRoute()
\t\t}} else if dispatch.AssignsLen < MAXASSIGNS {{
\t\t\tii := dispatch.AssignsLen
\t\t\tif dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {{
\t\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\t\tif dispatch.Assigns[ii].Cost >= 0 {{
\t\t\t\t\tdispatch.AssignsLen = ii + 1
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
\tdispatch.RenewnTotalCost()
\treturn dispatch
}}"""


def _render_global_delta(pickup_weight: float) -> str:
    weight = _fmt_weight(pickup_weight)
    return f"""func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {{
\tconst pickupWeight = {weight}

\tfor jj := range oris {{
\t\tbestIdx := -1
\t\tbestScore := -1.0

\t\tfor ii := 0; ii < dispatch.AssignsLen; ii++ {{
\t\t\tif dispatch.Assigns[ii].StationsLen == 0 {{
\t\t\t\tcontinue
\t\t\t}}
\t\t\toldCost := dispatch.Assigns[ii].Cost
\t\t\tdistPenalty := cal_dis(dispatch.Assigns[ii].StationCurrent, oris[jj])
\t\t\tif !dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {{
\t\t\t\tdispatch.Assigns[ii].Cost = -1
\t\t\t}} else {{
\t\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\t}}
\t\t\tnewCost := dispatch.Assigns[ii].Cost
\t\t\tif newCost >= 0 {{
\t\t\t\tscore := (newCost - oldCost) + pickupWeight*distPenalty
\t\t\t\tif bestIdx == -1 || score < bestScore {{
\t\t\t\t\tbestScore = score
\t\t\t\t\tbestIdx = ii
\t\t\t\t}}
\t\t\t}}
\t\t\tdispatch.Assigns[ii].RemoveShip(total_ship + jj)
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t}}

\t\tif bestIdx >= 0 {{
\t\t\tdispatch.Assigns[bestIdx].AddShip(total_ship+jj, oris[jj], dess[jj])
\t\t\tdispatch.Assigns[bestIdx].GenRoute()
\t\t}} else {{
\t\t\tinserted := false
\t\t\tfor ii := 0; ii <= dispatch.AssignsLen && ii < MAXASSIGNS; ii++ {{
\t\t\t\tif !dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {{
\t\t\t\t\tdispatch.Assigns[ii].Cost = -1
\t\t\t\t}} else {{
\t\t\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\t\t}}
\t\t\t\tif dispatch.Assigns[ii].Cost >= 0 {{
\t\t\t\t\tif ii >= dispatch.AssignsLen {{
\t\t\t\t\t\tdispatch.AssignsLen += 1
\t\t\t\t\t}}
\t\t\t\t\tinserted = true
\t\t\t\t\tbreak
\t\t\t\t}}
\t\t\t\tdispatch.Assigns[ii].RemoveShip(total_ship + jj)
\t\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\t}}
\t\t\tif !inserted {{
\t\t\t\tclosestIdx := 0
\t\t\t\tclosestDist := -1.0
\t\t\t\tfor ii := 0; ii < dispatch.AssignsLen; ii++ {{
\t\t\t\t\tdist := cal_dis(dispatch.Assigns[ii].StationCurrent, oris[jj])
\t\t\t\t\tif closestDist < 0 || dist < closestDist {{
\t\t\t\t\t\tclosestDist = dist
\t\t\t\t\t\tclosestIdx = ii
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\tif dispatch.Assigns[closestIdx].AddShip(total_ship+jj, oris[jj], dess[jj]) {{
\t\t\t\t\tdispatch.Assigns[closestIdx].GenRoute()
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
\tdispatch.RenewnTotalCost()
\treturn dispatch
}}"""


def _render_robust_first_feasible() -> str:
    return """func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
\tvar order [MAXASSIGNS]int
\trandLimit := 0
\tfor ii := range order {
\t\torder[ii] = ii
\t\tif ii < dispatch.AssignsLen && dispatch.Assigns[ii].StationsLen > 0 {
\t\t\torder[ii], order[randLimit] = order[randLimit], ii
\t\t\trandLimit++
\t\t}
\t}
\trand.Shuffle(randLimit, func(i, j int) {
\t\torder[i], order[j] = order[j], order[i]
\t})

\tfor jj := range oris {
\t\tinserted := false
\t\tfor _, ii := range order {
\t\t\tif ii > dispatch.AssignsLen || ii >= MAXASSIGNS {
\t\t\t\tcontinue
\t\t\t}
\t\t\tif ii < dispatch.AssignsLen && dispatch.Assigns[ii].StationsLen <= 0 {
\t\t\t\tcontinue
\t\t\t}
\t\t\tif !dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {
\t\t\t\tcontinue
\t\t\t}
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\tif dispatch.Assigns[ii].Cost >= 0 {
\t\t\t\tif ii >= dispatch.AssignsLen {
\t\t\t\t\tdispatch.AssignsLen = ii + 1
\t\t\t\t}
\t\t\t\tinserted = true
\t\t\t\tbreak
\t\t\t}
\t\t\tdispatch.Assigns[ii].RemoveShip(total_ship + jj)
\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t}
\t\tif !inserted && dispatch.AssignsLen < MAXASSIGNS {
\t\t\tii := dispatch.AssignsLen
\t\t\tif dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {
\t\t\t\tdispatch.Assigns[ii].GenRoute()
\t\t\t\tif dispatch.Assigns[ii].Cost >= 0 {
\t\t\t\t\tdispatch.AssignsLen = ii + 1
\t\t\t\t}
\t\t\t}
\t\t}
\t}
\tdispatch.RenewnTotalCost()
\treturn dispatch
}"""
