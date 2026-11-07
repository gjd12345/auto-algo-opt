# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore distinct feasible CVRP next-customer rankings. | 7 / 7; 7 / 7 | 6 / 6 | candidate_1=13.472631657044404, candidate_2=12.140124318569114, candidate_3=12.513826390704246, candidate_4=12.623760065043674, candidate_5=13.24261567382644, candidate_6=13.240243103923609 | — → 12.140124318569114 / — | selected=—; publication=published | diversified |
| 2 | Refine the best valid route constructor. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=12.534759249317986, candidate_2=13.145158410456043 | 12.140124318569114 → 12.140124318569114 / 0.0 | selected=cvrp_construct/insight_validated-parent@v0001; publication=none | stagnated |
| 3 | Pivot to a different small scoring variation. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=12.012577342105445, candidate_2=13.26409684241724 | 12.140124318569114 → 12.012577342105445 / -0.12754697646366964 | selected=cvrp_construct/insight_validated-parent@v0001; publication=none | improved |
