# Milestone 2 Exploratory Diagnostic: 2 Constructor Families x 3 Postprocessing Modes

- Generated at: `2026-11-22T15:04:36Z`
- Usage role: `dev_selection` (strictly isolated from `cvrp_m2_blind_120`)
- Time budget per instance: `500.0 ms`
- JSON SHA-256: `6ffb6d76a27952057e519b1f0fda411a7f3ae1bb36496d80746c19298b0ced8d`

## `cvrp_dev_hetero_24` (n=24)

| Constructor ID | Family | Raw | +2-opt | +Relocate+2-opt | Post Drop % | Bridged vs CW Raw % | Remaining vs CW Raw % |
|---|---|---:|---:|---:|---:|---:|---:|
| `nn` | `sequential_construct` | 20.5337 | 19.9009 | 17.9553 | 12.56% | 59.81% | +10.68% |
| `s2_r5_spiral` | `sequential_construct` | 18.1588 | 17.6627 | 16.8276 | 7.33% | 68.75% | +3.73% |
| `i605_cvrp_c1_tworegime` | `sequential_construct` | 17.6087 | 16.7521 | 16.4475 | 6.59% | 83.77% | +1.39% |
| `cw_parallel_merge` | `parallel_merge` | 16.2225 | 16.1868 | 16.1416 | 0.50% | — | 0.00% |

## `cvrp_select_multiscale_64` (n=64)

| Constructor ID | Family | Raw | +2-opt | +Relocate+2-opt | Post Drop % | Bridged vs CW Raw % | Remaining vs CW Raw % |
|---|---|---:|---:|---:|---:|---:|---:|
| `nn` | `sequential_construct` | 25.7007 | 25.0837 | 23.0581 | 10.28% | 53.72% | +10.96% |
| `s2_r5_spiral` | `sequential_construct` | 22.8904 | 22.1853 | 21.5848 | 5.70% | 61.90% | +3.87% |
| `i605_cvrp_c1_tworegime` | `sequential_construct` | 22.4722 | 21.5362 | 21.2408 | 5.48% | 72.82% | +2.21% |
| `cw_parallel_merge` | `parallel_merge` | 20.7811 | 20.7410 | 20.6978 | 0.40% | — | 0.00% |

