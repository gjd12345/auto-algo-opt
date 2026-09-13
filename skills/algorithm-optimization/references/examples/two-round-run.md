# Two-round Session example

The following is a shape example. Replace every operation ID and state version with the values returned by the current run.

```powershell
py -3.11 -m agent_skill_loop session init `
  --output outputs/session-cvrp `
  --operation-id init-cvrp-001 `
  --problem cvrp_construct `
  --eoh-model deepseek-flash `
  --eoh-endpoint https://api.deepseek.com/v1/chat/completions `
  --eoh-api-key-env DEEPSEEK_API_KEY `
  --eoh-max-requests 16 `
  --engine-wall-seconds 900 `
  --round-wall-seconds 300 `
  --max-solver-calls 20 `
  --memory-store outputs/memory-cvrp
```

Then repeat this controlled sequence for each round:

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

The first plan has `feedback_basis: null`. A second-round plan must use the exact feedback reference returned by round 1 and may use only Memory references whose full bodies were read and recorded. The EoH task receives the bounded plan context; it does not receive the Agent's private reasoning.

Inspect `session state` and the SQLite ledger after the run. The request purpose set must be a subset of `{eoh_probe,eoh_generation,eoh_repair}`, every completed solver row must have matching evidence, and an exported skill must reload with the same code and suite identity.
