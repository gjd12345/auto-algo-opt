# M6 Wave 2 B1 · Decoupled early stop and basin restart

The 4-arm audit records 12.0% mean request savings for the risk-bounded stop arm and 2 empirical Pareto points in request spend and blind loss. Mean signed blind regret was -0.3866%.

## 定义或方法步骤

Compare `no_early_stop`, `naive_patience_24`, `stagnation_restart_only`, `risk_bounded_adaptive_stop`. A global stop ends the request trajectory. A basin restart changes the continuation policy while preserving the remaining budget and incumbent. The blind objective is `penalized_relative_gap_pct`.

## 适用条件、假设与限制

With a valid bound q on the conditional probability of improvement and a bound M on its conditional magnitude given improvement, the expected remaining gain is at most qM. Those bounds depend on the continuation policy. The seed-level blind regret is empirical.

## 来源及支持的具体结论

| Seed | Baseline requests | Risk-bounded requests | Signed blind regret |
| --- | ---: | ---: | ---: |
| 20261124 | 100 | 93 | -0.14929% |
| 20261125 | 100 | 94 | -0.04997% |
| 20261126 | 100 | 77 | -0.96064% |

Pareto points at a 500 ms evaluation deadline

- `risk_bounded_adaptive_stop` (seed 20261126) used 77 requests and scored -18.05888.
- `naive_patience_24` (seed 20261124) used 100 requests and scored -18.20005.

The theory audit reproduced 49/49 logged stopping decisions.

- `experiments/milestone6_wave2_c2_b1/eval/b1_eval_report.json`
- `experiments/milestone6_wave2_c2_b1/wave2_theoretical_abstraction_verified.json`

## 代码和评测关联

- `tools/run_m6_wave2_c2_b1.py`
- `research_agent/loop.py`

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
