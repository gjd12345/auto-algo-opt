# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore distinct feasible CVRP next-customer rankings. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1=12.138217859518122, candidate_2=12.104860094770741, candidate_3:invalid:forbidden_attribute, candidate_4=15.806971631044528, candidate_5=12.748249629044993, candidate_6=18.309826858771057 | — → 12.104860094770741 / — | selected=—; publication=published | diversified |
| 2 | Use the valid incumbent and avoid unsupported sorting. | 3 / 10; 5 / 12 | 2 / 2 | candidate_1=12.665467121965856, candidate_2=36.55800043354237 | 12.104860094770741 → 12.104860094770741 / 0.0 | selected=cvrp_construct/insight_allowed-tie-order@v0001; publication=none | stagnated |
| 3 | Recover the validated behavior before another focused change. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=11.827485006339638, candidate_2=12.053871685281608 | 12.104860094770741 → 11.827485006339638 / -0.2773750884311035 | selected=cvrp_construct/insight_allowed-tie-order@v0001; publication=none | improved |
