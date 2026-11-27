# M6 Wave 1 · Clean deadline audit and no-contention wall timings

The A1, A2, A3, A4 audit found 6 uncensored overruns and 5,101 censored callback overruns. At 25 ms the strict common-completed counts were 80 for M2 and 0 for M3.

## 定义或方法步骤

Record `feasible_before_deadline` when a valid incumbent is observed by the deadline and `returned_before_deadline` when a valid solution is actually delivered by the deadline. For M3.2, cross training and evaluation deadlines in a 2×2 factorial at a fixed request cap. The audit reports separate contrasts for m32_blind_120_free_fleet, ext430_free_fleet, true_or_174_exact_k.

## 适用条件、假设与限制

A4 uses no-contention wall timings. Censored observations are recorded at the observed cutoff and give lower bounds on full solve time. Keep common-completed route quality separate from the overall penalized comparison, which incorporates delivery failures.

## 来源及支持的具体结论

- A1 corrected a ReEvo boundary case at 500.0699 ms from 14.268941 to a strict penalized score of 25.895949.
- A2 attributes 99.6006% of the M2 H4A overall gain to completion divergence.
- A3's verified blind free-fleet example gives average training and evaluation effects of +4.9942 and -7.3993, with interaction -10.3586 and diagonal contrast -2.4051.
- `500ms_cw_relocate_2opt` matched on 426 common completions with maximum absolute objective difference 0.
- `2000ms_m32_timeout_2000ms_s20261124_pruned` matched on 423 common completions with maximum absolute objective difference 0.

| Deadline | M3.2 solver | Strict free-fleet completion | Solve p50 (ms) | Solve p95 (ms) | Censored |
| --- | --- | ---: | ---: | ---: | ---: |
| 500ms | `m32_timeout_2000ms_s20261124_raw` | 242/430 | 402.72 | 502.13 | 188 |
| 500ms | `m32_timeout_2000ms_s20261124_pruned` | 230/430 | 441.88 | 501.88 | 200 |
| 500ms | `m32_ckpt400_s20261125` | 235/430 | 441.24 | 502.03 | 195 |
| 2000ms | `m32_timeout_2000ms_s20261124_raw` | 423/430 | 518.00 | 1544.41 | 7 |
| 2000ms | `m32_timeout_2000ms_s20261124_pruned` | 429/430 | 437.76 | 1339.23 | 1 |
| 2000ms | `m32_ckpt400_s20261125` | 420/430 | 555.33 | 1685.66 | 10 |

- `experiments/milestone6_wave1_clean_audit/wave1_master_summary.json`
- `experiments/milestone6_wave1_clean_audit/wave1_theoretical_abstraction_verified.json`

## 代码和评测关联

- `tools/run_m6_wave1_clean_audit.py`
- `tools/run_external_baselines_2026.py`

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
