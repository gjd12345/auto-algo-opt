"""
模块：strategy_templates（有界策略模板）
功能：把智能体（LLM/ReAct）的自由发挥限制在很小的范围内——它只能挑选一个策略族
      和几个数值旋钮，真正可执行的 Go 代码由本模块内已知安全的模板渲染而成。
职责：定义允许的策略族集合与策略规格数据类；把外部（可能不可信）的决策规范化为
      有界的策略 DSL；根据观测确定性地推荐策略；并把策略规格渲染成 InsertShips 的
      Go 源码字符串。
接口：
      - StrategySpec：冻结的数据类，描述一个策略（族、top_k、pickup_weight 等）。
      - normalize_strategy_spec(raw) -> StrategySpec：把 dict/StrategySpec 收敛到合法范围。
      - BoundedReactPlanner.decide(observation) -> StrategySpec：根据观测选策略。
      - render_strategy(spec) -> str：把策略规格渲染成 Go 代码字符串。
      - generate_template_candidates(observation, count) -> list[str]：生成去重后的候选代码集合。
输入：observation 字典（含 density、arrival_scale、active_failure_patterns 等观测字段）；
      或一个策略规格（dict 或 StrategySpec）。
输出：合法的 StrategySpec 对象，或可直接使用的 InsertShips Go 源码字符串（列表）。
示例：
      >>> code = render_strategy({"family": "fast_nearest", "top_k": 2})
      >>> code.startswith("func InsertShips")
      True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# 允许的策略族白名单：任何族名不在此集合内的输入都会被回退到 "sa_exact"，
# 从而保证只会渲染出本模块中已知安全的模板。
ALLOWED_FAMILIES = {
    "sa_exact",
    "fast_nearest",
    "balanced_delta",
    "global_delta",
    "robust_first_feasible",
}


@dataclass(frozen=True)
class StrategySpec:
    """一个有界策略的完整描述（不可变数据类）。

    字段：
        family：策略族名，必须属于 ALLOWED_FAMILIES。
        top_k：候选车辆的搜索宽度（只在部分族中生效）。
        pickup_weight：接单距离在打分中的权重（只在 delta 类族中生效）。
        fallback：无法执行时回退到的策略族名。
        rationale：选择该策略的理由说明（仅用于记录/调试，不影响渲染逻辑）。
    """

    family: str = "sa_exact"
    top_k: int = 4
    pickup_weight: float = 0.03
    fallback: str = "sa_exact"
    rationale: str = ""


def _density_value(density: str) -> int:
    """把密度标签解析成整数。

    接受形如 "d25"/"D70" 的字符串（去掉前缀 "d" 后取数字），也接受纯数字字符串。
    无法解析时回退到默认值 25。
    """
    text = str(density).lower().strip()
    if text.startswith("d"):
        text = text[1:]  # 去掉密度标签的 "d" 前缀，例如 "d25" -> "25"
    try:
        return int(text)
    except ValueError:
        return 25


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    """把任意输入转成整数并夹到 [lo, hi] 区间；无法转换时返回 default。"""
    try:
        val = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, val))


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    """把任意输入转成浮点数并夹到 [lo, hi] 区间；无法转换时返回 default。"""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, val))


def normalize_strategy_spec(raw: dict[str, Any] | StrategySpec) -> StrategySpec:
    """把智能体的决策收敛成合法且有界的策略 DSL。

    对传入的 dict 或 StrategySpec 逐字段校验：族名与回退族名都必须在白名单内，
    否则回退到 "sa_exact"；数值旋钮都会被夹到安全区间。一旦族名非法（reset_knobs），
    旋钮也会一并重置为默认值，避免不可信输入造成异常行为。

    返回：一个字段都在合法范围内的 StrategySpec。
    """
    if isinstance(raw, StrategySpec):
        raw = raw.__dict__

    family = str(raw.get("family", "sa_exact")).strip()
    reset_knobs = False
    if family not in ALLOWED_FAMILIES:
        # 族名非法：回退到默认族，并标记为需要连同旋钮一起重置。
        family = "sa_exact"
        reset_knobs = True

    fallback = str(raw.get("fallback", "sa_exact")).strip()
    if fallback not in ALLOWED_FAMILIES:
        fallback = "sa_exact"

    return StrategySpec(
        family=family,
        # 族名非法时旋钮用默认值；否则把输入夹到安全区间。
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
    """ReAct 第一步：观察运行结果，选出一个有界的策略规格。

    目前的决策规则是确定性的（基于观测的一串 if 判断）。当整个循环稳定后，LLM
    可以产出同样 JSON 形状的动作，并同样经由 normalize_strategy_spec 收敛。
    """

    def decide(self, observation: dict[str, Any]) -> StrategySpec:
        """根据观测选择策略规格。

        观测字段：
            active_failure_patterns：当前活跃的失败模式（如超时、非法成本）。
            density：动态密度标签（如 "d25"）。
            arrival_scale：到达率缩放系数。

        规则优先级（自上而下）：超时 -> 非法成本 -> 高密度 -> 中密度 ->
        高到达率 -> 兜底低延迟策略。返回对应的 StrategySpec。
        """
        failures = {
            str(item).lower()
            for item in observation.get("active_failure_patterns", [])
        }
        density = _density_value(str(observation.get("density", "d25")))
        arrival_scale = float(observation.get("arrival_scale", 1.0) or 1.0)

        # 出现超时：收窄插入搜索，只看最近的 2 辆车以降低耗时。
        if any("timeout" in item for item in failures):
            return StrategySpec(
                family="fast_nearest",
                top_k=2,
                pickup_weight=0.0,
                rationale="ReAct: timeout observed, shrink insertion search to top-2 nearest vehicles.",
            )

        # 出现负成本/可疑成本：改用保守的“首个可行位”插入。
        if any("negative" in item or "suspicious" in item for item in failures):
            return StrategySpec(
                family="robust_first_feasible",
                top_k=4,
                pickup_weight=0.0,
                rationale="ReAct: invalid-cost pattern observed, use conservative first-feasible insertion.",
            )

        # 高密度：优先鲁棒可行插入。
        if density >= 70:
            return StrategySpec(
                family="robust_first_feasible",
                top_k=4,
                pickup_weight=0.0,
                rationale="ReAct: high dynamic density favors robust feasible insertion.",
            )

        # 中密度：使用有界的插入增量（delta）搜索。
        if density >= 45:
            return StrategySpec(
                family="balanced_delta",
                top_k=3 if arrival_scale >= 0.8 else 4,
                pickup_weight=0.03,
                rationale="ReAct: medium density favors bounded insertion-delta search.",
            )

        # 低密度但到达率高：放开到全车辆的插入增量搜索。
        if arrival_scale >= 0.9:
            return StrategySpec(
                family="global_delta",
                top_k=6,
                pickup_weight=0.5,
                rationale="ReAct: guard-validated d25 runs favor all-vehicle insertion-delta search.",
            )

        # 兜底：低密度场景用低延迟的最近插入。
        return StrategySpec(
            family="fast_nearest",
            top_k=2,
            pickup_weight=0.0,
            rationale="ReAct: low density favors low-latency nearest insertion.",
        )


def _fmt_weight(value: float) -> str:
    """把浮点权重格式化成紧凑字符串（用于嵌入生成的 Go 代码）。"""
    return f"{value:.6g}"


def render_strategy(spec: StrategySpec | dict[str, Any]) -> str:
    """把策略规格渲染成一段可执行的 InsertShips Go 源码字符串。

    先经 normalize_strategy_spec 收敛到合法范围，再按 family 分派到对应的模板渲染函数。
    """
    spec = normalize_strategy_spec(spec)
    if spec.family == "fast_nearest":
        return _render_fast_nearest(spec.top_k)
    if spec.family == "balanced_delta":
        return _render_balanced_delta(spec.top_k, spec.pickup_weight)
    if spec.family == "global_delta":
        return _render_global_delta(spec.pickup_weight)
    if spec.family == "robust_first_feasible":
        return _render_robust_first_feasible()
    # 未匹配到任何族时的兜底：始终返回已知安全的 sa_exact 模板。
    return _render_sa_exact()


def generate_template_candidates(observation: dict[str, Any], count: int) -> list[str]:
    """从有界模板中生成一小批去重后的候选 Go 代码。

    先用 BoundedReactPlanner 选出主策略作为首选候选，再根据密度/到达率追加若干
    备选策略族（含基线安全候选），最后逐一渲染并去重，最多返回 count 段代码。

    返回：互不相同的 InsertShips Go 源码字符串列表。
    """
    planner = BoundedReactPlanner()
    primary = planner.decide(observation)
    density = _density_value(str(observation.get("density", "d25")))
    arrival_scale = float(observation.get("arrival_scale", 1.0) or 1.0)

    # 候选顺序即优先级：主策略在前，其余按场景追加为备选。
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

    # 逐一渲染并按代码文本去重，凑够 count 段即停止。
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
    """渲染 "sa_exact" 族：随机顺序遍历车辆，尝试插入并保留首个成本非负的可行位。"""
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
    """渲染 "fast_nearest" 族：只在距离最近的 top_k 辆车中尝试插入，追求低延迟。"""
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
    """渲染 "balanced_delta" 族：在最近的 top_k 辆车中，按“成本增量 + 接单距离惩罚”
    综合打分选择最优插入位，pickup_weight 控制接单距离的权重。
    """
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
    """渲染 "global_delta" 族：在所有车辆上做“成本增量 + 接单距离惩罚”打分搜索，
    搜索范围最大、质量最高但耗时也最高，pickup_weight 控制接单距离的权重。
    """
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
    """渲染 "robust_first_feasible" 族：随机顺序遍历车辆，接受第一个可行插入位，
    不追求最优、最稳健，适合高密度或出现非法成本时使用。
    """
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
