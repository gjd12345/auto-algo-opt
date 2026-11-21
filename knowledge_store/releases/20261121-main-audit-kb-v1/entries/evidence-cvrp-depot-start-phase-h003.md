# CVRP depot-start alpha=1 ranking switch and counterfactual swap (H-003)

For linear radial-savings constructive scoring `s_alpha(i, j) = d(i, j) - alpha * d(0, j)` on CVRP, at the depot departure step (`i = 0`) the score simplifies to `s_alpha(0, j) = (1 - alpha) * d(0, j)`. Minimizing `s_alpha(0, j)` undergoes a ranking switch at `alpha = 1` (ties at `alpha = 1` are governed by the tie-breaking rule).

## 定义或方法步骤

1. Evaluate the linear scoring family `s_alpha(i, j) = d(i, j) - alpha * d(0, j)` at `i = 0`:
   - `alpha < 1` selects the nearest feasible customer to the depot (inside-out departure), leaving peripheral customers for tail trips.
   - `alpha = 1` makes the primary term identically `0`, handing departure selection to the secondary tie-breaking rule.
   - `alpha > 1` selects the farthest feasible customer from the depot (outside-in departure).
2. Decouple the departure branch (`current_node == depot`) from mid-route scoring (`current_node != depot`) and perform counterfactual swaps replacing only `i = 0` while keeping mid-route rules (`V0`, `C`, `A`, `B`, `savings`) unchanged.

## 适用条件、假设与限制

- Applies to sequential single-route constructive heuristics under the `select_next_node` interface with Euclidean or metric distance matrices where `d(0, 0) = 0`.
- Pure-distance alpha-sweep numbers (`20.3165 -> 18.9302` across `alpha = 0.99 -> 1.01`, `-6.82%`, empty-return share `30.14% -> 23.22%`) are empirical tour-length measurements on the `ana72` 72-instance multi-scale suite (`n in {50, 100, 200}`, `{uniform, clustered}`, `Q = 40`, seed `20261123`).
- Replacing only the depot-start step does not overcome the structural gap between sequential single-node construction and global parallel route merging (e.g., Clarke-Wright merge).

## 来源及支持的具体结论

- Source: `src-cvrp-midterm-20261121` (`experiments/cvrp_midterm/REPORT_MIDTERM_SYNTHESIS.md`, `experiments/cvrp_midterm/analysis/boundary_analysis.json`, `experiments/cvrp_midterm/analysis/s2_holdout_eval.json`).
- On `ana72` (72 instances): pure-distance sweep drops from `20.3165` (`alpha=0.99`) to `18.9126` (`alpha=1.00, tie=far`) and `18.9302` (`alpha=1.01`); swapping only `i = 0` to `heavy_far` reduces `V0` from `20.2959` to `18.6124` (`-8.29%`) and `C` from `20.4104` to `18.7909` (`-7.93%`).
- On frozen `P0-120` blind test (`n = 50, 100, 200`, 40 instances each): keeping frozen `V0` mid-route scoring fixed and replacing only the departure step (`V0_decoupled_theory`) reduces `P0-120` total tour length by **7.96%** (mean `22.3910 -> 20.6081`), 95% paired Bootstrap CI `[6.88%, 8.98%]`, 0/10,000 non-positive resamples, `94/120` wins.

## 代码和评测关联

- Analysis script: `experiments/cvrp_midterm/analysis/boundary_analysis.py` -> `experiments/cvrp_midterm/analysis/boundary_analysis.json`.
- Blind evaluation script: `experiments/cvrp_midterm/analysis/eval_s2_holdout.py` -> `experiments/cvrp_midterm/analysis/s2_holdout_eval.json` (candidate `V0_decoupled_theory`, `code_sha256: bcb040b0555dd8199465141a689e92eaeb9a4449b1de94d14d316429d9f64a57`).
- Frozen blind suites: `reports/evidence/cvrp_p0_p1_p2_20261107/p0/suite_{50,100,200}.json` (read-only).

## 未确认项与冲突证据

- Exact optimal depot-start policy depends on remaining fleet demand (`rem_routes = sum(q)/rest_capacity`): late-stage compact seeds can outperform pure outside-in seeds on small residual sets.
- Results are validated on synthetic Euclidean CVRP instances (`n <= 200`); validation on CVRPLib Set X / asymmetric instances remains future work.
