# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore distinct feasible CVRP next-customer rankings. | 7 / 7; 7 / 7 | 6 / 6 | candidate_1=12.362994004717137, candidate_2=12.253436974529123, candidate_3=16.582523610003182, candidate_4=13.844526220173586, candidate_5=12.762486392614479, candidate_6=11.778191205660988 | — → 11.778191205660988 / — | selected=—; publication=disabled | diversified |
| 2 | Refine the verified incumbent before broad exploration. | 3 / 10; 5 / 12 | 1 / 2 | candidate_1=11.869774097695398, candidate_2:invalid:forbidden_attribute | 11.778191205660988 → 11.778191205660988 / 0.0 | selected=—; publication=disabled | stagnated |
| 3 | Stay with a simple feasible variation of the earlier source. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=12.20430157964136, candidate_2=11.67495002986569 | 11.778191205660988 → 11.67495002986569 / -0.1032411757952989 | selected=—; publication=disabled | improved |
