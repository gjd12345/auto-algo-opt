# OBP research workflow

## Read the relevant evidence

- Start with `session state --run RUN_DIR`. It provides the current round,
  budget, incumbent reference, frozen configuration reference and previous
  `feedback_basis`, when available.
- At cold start, resolve `obp_online` through
  `agent_skill_loop.problems.base.get_problem`. Read the ProblemSpec's
  `task_description`, `template_program` and `baseline_code`. The current
  run's `config_frozen.json` and `dev_suite.json` identify its settings and
  development data. Benchmark and metric identities are in the Session state
  for benchmark runs. Historical evaluation evidence may be unavailable.
- After collection, use `session read-evaluation --run RUN_DIR --round N`
  for verified candidate code, per-instance objectives and available metrics.
  Add `--candidate` to focus on a candidate, or `--include-diff` for a diff
  against the baseline. Follow the returned references to `execution_delta`
  and `comparison_packet` when relevant. These distinguish source changes,
  lineage, observed behavior and performance. Behavior evidence includes a
  digest and bounded event excerpts, so an unobserved step may be unavailable.
- Read earlier Plans or retrieve relevant knowledge only when it informs the
  current decision. Record exact references to materials used and retain
  existing hashes where the Session supplies them. Use development data for
  search and research analysis.

## Decide whether to analyze

Choose the next research action based on the evidence. An uncertain design
choice, stagnation or a failed instance may motivate a derivation, a numerical
check, or a review of candidate behavior. Use the host Agent's existing tools
and knowledge. When direct exploration is appropriate, continue with an
ordinary Plan. Keep any numerical investigation separate from the frozen
evaluator's ranking and use Session accounting for candidate evaluations.

If an analysis informs the next round, express the design change in
`direction` and `operations[].mechanism`, the constraints to retain in
`preserve`, and the expected observable effect in `hypothesis`. For
example, if an analysis identifies states where two candidates make the
same choice, the Agent may ask EoH to explore a change that distinguishes
those states and check for an actual decision difference in the available
evidence. Choose the mechanism from the current research, without requiring
a prescribed function family.

## Record the decision

Add `research_activity` to the Plan when recording a decision. The field
`mode` is required inside the object. All other fields are optional.

```json
{
  "research_activity": {
    "mode": "used",
    "trigger": "design_uncertainty",
    "question": "Do the two scoring rules make different choices on the development instances?",
    "finding_summary": "The available complete behavior signatures agree on this suite.",
    "finding_status": "empirical_observation",
    "decision": "modify",
    "decision_summary": "Explore a scoring change that can produce a different ordering.",
    "evidence_refs": ["rounds/round_0001/comparison_packet.json"]
  }
}
```

- `mode`: `used` or `not_used`. An omitted object leaves the decision
  unrecorded. For `not_used`, an optional `decision_summary` can explain the
  choice to proceed directly.
- `trigger`: `cold_start`, `stagnation`, `badcase`, `design_uncertainty`,
  `other`, or `not_applicable`.
- `finding_status`: `proved_under_assumptions`, `empirical_observation`,
  `hypothesis`, `inconclusive`, or `not_applicable`. State the assumptions
  of any derivation in the summary. Finite observations have the scope of
  the data examined.
- `decision`: `modify`, `retain`, `abandon`, `no_change`, or `not_applicable`.
- `evidence_refs`: exact references to sources actually used, such as a
  run-relative artifact path or a prior evaluation identity. These are
  Agent-reported references. The Runtime stores the list as metadata.

Use public findings and decisions. The normalized Plan retains the metadata
while Round Context compiles the existing search guidance fields.

## Follow the result

1. Link the normalized Plan to `context_manifest.json` using the Plan hash.
   Check whether guidance was enabled, shortened or omitted.
2. From the collected candidate, follow `generation_request_ref` to the
   actual prompt in the Session directory to check delivery. The compact
   benchmark export retains the normalized Plan but omits raw exchanges.
3. Use the candidate's evaluation ID and code SHA to connect its
   `execution_delta` and `evaluation_facts`. In Evaluate, use the existing
   `observations`, `hypotheses` and `next_search_advice` to record what the
   candidate implemented, what the result supports and what to try next.
   Delivery of advice, its adoption, and candidate performance are separate
   observations.
