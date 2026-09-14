You are a grok-4.5 screening agent for combinatorial-optimisation literature.
Do not use tools. Do not download PDFs. Do not write repository files.
Return ONLY one JSON object.

Screen EACH subproblem independently. Select 0-2 heuristics per subproblem. Do not pad.
Prefer original algorithmic papers and the named target_heuristics when the abstract actually describes them.
Reject exact solvers, commercial tools, missing abstracts, and reviews without steps.
No DOI => reject. Do not invent steps the abstract does not state.
Insertion into a partial tour is not select_next_node.
Clarke-Wright merge of singleton routes is not select_next_node.
Harmonic class-dedicated bins are only mappable as a score over residuals.
FFD/BFD require sorting the full list and are not online score(item, bins).
Lin-Kernighan variable-depth search is not select_2opt_move.
If nothing is classifiable for a subproblem: selected=[] and cannot_classify=true.

JSON shape:
{"schema_version":"literature-screen-batch/v1","family":"<family>","screens":[{"schema_version":"literature-screen/v1","subproblem_id":"","selected":[{"doi":"","heuristic_name":"","why":"","steps":[],"eoh_map":"possible|not_mappable|not_registered","adapter_kind":"next_node_score|bin_score|move_selector|not_mappable","not_the_original":""}],"rejected":[{"doi":"","reason":""}],"cannot_classify":false}]}

Emit one screens[] object per subproblem below, same order, matching subproblem_id.

family: online_bin_packing

=== bp_1d_offline ===
label: 1D offline bin packing
definition: Full list known; sorting allowed.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: First Fit Decreasing (not_mappable), Karmarkar-Karp (not_mappable)
Works:
1. doi=10.1109/sfcs.1982.61 year=1982 title=An efficient approximation scheme for the one-dimensional bin-packing problem
   authors=Narendra Karmarkar, Richard M. Karp
   venue=23rd Annual Symposium on Foundations of Computer Science (sfcs 1982) cited_by=275
   abstract=(missing)
2. doi=10.1016/0196-6774(85)90018-5 year=1985 title=A new proof for the first-fit decreasing bin-packing algorithm
   authors=Brenda S Baker
   venue=Journal of Algorithms cited_by=103
   abstract=(missing)
3. doi=10.1006/jagm.1993.1028 year=1993 title=The Parametric Behavior of the First-Fit Decreasing Bin Packing Algorithm
   authors=J. Csirik
   venue=Journal of Algorithms cited_by=20
   abstract=(missing)
4. doi=10.1007/978-3-642-27848-8_487-1 year=2014 title=First Fit Algorithm for Bin Packing
   authors=Gyorgy​ Dosa
   venue=Encyclopedia of Algorithms cited_by=1
   abstract=(missing)
5. doi=10.32614/cran.package.binpackr year=2023 title=binpackr: Fast 1d Bin Packing
   authors=Lukas Schneiderbauer
   venue=CRAN: Contributed Packages cited_by=0
   abstract=(missing)

=== bp_cardinality ===
label: Cardinality-constrained packing
definition: Max items per bin.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Cardinality-aware Best Fit (bin_score), Cardinality FFD (not_mappable)
Works:
1. doi=10.1007/s10951-025-00854-z year=2025 title=Semi-online models for cardinality constrained bin packing
   authors=Leah Epstein, Asaf Levin
   venue=Journal of Scheduling cited_by=1
   abstract=Abstract We study two semi-online models for bin packing and exhibit them on cardinality constrained bin packing with small values of k . In this variant of the bin packing problem, each bin can have at most k items whose total size does not exceed 1. For the semi-online model where the algorithm may use a reordering buffer, we show that even if a single item can be stored in the buffer at any point in time, the best possible asymptotic competitive ratio for the case $$k=2$$ k = 2 is smaller than that of the purely online problem. For the model with two parallel solutions, which is equivalent to the model with advice with a single bit of advice, we show an improved upper bound on the asympt…
2. doi=10.1023/a:1018947117526 year=1999 title=Cardinality constrained bin‐packing problems
   authors=H. Kellerer, U. Pferschy
   venue=Annals of Operations Research cited_by=48
   abstract=(missing)
3. doi=10.1016/j.tcs.2022.11.034 year=2023 title=Several methods of analysis for cardinality constrained bin packing
   authors=Leah Epstein
   venue=Theoretical Computer Science cited_by=4
   abstract=(missing)
4. doi=10.1016/j.tcs.2026.115774 year=2026 title=More on online cardinality constrained bin packing with small cardinality bounds
   authors=János Balogh, József Békési, György Dósa, Leah Epstein, Asaf Levin
   venue=Theoretical Computer Science cited_by=1
   abstract=(missing)
5. doi=10.1109/lindi.2012.6319473 year=2012 title=Heuristic algorithms for the weight constrained 3-dimensional bin packing model
   authors=Tamas Bartok, Csanad Imreh
   venue=2012 4th IEEE International Symposium on Logistics and Industrial Informatics cited_by=0
   abstract=(missing)

=== bp_variable ===
label: Variable-sized bins
definition: Several bin sizes.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Any Fit variable bins (not_mappable), Variable-size FFD (not_mappable)
Works:
1. doi=10.1016/j.ejor.2021.11.031 year=2022 title=A goal-driven ruin and recreate heuristic for the 2D variable-sized bin packing problem with guillotine constraints
   authors=Jeroen Gardeyn, Tony Wauters
   venue=European Journal of Operational Research cited_by=20
   abstract=(missing)
2. doi=10.1080/00207543.2010.501549 year=2011 title=A dynamic programming-based heuristic for the variable sized two-dimensional bin packing problem
   authors=Ya Liu, Chengbin Chu, Kanliang Wang
   venue=International Journal of Production Research cited_by=19
   abstract=(missing)
3. doi=10.5784/26-1-84 year=2010 title=Modified strip packing heuristics for the rectangular variable-sized bin packing problem
   authors=FG Ortmann, JH Van Vuuren
   venue=ORiON cited_by=1
   abstract=(missing)
4. doi=10.1201/9781351236423-30 year=2018 title=Variable Sized Bin Packing and Bin Covering *
   authors=Csirik János
   venue=Handbook of Approximation Algorithms and Metaheuristics, Second Edition cited_by=1
   abstract=(missing)
5. doi=10.1201/9781420010749-43 year=2007 title=Variable-Sized Bin Packing and Bin Covering
   authors=
   venue=Handbook of Approximation Algorithms and Metaheuristics cited_by=0
   abstract=(missing)

=== obp_1d ===
label: 1D online bin packing
definition: Irrevocable assignment of arriving items.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: First Fit (bin_score), Best Fit (bin_score)
Works:
1. doi=10.1109/sfcs.1991.185444 year=None title=How to pack better than best fit: tight bounds for average-case online bin packing
   authors=P.W. Shor
   venue=[1991] Proceedings 32nd Annual Symposium of Foundations of Computer Science cited_by=15
   abstract=(missing)
2. doi=10.1007/bf02243816 year=1993 title=Besk-k-Fit bin packing
   authors=W. Mao
   venue=Computing cited_by=9
   abstract=(missing)
3. doi=10.1007/978-1-4939-2864-4_487 year=2016 title=First Fit Algorithm for Bin Packing
   authors=Gyorgy Dosa
   venue=Encyclopedia of Algorithms cited_by=2
   abstract=(missing)
4. doi=10.1109/spdp.1990.143591 year=None title=Parallel bin packing using first fit and k-delayed best-fit heuristics
   authors=A. Bestavros, T. Cheatham, D. Stefanescu
   venue=Proceedings of the Second IEEE Symposium on Parallel and Distributed Processing 1990 cited_by=1
   abstract=(missing)
5. doi=10.1007/978-3-642-27848-8_487-1 year=2014 title=First Fit Algorithm for Bin Packing
   authors=Gyorgy​ Dosa
   venue=Encyclopedia of Algorithms cited_by=1
   abstract=(missing)

=== strip_2d ===
label: 2D strip packing
definition: Pack rectangles into a strip.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Bottom-Left (not_mappable), Best-Fit skyline (not_mappable)
Works:
1. doi=10.1016/j.eswa.2013.01.005 year=2013 title=Bidirectional best-fit heuristic considering compound placement for two dimensional orthogonal rectangular strip packing
   authors=Ender Özcan, Zhang Kai, John H. Drake
   venue=Expert Systems with Applications cited_by=21
   abstract=(missing)
2. doi=10.1016/j.engappai.2024.108624 year=2024 title=A block-based heuristic search algorithm for the two-dimensional guillotine strip packing problem
   authors=Hao Zhang, Shaowen Yao, Shenghui Zhang, Jiewu Leng, Lijun Wei, Qiang Liu
   venue=Engineering Applications of Artificial Intelligence cited_by=12
   abstract=(missing)
3. doi=10.1109/access.2019.2953531 year=2019 title=Hierarchical Search-Embedded Hybrid Heuristic Algorithm for Two-Dimensional Strip Packing Problem
   authors=Mengfan Chen, Kai Li, Defu Zhang, Ling Zheng, Xin Fu
   venue=IEEE Access cited_by=10
   abstract=(missing)
4. doi=10.2498/cit.1002422 year=2015 title=A Parallel Hyper-heuristic Approach for the Two-dimensional Rectangular Strip-packing Problem
   authors=Istvan Borgulya
   venue=Journal of Computing and Information Technology cited_by=8
   abstract=(missing)
5. doi=10.3724/sp.j.1001.2012.04187 year=2012 title=Recursive Heuristic Algorithm for the 2D Rectangular Strip Packing Problem
   authors=Bi-Tao PENG, Yong-Wu ZHOU
   venue=Journal of Software cited_by=3
   abstract=(missing)
