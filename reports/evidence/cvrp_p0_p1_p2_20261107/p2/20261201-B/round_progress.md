# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore distinct feasible CVRP next-customer rankings. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1:invalid:forbidden_syntax, candidate_2=11.595073610166125, candidate_3=12.868489297619602, candidate_4=11.842113423562765, candidate_5=11.718543948704115, candidate_6=11.988656882673395 | — → 11.595073610166125 / — | selected=—; publication=published | diversified |
| 2 | Refine the strongest verified candidate. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=13.090551847158965, candidate_2=12.225393966881336 | 11.595073610166125 → 11.595073610166125 / 0.0 | selected=cvrp_construct/insight_legal-ranking-refinement@v0001; publication=none | stagnated |
| 3 | Try a different focused ranking edit. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=12.615730430049949, candidate_2=13.11999969271782 | 11.595073610166125 → 11.595073610166125 / 0.0 | selected=cvrp_construct/insight_legal-ranking-refinement@v0001; publication=none | stagnated |
