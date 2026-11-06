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
- Memory is advisory context and is enabled by default for ordinary Sessions. Search returns summaries only; read the complete selected body before putting its reference in `plan.memory_basis`. A Memory failure is not a reason to discard verified algorithm facts. Use `--no-memory` for an explicit no-Memory run; controlled benchmark manifests remain off unless they explicitly enable it.
- Search the current problem first. Expand with `--include-shared` or `--include-cross-project` only when the Agent explicitly decides that transfer is useful; every adopted entry must still be fully read and hash-verified.
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
2. In `WAITING_FOR_PLAN`, when Memory is enabled, search the current problem and read at most two relevant complete entries. If deliberately skipping search or adopting no result, explain why in `reasoning_summary`; do not force irrelevant memories into a Plan. For rounds after the first, copy `state.feedback_basis` into the Plan. `feedback_ref` alone is only a path string, not that object. Check the returned injection manifest: adopted but omitted is not consumed by EoH.
3. Write a strict `plan.json` and submit it with `session submit-plan`.
4. Call `session execute` once. Poll `session state` until the task is terminal, then call `session collect`. A `STARTUP_FAILED` or `EVIDENCE_STORAGE_FAILED` terminal reason is an infrastructure failure, not an algorithm result; preserve the evidence and start a new Session after the environment is fixed.
5. Call `session read-evaluation` and reason only from its deterministic facts. The incumbent has already been selected by the Runtime before this step.
   Inspect the linked `execution_delta.json` for actual parent provenance,
   code differences, complete behavior evidence, and per-instance effects.
   Use [Iteration A evidence and Reflection v2](references/iteration-a-evidence.md)
   to separate observations, hypotheses, and next-step decisions. Unknown
   lineage or incomplete behavior is not evidence of sameness.
6. Write `evaluation.json`. Use `plan_alignment=aligned`, `partial`, `misaligned`, or `unknown`; new submissions MUST NOT emit the historical `deviated` spelling. Choose `memory_action.kind` as `none`, `insight`, or `solution` only when Memory is enabled; otherwise use `disabled`. Submit it once and inspect the returned Memory status.
7. Call `session finish-round --decision continue` only when the state and budget permit another round. Otherwise call it with `complete`, or use `session stop` for an explicit stop.
   Check the returned `memory_consumption_ref` and hash: selected/compiled,
   gateway-attempted, omitted, and published are different states.

Every Evaluate must consider whether evidence supports a reusable, scoped insight,
an update to existing knowledge, a gated solution, or no write. For `none`, include
`reason`; no improvement is required for an insight, but a repeated log entry is not
new knowledge. Failed/rejected publication can be corrected in READY_TO_FINISH with
`session memory-revise --file <memory-action.json>` using a fresh operation ID/current
version. Never rerun EoH or rewrite accepted Evaluate to fix Memory. Do not revise a
published entry through this command; ordinary versioned updates use the next Evaluate.

## Default round progress reporting

After each completed round, update a compact `round_progress.md` at the
Session output root and keep the previous rows unchanged. At Session
completion, print the complete table before the final prose summary. Build it
only from Runtime-verified state, request ledger, solver ledger, collected
evaluation facts, incumbent before/after facts, and Memory references.

Use these columns:

```text
Round | Plan input / mechanism | EoH requests delta / cumulative; solver
      | valid / generated | generated candidate objectives
      | incumbent before -> after / delta | Memory | status
```

Use `—` for a fact that is not present; never infer a score, request count,
Memory reference, or causal explanation. The Plan's `reasoning_summary` may
be shown as the explanation for the chosen mechanism, but it is not Runtime
evidence. The candidate objective list must preserve the evaluation facts'
candidate identities and indicate invalid candidates by their verified error
code rather than silently dropping them.

Compute `status` deterministically: `improved` when the verified incumbent
objective decreases, `stagnated` when it is unchanged, `all-invalid` when no
generated candidate is valid, `diversified` when the Plan declares a new
mechanism family or distinct hypotheses and the facts show a valid candidate
without an incumbent improvement, `budget-limited` when the Runtime reports a
budget stop, and `seed-insufficient` when the Runtime reports insufficient
verified seeds. If more than one applies, use the most specific terminal
condition (`all-invalid`, `seed-insufficient`, `budget-limited`) before the
quality condition.

After every mutation, refresh state rather than guessing the next version. Reuse the same `operation_id` when retrying an uncertain command; never invent a new ID to repeat an effectful `execute` task.

Read the focused contracts before producing documents:

- [protocol](references/protocol.md) for authority, states, identity, and failure rules.
- [plan and evaluate](references/plan-and-evaluate.md) for the exact JSON fields and evidence discipline.
- [two-round example](references/examples/two-round-run.md) for a compact command sequence.
- For offline benchmark audit/calibration and benchmark Session options, use
  the focused [benchmark contract](references/benchmark.md). All Skill
  references needed at runtime are contained under this Skill directory.
