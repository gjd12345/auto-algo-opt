# Milestone 4 Part 2: Frozen M3.2 Operator Dissection & Unified Empirical Closure

Generated: `2026-11-24`

## 1. Frozen M3.2 400-Request Winner AST & Select-16 Anytime Dissection (`m4_m32_operator_dissection.json`)

All 12 evolved 400-request snapshots (3 `curve:400` + 3 `model_routing` + 3 `l3b_dual_hook` + 3 `timeout_2000ms`) were validated and dissected offline on the first 16 `n=50` instances from `cvrp_select_multiscale_64` (`valid_count = 16/16` across all 12 snapshots):

| Track / Seed | Solver ID | Template | Hook LOC | Binary Ops | `select_16` @10ms -> @500ms | Dev `cvrp_dev_hetero_24` | Blind-120 Mean (`Exact-k`, `Timeouts`) |
|---|---|---|---:|---|---:|---:|---|
| `curve:400` (`20261124`) | `ckpt_cand_e4a1eb6c02` | `cvrp_ruin_recreate` | 62 | `Add,Div,Mult,Pow,Sub` | `11.2114 -> 11.1913` | `16.0134` | `40.6128` (`0.800`, `40`) |
| `curve:400` (`20261125`) | `ckpt_cand_d6c597ab94` | `cvrp_ruin_recreate` | 69 | `Add,Div,Mult,Sub` | `11.1491 -> 11.0577` | `15.7435` | `40.4754` (`0.767`, `40`) |
| `curve:400` (`20261126`) | `ckpt_cand_22af9ec1ab` | `cvrp_ruin_recreate` | 98 | `Add,BitAnd,Div,Mult,Sub` | `11.1539 -> 11.0525` | `15.7773` | `36.5116` (`0.808`, `33`) |
| `model_routing` (`20261124`) | `ckpt_cand_0b7c6e8ed1` | `cvrp_ruin_recreate` | 110 | `Add,Div,Mult,Sub` | `11.1823 -> 11.1667` | `15.9940` | `40.6017` (`0.683`, `40`) |
| `model_routing` (`20261125`) | `ckpt_cand_4d2fd0b1ff` | `cvrp_ruin_recreate` | 113 | `Add,BitAnd,Div,Mod,Mult,Pow,RShift,Sub` | `11.2109 -> 11.1235` | `15.8948` | `40.5289` (`0.700`, `40`) |
| `model_routing` (`20261126`) | `ckpt_cand_cff5042a7d` | `cvrp_ruin_recreate` | 74 | `Add,Div,Mod,Mult,Sub` | `11.1778 -> 11.0913` | `15.8452` | `40.4996` (`0.733`, `40`) |
| `l3b_dual_hook` (`20261124`) | `ckpt_cand_4a1480dd8f` | `cvrp_ruin_recreate_dual` | `36 + 53` | `Add,Div,Mult,Sub` | `11.2232 -> 11.2228` | `16.0924` | `50.9297` (`0.692`, `80`) |
| `l3b_dual_hook` (`20261125`) | `ckpt_cand_96095da4f5` | `cvrp_ruin_recreate_dual` | `55 + 64` | `Add,Div,Mult,Pow,Sub` | `11.2255 -> 11.1504` | `16.0526` | `50.9080` (`0.700`, `80`) |
| `l3b_dual_hook` (`20261126`) | `ckpt_cand_501be7ec5e` | `cvrp_ruin_recreate_dual` | `26 + 25` | `Add,Div,Mult(+Pow,Sub)` | `11.2254 -> 11.1979` | `16.0560` | `44.7318` (`0.758`, `57`) |
| `timeout_2000ms` (`20261124`) | `ckpt_cand_8c4dfb41aa` | `cvrp_ruin_recreate` | 103 | `Add,Div,Mult,Pow,Sub` | `11.1652 -> 11.0694` | `15.8374` | `22.9796` (`0.850`, `0`) |
| `timeout_2000ms` (`20261125`) | `ckpt_cand_31c4a39eb6` | `cvrp_ruin_recreate` | 81 | `Add,Div,Mult,Sub` | `11.2166 -> 11.1994` | `16.0496` | `23.1861` (`0.742`, `0`) |
| `timeout_2000ms` (`20261126`) | `ckpt_cand_dfda91b73b` | `cvrp_ruin_recreate` | 56 | `Add,Div,Mult,Sub` | `11.2230 -> 11.2067` | `16.0293` | `23.1676` (`0.758`, `0`) |

## 2. Emergent Algorithmic Mechanisms Discovered Without Human Prompt Intervention

1. **Three-Phase Temperature-Annealed Gumbel Ruin with Route-Slack Consolidation (`ckpt_cand_8c4dfb41aa`, best M3.2 blind seed `22.9796`)**:
   - Explicitly reconstructs per-route utilization (`route_used / capacity`) and stop-count sparsity (`1 / n_stops`), blending them across `exploit -> neutral -> diversify` phases weighted by normalized search progress (`iter_frac`) and `stagnation_ratio`.
   - Adds scale-invariant radial proximity `1 / (1 + (d(seed, j) / mean(d_0))^2)` around the maximum-saving customer plus deterministic Gumbel noise `-log(-log(u))`.
   - Raises exact-$k$ fleet attainment on `cvrp_m32_blind_120` from `0.675` (`l3_ctrl@2000ms`) / `0.683` (`cw_relocate_2opt`) to **`0.850`** (`102/120` instances), achieving `W/T/L = 116/2/2` vs `l3_ctrl@2000ms` (`p = 9.88e-21`, `-1.048%`) and `109/7/4` vs `cw_relocate_2opt` (`p = 5.68e-20`, `-0.998%`, bootstrap 95% CI `[+0.816%, +1.198%]`).
2. **Dimensionless Gibbs-Boltzmann Quota-Ladder (`ckpt_cand_22af9ec1ab`, lowest raw unpenalized all-120 mean `22.9430` across `valid` incumbents)**:
   - Combines dimensionless detour fraction (`removal_savings / route_dist`), capacity utilization (`(route_load / C) * (d_j / C)`), and saturating depot eccentricity (`d_0 / (d_0 + mean(d_0))`) into a negative energy scored via Gibbs inverse temperature `beta(iter_frac, stagnation_ratio)` and cumulative probability rank ladder.
3. **Scale-Dependent Wall-Clock Generalization Boundary (500ms vs 2000ms)**:
   - On `n=50` (40 blind insts, training scale) and `n=100` (40 blind insts, 2x scale), 500ms `curve_400` achieves `100%` completion (`11.2786` on `n=50` vs `11.4083` `cw_relocate_2opt`; `20.6153` on `n=100` vs `20.8666`) and monotonically improves `exact_k` with budget (`0.683 -> 0.739 -> 0.761 -> 0.792`).
   - On `n=200` (40 blind insts, 4x dev scale), Python inner-loop hook expressions (`56-113 LOC`) push solve latency to `p50 ~ 500ms`, causing **82.5-100% timeouts (`33/40` on `s26`, `40/40` on `s24/s25`, `113/120 = 94.2%` overall)** under the `500ms` hard deadline despite strong anytime incumbents (`37.1832` vs `cw_relocate_2opt 37.3591`). Comparing the full `timeout_2000ms` regime (evolving and blind-evaluating under a `2000ms` deadline with distinct frozen winners) against `curve_400` yields `0/120` timeouts across all 3 seeds and statistically significant improvements over the strict 0-timeout deterministic `l3_ctrl@2000ms` baseline on **every seed (`p = 9.88e-21, 2.91e-09, 4.00e-06`)**. (Note that `l3_ctrl@500ms` ran under `enforce_wall_deadline=False` with `9/120` `n=200` overruns up to `553.34ms`, so `l3_ctrl@2000ms` is the strict matched-deadline comparator.)
   - Dual-hook `l3b_dual_hook` suffers a compounded bottleneck (more malformed dual-function completions: `159-170 eoh_skipped` per 400 reqs vs `4-7` for single-hook `curve`, plus double Python scoring calls -> `72.3/120` timeouts @ 500ms), whereas 1-in-4 `model_routing` (`deepseek-v4-pro`) increases cost ~`1.65x` (`$0.583` vs `$0.354`) with mixed dev benefits and no mitigation of the `500ms` `n=200` runtime ceiling.
