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
state.memory_status distinguishes not_decided, none, disabled, pending and published.
When enabled, a proposed insight blocks voluntary finish-round until memory-write
succeeds (MEMORY_PUBLICATION_PENDING). A hard deadline takes precedence. Do not
bypass CAS or write a post-seal draft into Runtime; report an unpublished draft honestly.

## Search-quality guidance

Read candidate online_diagnostics and prescription_delta before interpreting a
failed hypothesis. Signed focus_error_mm is not an absolute constraint violation.
For unchanged geometry, sensor_delta = target_signed_error - measured_signed_error.
Changing curvature or thickness changes the focal plane: recompute compensation.
Report focus_constraint_margin_mm separately from dimensionless normalized margin.
A feasible boundary point is not evidence of tolerance robustness.

Duplicate parents do not test a new mechanism. selected_but_unchanged is diagnostic,
not a violation: variables_to_adjust permits changes rather than requiring all of them.
Separate malformed/unexecuted proposals, wrong compensation, constraint failures,
and genuinely evaluated but worse mechanisms. Consecutive failures trigger diagnosis,
not an unconditional family switch. Correct a localized execution mistake before
rejecting a mechanism; use distinct, physically coupled hypotheses after genuine ties
or worsening. Keep task bounds, ranking, budget and audit isolation unchanged.

For shape/thickness comparisons, state intended focal/defocus compensation and
actual deltas; a small number of local probes cannot exclude an entire family.
Report batch completion separately from target attainment, and user-reported
reference scores separately from verified same-protocol comparisons. Costs from
the generator do not include the host Agent or supervisor. Do not label this EoH.

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
