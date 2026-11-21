# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore distinct feasible CVRP next-customer rankings. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1=11.669699898844463, candidate_2=11.592529745864793, candidate_3=12.342616559559476, candidate_4=12.214843201376903, candidate_5:invalid:forbidden_attribute, candidate_6=32.574575887168145 | — → 11.592529745864793 / — | selected=—; publication=disabled | diversified |
| 2 | Refine the current verified candidate. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=11.343635583499372, candidate_2=12.073225362606161 | 11.592529745864793 → 11.343635583499372 / -0.2488941623654206 | selected=—; publication=disabled | improved |
| 3 | Make one last localized ranking edit. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=11.0864622525459, candidate_2=12.12218430347812 | 11.343635583499372 → 11.0864622525459 / -0.2571733309534725 | selected=—; publication=disabled | improved |
