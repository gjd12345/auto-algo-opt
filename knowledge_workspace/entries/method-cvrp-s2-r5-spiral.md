# CVRP state-only inward spiral with angular coherence and adaptive early return (R5 / s2_r5_spiral)

`s2_r5_spiral` (`auto_ana1_r5`, Round 5 `candidate_2` from `s2_autonomous_math_r8`) is a strictly scale-invariant sequential CVRP constructive rule under `select_next_node` selected offline via `ana72` (zero peeking at `P0-120`).

## 定义或方法步骤

1. **Dimensionless distance normalization**: compute `scale = mean(d_dep) + mean(d_cur) + 1e-12`, elongation ratio `rho(i, j) = d(i, j) / max(d(0, i) + d(0, j), 1e-12)`, and normalized fill `fill = demand / (rest_capacity + 1e-12)`.
2. **Two-phase depot-start branch (`current_node == depot`)**: compute `rem_routes = sum(dem) / (rest_capacity + 1e-12)`. When `rem_routes > 7.0`, select outside-in far-heavy seeds (`-d_dep/scale - 0.25*fill`); otherwise select compact radial-load seeds (`d_dep/scale - 0.30*fill`).
3. **State-only inward spiral (`current_node != depot`)**: define vehicle-state pressure `pressure = min(1.0, mean(dem) / (rest_capacity + 1e-12))` (uniform across all candidates at the same step, avoiding anti-heavy candidate bias) and effective depot pull `alpha_eff = 1.02 - 0.85 * pressure`.
4. **Angular coherence + combined score**: add Law-of-Cosines depot-ray alignment `cos(theta_0)` with weight `0.20`, yielding `score = (d_cur - alpha_eff * d_dep)/scale + 0.35*rho - 0.10*fill - 0.20*cos_t`.
5. **Capacity-adaptive early depot return (`return 0`)**: when `max(dem) > 0.55 * rest_capacity` and the best candidate has normalized saving `1 - rho_best < tau` where `tau = 0.25 + 0.50 * pressure`, proactively return `0` to the depot.

## EoH 适配

- ProblemSpec: `cvrp_construct`, entrypoint `select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix) -> int` (returning `0` triggers a valid voluntary early depot return in `agent_skill_loop/evaluator.py`).
- Uses only allowed NumPy operations (`asarray`, `mean`, `maximum`, `clip`, `zeros_like`, `sum`, `max`, `argmin`); strictly zero coordinate-scaling drift (`0.00%` spread across `1e-3 .. 1e3`).

## 适用条件、假设与限制

- Evaluated under single-route sequential construction (`select_next_node`) with exact Euclidean/metric distances and uniform/clustered synthetic CVRP instances (`n in {50, 100, 200}`).
- Multiple components (two-phase depot start, state-only `alpha_eff`, `rho`, `cos(theta_0)`, adaptive early return) act jointly; individual component contributions are bounded by existing ablation evidence (`H-003`..`H-007`) rather than a full factorial ablation over all subsets.
- Single paired search run (`s2_autonomous_math_r8` vs `s2_control_r8`, 48 EoH requests per arm, ~35% higher EoH token volume in the autonomous arm plus separate external Coding Agent analysis cost).
- Still trails the parallel Clarke-Wright merge reference (`cw_merge`): on `P0-120`, `R5 = 19.6092` vs `CW = 17.3570` (`R5` is `+12.98%` longer relative to `CW`; `CW` is `11.49%` shorter relative to `R5`); on `hetero-288`, `R5 = 25.0387` vs `CW = 22.9498` (`+9.10%` above `CW`).

## 来源及支持的具体结论

- Source: `src-cvrp-midterm-20261121` (`experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md`, `experiments/cvrp_midterm/analysis/s2_holdout_eval.json`, `experiments/cvrp_midterm/selection_s2/summary_s2.json`).
- **Frozen `P0-120` blind test (`n = 50 / 100 / 200`, 40 instances each)**:
  - `R5` mean `19.6092` (`P0-50: 10.3864`, `P0-100: 17.6375`, `P0-200: 30.8038`), `0.00%` scale spread.
  - Vs paired equal-request control `ctrl_dev1_r7` (`20.6229`): pooled total tour length reduced by **4.92%**, 95% paired Bootstrap CI `[4.22%, 5.67%]`, 0/10,000 non-positive resamples, `109/120` wins; by scale `8.62%` (`n=50`) / `5.54%` (`n=100`) / `3.23%` (`n=200`); mean per-instance relative reduction (distinct metric) is `5.66%`.
- **Shared-6 diagnostic suite** (development diagnostic containing the 4 search instances): `10.2714` vs `Frozen C 10.9197`, triggering `17` valid voluntary early returns (zero per-instance discrepancy vs official evaluator).
- **`hetero-288` 5-factor matrix**: total tour length `7211.13`, below the old 8-rule portfolio VBS (`7234.72`).

## 代码和评测关联

- Exported rule: `experiments/cvrp_midterm/selection_s2/rules_s2/s2_r5_spiral.py` (`code_sha256: e5e5dcf83797fc6ba67026eb08cb6504a7bcd10e3c3dbecbee948634dfc50587`).
- Origin run: `experiments/cvrp_midterm/runs/s2_autonomous_math_r8/rounds/round_0005` (`candidate_2`).
- Offline audit artifacts: `experiments/cvrp_midterm/analysis/audit_reverification_p0.json`, `experiments/cvrp_midterm/analysis/audit_reverification_p1.json`, `experiments/cvrp_midterm/analysis/s2_holdout_eval.json`, `experiments/cvrp_midterm/selection_s2/selectors_s2.json`.

## 未确认项与冲突证据

- Multi-seed search stability across independent runs is not yet established (Bootstrap intervals measure fixed-candidate per-instance resampling uncertainty, not multi-run search variance).
- Full component-wise factorial ablation of `rho`, `cos(theta_0)`, `alpha_eff`, and `early_return` on `P0-120` and CVRPLib benchmarks remains future work.
