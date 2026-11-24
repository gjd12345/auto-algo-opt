# Milestone 3.2 Scaling Law & Single-Factor Control Report (`cvrp_m32_blind_120`)

## 1. Main Curve (`36 -> 100 -> 200 -> 400`, `cvrp_ruin_recreate/v1`, 500 ms)

| Checkpoint | Raw Feas Mean | Penalized Mean (Std) | Min / Max | Comp | Feas | Exact-k | Timeouts/120 | Reqs | Wall(s) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 36 | 23.1931 | 36.2140 (7.8419) | 27.1607 / 40.8900 | 0.747 | 1.000 | 0.683 | 30.3 | 36.0 | 483.5 |
| 100 | 23.0521 | 38.8998 (2.8766) | 35.5797 / 40.6444 | 0.692 | 1.000 | 0.739 | 37.0 | 100.0 | 1670.9 |
| 200 | 23.0372 | 38.7545 (3.0885) | 35.1889 / 40.5991 | 0.694 | 1.000 | 0.761 | 36.7 | 200.0 | 3369.9 |
| 400 | 23.0257 | 39.1999 (2.3291) | 36.5116 / 40.6128 | 0.686 | 1.000 | 0.792 | 37.7 | 400.0 | 6865.9 |

*Note: `Raw Feas Mean` reports the unpenalized mean of all verified feasible solutions (including valid anytime incumbents returned at timeout); `Penalized Mean` applies the pre-declared `2 * reference_objective` penalty whenever `completed=False` (`budget_exhausted`).*

## 2. Single-Factor Controls (Matched Total Request Budget)

| Control | Raw Feas Mean | Penalized Mean (Std) | Min / Max | Comp | Feas | Exact-k | Timeouts/120 |
|---|---:|---:|---:|---:|---:|---:|---:|
| model_routing | 23.0718 | 40.5434 (0.0526) | 40.4996 / 40.6017 | 0.667 | 1.000 | 0.706 | 40.0 |
| l3b_dual_hook | 23.1823 | 48.8565 (3.5721) | 44.7318 / 50.9297 | 0.397 | 1.000 | 0.717 | 72.3 |
| timeout_2000ms | 23.1111 | 23.1111 (0.1142) | 22.9796 / 23.1861 | 1.000 | 1.000 | 0.783 | 0.0 |

## 3. Baseline Comparators (`enforce_wall_deadline=False` Deterministic Reference)

| Comparator | Raw Mean | Strict-Deadline Penalized | Within-Deadline Comp | Exact-k | Timeouts/120 |
|---|---:|---:|---:|---:|---:|
| cw_parallel_merge@500ms | 23.2930 | 23.2930 | 1.000 (120/120) | 0.675 | 0 |
| cw_relocate_2opt@500ms | 23.2113 | 23.2113 | 1.000 (120/120) | 0.683 | 0 |
| l3_ctrl@500ms | 23.2230 | 26.4966 | 0.925 (111/120) | 0.675 | 9 |
| l3_ctrl@2000ms | 23.2230 | 23.2230 | 1.000 (120/120) | 0.675 | 0 |

*Note: `baseline_comparators` run with `enforce_wall_deadline=False` so wall clock cannot clip deterministic trajectories mid-loop; `l3_ctrl@500ms` logged 9 overruns at `n=200` (502.6–553.3 ms), while `l3_ctrl@2000ms` had 0/120 overruns and is the strict deadline-matched comparator for `timeout_2000ms`.*
