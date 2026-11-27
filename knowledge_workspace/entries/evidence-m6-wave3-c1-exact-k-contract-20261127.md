# M6 Wave 3 C1 · Fleet-aware construction and the Exact-K contract

The clean C1 seed-level comparison records Y_11 strict Exact-K returns on ABP, Set X, and the official OR panel alongside PyVRP's feasible-incumbent and strict-return endpoints. The offline gate reported passed=True and evolved evaluation reported passed=False.

## 定义或方法步骤

A solution must cover each customer once, respect capacity Q on each route, and deliver exactly K nonempty routes before the deadline to count under Exact-K. Let rho be total demand divided by KQ and delta_max be the maximum demand divided by Q. Bounds rho ≤ 1 and delta_max ≤ 1 are necessary. A feasible partition into K routes is a witness. If the two smallest current route loads sum to more than Q, whole-route merges are blocked and achieving K may require exchanging or repacking customers.

## 适用条件、假设与限制

fleet_repair_enabled bundles 4-tier repair + 60/40 construction budget split + apply_relocate_2opt_guarded fallback vs _polish_exact; Y_11 vs Y_01 and Y_10 vs Y_00 remain isolated single-factor adjustment contrasts. A miss with a validated K-route witness shows a construction or return failure on a feasible case.

## 来源及支持的具体结论

| Seed | Deadline (ms) | Y_11 ABP Exact-K | Y_11 Set X Exact-K | Y_11 OR Exact-K | Y_11 OR free fleet | PyVRP OR exact feasible | PyVRP OR exact returned | Y_11 gate passed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 20261124 | 500 | 74/74 | 87/100 | 161/174 | 174/174 | 168/174 | 0/174 | True |
| 20261124 | 2000 | 74/74 | 87/100 | 161/174 | 174/174 | 170/174 | 0/174 | False |
| 20261125 | 500 | 74/74 | 89/100 | 163/174 | 174/174 | 168/174 | 0/174 | False |
| 20261125 | 2000 | 74/74 | 89/100 | 163/174 | 174/174 | 170/174 | 0/174 | True |
| 20261126 | 500 | 74/74 | 88/100 | 162/174 | 174/174 | 168/174 | 0/174 | True |
| 20261126 | 2000 | 74/74 | 88/100 | 162/174 | 174/174 | 170/174 | 0/174 | True |

Synthetic aggregate-capacity witness of insufficiency: demands [6, 6, 6] with Q=10 and K=2 need 3 routes. For demands [6, 5, 3, 2, 2, 2] with Q=10 and K=2, first-fit decreasing uses 3 routes despite a feasible K-route packing.

In the highest rho stratum of the 500 ms calibration, the observed overshoots vary with the maximum demand share:

- `delta_max<0.10`: 8/21 Y_00 fleet overshoots.
- `0.10<=delta_max<0.20`: 17/34 Y_00 fleet overshoots.
- `0.20<=delta_max`: 49/59 Y_00 fleet overshoots.

- `experiments/milestone6_wave3_c1_exact_k/c1_offline/c1_offline_430_report.json`
- `experiments/milestone6_wave3_c1_exact_k/eval/c1_eval_report.json`
- `experiments/milestone6_wave3_c1_exact_k/wave3_theoretical_abstraction_verified.json`
- `experiments/milestone6_wave3_c1_exact_k/wave3_tightness_feasibility_theory_verified.json`

## 代码和评测关联

- `tools/run_m6_wave3_c1_exact_k.py`
- `agent_skill_loop/interface_design/fleet_exact_k.py`

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
