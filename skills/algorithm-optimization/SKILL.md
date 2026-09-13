---
name: algorithm-optimization
description: "Drive a recoverable algorithm-evolution session: plan a bounded change, run the official EoH engine, inspect deterministic evaluations, record memory, and decide whether to continue."
---

# Algorithm Optimization

Use this skill when the user asks to improve a registered combinatorial-optimization heuristic through repeated generation and evaluation. The Coding Agent is the outer 3+1 controller: it plans, reads facts, evaluates, chooses Memory writes, and decides when to stop. The Session Runtime is the authority for state, budgets, process lifetime, evidence, and asset identity.

## Operating boundary

- DeepSeek or another configured provider is used only inside the official EoH execution task. Do not create separate Plan, Evaluate, Reflection, or Memory model calls.
- Do not edit the evaluator, suite, budget, frozen runtime, or optimization policy from a submitted document.
- Do not treat a candidate as valid from model text. Use `collect` and `read-evaluation`; only verified evidence determines validity, objective, incumbent, and exported skills.
- Do not use the deprecated `agent_skill_loop workflow` command. It returns a migration error and must not start the legacy model-driven loop.
- Memory is optional advisory context. Search returns summaries only; read the complete selected body before putting its reference in `plan.memory_basis`. A Memory failure is not a reason to discard verified algorithm facts.
- On rounds after the first, the Runtime adds a bounded `feedback_summary` to
  the EoH context. Treat it as trusted facts from the immediately previous
  evaluation: identities, scores, per-instance values, validity counts,
  errors, evidence references, and hashes. Do not ask the Runtime to choose an
  algorithm family, and do not replace these facts with a full historical
  report. Keep the host Agent's rationale in optional `reasoning_summary`; it
  is non-authoritative metadata and is not injected into EoH.
- Generated code and bounded repair use the same machine-derived
  `ProblemSpec` capability contract. Respect its interface, allowed imports
  and attributes, safe builtins, read-only inputs, and side-effect boundary;
  do not rely on Memory to discover evaluator restrictions.
- For a benchmark Session, use the frozen benchmark identity and canonical
  `MetricSpec`; raw objectives and reference objectives are facts, not
  alternate ranking signals. With `inheritance_mode=population_seeds`, let the
  Runtime derive the next round from the verified official final-population
  snapshot. Do not manually sort or inject a cold-start fallback when seed
  selection is insufficient.

## Session loop

1. Read `session state` and use its current `state_version` for the next mutation.
2. In `WAITING_FOR_PLAN`, optionally `session memory search`, then `session memory read` for at most two selected entries. For rounds after the first, copy `state.feedback_basis` into the Plan. `feedback_ref` alone is only a path string, not that object.
3. Write a strict `plan.json` and submit it with `session submit-plan`.
4. Call `session execute` once. Poll `session state` until the task is terminal, then call `session collect`. A `STARTUP_FAILED` or `EVIDENCE_STORAGE_FAILED` terminal reason is an infrastructure failure, not an algorithm result; preserve the evidence and start a new Session after the environment is fixed.
5. Call `session read-evaluation` and reason only from its deterministic facts. The incumbent has already been selected by the Runtime before this step.
6. Write `evaluation.json`. Use `plan_alignment=aligned`, `partial`, `misaligned`, or `unknown`; new submissions MUST NOT emit the historical `deviated` spelling. Choose `memory_action.kind` as `none`, `insight`, or `solution` only when Memory is enabled; otherwise use `disabled`. Submit it once and inspect the returned Memory status.
7. Call `session finish-round --decision continue` only when the state and budget permit another round. Otherwise call it with `complete`, or use `session stop` for an explicit stop.

After every mutation, refresh state rather than guessing the next version. Reuse the same `operation_id` when retrying an uncertain command; never invent a new ID to repeat an effectful `execute` task.

Read the focused contracts before producing documents:

- [protocol](references/protocol.md) for authority, states, identity, and failure rules.
- [plan and evaluate](references/plan-and-evaluate.md) for the exact JSON fields and evidence discipline.
- [two-round example](references/examples/two-round-run.md) for a compact command sequence.
- For offline benchmark audit/calibration and benchmark Session options, use
  the repository [CLI contract](../../docs/cli-contract.md) and
  [benchmark protocol](../../docs/protocol.md#30-benchmark-compatibility-and-controlled-experiments).
