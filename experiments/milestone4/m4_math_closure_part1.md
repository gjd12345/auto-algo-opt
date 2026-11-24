# Milestone 4 Part 1: Exact Shapley, HRK Lower-Bound & Similarity Group Closure

## 1. Exact 2^5 = 32 Shapley Attribution (`s2_r5_spiral.py`)

### Suite `cvrp_select_multiscale_64` (N=64, `11111` bit-for-bit max diff = `0.0`, residual = `0.00e+00`)

| Component | Shapley (Route Units Reduced) | Shapley (% vs `cw_relocate_2opt`) | LOO Marginal Loss | p_Holm |
|---|---:|---:|---:|---:|
| F1_depot_two_phase_override | +0.8430 | +4.0727% | +1.0850 | 2.000e-08 |
| F2_adaptive_inward_spiral_alpha | -0.0099 | -0.0481% | +0.2798 | 3.936e-03 |
| F3_triangular_elongation_rho | +0.0030 | +0.0144% | -0.0079 | 1.000e+00 |
| F4_cosine_angular_coherence | +0.0072 | +0.0348% | +0.0079 | 1.000e+00 |
| F5_capacity_adaptive_early_return | +0.6368 | +3.0765% | +0.4459 | 1.050e-06 |

#### Top Order-2 Shapley Synergy / Interaction Pairs (`I(i, j)`)

| Component Pair | Order-2 Interaction (Route Units) | Order-2 Interaction (% vs `cw_relocate_2opt`) |
|---|---:|---:|
| `F1_depot_two_phase_override__x__F2_adaptive_inward_spiral_alpha` | +0.8141 | +3.9335% |
| `F2_adaptive_inward_spiral_alpha__x__F5_capacity_adaptive_early_return` | -0.2796 | -1.3508% |
| `F1_depot_two_phase_override__x__F5_capacity_adaptive_early_return` | -0.2157 | -1.0421% |
| `F2_adaptive_inward_spiral_alpha__x__F3_triangular_elongation_rho` | +0.2082 | +1.0060% |
| `F3_triangular_elongation_rho__x__F5_capacity_adaptive_early_return` | +0.1061 | +0.5124% |

### Suite `cvrp_hist_p0_120` (N=120, `11111` bit-for-bit max diff = `0.0`, residual = `4.44e-16`)

| Component | Shapley (Route Units Reduced) | Shapley (% vs `cw_relocate_2opt`) | LOO Marginal Loss | p_Holm |
|---|---:|---:|---:|---:|
| F1_depot_two_phase_override | +0.7539 | +4.3732% | +0.8131 | 0.000e+00 |
| F2_adaptive_inward_spiral_alpha | +0.6897 | +4.0010% | +0.7274 | 0.000e+00 |
| F3_triangular_elongation_rho | +0.0648 | +0.3758% | +0.1218 | 3.536e-02 |
| F4_cosine_angular_coherence | +0.0932 | +0.5409% | +0.0894 | 3.099e-02 |
| F5_capacity_adaptive_early_return | +1.1460 | +6.6481% | +0.9105 | 0.000e+00 |

#### Top Order-2 Shapley Synergy / Interaction Pairs (`I(i, j)`)

| Component Pair | Order-2 Interaction (Route Units) | Order-2 Interaction (% vs `cw_relocate_2opt`) |
|---|---:|---:|
| `F2_adaptive_inward_spiral_alpha__x__F5_capacity_adaptive_early_return` | -0.5550 | -3.2198% |
| `F1_depot_two_phase_override__x__F2_adaptive_inward_spiral_alpha` | +0.3839 | +2.2270% |
| `F1_depot_two_phase_override__x__F5_capacity_adaptive_early_return` | -0.3407 | -1.9765% |
| `F3_triangular_elongation_rho__x__F5_capacity_adaptive_early_return` | +0.1445 | +0.8382% |
| `F3_triangular_elongation_rho__x__F4_cosine_angular_coherence` | -0.0996 | -0.5781% |

## 2. HRK Metric Lower Bound `R(I)` & Fixed-`n` Complementarity Analysis

- `cvrp_ext_cvrplib_abp_74`: R(I) lower bound violations vs official OPT = `0`
- Pure-geometry exogenous proxy `G(I) = R(I) + sqrt(n * A_bbox(I))` defines `eta_geom = R(I) / G(I)` with **zero algorithm tour denominator** so `corr(eta_geom, raw_gap)` is strictly free of shared-denominator coupling.

### Fixed-`n` Analysis: `cvrp_hist_hetero_288` — Single-Step Sequential Pool (`nn`, `s2_r4_cos`, `s2_r5_spiral`, `s2_r7_iso`) (common N=288, SBS=`s2_r5_spiral`)

| Size / Subset | Common N | Fixed SBS | Mean Raw Gap (SBS-VBS) | Pooled Gap (%) | corr(eta_geom, raw_gap) | corr(eta_exog, raw_gap) | corr(eta_exog, exog_rel_gap) |
|---|---:|---|---:|---:|---:|---:|---:|
| 100 | 96 | s2_r5_spiral | 0.2882 | 1.3031% | -0.2905 | -0.341 | -0.3787 |
| 200 | 96 | s2_r5_spiral | 0.1568 | 0.3881% | 0.2406 | 0.2545 | 0.1419 |
| 50 | 96 | s2_r5_spiral | 0.2714 | 2.1532% | -0.121 | -0.1554 | -0.2506 |

### Fixed-`n` Analysis: `cvrp_hist_hetero_288` — Constructive Pool (+ `cw_parallel_merge`, `cvrp_sweep_2opt`, `cvrp_farthest_insertion`) (common N=288, SBS=`cw_parallel_merge`)

| Size / Subset | Common N | Fixed SBS | Mean Raw Gap (SBS-VBS) | Pooled Gap (%) | corr(eta_geom, raw_gap) | corr(eta_exog, raw_gap) | corr(eta_exog, exog_rel_gap) |
|---|---:|---|---:|---:|---:|---:|---:|
| 100 | 96 | cw_parallel_merge | 0.0093 | 0.0462% | 0.1763 | 0.1859 | 0.1521 |
| 200 | 96 | cw_parallel_merge | 0.0000 | 0.0000% | None | None | None |
| 50 | 96 | cw_parallel_merge | 0.0397 | 0.3583% | -0.2186 | -0.2899 | -0.3192 |

### Fixed-`n` Analysis: `cvrp_hist_hetero_288` — Full Pool (Constructive + 2-opt/Relocate) (common N=288, SBS=`cw_relocate_2opt`)

| Size / Subset | Common N | Fixed SBS | Mean Raw Gap (SBS-VBS) | Pooled Gap (%) | corr(eta_geom, raw_gap) | corr(eta_exog, raw_gap) | corr(eta_exog, exog_rel_gap) |
|---|---:|---|---:|---:|---:|---:|---:|
| 100 | 96 | cw_relocate_2opt | 0.0056 | 0.0281% | 0.1303 | 0.132 | 0.1105 |
| 200 | 96 | cw_relocate_2opt | 0.0000 | 0.0000% | None | None | None |
| 50 | 96 | cw_relocate_2opt | 0.0294 | 0.2667% | -0.1989 | -0.2664 | -0.2978 |

### Pooled Cross-Size Summary (`45` sizes `n=15..100`, `euc_2d_nint` rounding caveat on fractional <1 coordinates): `cvrp_ext_cvrplib_abp_74` — Single-Step Sequential Pool (`nn`, `s2_r4_cos`, `s2_r5_spiral`, `s2_r7_iso`) (common N=74, SBS=`s2_r5_spiral`)

| Size / Subset | Common N | Fixed SBS | Mean Raw Gap (SBS-VBS) | Pooled Gap (%) | corr(eta_geom, raw_gap) | corr(eta_exog, raw_gap) | corr(eta_exog, exog_rel_gap) |
|---|---:|---|---:|---:|---:|---:|---:|
| all_abp_74 | 74 | s2_r5_spiral | 25.1622 | 2.3875% | -0.019 | 0.076 | -0.0079 |

### Pooled Cross-Size Summary (`45` sizes `n=15..100`, `euc_2d_nint` rounding caveat on fractional <1 coordinates): `cvrp_ext_cvrplib_abp_74` — Constructive Pool (+ `cw_parallel_merge`, `cvrp_sweep_2opt`, `cvrp_farthest_insertion`) (common N=74, SBS=`cw_parallel_merge`)

| Size / Subset | Common N | Fixed SBS | Mean Raw Gap (SBS-VBS) | Pooled Gap (%) | corr(eta_geom, raw_gap) | corr(eta_exog, raw_gap) | corr(eta_exog, exog_rel_gap) |
|---|---:|---|---:|---:|---:|---:|---:|
| all_abp_74 | 74 | cw_parallel_merge | 3.7703 | 0.4122% | -0.4385 | -0.476 | -0.5004 |

### Pooled Cross-Size Summary (`45` sizes `n=15..100`, `euc_2d_nint` rounding caveat on fractional <1 coordinates): `cvrp_ext_cvrplib_abp_74` — Full Pool (Constructive + 2-opt/Relocate) (common N=74, SBS=`cw_relocate_2opt`)

| Size / Subset | Common N | Fixed SBS | Mean Raw Gap (SBS-VBS) | Pooled Gap (%) | corr(eta_geom, raw_gap) | corr(eta_exog, raw_gap) | corr(eta_exog, exog_rel_gap) |
|---|---:|---|---:|---:|---:|---:|---:|
| all_abp_74 | 74 | cw_relocate_2opt | 2.3649 | 0.2601% | -0.41 | -0.4398 | -0.4237 |

## 3. Similarity Group, E(2) Isometry & alpha=1 Phase Bifurcation

### Scale & E(2) Invariance

```json
{
  "cvrp_tested_instance_count": 24,
  "cvrp_r5_max_scale_rel_drift": 4.386343467992116e-16,
  "cvrp_r5_max_e2_rel_drift": 9.248652506364682e-16,
  "tsp_max_scale_rel_drift": 3.907912642063975e-16,
  "tsp_max_e2_rel_drift": 5.703707110302274e-16,
  "obp_max_scale_abs_bins_drift": 0.0,
  "documented_exceptions": [
    "tsplib_euc_2d / euc_2d_int integer rounding breaks continuous scale equivariance at tiny scales",
    "1e-12 numerical denominator stabilization breaks extreme s->0 limits below machine scale",
    "wall-clock deadline truncation depends on runtime CPU speed"
  ]
}
```

### `s_alpha(i,j) = d(i,j) - alpha * d(0,j)` Bifurcation Sweep (`cvrp_select_multiscale_64`, full N=64 multi-scale)

| alpha | Mean Tour Length | Empty-Return Share (%) | Sign(1 - alpha) | Real-Instance Max Spread | All Instances Exact Tie |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 25.700729 | 37.1862% | +1.0000 | 1.33e+00 | False |
| 0.3 | 25.682579 | 38.0988% | +0.7000 | 9.33e-01 | False |
| 0.6 | 25.975254 | 37.9286% | +0.4000 | 5.33e-01 | False |
| 0.8 | 26.401233 | 36.9010% | +0.2000 | 2.66e-01 | False |
| 0.99 | 26.612220 | 34.1289% | +0.0100 | 1.33e-02 | False |
| 1.0 | 24.361343 | 28.6869% | +0.0000 | 0.00e+00 | True |
| 1.01 | 23.318978 | 26.2602% | -0.0100 | 1.33e-02 | False |
| 1.2 | 23.627110 | 26.2181% | -0.2000 | 2.66e-01 | False |
| 1.5 | 23.819336 | 26.3511% | -0.5000 | 6.66e-01 | False |
| 2.0 | 24.237538 | 25.7663% | -1.0000 | 1.33e+00 | False |

### Full `cvrp_dev_hetero_24` Reference Sweep (N=24)

| alpha | Mean Tour Length | Empty-Return Share (%) | Real-Instance Max Spread | All Instances Exact Tie |
|---:|---:|---:|---:|---:|
| 0.0 | 20.533714 | 36.5911% | 1.23e+00 | False |
| 0.3 | 20.133297 | 36.7003% | 8.60e-01 | False |
| 0.6 | 20.242422 | 37.3250% | 4.91e-01 | False |
| 0.8 | 20.784550 | 35.7070% | 2.46e-01 | False |
| 0.99 | 20.913179 | 32.2747% | 1.23e-02 | False |
| 1.0 | 19.092646 | 26.5388% | 0.00e+00 | True |
| 1.01 | 18.503391 | 24.4786% | 1.23e-02 | False |
| 1.2 | 18.625765 | 24.0825% | 2.46e-01 | False |
| 1.5 | 18.740315 | 23.9708% | 6.14e-01 | False |
| 2.0 | 19.201073 | 23.8136% | 1.23e+00 | False |
