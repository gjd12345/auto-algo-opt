# Algorithm Optimization Skill: operating contract

This reference is the compact Coding Agent view of the v1.1 Session protocol. The repository's full normative text is `docs/protocol.md`.

## Authority

The responsibilities are deliberately separated:

| Component | Authority |
|---|---|
| Coding Agent | Plan, interpretation of facts, Memory decision, continue/complete |
| Session Runtime | SQLite state, state versions, idempotency, budgets, task lifecycle, evidence checks |
| Official EoH | Population, parent selection, operators, generation and optional bounded repair |
| DeepSeek/provider | EoH probe, generation, retry, and explicitly enabled repair requests |
| Deterministic evaluator | Interface, safety, validity, objective, per-instance facts |
| Memory backend | Versioned advisory Markdown search/read/write; never calls a model |

Only the EoH task may use the provider. Its request purposes are limited to `eoh_probe`, `eoh_generation`, and `eoh_repair`. Plan/Evaluate/Memory decisions are submitted by the Coding Agent as files.

## State machine

The run has one active round:

```text
WAITING_FOR_PLAN → READY_TO_EXECUTE → EXECUTING
    → WAITING_FOR_EVALUATION → READY_TO_FINISH
    → ROUND_COMPLETED → WAITING_FOR_PLAN
```

`complete` transitions the run to `COMPLETED`; `stop` may produce `STOPPING` while a task is alive and then `STOPPED`. Provider-terminal, deadline, unknown-task, evidence, and budget failures are terminal or require explicit handling; they are never disguised as algorithmic failure.

## Mutation discipline

- `state_version` is global to the run. Every successful mutation advances it.
- Every effectful mutation has a unique `operation_id` and a stored receipt. Replaying the same input returns that receipt and produces no second request, solver call, task, or Memory version.
- An effectful task is started once per round. A crashed or unknown task is reconciled to a terminal state and is not automatically rerun.
- A request is durably reserved before HTTP. `reserved`/`sent` requests that lose their outcome become `unknown`; their budget is not refunded and their token fields are `null`.
- A solver row is reserved before evaluation. No objective may be invented for an interrupted or missing evidence record.

## Identity and evidence

The Runtime freezes the problem, suite hash, evaluator hash, baseline code hash, official EoH commit, repair policy, Runtime hash, and Skill hash at `session init`. Candidate identity is:

```text
candidate_id → revision → code_sha256 → evaluation_id
```

An exported skill is usable only when its problem, entrypoint, suite, evaluator, code, and evaluation evidence match. The incumbent is updated from collected deterministic facts before the Agent submits Evaluate; Evaluate or Memory errors cannot roll back that update.

## Memory

`memory search` deliberately omits bodies. `memory read` records the reference, body hash, and character range. A reference may enter `plan.memory_basis` only after the complete body has been read with no gaps. Memory writes are advisory and CAS/versioned; a failed write leaves the accepted evaluation and algorithm asset intact.
