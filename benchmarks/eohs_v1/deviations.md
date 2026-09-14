# EoH-S compatibility deviations

This repository freezes the benchmark protocol before claiming reproduction.
The `obp_mini` profile is a deterministic, small, regenerated fixture for
offline wiring and differential tests. It is not the EoH-S 128-instance
training set and it is not an exact reproduction of the paper's reported
test sets.

The `obp_evolution_mini` profile is a separate deterministic six-instance
profile for cross-round population-seed tests. It keeps the same online
protocol but uses fixed known-optimum references and deliberately
distinguishable legal priority policies. It is also not an upstream asset.

- `upstream_code` and `paper_protocol` are separate profiles.
- The OBP reference uses the upstream-compatible rounded lower-bound formula;
  it is recorded as `upstream_compatibility_reference`, not as a known optimum.
- The full upstream OBP/TSP/CVRP assets are not bundled in v1.1a. Missing
  assets remain `missing` until their bytes and license are verified.
- The mini fixture is used by the offline harness and never by a provider
  request or by a formal performance claim.
