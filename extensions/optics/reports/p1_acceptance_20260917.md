# P0 revision and P1 offline T1 acceptance — 2026-09-17

## Scope and verdict

P0 review amendments are incorporated. **P1 local offline adapter checks pass in the
recorded Windows environment.** This is not original-environment reproduction,
successful optical optimization, Session v2 acceptance, or an independent verifier PASS.

Worktree: `auto-algo-optics`; branch: `codex/optics-backend-v1`.
Base commit: `8a37fdda128e0f4032a2ac829ccf9f7ed56fb853`.
Implementation remains uncommitted at this handoff; no push was performed.

## Review disposition

| Review item | Resolution |
|---|---|
| Audit admission conflict | Single valid + complete + physics OK + online feasible predicate; empty eligible set means empty queue, no baseline forced into audit |
| Outer controller absent | Controller identity/hash distinct from generation provider, provenance and unavailable fields explicit; P3 freeze gate |
| UNKNOWN effects ambiguous | Separate MODEL/ONLINE/AUDIT consequence table; no new effects before process death is confirmed |
| Audit feedback leakage | Post-search audit retained; no resuming generation after seal |
| Capacity confused with effect rows | Init partitions capacity; actual audit startup atomically reserves four durable effects |
| Raw JSON extraction | Decoder token spans, UTF-8 byte offsets; no regex or reserialized raw claim |
| Original versus adapted protocol | Explicit mode and protocol_notes_hash; original label requires protocol evidence |

These are implemented document contracts. Session enforcement of controller/state/
budget/audit-queue rules belongs to P2, not to this P1 offline adapter.

## Validation performed

- Python 3.12 import and compileall passed.
- Four focused contract tests passed: strict input rejection, byte spans/canonicalization,
  S1/eligibility distinction, and comparison identity rejection.
- Imported 12 allowlisted T1 files with package/SHA256SUMS/acceptance hash validation.
- Initial prescription evaluated by both wrapper and unchanged upstream entrypoint.
- Full structured/numeric JSON equality, not just equal final score.
- Artifact/evidence hashes reload; S1 comparison reconstructed in a fresh process.
- Frozen asset tamper rejected; out-of-range candidate rejected with zero physical calls
  and no exported artifact.

| Mode | Original | Wrapper | Difference | Profiles, each side |
|---|---|---|---|---|
| online | ONLINE_FAIL | ONLINE_FAIL | None | 1 |
| diagnostic audit | FAIL | FAIL | None | 4 |

Baseline S1 key: `(0, -4.047660561176, -2.25, 0.2640065476546554)`.
The single deterministic sensor-z perturbation of +0.01 mm produced
`(0, -4.152784742252, -2.3, 0.26067846053208965)`; comparison retained the baseline.
Neither is a generated discovery. The baseline is comparable but infeasible and
would **not** enter the future production audit queue.

## Evidence and cost

Final local bundle: `extensions/optics/.local/p1_20260917_handoff/`.
Primary files: `p1_receipt.json`, `SHA256_manifest.json`, `comparison.json`,
`comparison_reloaded.json`, `adapter_online/`, `adapter_audit/`, `perturbed_online/`.
These raw task/evidence files are ignored, not intended for redistribution.

Final receipt SHA-256:
`9c893568a1dd6cd55acacd2977a3a040b330daa3260d6361cb0c505433727ae1`.
Final SHA256 manifest digest:
`82e3a1efce85f74394f77eb1130da7d33cefed15916ff1039905fc6cf642b707`.

Source package SHA-256:
`448cbfe470a26f7ed8ebc77d17fbc9e4a73660166493913f32f91de4a1b21076`.
Imported task contract hash:
`b69b61fe78ad14a28e7e52c9f6709ea8491cd4973cb3b5cf0869c095e5237db0`.

Final acceptance: 0 model requests; adapter 6 profiles, independent original-entrypoint
oracle 5 profiles, total 11. No assessment/profile double counting.
Two earlier development differentials each executed 11 profiles before error-classification,
receipt and nonregular-input tightening; the whole work session therefore used 33 physical
profiles, still 0 model requests. Earlier evidence is retained in `.local/p1_20260917/`
and `.local/p1_20260917_final/`, not mixed with the final bundle. The final check additionally
rejects directory input; the launcher preserves symlink identity for the worker's regular-file check.

Final measured wall time (includes process startup): online wrapper 0.672 s / oracle
0.438 s; four-profile audit wrapper 2.407 s / oracle 2.187 s. This is one tiny local
measurement, not a worst-case timeout or a P3 budget commitment.

## Isolation and unresolved gates

No edits in old `agent_skill_loop/`, `eoh_frozen/`, `skills/algorithm-optimization/`,
root `pyproject.toml` or original worktree's unrelated changes. New source resides
only in `extensions/optics/`; full CO regression was not run because no old execution
path was changed. Packaging compatibility remains P5 work.

Read-only comparison of the actual Runtime (`*.py` in the two packages) and Skill
(`*.md`/`*.yaml`) identity inputs found all 55 files byte-identical between the original
CO checkout and the optics worktree. Auxiliary files outside those hash inputs were
not used to claim identity equivalence.

Windows Python 3.12.11 differs from declared Linux Python 3.12.14. WSL startup failed
with `HCS_E_SERVICE_NOT_AVAILABLE`; no service configuration was changed. The receipt
explicitly sets `exact_original_environment_reproduction=false`.

Next step: repeat the same minimal differential in the declared environment when
available, then implement P2 Session lifecycle/effect ledger on this isolated branch.
No real model run is authorized or needed for that step. T3, queue execution, recovery,
Memory, Skill installation, wheel verification and independent verifier remain pending.
