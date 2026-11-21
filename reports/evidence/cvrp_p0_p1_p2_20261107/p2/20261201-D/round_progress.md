# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore route-coherent CVRP ranking with depot-aware distances. | 7 / 7; 7 / 7 | 3 / 6 | candidate_1:invalid:forbidden_attribute, candidate_2=11.46486250526582, candidate_3=11.592529745864793, candidate_4:invalid:forbidden_attribute, candidate_5:invalid:forbidden_attribute, candidate_6=12.25242003423594 | — → 11.46486250526582 / — | selected=—; publication=published | diversified |
| 2 | Retain adaptive positive savings with permitted comparison. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=13.359654221110384, candidate_2=14.189153311929742 | 11.46486250526582 → 11.46486250526582 / 0.0 | selected=cvrp_construct/insight_lexsort-contract@v0001; publication=published | stagnated |
| 3 | Preserve the sign of depot savings in the adaptive formula. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=11.592529745864793, candidate_2=14.120721764973728 | 11.46486250526582 → 11.46486250526582 / 0.0 | selected=cvrp_construct/insight_lexsort-contract@v0001,cvrp_construct/insight_keep-savings-sign@v0001; publication=none | stagnated |
