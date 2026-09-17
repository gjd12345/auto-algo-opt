# Session protocol

Install the independent optics wheel in Python 3.12. Commands use
`python -m artifact_session <action> --run <directory>`. For mutation actions supply
`--operation-id <unique-id> --expected-state-version <state.version>`.
`init` uses `--file <config.json>` with an explicit `init_operation_id`.

Actions: state, submit-plan, execute, collect, read-evaluation, submit-evaluation,
memory-search, memory-read, memory-write, finish-round, finalize, stop, recover, report.
JSON submissions use `--file`. read-evaluation uses `--round`. finish-round uses
`--decision continue|complete`. report optionally uses `--output <markdown>`.

Plan fields (all required): schema_id=`optical-prescription-plan/v1`, round_id,
task_contract_hash, hypothesis, variables_to_adjust (TaskSpec variable IDs), couplings,
invariants, metrics_to_watch, candidate_budget, feedback_basis, memory_basis.
The first feedback_basis is null. Later use the exact preceding read-evaluation ref.
Memory basis is a list of `{id,version,hash}` from actual memory-read results, not summaries.
Only the chosen variable subset may change relative to the parent; original task bounds
and static fields remain authoritative. Plan cannot set scores, model or thresholds.

Evaluate fields: schema_id=`optical-prescription-evaluation/v1`, round_id,
online_facts_ref (exact read-evaluation ref), plan_alignment
(aligned/partial/misaligned/unknown), observations, hypotheses, next_search_advice,
memory_action (none/insight). Distinguish observations from physical hypotheses.

An insight requires Evaluate to propose it. memory-write fields: id, kind=`insight`,
summary, body, based_on (latest version ref or null), evidence_ref (current online ref).
Describe task/sampling/candidate limits and uncertainty. No solution publication,
cross-task retrieval or audit evidence. Memory is optional and may be disabled.

execute/finalize return a task ID, not completed physics. Poll state, then collect and
read-evaluation. At hard search limits the runtime can seal and mark Agent Evaluate
skipped; do not manufacture an evaluation. finalize requires SEARCH_SEALED.

Audit eligibility: valid submission, complete online result, physics OK and online
feasible. Empty eligible queue is normal; diagnostic audit is not production verification.
MODEL/ONLINE unknown seals search. Audit unknown is incomplete; never retry its profile.
New effects require confirmation that an unknown process no longer runs.

Keep generation model, outer controller, protocol mode and costs separate. Unknown host
model/version fields are null, not guesses. Use adapted_external_controller unless the
original protocol has been explicitly verified. Never save credentials in manifests.
