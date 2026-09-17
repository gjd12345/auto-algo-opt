---
name: optical-design
description: Drive bounded native JSON optical-prescription sessions for registered T1/T3 tasks, using online physics feedback and post-search audit. Not for CO/EoH algorithm evolution.
---

# Optical design

Use the independent `artifact_session` runtime, not `agent_skill_loop`. Read
[protocol](references/protocol.md) before starting or continuing a Session.

The host Agent owns Plan, Evaluate, insight proposals and continue/complete decisions.
The runtime owns budgets, S1 acceptance, immutable facts and audit admission. A backend
model generates complete prescriptions, not Python code or trusted scores.

Read `state` before every mutation; use a new operation ID and current state version.
On uncertain mutation outcomes reuse that exact ID/input, never issue a new search.
Do not change frozen model/configuration or expand budget while a run is active.

Every round: consume prior online facts, propose a physically motivated variable
subset, execute, collect, inspect results, submit evidence-grounded Evaluate, optionally
write a bounded insight, then continue or seal. Do not mistake ties for improvement.
Update the round progress table after each completed round and print the full table
before the final summary. Use only runtime facts; missing values remain unknown.

Audit runs only after search is sealed. Never route audit observations back into Plan,
generation or Memory. Local audit PASS is not independent verifier PASS. A baseline
fallback is not a successful discovery. Do not import historical answers or arbitrary
author archives into prompts. Stop on identity/evidence errors rather than bypassing them.

No improvement is required for engineering acceptance. For effectiveness work, propose
new, separately frozen runs based on online evidence and the user's authorized budget;
never silently extend a running Session.
