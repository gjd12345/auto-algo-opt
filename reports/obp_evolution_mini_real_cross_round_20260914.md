# OBP evolution mini real cross-round probe

Date: 2026-09-14

This was a small real-provider probe, not a formal v1.1 pilot. It used the
new `obp_evolution_mini` profile and left the historical `obp_mini` profile
unchanged.

## Frozen input

| Field | Value |
| --- | --- |
| benchmark/profile | `eohs_v1 / obp_evolution_mini` |
| problem | `obp_online` |
| train suite hash | `52de3a0385cfad008d67e8392dcddfe38efaeeef03a266ecb85511c249fcd99c` |
| data manifest hash | `0eca0bb36d858e7591d7a9c9ad99c92a4622f2f46754869652346453a3a5d3ca` |
| reference kind | `known_optimum` |
| metric hash | `08550f7999f0bc40a0c55f06449a60209e693ba7848fbff4b21bddeb829fc53e` |
| provider/model | DeepSeek official API / `deepseek-flash` |
| inheritance | `population_seeds` |
| rounds | 2 requested |
| search | `pop_size=2`, `n_pop=1`, `max_sample_nums=4` |
| controls | Memory off, repair off, neutral guidance |
| budgets | 24 provider requests, 30 solver attempts, 600 s global, 300 s/round |

The exact command used the configured `DEEPSEEK_API_KEY` environment variable;
the key was not persisted in the repository or evidence.

## Result

Round 1 reached the official EoH search and real provider responses:

| Item | Result |
| --- | --- |
| provider requests charged | 8 (7 completed, 1 killed at round deadline) |
| probe | HTTP 200, 1.06 s |
| generation responses | 6 completed: 4 complete-content responses and 2 `generation_truncated`; probe is counted separately |
| solver attempts | 5: baseline + 4 generated candidates |
| valid generated candidates | 4 |
| distinct generated code hashes | 2 |
| generated objective | all `0.0` mean relative gap |
| round 1 stop | `DEADLINE_EXCEEDED` |
| round 2 provider calls | 0 |

The baseline and generated code were all Best-Fit-equivalent on the frozen
training suite. The official final population therefore contained one valid
member, not the required two members for `population_seeds` with
`pop_size=2`.

Round 2 did consume the previous round's factual feedback in
`rounds/round_0002/feedback_summary.json`, then correctly terminated before
launching a child process:

```text
termination_reason = insufficient_valid_seeds
external_effect_started = false
selected_members = 1
target_population_size = 2
```

This proves the no-cold-start safety gate and feedback handoff. It does not yet
prove a successful two-round multi-seed hot start. The full local Session is
under `outputs/obp_evolution_mini_real_20260914_01` (gitignored).
The [compact evidence bundle](evidence/obp_evolution_mini_real_20260914_01/bundle.json)
contains hash-checked training facts, population, seed selection, plans, context,
archive and request/solver receipts. Raw provider exchanges are omitted.
Verify it with `python tools/export_benchmark_evidence.py --verify
reports/evidence/obp_evolution_mini_real_20260914_01`.
No heldout evaluation or final selection was performed for this stopped probe.

## Offline checks

- Benchmark asset audit: passed for both profiles.
- New-profile upstream differential calibration: passed.
- Focused kernel test: passed.
- `py -3.11 -m compileall -q agent_skill_loop eoh_frozen`: passed.

This run should be classified as `cross_round_gate_verified` rather than
`cross_round_hot_start_completed`.
