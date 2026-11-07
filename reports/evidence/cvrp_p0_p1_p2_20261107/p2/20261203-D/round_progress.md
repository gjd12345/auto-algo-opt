# Round Progress

| Round | Plan input / mechanism | EoH requests Δ / Σ; solver | Valid / generated | Generated candidate objectives | Incumbent before → after / Δ | Memory | Status |
|---:|---|---:|---:|---|---|---|---|
| 1 | Explore route-coherent CVRP ranking with depot-aware distances. | 7 / 7; 7 / 7 | 5 / 6 | candidate_1=11.644549845559126, candidate_2=11.47582899613414, candidate_3=11.703877195401978, candidate_4:invalid:candidate_error, candidate_5=11.249899119944267, candidate_6=13.445141699360967 | — → 11.249899119944267 / — | selected=—; publication=published | diversified |
| 2 | Keep nearest start and refine the tight-capacity trigger. | 3 / 10; 5 / 12 | 1 / 2 | candidate_1=11.60994695542834, candidate_2:invalid:forbidden_attribute | 11.249899119944267 → 11.249899119944267 / 0.0 | selected=cvrp_construct/insight_tight-capacity-savings@v0001; publication=published | stagnated |
| 3 | Retain the original score and use simple arithmetic for a threshold-only edit. | 3 / 13; 5 / 17 | 2 / 2 | candidate_1=13.662950001947493, candidate_2=11.287897244886523 | 11.249899119944267 → 11.249899119944267 / 0.0 | selected=cvrp_construct/insight_tight-capacity-savings@v0001,cvrp_construct/insight_capacity-threshold-scope@v0001; publication=none | stagnated |
