# Evolution Trajectory Deep-Dive Audit (M3.0 / M3.1 / M3.2) — Engineering & Empirical Data Report

> **Target Audience**: Autonomous coding/research agents fixing repository bottlenecks and preparing post-M4 improvements.  
> **Strict Read-Only Provenance**: All metrics below were extracted strictly read-only (`?mode=ro&immutable=1`) from existing artifacts across **42 outer-agent runs** (`791` outer turns) and **4,800 M3.2 physical LLM requests** (`12` runs × `400` cap), persisted in [`experiments/milestone4/trajectory_deep_dive_metrics.json`](trajectory_deep_dive_metrics.json). No source file, test, or existing experiment artifact was modified during this audit.

---

## 0. Audit Scope & Executive Takeaways

| Scope Dimension | Count / Value | Primary Sources |
|---|---:|---|
| Outer-agent runs audited | **42 runs** (`18` M3.0 + `12` M3.1 + `12` M3.2) | `experiments/milestone3/phase3c_four_arm/`, `experiments/milestone3_1/runs/`, `experiments/milestone3_2/runs/` |
| Total outer-agent LLM turns | **791 turns** (`190` M3.0 + `166` M3.1 + `435` M3.2) | `agent_artifacts/agent_turns.jsonl` |
| M3.2 physical requests audited | **4,800 requests** (`12` runs × `400`) | `agent_budget.sqlite3` (`budget_requests`, `candidate_provenance`, `milestone_checkpoints`) |
| M3.2 valid generated candidates | **2,029 / 4,800 (`42.27%`)** | `candidate_provenance` (`generation_status = 'valid_candidate'`) |
| M3.2 `search_progress` events (`behavior_comparable`) | **3,239 events / `0` comparable (`0.0%`)** | `session_run/rounds/round_*/evaluation_facts.json` |
| Outer runs using `run_math_sandbox` | **2 / 42 (`4.76%`)** (`2 / 791` turns, `0.25%`) | `agent_turns.jsonl` |
| Outer runs using `propose_and_validate_interface` | **0 / 42 (`0.0%`)** | `agent_turns.jsonl` |
| M3.2 runs peaking at `ordinal <= 100` | **4 / 12 (`33.33%`)** (wasting `76.0%–86.8%` post-peak budget) | `candidate_provenance` |

**Five High-Signal Findings:**
1. **AST Whitelist Friction Is the #1 Yield Killer**: Out of `1,040` invalid M3.2 candidates, **`775` (`74.5%`)** were rejected by `forbidden_attribute`, led by benign allocation/math primitives missing from `agent_skill_loop/evaluator.py:90-102` (`_NUMPY_ATTRIBUTES`): `np.empty` (`453`), `np.tanh` (`145`), `np.fill_diagonal` (`68`), `np.sign` (`45`), `np.mod` (`30`), `np.stack` (`27`), `np.nan_to_num` (`24`), `np.ix_` (`14`). In M3.1, `np.ix_` (`26`) and `Lambda` (`23`) caused 2/3 seeds of `tsp_l1` to end in `no_champion`.
2. **Punctuated Equilibrium & 42.1% Mean Post-Peak Waste**: Across 12 M3.2 runs (`400` cap), global dev peaks occurred at mean ordinal **`231.67`** (median **`268.5`**, min **`53`**, max **`398`**), leaving **`42.08%`** of budget post-peak without improvement. `4/12` runs peaked before ordinal `100`.
3. **Severe Outer-Agent Tool Inertia & Ledger Pathology**: Across `791` outer turns, the controller relied heavily on `kb_search` (`161`) + `kb_read` (`113`) + `archive_summary` (`93`) + `list_interfaces` (`75`), while calling `diagnose_suite` only **`18` times (`2.28%`)** and `run_math_sandbox` only **`2` times (`0.25%`)**. Moreover, **`9` runs** called `hypothesis_update` without `hypothesis_propose` (`unknown_hypothesis` errors), and `hypotheses.jsonl` accumulated duplicate append-only `supported` rows (e.g., `timeout_2000ms_s20261124` has `12` rows for only **`1` distinct hypothesis ID**).
4. **Search-Progress Blindness**: Every M3.2 `evaluation_facts.json` has `search_progress.behavior_comparable = false` on all **`3,239/3,239`** attempt-trace events and `source_duplicate_rate = 0.0` in round summaries, disabling behavior-novelty backpressure.
5. **Champion Genealogy Surprises (`timeout_2000ms_s20261124`)**:
   - **Jump #8 (`ord=173`, `dev=15.980136`, `delta=-0.097931`, `sha=cd8aaa033dd5`)** is a **negative-log clamping degeneracy**: all 5 log terms (`log_s, log_p, log_l, log_sp, log_r`) evaluate `<= 0` across realistic routes, so `np.maximum(score, 0.0)` clamps the score vector to **all zeros**, yielding **exact `0.000000` parity** with `lambda ...: np.zeros(n)` (`dev_24` mean = `15.980136`).
   - **Jump #9 (`ord=242`, `dev=15.837376`, `delta=-0.142760`, `sha=8c4dfb41aa5f`)** breaks out via Round-5's explicit `slack_r` + `1/n_stops` sparsity + 3-phase logit + Gumbel `noise_amp`, **but** contains a **dead `temp` variable intron** (lines 78–79 compute and clip `temp`, never read anywhere in `logit + noise`), alongside unused input aliases `rload`, `rdist`.

---

## 1. Request-to-Candidate Conversion Funnel & Failure Taxonomy

### 1.1 M3.2 Aggregate Conversion Funnel (`4,800` Physical Requests Across `12` Runs)

```text
Physical Requests (4,800 = 100.00%)
 ├── Transport / Provider Loss: 543 (11.31%) [connectivity_failed: 422 | http_error: 118 | killed_unknown: 3]
 └── Completed HTTP Responses: 4,257 (88.69%)
      ├── Baseline Seeds: 12 (0.25%)
      ├── Outer Controller / Probe / Fallback overhead: ~537 (incl. 85 validation probes + outer turns)
      ├── EoH Skipped (parse/format mismatch): 668 (13.92%)  <-- 497/668 (74.4%) inside 3 l3b_dual_hook runs
      ├── Invalid Candidates (AST/Runtime/Bundle): 1,040 (21.67%) <-- 775/1,040 (74.5%) forbidden_attribute
      └── Valid Executable Candidates: 2,029 (42.27%)
           └── Global-Best Improving Jumps: 71 across 12 runs (1.48% of requests, 3.50% of valid candidates)
```

### 1.2 M3.2 Per-Run Funnel Table

| Run Name | Req `complete` | `http` / `conn` / `kill` | `valid` | `invalid` | `eoh_skipped` | `probe` | Top Failure Causes |
|---|---:|---|---:|---:|---:|---:|---|
| `curve_s20261124` | 348 | 20 / 31 / 1 | **246** | 54 | 6 | 7 | `forbidden_attribute` (53), `hook_runtime_exception` (1) |
| `curve_s20261125` | 349 | 15 / 35 / 1 | **204** | 97 | 7 | 7 | `forbidden_attribute` (93), `forbidden_syntax` (3) |
| `curve_s20261126` | 354 | 11 / 34 / 1 | **204** | 105 | 4 | 7 | `forbidden_attribute` (102), `forbidden_syntax` (2) |
| `l3b_dual_hook_s20261124` | 360 | 8 / 32 / 0 | **78** | 75 | **170** | 6 | `invalid_hook_bundle_program` (75), dual parse skip (170) |
| `l3b_dual_hook_s20261125` | 356 | 8 / 36 / 0 | **73** | 88 | **159** | 6 | `invalid_hook_bundle_program` (88), dual parse skip (159) |
| `l3b_dual_hook_s20261126` | 365 | 2 / 33 / 0 | **100** | 67 | **168** | 5 | `invalid_hook_bundle_program` (66), `nonfinite_objective` (1) |
| `model_routing_s20261124` | 361 | 2 / 37 / 0 | **188** | 97 | 34 | 7 | `forbidden_attribute` (89), `signature_mismatch` (4) |
| `model_routing_s20261125` | 355 | 7 / 38 / 0 | **150** | 97 | 60 | 8 | `forbidden_attribute` (93) |
| `model_routing_s20261126` | 358 | 4 / 38 / 0 | **177** | 84 | 54 | 7 | `forbidden_attribute` (81), `forbidden_syntax` (2) |
| `timeout_2000ms_s20261124` | 349 | 14 / 37 / 0 | **202** | 90 | 4 | 8 | `forbidden_attribute` (85), `hook_runtime_exception` (3) |
| `timeout_2000ms_s20261125` | 347 | 20 / 33 / 0 | **194** | 96 | 0 | 9 | `forbidden_attribute` (93), `forbidden_syntax` (2) |
| `timeout_2000ms_s20261126` | 355 | 7 / 38 / 0 | **213** | 90 | 2 | 8 | `forbidden_attribute` (86) |

### 1.3 Exact Invalid-Candidate Failure Breakdown (`M3.2` + `M3.1`)

- **M3.2 Aggregate `error_code` counts (`n = 1,040`)**: `forbidden_attribute` (**775**), `invalid_hook_bundle_program` (**224**), `forbidden_syntax` (**15**), `hook_runtime_exception` (**13**), `signature_mismatch` (**6**), `invalid_code` (**2**), `forbidden_rebinding` (**2**), `nonfinite_objective` (**1**), `invalid_return` (**1**), `forbidden_import` (**1**).
- **Top exact `error_detail` causes in M3.2**:
  - `np.empty`: **453** (`406` single-hook + `47` bundle messages)
  - `np.tanh`: **145** (`100` + `45`)
  - `np.fill_diagonal`: **68**
  - `np.sign`: **45** (`33` + `12`)
  - `hook_bundle_names_mismatch: Source units must match the declared hook names`: **42** (in `l3b_dual_hook`)
  - `np.mod`: **30**, `np.stack`: **27**, `np.nan_to_num`: **24**, `np.ix_`: **14**, `np.at` (e.g. `np.add.at` / ufunc `.at`): **10**, `np.bincount`: **10**
- **M3.1 Per-Run Funnel (`12` runs, `B_total=36`)**:

| Lane (`3` seeds total) | Valid | Invalid | Top Failure Details |
|---|---:|---:|---|
| `tsp_l1` (`s24 / s25 / s26`) | `6 / 11 / 4` (`21`) | `15 / 7 / 12` (`34`) | `np.ix_` (`26` across M3.1), `np.empty` (`6`), `np.fill_diagonal` (`3`), `invalid_return` (`2`) — caused **`s24` & `s26` `no_champion`** |
| `tsp_l2` (`s24 / s25 / s26`) | `16 / 16 / 13` (`45`) | `5 / 3 / 3` (`11`) | `Lambda` (`forbidden_syntax:Lambda`, `23` across M3.1), `np.lexsort` (`2`) |
| `obp_online` (`s24 / s25 / s26`) | `19 / 18 / 24` (`61`) | `1 / 1 / 0` (`2`) | `nonfinite_objective` (`1`), `invalid_hook_bundle_program` (`1`) |
| `bpp_offline` (`s24 / s25 / s26`) | `8 / 13 / 19` (`40`) | `8 / 5 / 5` (`18`) | `invalid_hook_bundle_program` (`18`) |

> **Root Cause Reference**: `agent_skill_loop/evaluator.py:90-109` (`_NUMPY_ATTRIBUTES` and `_MATH_ATTRIBUTES`, mirrored via `agent_skill_loop/interface_design/runtime.py:57,132`) already permits `zeros`, `zeros_like`, `ones`, `full`, `tanh`-less trig (`sin`, `cos`, `tan`, `exp`, `clip`), and `column_stack`/`hstack`, yet omits pure numeric/array primitives `empty`, `empty_like`, `tanh`, `sinh`, `cosh`, `sign`, `mod`, `fmod`, `remainder`, `stack`, `vstack`, `dstack`, `nan_to_num`, `fill_diagonal`, `bincount`, `lexsort`, `ix_`, `where`/`maximum`/`minimum` combinations. Because EoH prompts do not suppress `np.empty` or `np.tanh`, the LLM repeatedly regenerates them across all 400 requests.

---

## 2. Macro Trajectory Dynamics: Punctuated Equilibrium, Bloat & Dev-Blind Divergence

### 2.1 Punctuated Equilibrium & Post-Peak Budget Waste (`12` M3.2 Runs)

All runs start from the deterministic `L3 Worst-Cost Removal` baseline (`dev_24 = 16.142403`).

| Run Name | Peak Dev | Peak Ordinal | Post-Peak Waste | Jumps | Inter-Jump Waiting Times (Requests) | Intron Rate (`unused_vars > 0`) |
|---|---:|---:|---:|---:|---|---:|
| `curve_s20261124` | `16.0134` | `319` | `81` (`20.2%`) | `12` | `[16, 1, 2, 7, 3, 12, 9, 1, 57, 26, 18, 167]` | `45/246` (`18.3%`) |
| `curve_s20261125` | `15.7435` | **`96`** | **`304` (`76.0%`)** | `3` | `[15, 34, 47]` | `18/204` (`8.8%`) |
| `curve_s20261126` | `15.7773` | `375` | `25` (`6.2%`) | `5` | `[63, 26, 11, 170, 105]` | `38/204` (`18.6%`) |
| `l3b_dual_hook_s20261124` | `16.0924` | `281` | `119` (`29.8%`) | `3` | `[95, 24, 162]` | `4/78` (`5.1%`) |
| `l3b_dual_hook_s20261125` | `16.0526` | `314` | `86` (`21.5%`) | `9` | `[18, 34, 62, 1, 54, 63, 19, 32, 31]` | `13/73` (`17.8%`) |
| `l3b_dual_hook_s20261126` | `16.0560` | **`60`** | **`340` (`85.0%`)** | `4` | `[10, 3, 32, 15]` | `28/100` (`28.0%`) |
| `model_routing_s20261124` | `15.9940` | `398` | `2` (`0.5%`) | `5` | `[17, 9, 63, 165, 144]` | `25/188` (`13.3%`) |
| `model_routing_s20261125` | `15.8948` | `318` | `82` (`20.5%`) | `7` | `[24, 1, 15, 156, 2, 1, 119]` | `47/150` (`31.3%`) |
| `model_routing_s20261126` | `15.8452` | `256` | `144` (`36.0%`) | `7` | `[20, 17, 5, 7, 150, 49, 8]` | `45/177` (`25.4%`) |
| `timeout_2000ms_s20261124` | `15.8374` | `242` | `158` (`39.5%`) | `9` | `[17, 7, 18, 17, 9, 3, 15, 87, 69]` | **`115/202` (`56.9%`)** |
| `timeout_2000ms_s20261125` | `16.0496` | **`53`** | **`347` (`86.8%`)** | `3` | `[14, 37, 2]` | `64/194` (`33.0%`) |
| `timeout_2000ms_s20261126` | `16.0293` | **`68`** | **`332` (`83.0%`)** | `4` | `[43, 2, 15, 8]` | `58/213` (`27.2%`) |

- **Aggregate Summary**: Mean peak ordinal = **`231.67`** (median = **`268.5`**), mean post-peak waste = **`42.08%`**. Exactly **`4/12` (`33.33%`)** runs peaked at `ordinal <= 100` (`53, 60, 68, 96`) and produced **zero further improvements** over the remaining `304–347` requests.

### 2.2 Quartile Complexity & Yield Drift Across `12` M3.2 Runs

| Request Quartile | Mean Valid Rate | Mean LOC | Mean AST Nodes | Mean Python Loops | Mean Intron Fraction |
|---|---:|---:|---:|---:|---:|
| `Q1 (1–100)` | `49.47%` | `72.40` | `733.2` | `0.38` | `21.42%` |
| `Q2 (101–200)` | `55.55%` | `80.65` | `834.6` | `0.30` | `22.25%` |
| `Q3 (201–300)` | `56.53%` | `84.02` | `879.7` | `0.57` | `27.79%` |
| `Q4 (301–400)` | `58.13%` | **`85.49`** | **`904.9`** | **`0.61`** | `21.90%` |

- **Structural Code Bloat**: Across the `400`-request horizon, AST node complexity increases **`+23.4%`** (`733.2 -> 904.9`), LOC rises **`+18.1%`** (`72.40 -> 85.49`), and explicit Python `for`/`while`/comprehension loops increase **`+60.5%`** (`0.38 -> 0.61`), peaking in `l3b_dual_hook_s20261125` (`Q1: 82.7 LOC / 0.16 loops -> Q4: 130.7 LOC / 1.90 loops`) and `curve_s20261125` (`Q1: 70.8 LOC / 0.04 loops -> Q4: 94.9 LOC / 1.17 loops`).
- Because inner EoH evaluates exclusively on `n=50` (`cvrp_dev_hetero_24`), this steady growth in loop count and AST weight incurs **zero penalty** during search while pushing `n=200` per-instance solve latency right past `500 ms`.

### 2.3 Dev-vs-Blind Checkpoint Divergence (`m32_scaling_report.json` + `milestone_checkpoints`)

| Checkpoint / Control | Dev Mean (`s24 / s25 / s26`) | Blind Raw Valid Mean (`s24 / s25 / s26`) | Blind Penalized Mean | Blind `comp` | Blind `exact-k` |
|---|---|---|---:|---:|---:|
| `curve_36` | `16.0896 / 15.9739 / 16.1424` | `23.2162 / 23.1401 / 23.2230` | `36.2140` | `0.747` | `0.683` |
| `curve_100` | `16.0818 / 15.7435 / 15.7880` | `23.2114 / 22.9727 / 22.9722` | `38.8998` | `0.692` | `0.739` |
| `curve_200` | `16.0504 / 15.7435 / 15.7880` | `23.1674 / 22.9722 / 22.9720` | `38.7545` | `0.694` | `0.761` |
| `curve_400` | `16.0134 / 15.7435 / 15.7773` | `23.1696 / 22.9645 / 22.9430` | `39.1999` | `0.686` | **`0.792`** |
| `model_routing` (`400`) | `15.9940 / 15.8948 / 15.8452` | `23.1555 / 23.0477 / 23.0123` | `40.5434` | `0.667` | `0.706` |
| `l3b_dual_hook` (`400`) | `16.0924 / 16.0526 / 16.0560` | `23.2152 / 23.1687 / 23.1628` | `48.8565` | `0.397` | `0.717` |
| `timeout_2000ms` (`400`) | `15.8374 / 16.0496 / 16.0293` | `22.9796 / 23.1861 / 23.1676` | **`23.1111`** | **`1.000`** | `0.783` (`s24: 0.850`) |

---

## 3. Outer Research Agent Tool Inertia & Hypothesis Ledger Pathology

### 3.1 Cross-Milestone Tool Distribution (`42` Runs, `791` Outer Turns)

| Milestone (Runs / Turns) | `submit_plan` | `kb_search + kb_read` | `archive_summary` | `list_interfaces` | `diagnose_suite` | `run_math_sandbox` | `propose_and_validate_interface` | `hypothesis_propose` | `hypothesis_update` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **M3.0** (`18` / `190`) | `47` | `61` (`34+27`) | `19` | `15` | `7` (`7/18` runs) | **`0`** (`0/18` runs) | **`0`** | `1` (`1/18` runs) | `5` (`3` runs w/o propose) |
| **M3.1** (`12` / `166`) | `31` | `53` (`37+16`) | `15` | `28` | `7` (`5/12` runs) | **`1`** (`1/12` runs) | **`0`** | `4` (`4/12` runs) | `4` (`1` run w/o propose) |
| **M3.2** (`12` / `435`) | `84` (+`1`) | `160` (`90+70`) | `59` | `32` | `4` (`3/12` runs) | **`1`** (`1/12` runs) | **`0`** | `6` (`5/12` runs) | `25` (`5` runs w/o propose) |
| **Total (`42` / `791`)** | **`163`** | **`274` (`34.6%`)** | **`93` (`11.8%`)** | **`75` (`9.5%`)** | **`18` (`2.28%`)** | **`2` (`0.25%`)** | **`0` (`0.0%`)** | **`11`** | **`34`** (`9` runs orphan) |

**Top Behavioral Transitions in M3.2 (`435` turns)**:
`kb_search -> kb_read` (`69`) → `kb_read -> submit_plan` (`37`) → `submit_plan -> finish_round` (`46`) → `finish_round -> archive_summary` (`31`) → `archive_summary -> kb_search` (`37`).

### 3.2 Three Structural Pathologies Exposed

1. **Tool Inertia Collapse ("KB-Archive-Evolve Comfort Loop")**: Despite `research_agent/prompts.py:207-210` advising the agent to call `diagnose_suite` or `run_math_sandbox`, `95.2%` of all runs (`40/42`) **never executed `run_math_sandbox` once**, and `64.3%` (`27/42`) **never ran `diagnose_suite` once**. Even in 8-round `400`-request M3.2 runs, the agent defaulted to a passive loop (`archive_summary -> kb_search -> kb_read -> submit_plan`).
2. **Orphan `hypothesis_update` & Append-Only Duplicate Rows (`research_agent/tools/ledger_tools.py:57,105`)**:
   - In **`9/42` runs**, the agent called `hypothesis_update` (using `round_id` or plan strings as IDs) without calling `hypothesis_propose` first, triggering `ValueError: unknown_hypothesis:...` inside `loop.py:505-507`.
   - In `timeout_2000ms_s20261124`, `hypotheses.jsonl` has **`12` lines** (`1 proposed + 11 supported`), yet **`11` of them update the exact same single `hypothesis_id`** (`h_r2_ruin_depot_load_gate_rankpower`) because `HypothesisLedgerTool._append` writes a fresh line on every update while `ledger_tools.py` is never automatically coupled to `plan.hypothesis`.
3. **Causal Re-Interpretation of M3.0 Variance Compression**: Because M3.0 runs (`M3-2` and `M3-3`) logged **`0/18` `run_math_sandbox` calls** and **`0/18` `propose_and_validate_interface` calls**, the **>20× variance compression** in M3.0 (`std: 1.4276 / 1.3268 -> 0.0205 / 0.0611`) is empirically attributable to **structured KB retrieval + stepping-stone archive feedback + 5-gate template locking**, *not* active Python sandbox diagnosis—meaning active sandbox usage remains almost completely untapped headroom.

---

## 4. Micro Genealogy of the M3.2 Champion (`timeout_2000ms_s20261124`)

### 4.1 Round-by-Round Alignment (`plan_r*.json` -> `candidate_provenance` Jumps)

| Round (Req Range) | Outer Plan Mechanism (`plan_r*.json`) | Jumps Captured | Dev Best After Round | Structural Transition |
|---|---|---|---:|---|
| **R1** (`1–35`) | Rank-power destroy score + load/depot/demand gates | `#1 (ord=17)`, `#2 (ord=24)` | `16.1297` | Phase I: exponential log-z-score (`#1`) -> rank-power × 4 multiplicative gates (`#2`) |
| **R2** (`36–100`) | *Fallback cap plan* (`"Evolve cvrp_ruin_recreate..."`) | `#3 (ord=42)`, `#4 (ord=59)`, `#5 (ord=68)`, `#6 (ord=71)`, `#7 (ord=86)` | `16.0781` | Phase I refinement: softmax additive (`#3`), harmonic disruption (`#4`), log-linear (`#5`), sigmoid conjunctive fragility (`#6`), z-score additive (`#7`) |
| **R3** (`101–157`) | Add Shaw spatial relatedness + hash jitter | *(none)* | `16.0931` | Exploration without breaking `16.0781` |
| **R4** (`158–208`) | Two-phase rank exp + route-sparsity + Shaw relatedness | **`#8 (ord=173)`** | **`15.9801`** | **Phase II (Accidental Zero-Clamping Degeneracy)**: see §4.2 |
| **R5** (`209–269`) | **Capacity-slack × `1/n_stops` sparsity + 3-phase clock** | **`#9 (ord=242)`** | **`15.8374`** | **Phase III (True Champion Emergence)**: see §4.2 |
| **R6–R8** (`270–400`) | Sector coherence / *Fallback R7* / self-norm `gamma` | *(none)* | `15.8374` | Post-peak plateau (`158` requests, `39.5%`) |

### 4.2 Two Critical Micro-Level Discoveries in Jumps #8 and #9

1. **Jump #8 (`ord=173`, `sha=cd8aaa033dd5`, `dev=15.980136`, `delta=-0.097931`) Is Behaviorally Equivalent to `np.zeros(n)`**:
   - Jump #8 computes `log_s = np.log(snorm + 0.02)`, `log_p = np.log(0.4 + 0.6*prox)`, `log_l = np.log(0.5 + 0.5*util)`, `log_sp = np.log(0.3 + 0.7*sparse)`, and `log_r = np.log(0.05 + 0.95*rel_kernel)`, forms a positively weighted sum `score`, and applies `np.maximum(score, 0.0)`.
   - Because `prox, util, sparse, rel_kernel <= 1.0`, the four logs are `<= 0` everywhere, while `log(snorm + 0.02) <= log(1.02) = +0.0198`. Under weighted combination, `score <= 0` for **`50/50`** customers across tested states (`dev24_n50_uniform_centre_loose_uniform-00` early/mid/late = `0/50` nonzero; realistic `0.9*cap` route check = `0/50` nonzero).
   - Independent evaluation on `cvrp_dev_hetero_24` confirms **exact 6-decimal parity**: `Jump #8 = 15.980136` vs **`np.zeros(n) = 15.980136`**. In `cvrp_ruin_recreate`, an all-zero score triggers deterministic tie-breaking/index rotation + Regret-2 recreate, proving that Round 4's `-0.0979` jump came from escaping savings-concentrated ruin into rotating deterministic block ruin rather than from its Shaw kernel.
2. **Jump #9 (`ord=242`, `sha=8c4dfb41aa5f`, `ckpt_cand_8c4dfb41aa`, `dev=15.837376`, `blind=22.9796`, `exact-k=0.850`) Contains a Dead `temp` Intron**:
   - Lines 78–79 compute `temp = 0.15 + 1.05 * diversify_w + 0.85 * st * (0.5 + 0.5 * exploit_w); temp = float(np.clip(temp, 0.05, 2.0))`, **but `temp` is never read anywhere in lines 80–103**.
   - Instead, the actual stochasticity schedule in `score = logit + noise` is driven by **`noise_amp = 0.55 * exploit_w + 0.25 * neutral_w + 0.15 * diversify_w`** multiplying deterministic Gumbel noise `-np.log(-np.log(u))` (`+ 0.10 * h2 * st`). Additionally, `rload` and `rdist` are unused inputs (`unused_vars = ['rdist', 'rload']`), as the hook reconstructs `route_used` and `1/n_stops` directly from `demands` and `route_ids`.

---

## 5. Actionable P0 / P1 / P2 Fix Contracts for the Code-Fixing Agent

| Priority | Target Files & Symbols | Concrete Defect / Opportunity | Acceptance & Verification Check |
|---|---|---|---|
| **P0** | `agent_skill_loop/evaluator.py:90-109` (`_NUMPY_ATTRIBUTES`, `_MATH_ATTRIBUTES`) & `research_agent/sandbox_worker.py` | `forbidden_attribute` rejected **`775`** M3.2 candidates (`np.empty` 453, `np.tanh` 145, `np.fill_diagonal` 68, `np.sign` 45, `np.mod` 30, `np.stack` 27, `np.nan_to_num` 24) and **`39`** M3.1 candidates (`np.ix_` 26). | Add safe numeric/array attributes (`empty`, `empty_like`, `tanh`, `sinh`, `cosh`, `sign`, `mod`, `fmod`, `remainder`, `stack`, `vstack`, `dstack`, `nan_to_num`, `fill_diagonal`, `bincount`, `lexsort`, `ix_`) while keeping `fromfile/tofile/save/load/ctypes` blocked. Verify `capability_contract_dict` & AST parity tests pass. |
| **P0** | `agent_skill_loop/interface_design/dynamic_eoh.py` / `eval_worker.py` / `validator.py` | Candidate-level latency & degenerate all-zero hooks are unchecked inside EoH (`n=50` dev only), enabling `94.2%` `n=200` timeouts at `500 ms` and Jump #8's `np.zeros` clamping trap. | Add fast candidate pre-screen (or soft penalty) on `gate5_n200_stress` latency margin + degenerate constant-output detector (`np.ptp(scores) <= 1e-12` across non-trivial state). Verify Jump #8-style all-zero output is flagged and `timeout` candidates cannot dominate unconstrained dev. |
| **P1** | `agent_skill_loop/evidence/search_progress.py:330-342` & `interface_design/session_bridge.py` | `search_progress` logged `0 / 3,239` `behavior_comparable` events and `0.0` `source_duplicate_rate` in M3.2, disabling behavioral novelty rejection. | Populate candidate `behavior` signatures in `session_bridge` / `evaluation_facts.json` for `interface_design` templates so `behavior_comparable_count > 0` and `archive_tools` novelty guard fires cleanly. |
| **P1** | `research_agent/prompts.py`, `research_agent/loop.py:444-566`, `research_agent/tools/ledger_tools.py` | Outer agent ran `run_math_sandbox` in only `2/791` turns, `diagnose_suite` in `18/791`, and emitted `9` orphan `hypothesis_update` calls + duplicate `supported` rows. | Enforce stagnation-triggered mandatory `diagnose_suite` / `run_math_sandbox` when 1 round yields zero dev improvement; auto-register `plan.hypothesis` or validate `hypothesis_id` cleanly; compact or deduplicate identical `(hypothesis_id, status, evidence)` writes. |
| **P1** | `research_agent/loop.py` / `milestone_checkpoint.py` | `4/12` runs peaked `<= 100` requests and burned `76%–87%` budget in zero-jump tails. | Add optional early-stopping / basin-restart policy triggered by `no_jump_requests >= K` + rising behavioral duplicate rate, reallocating remaining budget to fresh seeds or stronger planner tier. |
| **P2** | `experiments/milestone4/m4_math_closure_part2.md` & thesis Chapter 6 | M4 Part 2 describes `ckpt_cand_8c4dfb41aa` (Jump #9) as having a "three-phase temperature schedule" `temp` without noting `temp` is dead code and `noise_amp` drives Gumbel amplitude. | Add explicit erratum/precision note clarifying `noise_amp` (`0.55 -> 0.25 -> 0.15`) vs dead `temp` intron, and document Jump #8's `np.zeros` clamping discovery. |
