# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore route-coherent CVRP ranking with depot-aware distances. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1=11.492664634891767, candidate_2:invalid:candidate_error, candidate_3=11.508953934111808, candidate_4=12.018605712471674, candidate_5=11.45280162991609, candidate_6=16.069159898685125 | — → 11.45280162991609 / — | selected=—; publication=disabled | diversified |
| 2 | Test a bounded change to the demand-dependent distance cost. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=11.316182611508978, candidate_2=13.501298847594635 | 11.45280162991609 → 11.316182611508978 / -0.13661901840711188 | selected=—; publication=disabled | improved |
| 3 | Modify one effective coefficient without changing common scaling. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=11.55450695300768, candidate_2=11.099665089664072 | 11.316182611508978 → 11.099665089664072 / -0.21651752184490647 | selected=—; publication=disabled | improved |
