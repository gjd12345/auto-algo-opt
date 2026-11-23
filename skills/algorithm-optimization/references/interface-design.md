# Plan-Time Interface Diagnostics & Switching (Milestone 2)

This reference lets any Coding Agent harness (Claude Code, Codex, OpenCode,
Antigravity, Cursor) drive Milestone 2 plan-time interface design through the
standard recoverable `session` CLI without bypassing Session Runtime authority.

## 1. Harness-Agnostic Discovery & Diagnostics CLI

Run these read-only / diagnostic commands in `WAITING_FOR_PLAN` before
submitting `plan.json`:

```bash
# List registered versioned templates, hook signatures, source hashes, and KB clues
python -m agent_skill_loop interface list-templates

# Run 2x3 exploratory gap decomposition + target-budget headroom probe
python -m agent_skill_loop interface diagnose --output <diag_dir> --budget-ms 500
```

Inspect the returned JSON:
- `budget_probe.templates` reports `full_completion_rate`, `solve_ms_p50`,
  `solve_ms_p95`, and `n200_full_completion_rate` under the target budget.
- `recommended_interface` reports the deterministic diagnostic recommendation
  and `decision_trace` (0 LLM tokens). You may adopt it or justify another
  registered template in `plan.json`.

## 2. Submitting an `interface_selection` in `plan.json`

To switch or pin a registered template for the current round, include the
optional `interface_selection` object in `plan.json`:

```json
{
  "round_id": 1,
  "direction": "Switch from sequential pointwise construction to parallel merge priority scoring.",
  "operations": [
    {
      "type": "replace",
      "target": "score_merge_static",
      "mechanism": "Generalized scale-invariant Clarke-Wright savings with mild capacity-fill adjustment."
    }
  ],
  "preserve": "Exact feasibility and coordinate-scale invariance.",
  "feedback_basis": null,
  "memory_basis": [],
  "reference_skill_ref": null,
  "hypothesis": "Parallel route merging escapes pointwise route-partitioning bottlenecks on dev_24.",
  "interface_selection": {
    "template_id": "cvrp_parallel_merge_static",
    "template_version": "v1",
    "postprocess_mode": "none",
    "template_options": {"positive_savings_only": true},
    "cited_kb_ids": ["method-cvrp-cw-parallel"],
    "diagnostic_ref": {"path": "<diag_json>", "sha256": "<sha256>", "usage_role": "dev_selection"},
    "rationale": "2x3 gap decomposition shows pointwise + Relocate+2opt trails bare CW; L2a has full headroom."
  }
}
```

When you run `session submit-plan`:
- The Session Runtime automatically runs all **5 behavioral gates**
  (`InterfaceValidator`: AST whitelist, template/signature contract, subprocess
  feasibility, pre-postprocessing dual-action causal probe, and 500 ms budget /
  scale-drift diagnostics).
- If any gate fails, `submit-plan` rejects the plan with
  `INTERFACE_VALIDATION_FAILED` and persists `rounds/round_XXXX/interface_validation.json`
  with exact `line_no`, `symbol`, and `fix_hint`.
- If all 5 gates pass, `interface_design.json` and `interface_validation.json`
  are frozen inside the round directory. Execute and collect bind both artifacts
  to the successful plan receipt.

## 3. Execute, Collect, Evaluate, and Return Frozen Solvers to M1 Workbench

Proceed with the normal Session commands unchanged:

```bash
python -m agent_skill_loop session execute --run <run_dir> ...
# Poll `session state` until terminal, then:
python -m agent_skill_loop session collect --run <run_dir> ...
python -m agent_skill_loop session read-evaluation --run <run_dir>
```

`evaluation_facts.json` includes `interface_selection` and `frozen_solver_ref`
(`rounds/round_XXXX/eoh_run/frozen_solver_manifest.json`) when a generated
candidate passes the gates again. Review `winner_validation_report.json` for
the actual candidates checked. Review `interface_seed_receipt.json` for
compatible inherited candidates and template baselines across rounds. To independently
re-evaluate frozen round winners on the Milestone 1 Workbench:

```bash
python -m agent_skill_loop interface workbench-eval \
  --frozen-manifest <run_dir>/rounds/round_0001/eoh_run/frozen_solver_manifest.json \
  --output <bundle_dir> \
  --budget-id standard_500ms --budget-ms 500
```

## Guardrails

- Never load or reference `cvrp_m2_blind_120` during development, diagnostics, or
  Session rounds.
- Omitting `interface_selection` keeps 100% legacy `FrozenProblem` behavior.
- Never edit `eoh_frozen/` or registered template code from a Session plan.
- Re-run experiments in a new output directory. Compare attempted requests
  across planner, pilots, retries, and continuation using one arm-wide cap.
- The [Milestone 2 runbook](../../../docs/milestone2-reliability.md) covers
  custody, publication recovery, and historical comparison limits.
