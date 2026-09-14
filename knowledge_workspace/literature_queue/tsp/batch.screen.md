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

family: tsp

=== tsp_asymmetric ===
label: Asymmetric TSP
definition: Directed distances, d(i,j) may differ from d(j,i).
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Directed Nearest Neighbor (next_node_score), Directed 3-opt (move_selector)
Works:
1. doi=10.38032/jea.2024.01.004 year=2024 title=Improvement of the Nearest Neighbor Heuristic Search Algorithm for Traveling Salesman Problem
   authors=Md. Ziaur Rahman, Sakibur Rahamn Sheikh, Ariful Islam, Md. Azizur Rahman
   venue=Journal of Engineering Advancements cited_by=7
   abstract=The Traveling Salesman Problem (TSP) is classified as a non-deterministic polynomial (NP) hard problem, which has found widespread application in several scientific and technological domains. Due to its NP-hard nature, it is very hard to solve effectively and efficiently. Despite this rationale, a multitude of optimization approaches have been proposed and developed by scientists and researchers during the last several decades. Among these several algorithms, heuristic approaches are deemed appropriate for addressing this intricate issue. One of the simplest and most easily implementable heuristic algorithms for TSP is the nearest neighbor algorithm (NNA). However, its solution quality suff…
2. doi=10.55606/jurrimipa.v2i2.1614 year=2023 title=Perbandingan Algoritma Cheapest Insertion Heuristic Dan Nearest Neighbor Dalam Menyelesaikan Traveling Salesman Problem
   authors=Rizki Putra Sinaga, Faridawaty Marpaung
   venue=JURNAL RISET RUMPUN MATEMATIKA DAN ILMU PENGETAHUAN ALAM cited_by=1
   abstract=The main problem of the Traveling Salesman Problem is that a salesman travels to several places to go with a known distance and then returns to his original place by using the shortest route from his journey, and all the places the salesman goes to are only allowed once. This research focuses on the problem of distributing goods at PT. The Medan Nugraha Ekakurir (JNE) route with the destination delivery address in the Medan area. The Cheapest Insertion Heuristic Algorithm is an algorithm used to form tours (travels) by gradually building the shortest path route with minimal weight, by adding new points one at a time. One. The Nearest Neighbor Algorithm is a simple and fast algorithm to buil…
3. doi=10.1016/j.dam.2014.03.012 year=2015 title=On the nearest neighbor rule for the metric traveling salesman problem
   authors=Stefan Hougardy, Mirko Wilde
   venue=Discrete Applied Mathematics cited_by=18
   abstract=(missing)
4. doi=10.4236/oalib.1107520 year=2021 title=Repetitive Nearest Neighbor Based Simulated Annealing Search Optimization Algorithm for Traveling Salesman Problem
   authors=Md. Azizur Rahman, Hasan Parvez
   venue=OALib cited_by=7
   abstract=(missing)
5. doi=10.1109/ihmsc.2014.88 year=2014 title=A Nearest Neighbor Method with a Frequency Graph for Traveling Salesman Problem
   authors=Yong Wang
   venue=2014 Sixth International Conference on Intelligent Human-Machine Systems and Cybernetics cited_by=3
   abstract=(missing)

=== tsp_metric ===
label: Metric TSP
definition: Distances satisfy the triangle inequality.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Nearest Neighbor (next_node_score), Christofides (not_mappable)
Works:
1. doi=10.7551/mitpress/4908.003.0005 year=2006 title=Nearest-Neighbor Searching and Metric Space Dimensions
   authors=Kenneth L. Clarkson
   venue=Nearest-Neighbor Methods in Learning and Vision cited_by=73
   abstract=(missing)
2. doi=10.1007/bf01890118 year=1984 title=A computationally efficient approximation to the nearest neighbor interchange metric
   authors=Edward K. Brown, William H. E. Day
   venue=Journal of Classification cited_by=15
   abstract=(missing)
3. doi=10.1007/978-0-387-30162-4_230 year=2008 title=Metric TSP
   authors=Markus Bläser
   venue=Encyclopedia of Algorithms cited_by=1
   abstract=(missing)
4. doi=10.1109/icip.2009.5413381 year=2009 title=Quantization based nearest-neighbor-preserving metric approximation
   authors=Hye-Yeon Cheong, Antonio Ortega
   venue=2009 16th IEEE International Conference on Image Processing (ICIP) cited_by=1
   abstract=(missing)
5. doi=10.1007/springerreference_57749 year=None title=Metric TSP, 1976; Christofides
   authors=
   venue=SpringerReference cited_by=0
   abstract=(missing)

=== tsp_open ===
label: Open TSP / Hamiltonian path
definition: Path visits each city once, no return.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Path Nearest Neighbor (next_node_score), Cheapest Insertion path (not_mappable)
Works:
1. doi=10.31219/osf.io/kb8w2 year=2025 title=A Heuristic Approach to the Traveling Salesman Problem on a Sphere: A Geodesic Distance Study
   authors=Edison Carrasco-Jiménez
   venue=None cited_by=0
   abstract=This paper addresses an instance of the Traveling Salesman Problem (TSP) on a sphere, utilizing a greedy heuristic approach to find an approximate solution. The points on the surface of the sphere represent cities distributed randomly, and the red line shows the shortest approximate path between them. We calculate the total geodesic distance traveled, highlighting the complexity of the problem and the inherent limitations of heuristic methods. Additionally, we explore potential improvements to the algorithm and discuss the implications of these results in the context of combinatorial optimization and computational complexity theory.
2. doi=10.1016/0166-218x(91)90044-w year=1991 title=Sensitivity analysis for minimum Hamiltonian path and traveling salesman problems
   authors=Marek Libura
   venue=Discrete Applied Mathematics cited_by=38
   abstract=(missing)
3. doi=10.21236/ada197167 year=1988 title=Sensitivity Analysis for Shortest Hamiltonian Path and Traveling Salesman Problems
   authors=Marek Libura
   venue=None cited_by=1
   abstract=(missing)
4. doi=10.1007/springerreference_72340 year=None title=Heuristic and Metaheuristic Algorithms for the Traveling Salesman Problem
   authors=
   venue=SpringerReference cited_by=0
   abstract=(missing)
5. doi=10.17918/00007365 year=None title=Heuristic strategies for large scale traveling salesman problem, applicable to the traveling sequence optimization of industrial robots
   authors=Dimitrios A. Andreou
   venue=None cited_by=0
   abstract=(missing)

=== tsp_tw ===
label: TSP with time windows
definition: Visit cities inside time windows.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: I1 insertion TSPTW (not_mappable), Time-window NN (not_mappable)
Works:
1. doi=10.1287/opre.46.3.330 year=1998 title=A Generalized Insertion Heuristic for the Traveling Salesman Problem with Time Windows
   authors=Michel Gendreau, Alain Hertz, Gilbert Laporte, Mihnea Stan
   venue=Operations Research cited_by=161
   abstract=This article describes a generalized insertion heuristic for the Traveling Salesman Problem with Time Windows in which the objective is the minimization of travel times. The algorithm gradually builds a route by inserting at each step a vertex in its neighbourhood on the current route, and performing a local reoptimization. This is done while checking the feasibility of the remaining part of the route. Backtracking is sometimes necessary. Once a feasible route has been determined, an attempt is made to improve it by applying a post-optimization phase based on the successive removal and reinsertion of all vertices. Tests performed on 375 instances indicate that the proposed heuristic compare…
2. doi=10.1145/2330163.2330219 year=2012 title=A genetic and insertion heuristic algorithm for solving the dynamic ridematching problem with time windows
   authors=Wesam Mohamed Herbawi, Michael Weber
   venue=Proceedings of the 14th annual conference on Genetic and evolutionary computation cited_by=52
   abstract=(missing)
3. doi=10.1371/journal.pone.0130224 year=2015 title=Sequential Insertion Heuristic with Adaptive Bee Colony Optimisation Algorithm for Vehicle Routing Problem with Time Windows
   authors=Sana Jawarneh, Salwani Abdullah
   venue=PLOS ONE cited_by=17
   abstract=(missing)
4. doi=10.1007/s11067-017-9369-7 year=2017 title=Efficient Insertion Heuristic Algorithms for Multi-Trip Inventory Routing Problem with Time Windows, Shift Time Limits and Variable Delivery Time
   authors=Ampol Karoonsoontawong, Onwasa Kobkiattawin, Chi Xie
   venue=Networks and Spatial Economics cited_by=10
   abstract=(missing)
5. doi=10.1145/298151.298356 year=1999 title=Coding TSP tours as permutations via an insertion heuristic
   authors=Bryant A. Julstrom
   venue=Proceedings of the 1999 ACM symposium on Applied computing cited_by=6
   abstract=(missing)
