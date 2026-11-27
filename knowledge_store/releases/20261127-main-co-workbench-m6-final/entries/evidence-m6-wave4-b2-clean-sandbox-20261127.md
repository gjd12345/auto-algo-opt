# M6 Wave 4 B2 · Clean numerical sandbox ablation

Valid script execution went from 14/18 (77.8%) in the first pilot to 10/10 (100%) in the hardened pilot and 62/69 (89.86%) in the full 30-cell ablation. The full audit recorded gate_bypass_count=0.

## 定义或方法步骤

Compare free tool choice, slice-only diagnostics, and sandbox-only diagnostics at a 500 ms evaluation deadline. Count scripts as valid after successful execution with verified finite numeric evidence. Report script validity, diagnostic-round completion, and routing outcomes at their respective denominators.

## 适用条件、假设与限制

The first and hardened pilots recorded 0 and 0 gate bypasses, respectively. Their mixes of script attempts could differ. The seed-level intervals show effects in both directions and the experiment did not specify an equivalence margin. The Set X Exact-K endpoint is null.

## 来源及支持的具体结论

The full ablation verified 8/13 required diagnostic rounds. 28/30 cells had a valid script.

- `cvrp_ext_cvrplib_abp_74`: 100% to 100% strict free-fleet completion across 30 cells.
- `cvrp_ext_cvrplib_x_100`: 100% to 100% strict free-fleet completion across 30 cells.
- `cvrp_b2_clean_blind_120`: 100% to 100% strict free-fleet completion across 30 cells.

- Set X, DeepSeek-V4.1-Flash, seed 20261127, slice-only vs free-tool gave -0.6962% common-completed gain (paired bootstrap 95% CI -0.9637% to -0.4055%, Holm-adjusted Wilcoxon p=0.04019313).
- ABP, DeepSeek-V4.1-Flash, seed 20261126, sandbox-only vs slice-only gave +0.7250% common-completed gain (paired bootstrap 95% CI +0.1453% to +1.3835%, Holm-adjusted Wilcoxon p=0.03031566).
- clean blind, DeepSeek-V4.1-Flash, seed 20261127, sandbox-only vs slice-only gave +0.5603% common-completed gain (paired bootstrap 95% CI +0.2537% to +0.8585%, Holm-adjusted Wilcoxon p=0.00593867).
- clean blind, Qwen4-Max, seed 20261127, sandbox-only vs slice-only gave -0.3257% common-completed gain (paired bootstrap 95% CI -0.5633% to -0.1098%, Holm-adjusted Wilcoxon p=0.04132255).

- `experiments/milestone6_wave4_b2_b3/b2_sandbox_pilot_attempt1/b2_pilot_audit.json`
- `experiments/milestone6_wave4_b2_b3/b2_sandbox/b2_pilot_audit.json`
- `experiments/milestone6_wave4_b2_b3/b2_sandbox/b2_evaluation.json`
- `experiments/milestone6_wave4_b2_b3/wave4_theoretical_abstraction_verified.json`

## 代码和评测关联

- `tools/run_m6_wave4_b2_b3.py`
- `research_agent/tools/math_sandbox.py`

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
