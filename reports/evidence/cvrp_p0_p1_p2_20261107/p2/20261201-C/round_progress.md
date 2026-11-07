# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore route-coherent CVRP ranking with depot-aware distances. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1=11.090283215317896, candidate_2=11.769492629241945, candidate_3:invalid:candidate_error, candidate_4=11.979111745535262, candidate_5=14.368707037914229, candidate_6=11.272808359932702 | — → 11.090283215317896 / — | selected=—; publication=disabled | diversified |
| 2 | Separate route start and route continuation. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=11.086331927330194, candidate_2=11.102101695966054 | 11.090283215317896 → 11.086331927330194 / -0.003951287987701946 | selected=—; publication=disabled | improved |
| 3 | Test a small savings adjustment around the valid incumbent. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=11.077319003972312, candidate_2=11.106175993747614 | 11.086331927330194 → 11.077319003972312 / -0.00901292335788284 | selected=—; publication=disabled | improved |
