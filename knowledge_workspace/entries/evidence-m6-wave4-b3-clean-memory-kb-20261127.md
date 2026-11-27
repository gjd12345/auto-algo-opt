# M6 Wave 4 B3 · Unified-base KB and C2-gated memory transfer

12/12 forked cells had attribution_valid=True and the audit recorded 0 hard alarms. Set X strict free-fleet completions per cell ranged from 100/100 to 100/100. `arm_b3_2_offline_l3_c2_gated` avoided observed negative transfer in 3/3 Set X seeds.

## 定义或方法步骤

Start all arms from the pinned base KB `20261125-main-co-workbench-m5-final`. Compare base KB only, online writeback, frozen offline L3 with C2, and full closed-loop memory with C2. The report evaluates at 500 ms and flags negative transfer for lower strict completion or a higher mean objective on common-completed pairs against the base arm.

## 适用条件、假设与限制

Set X parity is a free-fleet result and the report's Set X Exact-K endpoint is null. The experiment holds the base KB fixed. Identifying the separate contributions of screening, tags, and gateway attribution would require additional matched comparisons.

## 来源及支持的具体结论

| Model | Seed | Set X treatment | Common-completed pairs | Mean treatment minus base | Negative transfer |
| --- | --- | --- | ---: | ---: | --- |
| DeepSeek-V4.1-Flash | 20261124 | `arm_b3_1_online_writeback` | 100/100 | +272.74 | True |
| DeepSeek-V4.1-Flash | 20261124 | `arm_b3_2_offline_l3_c2_gated` | 100/100 | -71.64 | False |
| DeepSeek-V4.1-Flash | 20261124 | `arm_b3_3_full_closed_loop_c2_gated` | 100/100 | -59.21 | False |
| DeepSeek-V4.1-Flash | 20261125 | `arm_b3_1_online_writeback` | 100/100 | +26.79 | True |
| DeepSeek-V4.1-Flash | 20261125 | `arm_b3_2_offline_l3_c2_gated` | 100/100 | -133.05 | False |
| DeepSeek-V4.1-Flash | 20261125 | `arm_b3_3_full_closed_loop_c2_gated` | 100/100 | +141.78 | True |
| DeepSeek-V4.1-Flash | 20261126 | `arm_b3_1_online_writeback` | 100/100 | -174.54 | False |
| DeepSeek-V4.1-Flash | 20261126 | `arm_b3_2_offline_l3_c2_gated` | 100/100 | -184.07 | False |
| DeepSeek-V4.1-Flash | 20261126 | `arm_b3_3_full_closed_loop_c2_gated` | 100/100 | -203.75 | False |

- `experiments/milestone6_wave4_b2_b3/b3_memory_kb/b3_fork_roster.json`
- `experiments/milestone6_wave4_b2_b3/b3_memory_kb/b3_evaluation.json`
- `experiments/milestone6_wave4_b2_b3/wave4_theoretical_abstraction_verified.json`

## 代码和评测关联

- `tools/run_m6_wave4_b2_b3.py`
- `agent_skill_loop/memory/retrieval_m35.py`

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
