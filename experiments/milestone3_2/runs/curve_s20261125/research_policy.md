# Autonomous CO Research Charter (Milestone 3)

## Non-Negotiable Audit Rules
1. **Hard Budget Conservation**: Every outer planning/reflection call and every inner EoH generation/repair call deducts from ONE shared persistent `PersistentRequestBudget`.
2. **Evidence-Bound Hypotheses**: Never mark a hypothesis `supported`, `refuted`, or `abandoned` without citing at least one disk-persisted artifact path and exact SHA-256 checksum.
3. **Blind & Selection Isolation**: Work exclusively on dev suites (`cvrp_dev_hetero_24`, `tsp_m31_dev_36`, `obp_m31_dev_36`, `bpp_m31_dev_36`) and synthetic fixtures during search. Selection suites and sealed blind suites (`cvrp_select_multiscale_64`, `tsp_m31_select_36`, `obp_m31_select_36`, `bpp_m31_select_36`, `cvrp_m2_blind_120`, `cvrp_m3_blind_120`, `cvrp_m32_blind_120`, `tsp_m31_blind_72`, `obp_m31_blind_72`, `bpp_m31_blind_72`) are strictly forbidden in interactive tools and sandboxes. Offline BPP must stay strictly separate from Online OBP (zero future lookahead in Online OBP).
4. **Five-Gate Interface Integrity**: Switch `(template_id, postprocess_mode)` only via registered templates that pass all 5 behavioral gates under the target per-instance time budget.
5. **Non-Destructive Archive**: Retain complementary stepping-stone solvers across regimes and time-quality Pareto trade-offs; target the highest-regret `weakest_regimes` in the next round.
