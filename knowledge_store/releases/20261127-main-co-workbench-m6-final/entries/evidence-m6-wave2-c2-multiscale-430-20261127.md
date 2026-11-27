# M6 Wave 2 C2 · Geometry–scale probing and strict returns

C2 strict free-fleet returns on the external 430-instance panel (500 ms: 430/430 for `cw_static` and 428/430 for `cw_relocate_2opt`; 2000 ms: 430/430 for `cw_static` and 430/430 for `cw_relocate_2opt`).

## 定义或方法步骤

Probe joint geometry and scale regimes when screening candidates. The offline benchmark reports strict free-fleet delivery and Exact-K scoring separately. Its Exact-K procedure is `project_returned_free_fleet_routes_onto_exact_target`.

## 适用条件、假设与限制

The common-completed comparison measures route quality on pairs that returned. The overall penalized comparison also reflects which solvers returned. A measured probe covers its tested regime. A deadline guarantee requires a sound runtime bound or a guarded fallback.

## 来源及支持的具体结论

| Deadline (ms) | Solver | Strict free-fleet returns | Strict Exact-K returns |
| ---: | --- | ---: | ---: |
| 500 | `cw_relocate_2opt` | 428/430 | 305/430 |
| 500 | `cw_static` | 430/430 | 306/430 |
| 500 | `m5_ds_legacy_s20261128` | 430/430 | 308/430 |
| 500 | `m5_ds_whitelist_s20261127` | 430/430 | 319/430 |
| 500 | `m5_qwen_ctrl_s20261125` | 430/430 | 314/430 |
| 2000 | `cw_relocate_2opt` | 430/430 | 306/430 |
| 2000 | `cw_static` | 430/430 | 306/430 |
| 2000 | `m5_ds_legacy_s20261128` | 430/430 | 308/430 |
| 2000 | `m5_ds_whitelist_s20261127` | 430/430 | 319/430 |
| 2000 | `m5_qwen_ctrl_s20261125` | 430/430 | 314/430 |

`cw_static` tied the baseline on 428/428 common completions at 500 ms and 430/430 at 2000 ms. The missed baseline instances accounted for 91.2007% of the verified 500 ms total objective difference.

- `experiments/milestone6_wave2_c2_b1/c2_offline/c2_offline_430_report.json`
- `experiments/milestone6_wave2_c2_b1/wave2_theoretical_abstraction_verified.json`

## 代码和评测关联

- `tools/run_m6_wave2_c2_b1.py`
- `agent_skill_loop/interface_design/multiscale.py`

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
