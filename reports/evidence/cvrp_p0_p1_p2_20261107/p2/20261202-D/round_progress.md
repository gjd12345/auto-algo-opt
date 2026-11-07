# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore route-coherent CVRP ranking with depot-aware distances. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1:invalid:candidate_error, candidate_2=12.020939663188145, candidate_3=11.59758406835406, candidate_4=11.977215852942606, candidate_5=14.287530701000051, candidate_6=25.700564687229924 | — → 11.59758406835406 / — | selected=—; publication=published | diversified |
| 2 | Hold the farthest start fixed while revising fill scaling. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=11.693504582881111, candidate_2=12.291211291392372 | 11.59758406835406 → 11.59758406835406 / 0.0 | selected=cvrp_construct/insight_farthest-start-savings@v0001; publication=none | stagnated |
| 3 | Keep the verified farthest start and soften the in-route fill reward. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=11.924050985765893, candidate_2=13.056272554728787 | 11.59758406835406 → 11.59758406835406 / 0.0 | selected=cvrp_construct/insight_farthest-start-savings@v0001; publication=none | stagnated |
