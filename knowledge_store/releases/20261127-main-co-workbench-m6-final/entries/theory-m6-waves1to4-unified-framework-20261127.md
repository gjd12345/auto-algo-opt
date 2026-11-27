# M6 Waves 1–4 · Unified deadline, feasibility, and transfer framework

Treat deadline observability, computational admission, fleet feasibility, and information transfer as separate conditions on the same solver decision. Once all arms meet the free-fleet deadline, their free-fleet comparison measures route quality. An exact-k requirement can still expose a separate feasibility barrier.

## 定义或方法步骤

- For instance i, fleet contract m, and deadline D, F_i^m(D) indicates a certified feasible incumbent by D and R_i^m(D) indicates a valid contract-compliant return by D. With a common clock and consistent validation, R_i^m(D) <= F_i^m(D).
- P_i^m = R_i^m L_i^m + (1 - R_i^m) 2 Ref_i, where L_i^m is the returned objective and Ref_i is the fixed scoring reference.
- Delta_penalized = (1/N) sum_i (P_base,i - P_candidate,i). Partition this sum by (R_base,i, R_candidate,i). Delta_common instead averages L_base,i - L_candidate,i only where both return successfully.
- When both arms return successfully on every instance under the same fleet contract, common_completed and penalized_2x select the same pairs and give the same objective contrast.

### Wave 1 · Deadline observability

Deadline-accounting invariance holds for a fixed event history through D. Later events and changes to request-accounting presentation leave that prefix and its strict score unchanged. Training or evaluation budget changes can alter the event history itself.

Cross training deadline and evaluation deadline at a fixed search request cap. For cell means mu_ab, the training-by-evaluation interaction is mu_11 - mu_10 - mu_01 + mu_00. A diagonal contrast mixes changes in both deadlines.

### Wave 2 · Computational admission and search continuation

Let z = (geometry, scale, fleet regime). Admit a candidate on represented joint regimes only when its measured runtime and quality satisfy the admission rules. A deadline guarantee additionally needs a valid upper envelope over the deployment regime, or a guarded fallback with return time reserved.

Let G_t >= 0 be the future improvement available if search continues, conditional on the observed prefix H_t and the specified continuation policy. If Pr(G_t > 0 | H_t) <= q_t and E[G_t | G_t > 0, H_t] <= M_t, then E[G_t | H_t] <= q_t M_t.

A global stop spends the remaining option value of search when the risk bound meets the threshold. A basin restart changes the continuation policy while preserving the remaining request budget and the incumbent. Recalibrate q_t and M_t for that continuation policy.

The empirical Pareto frontier is the set of logged points undominated jointly in requests spent and reported loss. It describes the observed runs.

### Wave 3 · Fleet feasibility

For capacity Q and an exact fleet of K nonempty routes, validate customer coverage, every route load, and route count. Reserve time for construction, fleet repair, polishing, and return. Use a validated K-route witness when available. Free-fleet success and search failure to find a K-route witness are distinct outcomes.

rho = sum_i q_i / (K Q), delta_max = max_i q_i / Q. Even with rho <= 1 and delta_max <= 1, the indivisible demands must admit a capacity-feasible partition.

For current loads l_1,...,l_r with r > K, min_{a<b}(l_a + l_b) > Q blocks every whole-route merge under capacity. Customer exchanges or repacking can still reach K.

For normalized loads u_j = l_j/Q in a K-route packing, if u_1 = m and their mean is rho, then sum_j (u_j - rho)^2 >= K/(K-1) (m-rho)^2 for K > 1. Equality holds when the other loads are equal.

### Wave 4 · Diagnostic evidence and transfer

Once completion is fixed, diagnostics can affect the objective through changes in which valid solver is selected or returned.

A memory policy can preserve completion and still reduce solution quality. Offline screening and freezing can improve the bias–variance trade-off when online feedback reuses noisy winners.

## 适用条件、假设与限制

- Index each comparison by fleet contract, evaluation deadline, training deadline, search request budget, suite, and seed. Charge requests to the search ledger and wall time to the solve deadline.
- Compute paired Wilcoxon tests and paired bootstrap intervals within each seed, with Holm adjustment in the reported comparison family. A seed-by-arm cell count describes coverage. Instances reused across seeds do not supply independent replicated samples.
- Use dev_24 for development, select_64 for selection, and sealed blind suites for final evaluation under their declared roles. Preserve null endpoints and censored timing observations.
- W4-1 assumption. The gate is the only path for a decision that requires evidence, and the audit records every attempted transition.
- W4-1 assumption. The validity-rate comparison in the theorem uses fixed attempted scripts. Comparing different live runs leaves the attempted-script mix free to change.
- W4-1 assumption. A small route-quality bound requires a small affected objective share or small cost movement on affected cases. Full completion alone supplies neither condition.
- W4-2 assumption. A tag identifies a represented joint regime, and the deployment case satisfies the conditions of its certificate. If runtime is uncertain, the fallback is already contract-valid and its return time is reserved.
- W4-2 assumption. Read, write, and injection liveness are checked only for arms requiring those actions. Attributing an injection and verifying that the required injection occurred are separate checks.
- W4-2 assumption. Within a fixed joint regime, online estimation errors follow a linear feedback model with independent centered innovations. The separate selection model assumes a symmetric Gaussian score error and a zero acceptance threshold. Neither model's parameters are identified by the supplied reports.
- B2 compares the diagnostic arms at full free-fleet completion. The bound on route-quality effects additionally depends on the affected objective share and per-instance cost changes.
- B3 estimates neither population variance nor target SNR. The online-versus-offline ordering is conditional on the stated feedback and selection models.

## 来源及支持的具体结论

### W4-1 · Instrumentation Fidelity and Diagnostic Modality Saturation

For a fixed set of executed scripts, require every gated decision to pass the evidence predicate and every accepted artifact to have a valid schema, allowed fields, successful execution, and finite numeric evidence. If a repair preserves existing valid outputs and converts invalid outputs to valid ones, the valid-execution rate increases by the converted fraction. Separately, when paired arms achieve full strict free-fleet completion, the penalized and common-completed contrasts coincide. If diagnostics change the returned choice only on A, and |L_new,i - L_base,i| <= epsilon_i L_base,i on A with positive baseline costs, the absolute relative aggregate gain is at most sum_{i in A}(epsilon_i L_base,i) / sum_i L_base,i.


- The guarded transition makes accepted-without-valid-evidence impossible under the assumed execution path. For fixed attempts, each repaired invalid output raises the valid numerator once.
- Full paired completion makes every deadline penalty vanish. Terms outside A are zero by definition. Applying the triangle inequality to the remaining cost differences gives the bound.

### W4-2 · C2-Gated Transfer Safety and Offline-Distillation Variance Dominance

Assume joint geometry–scale coverage and a sound bound on incremental solve time, or a valid incumbent with a guarded fallback and time reserved for return. Then admitted memory transfer preserves strict completion under the certified fleet contract. Complete gateway logging links each injection to its source and downstream candidates. In the feedback model below, frozen offline L3 has lower estimation variance when its error variance is below the cumulative online innovation variance. Dominance in expected target objective additionally requires the online signal to fall below the derived selection threshold.

- Timing certificate: T_base(z) + U_transfer(z) + T_return(z) <= D. With a guarded fallback, invoke it early enough to satisfy the same return deadline under the same fleet contract.
- Online noise: u_(t+1) = a u_t + eta_(t+1), with u_0 = 0 and Var(eta_t) = sigma_W^2. Thus V_W(t) = sigma_W^2 sum_{j=0}^{t-1} a^(2j). Frozen L3 has a fixed regime-level error variance V_L. Variance dominance holds if V_L < V_W(t). MSE dominance holds if b_L^2 + V_L < b_W^2 + V_W(t), where b_L and b_W are target-regime biases.
- For expected objective, measure gains relative to frozen L3. Let p be the prior probability that a proposed write has true target gain g > 0, and let a bad write incur loss ell > 0. Let good and bad writes have selection-score means +s and -s and common noise standard deviation nu > 0. Then p_TP = Phi(s/nu), p_FP = 1 - Phi(s/nu), and expected online incremental gain is p g p_TP - (1-p) ell p_FP.
- Frozen L3 weakly dominates in expected target objective when Phi(s/nu) <= h, where h = (1-p) ell / (p g + (1-p) ell). For h in (1/2, 1), this is the explicit amplitude-SNR condition s/nu <= Phi^(-1)(h). Strict inequality gives strict dominance. In the feedback model, setting nu^2 = V_W(t) shows how variance amplification can move an online policy across this boundary.

- On the certificate branch, the timing sum fits D. On the fallback branch, the reserved time suffices to return the certified incumbent. Gateway records establish provenance under the logging assumption.
- Expand the feedback recursion and sum the independent innovation variances. A frozen artifact carries no within-run accumulation from new innovations. Its fixed variance can still reflect offline estimation uncertainty.
- Condition on whether a proposed write is helpful or harmful. Multiplying each acceptance probability by its signed target consequence gives the incremental expected gain. Rearrangement gives the SNR threshold. A favorable online mean effect can outweigh a variance disadvantage.

### CE1_proxy_scale_escape

Synthetic elapsed time is T(n) = n/5 + 1[n>200] n^2/500 ms. A proxy screen operating only up to n_probe=200 observes the linear branch. At n=500 the candidate exceeds a 500 ms deadline even though the baseline linear branch fits. The excess over baseline scales quadratically.

Finite proxy measurements cannot certify a runtime bound on an untested branch.

```python
from fractions import Fraction as F

def time(n):
    return F(n, 5) + (F(n * n, 500) if n > 200 else 0)

assert all(time(n) < 500 for n in (50, 100, 200))
assert time(200) == 40 and time(201) > 40
assert F(500, 5) < 500 < time(500) == 600
assert time(1000) - 200 == 4 * (time(500) - 100)
```

### CE2_geometry_scale_interaction

Both static-interface choices are legal, have the same runtime and fleet feasibility, and share base cost 100. The aggressive threshold activates a local choice with a geometry-by-scale cost change. A clustered-small-heavy development mix favors it. A synthetic Set X-like mix with uniform and corridor instances reverses the ordering while preserving both marginal tag distributions. A screen checking geometry and scale separately sees identical marginal coverage.

Marginal coverage can conceal disjoint joint support and a reversal in target quality under identical completion.

```python
from fractions import Fraction as F
from statistics import mean

def cost(theta, geometry, scale):
    delta = {('clustered', 'small'): -4, ('clustered', 'large'): 2,
             ('uniform', 'small'): 8, ('uniform', 'large'): -2,
             ('corridor', 'small'): 8, ('corridor', 'large'): -2}
    return 100 + (delta[geometry, scale] if F(1, 2) <= theta else 0)

dev = [('clustered', 'small')]*12 + [('uniform', 'large')]*6 + [('corridor', 'large')]*6
target = [('clustered', 'large')]*50 + [('uniform', 'small')]*25 + [('corridor', 'small')]*25
for axis in (0, 1):
    for tag in {row[axis] for row in dev}:
        assert F(sum(row[axis] == tag for row in dev), len(dev)) == F(sum(row[axis] == tag for row in target), len(target))
lo, hi = F(1, 4), F(3, 4)
loss = lambda theta, rows: mean(cost(theta, *row) for row in rows)
assert (loss(hi, dev), loss(lo, dev), loss(hi, target), loss(lo, target)) == (97, 100, 105, 100)
```

### CE3_online_winner_feedback

A stable offline artifact yields target gain 1 each round. An online proposal with true score -1 receives a one-time dev perturbation of +3 or -3 with equal probability. The lucky dev winner is written when its observed score beats 1. Its downstream harm starts at 1 and doubles on each reuse. The other seed retains the stable policy. Runtime and attribution can remain valid throughout.

Selecting a noisy dev winner and reusing it creates persistent error. Per-round averaging formulas that assume fresh independent errors miss this mechanism.

```python
from fractions import Fraction as F
from statistics import mean, pvariance

def online_gain(noise, t):
    spurious_winner = int(-1 + noise > 1)
    return 1 - 2**(t - 1) * spurious_winner

assert [online_gain(3, t) for t in (1, 2, 3)] == [0, -1, -3]
assert [online_gain(-3, t) for t in (1, 2, 3)] == [1, 1, 1]
assert [pvariance([online_gain(e, t) for e in (-3, 3)]) for t in (1, 2, 3)] == [F(1, 4), 1, 4]
assert mean(online_gain(e, 3) for e in (-3, 3)) == -1
assert mean([1, 1]) == 1 and pvariance([1, 1]) == 0
```


- `experiments/milestone6_wave1_clean_audit/wave1_theoretical_abstraction_verified.json`
- `experiments/milestone6_wave2_c2_b1/wave2_theoretical_abstraction_verified.json`
- `experiments/milestone6_wave3_c1_exact_k/wave3_theoretical_abstraction_verified.json`
- `experiments/milestone6_wave3_c1_exact_k/wave3_tightness_feasibility_theory_verified.json`
- `experiments/milestone6_wave4_b2_b3/wave4_theoretical_abstraction_verified.json`

## 代码和评测关联

- `tools/run_m6_wave1_clean_audit.py`
- `tools/run_m6_wave2_c2_b1.py`
- `tools/run_m6_wave3_c1_exact_k.py`
- `tools/run_m6_wave4_b2_b3.py`

## 未确认项与冲突证据

The paired contrasts apply to their recorded suites, endpoints, and seeds. Blind instances repeated across seeds do not constitute independent replicates.
