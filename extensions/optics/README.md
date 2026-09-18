# Optical prescription optimization

Independent Python 3.12 package for optimizing **prescription artifacts**, not
generating optimizer algorithms. Existing Python 3.11 CO packages, official EoH and
algorithm-optimization Skill remain unchanged.

Host Agent Plan/Evaluate → serial prescription generation → original physics in
a child process → trusted S1 acceptance → next round. Optional online-only insight
memory is separate. Search seals before a frozen four-profile audit queue.

## Install and use

```powershell
& $opticsPython -m pip install ./extensions/optics
& $opticsPython -m optics_backend --help
& $opticsPython -m artifact_session --help
```

The wheel contains optics_backend, artifact_session and optical_design_skill
resources, with no EoH or third-party runtime dependency. Read the
[optical-design Skill](skills/optical-design/SKILL.md) for host actions.

Task assets are not distributed. Use optics_backend import-task with the reviewed
archive, its SHA256, and task optics-t1-singlet or optics-t3-triplet. Consult --help
for arguments. Keep the imported task contract hash.

```text
python -m artifact_session init --run <new-directory> --file <config.json>
python -m artifact_session state --run <directory>
python -m artifact_session submit-plan --run <directory> --file <plan.json> --operation-id <unique-id> --expected-state-version <version>
python -m artifact_session execute --run <directory> --operation-id <unique-id> --expected-state-version <version>
python -m artifact_session collect --run <directory> --operation-id <unique-id> --expected-state-version <version>
python -m artifact_session read-evaluation --run <directory> --round <n>
python -m artifact_session report --run <directory> --output <report.md>
```

Continue with submit-evaluation/finish-round; finalize after search seals. Fetch
state versions rather than guessing. tools/prepare_pilot.py demonstrates config
preparation without requests. Credentials are environment-only. Every run freezes
finite request/profile/deadline limits, even if the overall research budget is open.
Code changes require a new Session, not identity bypass on a historical run.

### Continue from an online parent

An optional `online_parent` in a new Session config contains `source_run`,
`assessment_id`, `facts_sha256`, and `canonical_artifact_sha256`. The source must
be sealed, have no running task, and contain a complete online assessment of the
same task. Audit assessments are rejected. Initialization freezes a verified copy
of the prescription; the original task baseline stays unchanged.

Before generation, the new run evaluates both baseline and imported parent using
its own online evaluator and budget. Only a strictly better parent replaces the
incumbent. Reserve two startup online profiles instead of one. Inherited parents
are not generated discoveries; reports show baseline/parent/generated costs
separately. Completed parent reassessments recover idempotently without replay.
Old frozen Sessions must keep their original installation; install the changed
Runtime in a separate environment for new Sessions.

## Focused offline acceptance

Use a fresh output directory and PYTHONPATH=extensions/optics/src for checkout tests.
All these tools make zero external model requests:

- tools/verify_p1.py: T1 import and independent upstream differential.
- tools/verify_task_differential.py: T1/T3 original-entrypoint comparison.
- tools/verify_session.py: two rounds, feedback and Memory consumption.
- tools/verify_lifecycle.py: profile timeout and owned process cancellation.
- tools/verify_audit.py: PASS, unknown-audit continuation and invalid fallback.
- tools/verify_evidence.py --run <directory>: read-only hash-chain/facts reload.

## Boundaries

See [P0–P5 acceptance and live results](reports/p0_p5_acceptance_20260917.md).
Windows Python 3.12.11 was exercised; original Linux Python 3.12.14 is unverified.
The prior T1 final prescription separately passed the supplied independent verifier
on Windows (22 assertions). Local audit PASS alone is not verifier certification.
T3 was calibrated offline, not optimized with a live model.

Evidence assumes a trusted host. Digests are not signatures and process isolation
is not a malicious-evaluator sandbox. Physics children have no provider credential;
OS-enforced network denial is not implemented. Unknown effects are never replayed.
Recovery validates complete durable assessment receipts against task, artifact,
environment and effect identities before atomically restoring assessment/candidate/
incumbent state. Incomplete receipts are not promoted; conflicts fail closed and
live children block recovery. See the recovery addendum in the acceptance report.

Private assets, raw evidence and credentials must not be committed.
The [P1 acceptance](reports/p1_acceptance_20260917.md) is historical.
