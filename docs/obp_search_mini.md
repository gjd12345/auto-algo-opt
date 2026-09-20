# OBP search mini profile

`obp_search_mini` is the frozen Iteration B search profile. It uses the same
online bin-packing interface and evaluator as the other OBP profiles, with
four training instances and two heldout instances.

The item orders were selected deterministically from a seeded integer search.
Each reference was checked by the local branch-and-bound exact bin-packing
procedure. The frozen best-fit baseline uses one more bin than the known
optimum on every instance, while the calibration first-fit policy reaches the
reference. This gives the live search a measurable improvement target without
changing the problem interface or metric.

This is a regenerated protocol-compatible engineering profile. It is not an
exact copy of the full EoH-S corpus and is not used to claim benchmark SOTA.
