# Plan and Evaluate documents

The Runtime accepts strict JSON. Keep files as one JSON object with no code fences and no extra authority fields.

## `plan.json`

Required fields:

```json
{
  "round_id": 1,
  "direction": "Change the next-node ranking while preserving feasibility",
  "operations": [
    {"type": "replace", "target": "ranking", "mechanism": "Use residual-capacity fit as a tie break"}
  ],
  "preserve": "Problem interface, capacity constraints, evaluator and deterministic behavior",
  "feedback_basis": null,
  "memory_basis": [],
  "reference_skill_ref": null,
  "hypothesis": "The change may reduce avoidable capacity waste; this is unproven.",
  "search_policy": null,
  "reasoning_summary": "The host Agent selected this bounded experiment because ..."
}
```

`reasoning_summary` is optional, non-authoritative metadata for the host
Agent's explanation. It is saved with the submitted Plan but is not a source
of Runtime facts and is not injected into the official EoH context.

Allowed operation types are `add`, `remove`, `replace`, and `preserve`. Each operation has only `type`, `target`, and `mechanism` (an optional `mechanism_note` is non-authoritative). Do not include code, objective, validity, budget, provider, evaluator, operator, or stop fields.

For round 2 and later, copy `state.feedback_basis` exactly, including the previous round number, exact evaluation reference, and suite hash. `state.feedback_ref` is the legacy path-only field, not an object. The basis must point to the immediately previous round. Use `reference_skill_ref` only for the exact incumbent skill reference supplied by the Runtime. A selected Memory reference must be an exact, completely-read reference; submit at most two.

`search_policy` is optional and Runtime-bounded. Use `null` to inherit the
Session defaults, or provide any subset of `pop_size`, `n_pop`, and
`max_sample_nums` to request a different round allocation. The Runtime records
the effective values and rejects a value outside the frozen limits with
`PLAN_SEARCH_POLICY_OUT_OF_BOUNDS`; this field cannot change hard budgets.

For round 2 and later, the EoH context also contains a Runtime-generated
`feedback_summary`. It is a bounded fact record from the previous round with
the incumbent and best generated identities/objectives/delta, per-instance
objectives, generated valid/invalid counts, major errors, evidence references,
and suite/evaluator hashes. It never contains candidate source code or a
Runtime-selected search recommendation. The Agent must use these facts when
explaining the next Plan, but remains responsible for the search decision.

## `evaluation.json`

Use the deterministic facts from `read-evaluation`; do not recalculate or claim a causal improvement from one run. The accepted shape is:

```json
{
  "plan_alignment": "aligned",
  "observations": [
    {
      "claim": "The generated candidate was valid on every development instance.",
      "evidence_refs": ["evaluation:evaluation-id"]
    }
  ],
  "hypotheses": [
    {
      "claim": "The ranking change may help when residual capacity is tight.",
      "confidence": "low",
      "evidence_refs": ["evaluation:evaluation-id"]
    }
  ],
  "next_search_advice": {"direction": "Try a different capacity-distance coupling next round."},
  "memory_action": {"kind": "none"}
}
```

`plan_alignment` MUST be one of `aligned`, `partial`, `misaligned`, or `unknown`:

- `aligned`: the observed implementation follows the submitted direction;
- `partial`: only some of the direction was implemented or supported by evidence;
- `misaligned`: the observed implementation materially differs from the direction;
- `unknown`: the available evidence is insufficient to determine alignment.

`deviated` is accepted only for historical Session-client compatibility. New Skill submissions MUST use `misaligned` instead. Every observation needs at least one exact evidence reference from the returned facts; hypotheses use `low`, `medium`, or `high` confidence. `next_search_advice` is optional and advisory.

When Memory is enabled, choose exactly one of:

- `{"kind":"none"}`;
- an `insight` with `name`, `description`, `project`, `scene`, `body`, and optional evidence/basis references;
- a `solution` with the same content plus exact `based_on` and `evidence_ref`, only when the verified generated skill passes the frozen solution threshold.

When Memory is disabled, use `{"kind":"disabled"}`. A baseline or invalid candidate cannot become a solution. An invalid candidate may support a specific failure insight with its real evidence reference; do not turn one failure into an unconditional ban or fabricate code/evaluation identity.
