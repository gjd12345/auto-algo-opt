# Experiment readiness and Memory correction — 2026-09-18

Scope: native optics and CO Session Memory. No live provider calls; sealed T1/T3
evidence and previously installed experiment environments were not edited. This is
a working-tree acceptance record, not a claim of remote CI success or formal release.

## Review disposition

| Review item | Implementation / evidence |
|---|---|
| closure-parity | Downloaded run 35227017253 artifacts: only `/skill_hash` differs. Recomputed old commit bytes using PurePosixPath/PureWindowsPath ordering, reproducing both exact remote hashes. Fixed case-sensitive POSIX resource-name ordering; comparison gate retained with field-level diagnostics. Remote rerun pending push. |
| optics CI absent | Added Python 3.12 Ubuntu/Windows job: install, Skill validator, contract tests including two-round host Memory fixture, compile, outside-checkout wheel. Public CI does not include private task physics/verifier. |
| duplicate physics | Before cache lookup, isolated worker runs original static/variable checks against current parent and Plan. Full same-Session online identity required, complete evidence reloaded. Cache hit records source; generation/candidate charged, no new physics reservation. Baseline/imported parents still reassessed. Durable reuse receipt supports recovery. |
| audit provenance | Session audit now local_verification_audit/verification_pipeline=true; manual audit stays diagnostic. Independent verifier remains separate. |
| environment | Replaced hard-coded stdlib claim with measured installed distribution names/versions, dependency manifest hash, Python/platform/architecture. Conservative installed inventory, not a claim to resolve arbitrary external native dependencies. Task implementation hash remains separately frozen. |
| deterministic report | Optical Skill invokes artifact_session report; Agent prose stays outside computed table. Counts separate comparable/feasible/duplicates/reused and Memory read/publication. |
| SQLite | New databases add task/assessment/candidate/effect round FKs, assessment references and mode/effect checks. No migration/rewrite of sealed historical databases; exhaustive state constraints deferred. |
| README CLI | read-evaluation example includes --round. |

## Memory

- Insight body/scene prevalidation before Evaluate acceptance; required literal
  Why/How-to-apply sections documented in the self-contained CO Skill.
- memory-revise corrects failed/rejected current-round publication only, preserving
  original Evaluate/proposal. New idempotent operation, same evidence/threshold/CAS
  checks; no EoH/solver execution. Published or finished-round revisions rejected.
- New Skill submissions explain no-write decisions using MemoryAction.reason;
  historical none shape stays compatible. Enabled Plan defaults to search; deliberate
  skip/non-adoption explained in reasoning_summary. Memory-off experiments unchanged.
- State exposes publication status/write history/read pages. Injection manifest still
  distinguishes adopted/injected/omitted bodies. No forced writes or algorithm policy.

## Validation performed

- CO Memory subset: 5 passed; expanded failed-write→revision→next-round complete-read
  case passed separately. Resource-order regression passed.
- Optics initial targeted suite: 15 passed, 5 subtests; additional two-round host
  Memory fixture checked separately (no physics assertions).
- Python 3.11 CO / Python 3.12 optics compile and both Skill validators passed.
- Fresh wheel installed outside checkout: packaged Skill and both CLI imports passed.
- Private T1 two-round fixture: 2 fixture requests, 0 external requests, 2 online
  profiles (baseline + novel candidate), first generated baseline duplicate reused;
  Memory body enters round 2; completed with empty eligible audit queue.
  Local receipt: outputs/optics_readiness_fixture_20260918/fixture_receipt.json.

Not run: full repository regression, remote matrix, private T3 differential,
independent verifier, new paid experiments. No global optimality or Memory benefit
claim. New runtime/Skill identities require fresh Sessions, not bypasses on old runs.
