## Benchmark contract

This is the focused benchmark and CLI contract bundled with the
`algorithm-optimization` Skill. It is intentionally self-contained so a
packaged Skill does not depend on files outside its own directory.

### Scope and commands

Benchmark mode is offline and read-only with respect to providers. It must not
create a Session or send an LLM request for audit, calibration, evaluation, or
report assembly.

The repository CLI exposes these operations:

```text
python -m agent_skill_loop benchmark audit
python -m agent_skill_loop benchmark calibrate-obp --gold <gold.json>
python -m agent_skill_loop benchmark evaluate --code <candidate.py> --split dev_train
python -m agent_skill_loop benchmark evaluate-set --candidates <candidates.json> --split dev_train
python -m agent_skill_loop benchmark snapshot --population <population.json> --generation <n> --metric-spec-hash <sha256> --output <snapshot.json>
python -m agent_skill_loop benchmark freeze-selection --kind <selection_kind> --population-snapshot <snapshot.json> --metric-spec-hash <sha256> --output <selection.json>
python -m agent_skill_loop benchmark evaluate-selection --selection <selection.json> --split heldout --output <test_result.json>
```

`audit` verifies registered asset byte hashes. `calibrate-obp` compares the
independent upstream-compatible implementation with the production evaluator
and uses zero provider calls. A benchmark candidate set retains invalid-member
evidence and partial per-instance successes. Its aggregate is reconstructed
from the minimum valid member gap for each instance; missing instance coverage
is incomplete, not silently filled.

### Registered assets and identity

The default profile is `eohs_v1/obp_mini`. It is a regenerated,
protocol-compatible fixture, not an exact copy of the full upstream corpus.
The loader must bind a suite to the registered asset. A caller-declared
manifest hash is not sufficient: normalized instance content, order,
identifiers, and reference values must match the registered file.

Every evaluation is identified by the complete tuple:

```text
candidate_code_sha256
problem_spec_hash
data_manifest_hash
evaluator_hash
metric_spec_hash
```

The benchmark `MetricSpec` is the only training ranking signal. For OBP it is
the mean per-instance relative gap. Raw objective and reference objective are
stored as facts and do not replace the gap. `reference_kind` must be one of
`known_optimum`, `best_known`, `solver_reference`, `analytical_reference`, or
`upstream_compatibility_reference`.

### Session and inheritance

Benchmark Sessions freeze benchmark, problem, data, reference, and metric
hashes before EoH starts. A `PopulationSnapshot` preserves the official final
population in original order, including generation, member index, algorithm
text/hash, code/hash, objective, evaluation id, revision, and origin. It is
not sorted, deduplicated, or truncated.

`SeedSelection` is a separate deterministic derivation:

```text
valid filter -> code hash deduplication -> stable fitness sort
-> target population truncation -> complete re-evaluation
```

The supported inheritance modes are `incumbent_only`, `population_seeds`, and
`explicit_seeds`. `population_seeds` cold-starts only the first round; later
rounds require a verified preceding snapshot. Insufficient seeds are an
explicit terminal condition and never trigger a silent cold-start substitute.
Seed reevaluation is charged to the shared evaluator budget.

### Selection and test isolation

`FrozenSelection.selection_kind` is exactly one of:

```text
incumbent_top1
archive_topk
final_population_set
```

Training archive and heldout results are separate. Test evaluation requires a
locked selection and the registered `heldout` suite for the same benchmark and
problem. It verifies benchmark, suite, data, reference, problem, and metric
identities, and cannot update archive, Memory, or incumbent. Reports must
recheck the same identities and reconstruct the per-instance member matrix
from the member evidence; contradictory cells or aggregates are rejected.

### Budget and controlled pilot

Each run reports both total and derived evaluator attempts:

```text
total_evaluation_attempts
novel_candidate_evaluations
seed_reevaluation_attempts
baseline_attempts
repair_attempts
```

The controlled pilot uses one Runtime adapter:

```text
A: one full Session, neutral Plan, initial population
B: fixed multi-round Session, incumbent_only, factual feedback, neutral Plan
C: fixed multi-round Session, population_seeds, factual feedback, neutral Plan
D: same as C, with adaptive Agent guidance
```

A/B are interpreted only as continuous EoH versus a sessionized baseline. C/D
compare Agent guidance with the same inheritance, feedback, and budget. Memory
and repair are off unless the experiment manifest explicitly enables them.
