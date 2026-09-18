# Iteration A: evidence before interpretation

These are observational sidecars; the official EoH remains responsible for
operator, parent, and population selection. Scores and acceptance still come
only from the frozen evaluator and Session ledger.

- `execution_delta.json` compares each generated revision with verified actual
  parents when known and separately with the incumbent. `source_relation` is
  an exact code-hash comparison. `behavior_relation` is comparable only for
  complete traces on the same behavior contract, suite, and ordered instances;
  it never proves semantic equivalence. A missing or interrupted observation
  is `not_comparable`, not `same`.
- `evaluation_facts.json` links the delta by `ref` and `sha256`. The next
  round's bounded factual feedback links that evidence; it does not put
  candidate code, entire histories, or algorithm-family recommendations into
  the model prompt.
- `memory_consumption.json` at round finish separately records search,
  read, selected, compiled, omitted, gateway-attempt, and publication states.
  A compiled excerpt is not a request. A request attempted by the gateway is
  not proof of delivery, model attention, or improvement. Missing evidence
  stays explicit; do not silently claim an item was consumed.
- `startup_preflight.json` records the actual child-process loaded identity.
  Compare it with the Session's frozen implementation/Skill/evaluator/problem
  identity before treating solver or provider work as valid. Historical
  Sessions with older identities stay read-only.

## Reflection v2 (host Agent, not Runtime facts)

After `read-evaluation`, write the Evaluate observations and the next Plan's
`reasoning_summary` using this distinction:

1. **Observed:** cite exact evaluation or delta references for source change,
   valid/error, per-instance objective, behavior coverage, and the verified
   parent list (or say unknown).
2. **Interpretation:** state a falsifiable mechanism hypothesis and its
   scope; do not label a declared mechanism as executed merely because the
   Plan named it. Repeated source changes with identical complete behavior on
   this suite support only a suite-scoped observation.
3. **Decision:** choose one next experiment under the frozen Plan and budget
   boundaries. Explain which observed result it addresses and what distinct
   behavior or effect would test it. If evidence is inconclusive, say so.

Memory is optional. Publish only a scoped and reusable insight or gated
solution when the evidence actually supports it. `none` with a reason is a
valid decision. Keep Agent interpretations separate from deterministic facts.
