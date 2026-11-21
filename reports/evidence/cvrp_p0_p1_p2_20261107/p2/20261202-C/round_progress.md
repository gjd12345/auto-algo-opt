# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore route-coherent CVRP ranking with depot-aware distances. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1=11.897492475902993, candidate_2=12.492955704596028, candidate_3=12.319020892092484, candidate_4=12.056953972221203, candidate_5=15.400764413051837, candidate_6:invalid:forbidden_attribute | — → 11.897492475902993 / — | selected=—; publication=disabled | diversified |
| 2 | Probe one bounded savings coefficient change. | 3 / 10; 5 / 12 | 1 / 2 | candidate_1=11.962252449673613, candidate_2:invalid:forbidden_attribute | 11.897492475902993 → 11.897492475902993 / 0.0 | selected=—; publication=disabled | stagnated |
| 3 | Explore a smaller savings intercept while holding route start constant. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=12.058579613284579, candidate_2=11.724845159787085 | 11.897492475902993 → 11.724845159787085 / -0.1726473161159081 | selected=—; publication=disabled | improved |
