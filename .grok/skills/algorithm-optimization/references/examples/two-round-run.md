# Two-round Session example

Run in WSL2 Bash with the same Linux Python 3.11 virtual environment used to install the Runtime (see the repository README). This is a shape example: choose a fresh operation ID for each new mutation and reuse it on uncertain retries. Replace state-version placeholders with the latest `session state` value. The `<...>` placeholders are not runnable Bash syntax.

Use a provider model authorized for your account. Provide its key through the named process environment variable; never put the value in a plan, command-line argument or report. This example permits up to two Agent-controlled rounds; there is no automatic `--rounds` loop. After round 2 choose `complete`. Budgets can end execution earlier.

```bash
python -m agent_skill_loop session init \
  --output outputs/session-cvrp \
  --operation-id init-cvrp-001 \
  --problem cvrp_construct \
  --eoh-model "$EOH_MODEL" \
  --eoh-endpoint https://api.deepseek.com/v1/chat/completions \
  --eoh-api-key-env DEEPSEEK_API_KEY \
  --eoh-max-requests 16 \
  --eoh-round-max-requests 8 \
  --engine-wall-seconds 900 \
  --round-wall-seconds 300 \
  --max-solver-calls 20 \
  --default-pop-size 4 \
  --default-n-pop 2 \
  --default-max-sample-nums 8 \
  --max-pop-size 8 \
  --max-n-pop 5 \
  --max-sample-nums-per-round 16 \
  --memory-store outputs/memory-cvrp
```

The six search-policy flags freeze the Session defaults and admissible
per-round envelope. They do not force every round to use the same values.
The Agent may leave `search_policy` as `null` or request a partial override in
the plan; Runtime records the resulting effective policy and passes it to the
official EoH task.

Then repeat this controlled sequence for each round. The values shown as
`<...>` must be replaced with the values returned by the immediately
preceding command; they are not literal JSON values:

```text
state
→ optional memory search/read
→ write plan.json
→ submit-plan
→ execute
→ poll state until task is EXITED
→ collect
→ read-evaluation
→ write evaluation.json
→ submit-evaluation
→ finish-round --decision continue|complete
```

Round 1 example (`plan-r1.json`):

```json
{
  "round_id": 1,
  "direction": "Test residual-capacity fit as a tie break in next-node ranking",
  "operations": [
    {"type": "replace", "target": "ranking", "mechanism": "Prefer feasible nodes with smaller residual-capacity waste"}
  ],
  "preserve": "Problem interface, capacity constraints, evaluator and deterministic suite",
  "feedback_basis": null,
  "memory_basis": [],
  "reference_skill_ref": null,
  "hypothesis": "Residual-capacity fit may reduce avoidable route waste; this is unproven."
}
```

Submit it with the current state version:

```bash
python -m agent_skill_loop session submit-plan \
  --run outputs/session-cvrp \
  --operation-id plan-r1-001 \
  --expected-state-version <state_version_from_state> \
  --file plan-r1.json

python -m agent_skill_loop session execute \
  --run outputs/session-cvrp \
  --operation-id execute-r1-001 \
  --expected-state-version <updated_state_version>

# Poll state until the task is terminal, then collect with a fresh version.
python -m agent_skill_loop session collect \
  --run outputs/session-cvrp \
  --operation-id collect-r1-001 \
  --expected-state-version <current_state_version>

python -m agent_skill_loop session read-evaluation \
  --run outputs/session-cvrp
```

After reasoning from `read-evaluation`, submit an `evaluation.json` whose
observation references an exact returned evidence reference. New clients use
`aligned`, `partial`, `misaligned`, or `unknown` for `plan_alignment`:

```json
{
  "plan_alignment": "partial",
  "observations": [
    {"claim": "The candidate changed the ranking but did not improve every instance.", "evidence_refs": ["evaluation:<exact-id>"]}
  ],
  "hypotheses": [],
  "next_search_advice": {"direction": "Test a smaller residual-capacity perturbation."},
  "memory_action": {"kind": "none"}
}
```

```bash
python -m agent_skill_loop session submit-evaluation \
  --run outputs/session-cvrp \
  --operation-id eval-r1-001 \
  --expected-state-version <current_state_version> \
  --file evaluation.json

python -m agent_skill_loop session finish-round \
  --run outputs/session-cvrp \
  --operation-id finish-r1-001 \
  --expected-state-version <current_state_version> \
  --decision continue
```

Round 2 must copy the exact `feedback_basis` object returned by state after
round 1. Do not invent a filename, round number, or suite hash:

```json
{
  "round_id": 2,
  "direction": "Try a different capacity-distance coupling using the prior facts",
  "operations": [
    {"type": "replace", "target": "ranking", "mechanism": "Reduce the capacity term while retaining feasibility checks"}
  ],
  "preserve": "Problem interface, capacity constraints, evaluator and deterministic suite",
  "feedback_basis": {
    "round_id": 1,
    "evaluation_ref": "<exact feedback_basis.evaluation_ref from state>",
    "suite_hash": "<exact feedback_basis.suite_hash from state>"
  },
  "memory_basis": [],
  "reference_skill_ref": null,
  "hypothesis": "A smaller capacity term may avoid over-penalizing useful nearby nodes; this is unproven.",
  "search_policy": {"max_sample_nums": 12}
}
```

Use fresh operation IDs and the state version returned after each mutation for
the second `submit-plan → execute → collect → read-evaluation →
submit-evaluation → finish-round` sequence. The EoH task receives the bounded
plan context; it does not receive the Agent's private reasoning.

Inspect `session state` and the SQLite ledger after the run. The request purpose set must be a subset of `{eoh_probe,eoh_generation,eoh_repair}`, every completed solver row must have matching evidence, and an exported skill must reload with the same code and suite identity.
