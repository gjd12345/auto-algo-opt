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
  "hypothesis": "The change may reduce avoidable capacity waste; this is unproven."
}
```

Allowed operation types are `add`, `remove`, `replace`, and `preserve`. Each operation has only `type`, `target`, and `mechanism` (an optional `mechanism_note` is non-authoritative). Do not include code, objective, validity, budget, provider, evaluator, operator, or stop fields.

For round 2 and later, `feedback_basis` must be copied exactly from the current state's `feedback_ref` contract, including the previous round number, exact evaluation reference, and suite hash. It must point to the immediately previous round. Use `reference_skill_ref` only for the exact incumbent skill reference supplied by the Runtime. A selected Memory reference must be an exact, completely-read reference; submit at most two.

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

`plan_alignment` is `aligned`, `deviated`, or `unknown`. Every observation needs at least one exact evidence reference from the returned facts; hypotheses use `low`, `medium`, or `high` confidence. `next_search_advice` is optional and advisory.

When Memory is enabled, choose exactly one of:

- `{"kind":"none"}`;
- an `insight` with `name`, `description`, `project`, `scene`, `body`, and optional evidence/basis references;
- a `solution` with the same content plus exact `based_on` and `evidence_ref`, only when the verified generated skill passes the frozen solution threshold.

When Memory is disabled, use `{"kind":"disabled"}`. Never set a Memory action to publish a baseline, an invalid candidate, or a candidate whose code/evaluation identity does not match the supplied facts.
