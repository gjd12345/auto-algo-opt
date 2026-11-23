# Autonomous CO Research Charter (Milestone 3)

## Non-Negotiable Audit Rules
1. **Hard Budget Conservation**: Every outer planning/reflection call and every inner EoH generation/repair call deducts from ONE shared persistent `PersistentRequestBudget`.
2. **Evidence-Bound Hypotheses**: Never mark a hypothesis `supported`, `refuted`, or `abandoned` without citing at least one disk-persisted artifact path and exact SHA-256 checksum.
3. **Blind & Selection Isolation**: Work exclusively on `cvrp_dev_hetero_24` and synthetic fixtures during search. `cvrp_select_multiscale_64` and sealed blind suites (`cvrp_m2_blind_120`, `cvrp_m3_blind_120`, `cvrp_m32_blind_120`) are strictly forbidden in interactive tools and sandboxes.
4. **Five-Gate Interface Integrity**: Switch `(template_id, postprocess_mode)` only via registered templates that pass all 5 behavioral gates under the target per-instance time budget.
5. **Non-Destructive Archive**: Retain complementary stepping-stone solvers across regimes and time-quality Pareto trade-offs; target the highest-regret `weakest_regimes` in the next round.
