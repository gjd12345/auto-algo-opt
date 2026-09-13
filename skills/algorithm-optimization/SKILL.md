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

## Session loop

1. Read `session state` and use its current `state_version` for the next mutation.
2. In `WAITING_FOR_PLAN`, optionally `session memory search`, then `session memory read` for at most two selected entries. For rounds after the first, use the exact `feedback_ref` shown by state.
3. Write a strict `plan.json` and submit it with `session submit-plan`.
4. Call `session execute` once. Poll `session state` until the task is terminal, then call `session collect`.
5. Call `session read-evaluation` and reason only from its deterministic facts. The incumbent has already been selected by the Runtime before this step.
6. Write `evaluation.json`. Use `plan_alignment=aligned`, `partial`, `misaligned`, or `unknown`; new submissions MUST NOT emit the historical `deviated` spelling. Choose `memory_action.kind` as `none`, `insight`, or `solution` only when Memory is enabled; otherwise use `disabled`. Submit it once and inspect the returned Memory status.
7. Call `session finish-round --decision continue` only when the state and budget permit another round. Otherwise call it with `complete`, or use `session stop` for an explicit stop.

After every mutation, refresh state rather than guessing the next version. Reuse the same `operation_id` when retrying an uncertain command; never invent a new ID to repeat an effectful `execute` task.

Read the focused contracts before producing documents:

- [protocol](references/protocol.md) for authority, states, identity, and failure rules.
- [plan and evaluate](references/plan-and-evaluate.md) for the exact JSON fields and evidence discipline.
- [two-round example](references/examples/two-round-run.md) for a compact command sequence.
