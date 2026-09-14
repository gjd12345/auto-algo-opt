# OBP evolution mini profile

`obp_evolution_mini` is a new, deterministic six-instance profile for the
v1.1 cross-round wiring test. It does not replace the historical
`obp_mini` profile and is not a claim of reproducing the 128-instance EoH-S
asset.

The instances keep the EoH-S online bin-packing protocol: the evaluator owns
item order, feasibility filtering, stable first-maximum tie breaking, opening
a new bin, and the bin-count objective. Candidate code only implements
`priority(item, bins)`.

The four training references and two heldout references are known optima. They
were checked with `branch_and_bound_exact_bin_packing_v1` on the same item
multisets; the reference solver sorts only its private search order, while the
frozen evaluator preserves the manifest order. The small profile is designed
to make legal priority policies distinguishable:

| profile split | instances | known-optimum bins |
| --- | ---: | --- |
| `dev_train` | 4 | `5, 5, 7, 4` |
| `heldout` | 2 | `5, 4` |

For example, on the training instances, the deterministic calibration
policies produce different bin counts (`first_fit`, `best_fit`, and a
worst-fit probe), so a finite population can retain more than one valid
fitness value. This is a wiring/calibration asset, not a performance claim.
