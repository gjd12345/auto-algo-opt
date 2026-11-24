---
name: "dev-baseline-cvrp-parallel-merge-dynamic"
description: "CVRP cvrp_parallel_merge_dynamic baseline dev_train benchmark (16.2225)."
type: "insight"
project: "cvrp_construct"
scene: "select_next_node"
---

**Why:** Evaluated stock cvrp_parallel_merge_dynamic on 24 authorized dev_train cases (24/24 valid, penalized mean 16.2225; best baseline is cvrp_ruin_recreate at 16.1424).
**How to apply:** Use verified dev differences across templates to prioritize constructive vs ruin-recreate updates while keeping interface constraints intact.
**Limitations:** Baseline-only dev observation; verify any evolved candidate on the same evaluator.
