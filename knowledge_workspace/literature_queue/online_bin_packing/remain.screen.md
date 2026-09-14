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
The top-level family field may be "mixed" when several families are packed together; each screen still has its own subproblem_id.

family: online_bin_packing

=== bp_2d ===
family: online_bin_packing
label: 2D bin packing
definition: Pack rectangles into bins.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Maxrects (not_mappable), Guillotine 2D (not_mappable)
Works:
1. doi=10.1287/ijoc.11.4.345 year=1999 title=Heuristic and Metaheuristic Approaches for a Class of Two-Dimensional Bin Packing Problems
   authors=Andrea Lodi, Silvano Martello, Daniele Vigo
   venue=INFORMS Journal on Computing cited_by=264
   abstract=Two-dimensional bin packing problems consist of allocating, without overlapping, a given set of small rectangles (items) to a minimum number of large identical rectangles (bins), with the edges of the items parallel to those of the bins. According to the specific application, the items may either have a fixed orientation or they can be rotated by 90°. In addition, it may or no…
2. doi=10.4028/www.scientific.net/amr.756-759.2705 year=2013 title=A Constructive Heuristic for Two-Dimensional Bin Packing
   authors=Bo Han Wang, Jia Min Liu, Yong Yue, Malcolm Keech
   venue=Advanced Materials Research cited_by=1
   abstract=Two-dimensional bin packing is encountered in various applications where small rectangular items are packed into a minimum number of large rectangular objects (bins). Aiming at an optimal area utilization, the paper presents an effective constructive heuristic approach to two-dimensional bin packing. The heuristic approach integrates ranking, placement and search strategies al…
3. doi=10.51415/10321/3180 year=None title=Two and three-dimensional bin packing problems : an efficient implementation of evolutionary algorithms
   authors=Andile Ntanjana
   venue=None cited_by=1
   abstract=The present research work deals with the implementation of heuristics and genetic algo- rithms to solve various bin packing problems (BPP). Bin packing problems are a class of optimization problems that have numerous applications in the industrial world, ranging from efficient cutting of material to packing various items in a larger container. Bin packing problems are known to…

=== bp_3d ===
family: online_bin_packing
label: 3D bin packing
definition: Pack boxes.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Deepest-Bottom-Left (not_mappable), Extreme-point 3D (not_mappable)
Works:
1. doi=10.1287/opre.48.2.256.12386 year=2000 title=The Three-Dimensional Bin Packing Problem
   authors=Silvano Martello, David Pisinger, Daniele Vigo
   venue=Operations Research cited_by=526
   abstract=The problem addressed in this paper is that of orthogonally packing a given set of rectangular-shaped items into the minimum number of three-dimensional rectangular bins. The problem is strongly NP-hard and extremely difficult to solve in practice. Lower bounds are discussed, and it is proved that the asymptotic worst-case performance ratio of the continuous lower bound is 1/8…
2. doi=10.1287/ijoc.11.4.345 year=1999 title=Heuristic and Metaheuristic Approaches for a Class of Two-Dimensional Bin Packing Problems
   authors=Andrea Lodi, Silvano Martello, Daniele Vigo
   venue=INFORMS Journal on Computing cited_by=264
   abstract=Two-dimensional bin packing problems consist of allocating, without overlapping, a given set of small rectangles (items) to a minimum number of large identical rectangles (bins), with the edges of the items parallel to those of the bins. According to the specific application, the items may either have a fixed orientation or they can be rotated by 90°. In addition, it may or no…
3. doi=10.51415/10321/3180 year=None title=Two and three-dimensional bin packing problems : an efficient implementation of evolutionary algorithms
   authors=Andile Ntanjana
   venue=None cited_by=1
   abstract=The present research work deals with the implementation of heuristics and genetic algo- rithms to solve various bin packing problems (BPP). Bin packing problems are a class of optimization problems that have numerous applications in the industrial world, ranging from efficient cutting of material to packing various items in a larger container. Bin packing problems are known to…

=== bp_colored ===
family: online_bin_packing
label: Colored bin packing
definition: Color constraints.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Color-aware FF (not_mappable), Colored Best Fit (not_mappable)
Works:
1. doi=10.1287/ijoc.1040.0089 year=2006 title=A Set-Covering-Based Heuristic Approach for Bin-Packing Problems
   authors=Michele Monaci, Paolo Toth
   venue=INFORMS Journal on Computing cited_by=79
   abstract=Several combinatorial optimization problems can be formulated as large set-covering problems. In this work, we use the set-covering formulation to obtain a general heuristic algorithm for this type of problem, and describe our implementation of the algorithm for solving two variants of the well-known (one-dimensional) bin-packing problem: the two-constraint bin-packing problem…
2. doi=10.1162/evco_a_00121 year=2015 title=A Lifelong Learning Hyper-heuristic Method for Bin Packing
   authors=Kevin Sim, Emma Hart, Ben Paechter
   venue=Evolutionary Computation cited_by=66
   abstract=We describe a novel hyper-heuristic system that continuously learns over time to solve a combinatorial optimisation problem. The system continuously generates new heuristics and samples problems from its environment; and representative problems and heuristics are incorporated into a self-sustaining network of interacting entities inspired by methods in artificial immune system…
3. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…

=== bp_conflicts ===
family: online_bin_packing
label: Bin packing with conflicts
definition: Some pairs cannot share a bin.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Conflict-aware FF (not_mappable), Graph coloring + packing (not_mappable)
Works:
1. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…
2. doi=10.3390/electronics14101956 year=2025 title=Neural-Driven Constructive Heuristic for 2D Robotic Bin Packing Problem
   authors=Mariusz Kaleta, Tomasz Śliwiński
   venue=Electronics cited_by=4
   abstract=This study addresses the two-dimensional weakly homogeneous Bin Packing Problem (2D-BPP) in the context of robotic packing, where items must be arranged in a manner feasible for robotic manipulation. Traditional heuristics for this NP-hard problem often lack adaptability across diverse datasets, while metaheuristics typically suffer from slow convergence. To overcome these lim…
3. doi=10.1515/ausi-2015-0011 year=2015 title=Bin packing with directed stackability conflicts
   authors=Attila Bódis
   venue=Acta Universitatis Sapientiae, Informatica cited_by=4
   abstract=Abstract The Bin Packing problem is a well-known and highly investigated problem in the computer science: we have n items given with their sizes, and we want to assign them to unit capacity bins such, that we use the minimum number of bins. In this paper, some generalizations of this problem are considered, where there are some additional stackability constraints defining that…

=== bp_dynamic ===
family: online_bin_packing
label: Dynamic packing
definition: Insert and delete over time.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Dynamic FF (not_mappable), Repacking local search (not_mappable)
Works:
1. doi=10.1287/ijoc.1040.0089 year=2006 title=A Set-Covering-Based Heuristic Approach for Bin-Packing Problems
   authors=Michele Monaci, Paolo Toth
   venue=INFORMS Journal on Computing cited_by=79
   abstract=Several combinatorial optimization problems can be formulated as large set-covering problems. In this work, we use the set-covering formulation to obtain a general heuristic algorithm for this type of problem, and describe our implementation of the algorithm for solving two variants of the well-known (one-dimensional) bin-packing problem: the two-constraint bin-packing problem…
2. doi=10.1162/evco_a_00121 year=2015 title=A Lifelong Learning Hyper-heuristic Method for Bin Packing
   authors=Kevin Sim, Emma Hart, Ben Paechter
   venue=Evolutionary Computation cited_by=66
   abstract=We describe a novel hyper-heuristic system that continuously learns over time to solve a combinatorial optimisation problem. The system continuously generates new heuristics and samples problems from its environment; and representative problems and heuristics are incorporated into a self-sustaining network of interacting entities inspired by methods in artificial immune system…
3. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…

=== bp_fragile ===
family: online_bin_packing
label: Fragile objects
definition: Items cannot support others.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Fragile FFD (not_mappable), Load-limit packing (not_mappable)
Works:
1. doi=10.1287/ijoc.1040.0089 year=2006 title=A Set-Covering-Based Heuristic Approach for Bin-Packing Problems
   authors=Michele Monaci, Paolo Toth
   venue=INFORMS Journal on Computing cited_by=79
   abstract=Several combinatorial optimization problems can be formulated as large set-covering problems. In this work, we use the set-covering formulation to obtain a general heuristic algorithm for this type of problem, and describe our implementation of the algorithm for solving two variants of the well-known (one-dimensional) bin-packing problem: the two-constraint bin-packing problem…
2. doi=10.1162/evco_a_00121 year=2015 title=A Lifelong Learning Hyper-heuristic Method for Bin Packing
   authors=Kevin Sim, Emma Hart, Ben Paechter
   venue=Evolutionary Computation cited_by=66
   abstract=We describe a novel hyper-heuristic system that continuously learns over time to solve a combinatorial optimisation problem. The system continuously generates new heuristics and samples problems from its environment; and representative problems and heuristics are incorporated into a self-sustaining network of interacting entities inspired by methods in artificial immune system…
3. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…

=== bp_guillotine ===
family: online_bin_packing
label: Guillotine packing
definition: Cuts must be guillotine.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Guillotine BF (not_mappable), Recursive guillotine (not_mappable)
Works:
1. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…
2. doi=10.3390/electronics14101956 year=2025 title=Neural-Driven Constructive Heuristic for 2D Robotic Bin Packing Problem
   authors=Mariusz Kaleta, Tomasz Śliwiński
   venue=Electronics cited_by=4
   abstract=This study addresses the two-dimensional weakly homogeneous Bin Packing Problem (2D-BPP) in the context of robotic packing, where items must be arranged in a manner feasible for robotic manipulation. Traditional heuristics for this NP-hard problem often lack adaptability across diverse datasets, while metaheuristics typically suffer from slow convergence. To overcome these lim…
3. doi=10.1088/1742-6596/1656/1/012005 year=2020 title=An improved priority heuristic for the fixed guillotine rectangular packing problem
   authors=Zhengyang Shang, Mingming Pan, Jiabao Pan
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract An improved priority heuristic (IPH) is presented for the guillotine rectangular packing problem with a fixed orientation constraint. This algorithm can continuously divide the remaining space into blocks and recursively layout the entire space by filling each current block. IPH inherits the placement method of PH and adopts an improved space partitioning rule. The pa…

=== bp_mo ===
family: online_bin_packing
label: Multi-objective packing
definition: Bins plus another objective.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Weighted FF (not_mappable), Pareto packing (not_mappable)
Works:
1. doi=10.1287/ijoc.1040.0089 year=2006 title=A Set-Covering-Based Heuristic Approach for Bin-Packing Problems
   authors=Michele Monaci, Paolo Toth
   venue=INFORMS Journal on Computing cited_by=79
   abstract=Several combinatorial optimization problems can be formulated as large set-covering problems. In this work, we use the set-covering formulation to obtain a general heuristic algorithm for this type of problem, and describe our implementation of the algorithm for solving two variants of the well-known (one-dimensional) bin-packing problem: the two-constraint bin-packing problem…
2. doi=10.1162/evco_a_00121 year=2015 title=A Lifelong Learning Hyper-heuristic Method for Bin Packing
   authors=Kevin Sim, Emma Hart, Ben Paechter
   venue=Evolutionary Computation cited_by=66
   abstract=We describe a novel hyper-heuristic system that continuously learns over time to solve a combinatorial optimisation problem. The system continuously generates new heuristics and samples problems from its environment; and representative problems and heuristics are incorporated into a self-sustaining network of interacting entities inspired by methods in artificial immune system…
3. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…

=== bp_offline_ffd ===
family: online_bin_packing
label: FFD/BFD offline
definition: Sort then First/Best Fit.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: First Fit Decreasing (not_mappable), Best Fit Decreasing (not_mappable)
Works:
1. doi=10.1137/0602019 year=1981 title=A Tight Asymptotic Bound for Next-Fit-Decreasing Bin-Packing
   authors=B. S. Baker, E. G. Coffman, Jr.
   venue=SIAM Journal on Algebraic Discrete Methods cited_by=54
   abstract=In this note we derive a tight asymptotic bound on the relative performance of the Next-Fit-Decreasing approximation rule for classical one-dimensional bin-packing. The proof provides a novel application of certain well-known sequences of unit fractions. Potential applications are mentioned.
2. doi=10.1007/s00453-021-00844-5 year=2021 title=Best Fit Bin Packing with Random Order Revisited
   authors=Susanne Albers, Arindam Khan, Leon Ladewig
   venue=Algorithmica cited_by=17
   abstract=Abstract Best Fit is a well known online algorithm for the bin packing problem, where a collection of one-dimensional items has to be packed into a minimum number of unit-sized bins. In a seminal work, Kenyon [SODA 1996] introduced the (asymptotic) random order ratio as an alternative performance measure for online algorithms. Here, an adversary specifies the items, but the or…
3. doi=10.2307/3214408 year=1989 title=Next-fit bin packing with random piece sizes
   authors=Shlomo Halfin
   venue=Journal of Applied Probability cited_by=7
   abstract=Investigations into time-slotted communication channels for transmission of data packets led us to analyze the stochastic behavior of the next-fit bin packing algorithm. In this paper we obtain results for general piece-size distributions and truncated distributions, we calculate explicit solutions for the case of the truncated exponential, and we apply the results to calculat…

=== bp_offline_kk ===
family: online_bin_packing
label: Karmarkar-Karp / differencing
definition: Offline LP or differencing.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Karmarkar-Karp differencing (not_mappable), Multifit (not_mappable)
Works:
1. doi=10.1137/0216012 year=1987 title=An Efficient Approximation Scheme for Variable-Sized Bin Packing
   authors=Frank D. Murgolo
   venue=SIAM Journal on Computing cited_by=60
   abstract=In the classical bin packing problem one is required to pack a given list of items into the smallest possible number of unit-sized bins. Because this problem is NP-complete, researchers have tried to find efficient approximation algorithms that solve this problem in a reasonable amount of time. If we let $A(I)$ be the number of bins used by algorithm A to pack a list of items…
2. doi=10.1137/0222021 year=1993 title=A Monte-Carlo Algorithm for Estimating the Permanent
   authors=N. Karmarkar, R. Karp, R. Lipton, L. Lovász, M. Luby
   venue=SIAM Journal on Computing cited_by=59
   abstract=Let A be an $n \times n$ matrix with 0-1 valued entries, and let ${\operatorname{per}}(A)$ be the permanent of A. This paper describes a Monte-Carlo algorithm that produces a “good in the relative sense” estimate of ${\operatorname{per}}(A)$ and has running time ${\operatorname{poly}}(n)2^{{n / 2}} $, where ${\operatorname{poly}}(n)$ denotes a function that grows polynomially…
3. doi=10.2307/3214002 year=1986 title=Probabilistic analysis of optimum partitioning
   authors=Narendra Karmarkar, Richard M. Karp, George S. Lueker, Andrew M. Odlyzko
   venue=Journal of Applied Probability cited_by=35
   abstract=Given a set of n items with real-valued sizes, the optimum partition problem asks how it can be partitioned into two subsets so that the absolute value of the difference of the sums of the sizes over the two subsets is minimized. We present bounds on the probability distribution of this minimum under the assumption that the sizes are independent random variables drawn from a c…

=== bp_open_end ===
family: online_bin_packing
label: Open-end packing
definition: Last item may overflow slightly.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Open-end FF (not_mappable), Open-end BF (not_mappable)
Works:
1. doi=10.1287/opre.51.5.759.16753 year=2003 title=The Ordered Open-End Bin-Packing Problem
   authors=Jian Yang, Joseph Y.-T. Leung
   venue=Operations Research cited_by=29
   abstract=We study a variant of the classical bin-packing problem, the ordered open-end bin-packing problem, where first a bin can be filled to a level above 1 as long as the removal of the last piece brings the bin's level back to below 1 and second, the last piece is the largest-indexed piece among all pieces in the bin. We conduct both worst-case and average-case analyses for the pro…
2. doi=10.1287/opre.1070.0415 year=2008 title=An Optimization Algorithm for the Ordered Open-End Bin-Packing Problem
   authors=Alberto Ceselli, Giovanni Righini
   venue=Operations Research cited_by=19
   abstract=The ordered open-end bin-packing problem is a variant of the bin-packing problem in which the items to be packed are sorted in a given order and the capacity of each bin can be exceeded by the last item packed into the bin. We present a branch-and-price algorithm for its exact optimization. The pricing subproblem is a special variant of the binary knapsack problem, in which th…
3. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…

=== bp_resource ===
family: online_bin_packing
label: Resource-constrained packing
definition: Extra resources besides size.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Multi-resource BF (not_mappable), Resource FFD (not_mappable)
Works:
1. doi=10.3390/su13179956 year=2021 title=Comparison of Heuristic Priority Rules in the Solution of the Resource-Constrained Project Scheduling Problem
   authors=Osman Hürol Türkakın, David Arditi, Ekrem Manisalı
   venue=Sustainability cited_by=12
   abstract=Resource-constrained project scheduling (RCPS) aims to minimize project duration under limited resource availabilities. The heuristic methods that are often used to solve the RCPS problem make use of different priority rules. The comparative merits of different priority rules have not been discussed in the literature in sufficient detail. This study is a response to this resea…
2. doi=10.1142/s0217595907001334 year=2007 title=A NEW HEURISTIC ALGORITHM FOR CONSTRAINED RECTANGLE-PACKING PROBLEM
   authors=DUANBING CHEN, WENQI HUANG
   venue=Asia-Pacific Journal of Operational Research cited_by=4
   abstract=The constrained rectangle-packing problem is the problem of packing a subset of rectangles into a larger rectangular container, with the objective of maximizing the layout value. It has many industrial applications such as shipping, wood and glass cutting, etc. Many algorithms have been proposed to solve it, for example, simulated annealing, genetic algorithm and other heurist…
3. doi=10.2139/ssrn.1089355 year=2008 title=A Heuristic Methodology for Solving Spatial a Resource-Constrained Project Scheduling Problems
   authors=Eline De Frene, Damien Schatteman, Willy Herroelen, Stijn Van de Vonder
   venue=None cited_by=2
   abstract=In this paper we present a heuristic methodology for solving resource-constrained project scheduling problems with renewable and spatial resources. We especially concentrate on spatial resources that are encountered in construction projects, but our analysis can easily be generalized to other sectors. Our methodology is based on the application of a schedule generation scheme…

=== bp_stochastic ===
family: online_bin_packing
label: Stochastic packing
definition: Item sizes random.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Expected-size BF (not_mappable), Distribution-aware Harmonic (not_mappable)
Works:
1. doi=10.1162/evco_a_00121 year=2015 title=A Lifelong Learning Hyper-heuristic Method for Bin Packing
   authors=Kevin Sim, Emma Hart, Ben Paechter
   venue=Evolutionary Computation cited_by=66
   abstract=We describe a novel hyper-heuristic system that continuously learns over time to solve a combinatorial optimisation problem. The system continuously generates new heuristics and samples problems from its environment; and representative problems and heuristics are incorporated into a self-sustaining network of interacting entities inspired by methods in artificial immune system…
2. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…
3. doi=10.3390/electronics14101956 year=2025 title=Neural-Driven Constructive Heuristic for 2D Robotic Bin Packing Problem
   authors=Mariusz Kaleta, Tomasz Śliwiński
   venue=Electronics cited_by=4
   abstract=This study addresses the two-dimensional weakly homogeneous Bin Packing Problem (2D-BPP) in the context of robotic packing, where items must be arranged in a manner feasible for robotic manipulation. Traditional heuristics for this NP-hard problem often lack adaptability across diverse datasets, while metaheuristics typically suffer from slow convergence. To overcome these lim…

=== cutting_stock ===
family: online_bin_packing
label: 1D cutting stock
definition: Few item types, many copies.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Pattern generation greedy (not_mappable), FFD cutting stock (not_mappable)
Works:
1. doi=10.1287/opre.1040.0109 year=2004 title=A New Placement Heuristic for the Orthogonal Stock-Cutting Problem
   authors=E. K. Burke, G. Kendall, G. Whitwell
   venue=Operations Research cited_by=300
   abstract=This paper presents a new best-fit heuristic for the two-dimensional rectangular stock-cutting problem and demonstrates its effectiveness by comparing it against other published approaches. A placement algorithm usually takes a list of shapes, sorted by some property such as increasing height or decreasing area, and then applies a placement rule to each of these shapes in turn…
2. doi=10.1287/mnsc.17.12.b793 year=1971 title=A Heuristic Programming Solution to a Nonlinear Cutting Stock Problem
   authors=Robert W. Haessler
   venue=Management Science cited_by=83
   abstract=A heuristic procedure for scheduling production rolls of paper through a finishing operation to cut them down to finished roll sizes is described. The ratio of service time to interarrival time of production rolls at the initial cutting station is large so that insufficient time is available to set it up unless a minimum number of production rolls are to be processed in the sa…
3. doi=10.1287/mnsc.23.1.78 year=1976 title=An Improved Heuristic Procedure for a Nonlinear Cutting Stock Problem
   authors=I. Coverdale, F. Wharton
   venue=Management Science cited_by=30
   abstract=Many industries acquire stocks of material in large standard sizes which are then reduced to required widths or lengths according to demand. Scheduling the cutting operations is a particularly difficult problem when a few cutting patterns must be chosen from a vast number of feasible patterns such that the total cost of the reduction process is minimised. Physical constraints…

=== obp_advice ===
family: online_bin_packing
label: Online packing with advice
definition: Limited future bits.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Advice-assisted FF (not_mappable), Advice Harmonic (not_mappable)
Works:
1. doi=10.1613/jair.1.14820 year=2023 title=Online Bin Packing with Predictions
   authors=Spyros Angelopoulos, Shahin Kamali, Kimia Shadkami
   venue=Journal of Artificial Intelligence Research cited_by=14
   abstract=Bin packing is a classic optimization problem with a wide range of applications, from load balancing to supply chain management. In this work, we study the online variant of the problem, in which a sequence of items of various sizes must be placed into a minimum number of bins of uniform capacity. The online algorithm is enhanced with a potentially erroneous prediction concern…
2. doi=10.24963/ijcai.2022/635 year=2022 title=Online Bin Packing with Predictions
   authors=Spyros Angelopoulos, Shahin Kamali, Kimia Shadkami
   venue=Proceedings of the Thirty-First International Joint Conference on Artificial Intelligence cited_by=9
   abstract=Bin packing is a classic optimization problem with a wide range of applications from load balancing to supply chain management. In this work, we study the online variant of the problem, in which a sequence of items of various sizes must be placed into a minimum number of bins of uniform capacity. The online algorithm is enhanced with a (potentially erroneous) prediction concer…
3. doi=10.1115/imece2021-73282 year=2021 title=Solving a Profited 3D Bin Packing Problem Using a Hybrid Genetic Algorithm
   authors=Miri Weiss Cohen
   venue=Volume 6: Design, Systems, and Complexity cited_by=2
   abstract=Abstract This work deals with a problem incorporating two well-known problems: the 3D Bin-packing problem (3D-BPP), and the Knapsack problem. Given the complexity of the problem a hybrid Genetic Algorithm (GA) methodology combining the Deepest Bottom Left Fill (DBLF) heuristics within the GA is presented. The research compares between two methods a basic genetic algorithm base…

=== obp_lookahead ===
family: online_bin_packing
label: k-lookahead online packing
definition: See k future items.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: k-lookahead BF (not_mappable), Lookahead Harmonic (not_mappable)
Works:
1. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…
2. doi=10.3390/s24165370 year=2024 title=Integrating Heuristic Methods with Deep Reinforcement Learning for Online 3D Bin-Packing Optimization
   authors=Ching-Chang Wong, Tai-Ting Tsai, Can-Kun Ou
   venue=Sensors cited_by=11
   abstract=This study proposes a method named Hybrid Heuristic Proximal Policy Optimization (HHPPO) to implement online 3D bin-packing tasks. Some heuristic algorithms for bin-packing and the Proximal Policy Optimization (PPO) algorithm of deep reinforcement learning are integrated to implement this method. In the heuristic algorithms for bin-packing, an extreme point priority sorting me…
3. doi=10.3390/electronics14101956 year=2025 title=Neural-Driven Constructive Heuristic for 2D Robotic Bin Packing Problem
   authors=Mariusz Kaleta, Tomasz Śliwiński
   venue=Electronics cited_by=4
   abstract=This study addresses the two-dimensional weakly homogeneous Bin Packing Problem (2D-BPP) in the context of robotic packing, where items must be arranged in a manner feasible for robotic manipulation. Traditional heuristics for this NP-hard problem often lack adaptability across diverse datasets, while metaheuristics typically suffer from slow convergence. To overcome these lim…

=== vector_bp ===
family: online_bin_packing
label: Vector bin packing
definition: Multi-dimensional capacities.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Vector FFD (not_mappable), Norm-based Best Fit (not_mappable)
Works:
1. doi=10.1287/ijoc.1040.0089 year=2006 title=A Set-Covering-Based Heuristic Approach for Bin-Packing Problems
   authors=Michele Monaci, Paolo Toth
   venue=INFORMS Journal on Computing cited_by=79
   abstract=Several combinatorial optimization problems can be formulated as large set-covering problems. In this work, we use the set-covering formulation to obtain a general heuristic algorithm for this type of problem, and describe our implementation of the algorithm for solving two variants of the well-known (one-dimensional) bin-packing problem: the two-constraint bin-packing problem…
2. doi=10.1162/evco_a_00121 year=2015 title=A Lifelong Learning Hyper-heuristic Method for Bin Packing
   authors=Kevin Sim, Emma Hart, Ben Paechter
   venue=Evolutionary Computation cited_by=66
   abstract=We describe a novel hyper-heuristic system that continuously learns over time to solve a combinatorial optimisation problem. The system continuously generates new heuristics and samples problems from its environment; and representative problems and heuristics are incorporated into a self-sustaining network of interacting entities inspired by methods in artificial immune system…
3. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…
