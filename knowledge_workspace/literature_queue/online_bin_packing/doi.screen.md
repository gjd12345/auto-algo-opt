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

=== bp_batch ===
family: online_bin_packing
label: Batch packing
definition: Items arrive in batches.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Batch Best Fit (bin_score), Sort-within-batch FFD (not_mappable)
Works:
1. doi=10.1137/0203025 year=1974 title=Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms
   authors=D. S. Johnson, A. Demers, J. D. Ullman, M. R. Garey, R. L. Graham
   venue=SIAM Journal on Computing cited_by=691
   abstract=The following abstract problem models several practical problems in computer science and operations research: given a list L of real numbers between 0 and l, place the elements of L into a minimum number $L^ * $ of “bins” so that no bin contains numbers whose sum exceeds l. Motivated by the likelihood that an excessive amount of computation will be required by any algorithm wh…
2. doi=10.1137/0204038 year=1975 title=Preserving Proximity in Arrays
   authors=Arnold L. Rosenberg
   venue=SIAM Journal on Computing cited_by=31
   abstract=Efficiency of storage management in algorithms which use arrays is often enhanced if the arrays are stored in a proximity-preserving manner; that is, array positions which are close to one another in the array are stored close to one another. This paper is devoted to studying certain qualitative and quantitative questions concerning preservation of proximity by array storage s…
3. doi=10.1111/itor.12030 year=2013 title=An improved best‐fit heuristic for the orthogonal strip packing problem
   authors=Jannes Verstichel, Patrick De Causmaecker, Greet Vanden Berghe
   venue=International Transactions in Operational Research cited_by=25
   abstract=Abstract The best‐fit heuristic is a simple and powerful tool for solving the two‐dimensional orthogonal strip packing problem. It is the most efficient constructive heuristic on a wide range of rectangular strip packing benchmark problems. In this paper, the results of the original best‐fit heuristic are further improved by adding new item orderings and item placement strateg…

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
1. doi=10.1137/0212045 year=1983 title=Authenticated Algorithms for Byzantine Agreement
   authors=D. Dolev, H. R. Strong
   venue=SIAM Journal on Computing cited_by=459
   abstract=Reaching agreement in a distributed system in the presence of faulty processors is a central issue for reliable computer systems. Using an authentication protocol, one can limit the undetected behavior of faulty processors to a simple failure to relay messages to all intended targets. In this paper we show that, in spite of such an ability to limit faulty behavior, and no matt…
2. doi=10.1137/0212043 year=1983 title=Fast Parallel Computation of Polynomials Using Few Processors
   authors=L. G. Valiant, S. Skyum, S. Berkowitz, C. Rackoff
   venue=SIAM Journal on Computing cited_by=192
   abstract=It is shown that any multivariate polynomial of degree d that can be computed sequentially in C steps can be computed in parallel in $O((\log d)(\log C + \log d))$ steps using only $(Cd)^{O(1)} $ processors.
3. doi=10.1287/ijoc.1040.0089 year=2006 title=A Set-Covering-Based Heuristic Approach for Bin-Packing Problems
   authors=Michele Monaci, Paolo Toth
   venue=INFORMS Journal on Computing cited_by=79
   abstract=Several combinatorial optimization problems can be formulated as large set-covering problems. In this work, we use the set-covering formulation to obtain a general heuristic algorithm for this type of problem, and describe our implementation of the algorithm for solving two variants of the well-known (one-dimensional) bin-packing problem: the two-constraint bin-packing problem…

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

=== bp_resource ===
family: online_bin_packing
label: Resource-constrained packing
definition: Extra resources besides size.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Multi-resource BF (not_mappable), Resource FFD (not_mappable)
Works:
1. doi=10.1287/ijoc.1040.0089 year=2006 title=A Set-Covering-Based Heuristic Approach for Bin-Packing Problems
   authors=Michele Monaci, Paolo Toth
   venue=INFORMS Journal on Computing cited_by=79
   abstract=Several combinatorial optimization problems can be formulated as large set-covering problems. In this work, we use the set-covering formulation to obtain a general heuristic algorithm for this type of problem, and describe our implementation of the algorithm for solving two variants of the well-known (one-dimensional) bin-packing problem: the two-constraint bin-packing problem…
2. doi=10.3390/su13179956 year=2021 title=Comparison of Heuristic Priority Rules in the Solution of the Resource-Constrained Project Scheduling Problem
   authors=Osman Hürol Türkakın, David Arditi, Ekrem Manisalı
   venue=Sustainability cited_by=12
   abstract=Resource-constrained project scheduling (RCPS) aims to minimize project duration under limited resource availabilities. The heuristic methods that are often used to solve the RCPS problem make use of different priority rules. The comparative merits of different priority rules have not been discussed in the literature in sufficient detail. This study is a response to this resea…
3. doi=10.1142/s0217595907001334 year=2007 title=A NEW HEURISTIC ALGORITHM FOR CONSTRAINED RECTANGLE-PACKING PROBLEM
   authors=DUANBING CHEN, WENQI HUANG
   venue=Asia-Pacific Journal of Operational Research cited_by=4
   abstract=The constrained rectangle-packing problem is the problem of packing a subset of rectangles into a larger rectangular container, with the objective of maximizing the layout value. It has many industrial applications such as shipping, wood and glass cutting, etc. Many algorithms have been proposed to solve it, for example, simulated annealing, genetic algorithm and other heurist…

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
3. doi=10.1002/rsa.10037 year=2002 title=Linear waste of best fit bin packing on skewed distributions
   authors=Claire Kenyon, Michael Mitzenmacher
   venue=Random Structures &amp; Algorithms cited_by=4
   abstract=Abstract We prove that Best Fit bin packing has linear waste on the discrete distribution U { j , k } (where items are drawn uniformly from the set {1/ k , 2/ k , …, j / k }) for sufficiently large k when j = α k and 0.66 ≤ α &lt; 2/3. Our results extend to continuous skewed distributions, where items are drawn uniformly on [0, a ], for 0.66 ≤ a &lt; 2/3. This implies that the…

=== bp_types ===
family: online_bin_packing
label: Few item types
definition: Many copies of few sizes.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Type-aware Best Fit (bin_score), Grouping Harmonic (bin_score)
Works:
1. doi=10.1137/0203025 year=1974 title=Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms
   authors=D. S. Johnson, A. Demers, J. D. Ullman, M. R. Garey, R. L. Graham
   venue=SIAM Journal on Computing cited_by=691
   abstract=The following abstract problem models several practical problems in computer science and operations research: given a list L of real numbers between 0 and l, place the elements of L into a minimum number $L^ * $ of “bins” so that no bin contains numbers whose sum exceeds l. Motivated by the likelihood that an excessive amount of computation will be required by any algorithm wh…
2. doi=10.1145/3828.3833 year=1985 title=A simple on-line bin-packing algorithm
   authors=C. C. Lee, D. T. Lee
   venue=Journal of the ACM cited_by=286
   abstract=The one-dimensional on-line bin-packing problem is considered, A simple O (1)-space and O ( n )-time algorithm, called HARMONIC M , is presented. It is shown that this algorithm can achieve a worst-case performance ratio of less than 1.692, which is better than that of the O ( n )-space and O ( n log n )-time algorithm FIRST FIT. Also shown is that 1.691 … is a lower bound for…
3. doi=10.1111/itor.12030 year=2013 title=An improved best‐fit heuristic for the orthogonal strip packing problem
   authors=Jannes Verstichel, Patrick De Causmaecker, Greet Vanden Berghe
   venue=International Transactions in Operational Research cited_by=25
   abstract=Abstract The best‐fit heuristic is a simple and powerful tool for solving the two‐dimensional orthogonal strip packing problem. It is the most efficient constructive heuristic on a wide range of rectangular strip packing benchmark problems. In this paper, the results of the original best‐fit heuristic are further improved by adding new item orderings and item placement strateg…

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

=== obp_bestfit_family ===
family: online_bin_packing
label: Best-Fit online family
definition: Prefer tight residual.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Best Fit (bin_score), Almost Best Fit (bin_score)
Works:
1. doi=10.1137/0203025 year=1974 title=Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms
   authors=D. S. Johnson, A. Demers, J. D. Ullman, M. R. Garey, R. L. Graham
   venue=SIAM Journal on Computing cited_by=691
   abstract=The following abstract problem models several practical problems in computer science and operations research: given a list L of real numbers between 0 and l, place the elements of L into a minimum number $L^ * $ of “bins” so that no bin contains numbers whose sum exceeds l. Motivated by the likelihood that an excessive amount of computation will be required by any algorithm wh…
2. doi=10.1137/s009753979834669x year=2001 title=Variable-Sized Bin Packing: Tight Absolute Worst-Case Performance Ratios for Four Approximation Algorithms
   authors=Chengbin Chu, Rémy La
   venue=SIAM Journal on Computing cited_by=28
   abstract=In this paper we consider a one-dimensional bin packing problem where the bins do not have identical sizes, or a variable-sized bin packing problem, to minimize the bin consumption, i.e., the total size of the opened bins. The identical size problem has been extensively studied in the literature both for static and dynamic settings. The worst-case or average-case performance h…
3. doi=10.1137/0222004 year=1993 title=Tight Worst-Case Performance Bounds for Next-
                    <i>k</i>
                    -Fit Bin Packing
   authors=Weizhen Mao
   venue=SIAM Journal on Computing cited_by=18
   abstract=The bin packing problem is to pack a list of reals in $( {0,1} ]$ into unit-capacity bins using the minimum number of bins. Let $R[A]$ be the limiting worst value for the ratio ${{A(L)} / {L^ * }}$ as $L^ * $ goes to $\infty $, where $A(L)$ denotes the number of bins used in the approximation algorithm A, and $L^ * $ denotes the minimum number of bins needed to pack L. Obvious…

=== obp_irrevocable ===
family: online_bin_packing
label: Irrevocable online packing
definition: No repacking; matches EoH OBP.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Worst Fit (bin_score), Residual-utilization score (bin_score)
Works:
1. doi=10.1137/0203025 year=1974 title=Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms
   authors=D. S. Johnson, A. Demers, J. D. Ullman, M. R. Garey, R. L. Graham
   venue=SIAM Journal on Computing cited_by=691
   abstract=The following abstract problem models several practical problems in computer science and operations research: given a list L of real numbers between 0 and l, place the elements of L into a minimum number $L^ * $ of “bins” so that no bin contains numbers whose sum exceeds l. Motivated by the likelihood that an excessive amount of computation will be required by any algorithm wh…
2. doi=10.1137/0222004 year=1993 title=Tight Worst-Case Performance Bounds for Next-
                    <i>k</i>
                    -Fit Bin Packing
   authors=Weizhen Mao
   venue=SIAM Journal on Computing cited_by=18
   abstract=The bin packing problem is to pack a list of reals in $( {0,1} ]$ into unit-capacity bins using the minimum number of bins. Let $R[A]$ be the limiting worst value for the ratio ${{A(L)} / {L^ * }}$ as $L^ * $ goes to $\infty $, where $A(L)$ denotes the number of bins used in the approximation algorithm A, and $L^ * $ denotes the minimum number of bins needed to pack L. Obvious…
3. doi=10.1007/s00453-021-00844-5 year=2021 title=Best Fit Bin Packing with Random Order Revisited
   authors=Susanne Albers, Arindam Khan, Leon Ladewig
   venue=Algorithmica cited_by=17
   abstract=Abstract Best Fit is a well known online algorithm for the bin packing problem, where a collection of one-dimensional items has to be packed into a minimum number of unit-sized bins. In a seminal work, Kenyon [SODA 1996] introduced the (asymptotic) random order ratio as an alternative performance measure for online algorithms. Here, an adversary specifies the items, but the or…

=== obp_lookahead ===
family: online_bin_packing
label: k-lookahead online packing
definition: See k future items.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: k-lookahead BF (not_mappable), Lookahead Harmonic (not_mappable)
Works:
1. doi=10.1145/3828.3833 year=1985 title=A simple on-line bin-packing algorithm
   authors=C. C. Lee, D. T. Lee
   venue=Journal of the ACM cited_by=286
   abstract=The one-dimensional on-line bin-packing problem is considered, A simple O (1)-space and O ( n )-time algorithm, called HARMONIC M , is presented. It is shown that this algorithm can achieve a worst-case performance ratio of less than 1.692, which is better than that of the O ( n )-space and O ( n log n )-time algorithm FIRST FIT. Also shown is that 1.691 … is a lower bound for…
2. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…
3. doi=10.3390/s24165370 year=2024 title=Integrating Heuristic Methods with Deep Reinforcement Learning for Online 3D Bin-Packing Optimization
   authors=Ching-Chang Wong, Tai-Ting Tsai, Can-Kun Ou
   venue=Sensors cited_by=11
   abstract=This study proposes a method named Hybrid Heuristic Proximal Policy Optimization (HHPPO) to implement online 3D bin-packing tasks. Some heuristic algorithms for bin-packing and the Proximal Policy Optimization (PPO) algorithm of deep reinforcement learning are integrated to implement this method. In the heuristic algorithms for bin-packing, an extreme point priority sorting me…

=== obp_score ===
family: online_bin_packing
label: Score-based online packing
definition: Learned or designed score over residuals.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Residual-utilization score (bin_score), Piecewise residual score (bin_score)
Works:
1. doi=10.1137/0203025 year=1974 title=Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms
   authors=D. S. Johnson, A. Demers, J. D. Ullman, M. R. Garey, R. L. Graham
   venue=SIAM Journal on Computing cited_by=691
   abstract=The following abstract problem models several practical problems in computer science and operations research: given a list L of real numbers between 0 and l, place the elements of L into a minimum number $L^ * $ of “bins” so that no bin contains numbers whose sum exceeds l. Motivated by the likelihood that an excessive amount of computation will be required by any algorithm wh…
2. doi=10.1145/3828.3833 year=1985 title=A simple on-line bin-packing algorithm
   authors=C. C. Lee, D. T. Lee
   venue=Journal of the ACM cited_by=286
   abstract=The one-dimensional on-line bin-packing problem is considered, A simple O (1)-space and O ( n )-time algorithm, called HARMONIC M , is presented. It is shown that this algorithm can achieve a worst-case performance ratio of less than 1.692, which is better than that of the O ( n )-space and O ( n log n )-time algorithm FIRST FIT. Also shown is that 1.691 … is a lower bound for…
3. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…

=== obp_worstfit_family ===
family: online_bin_packing
label: Worst-Fit online family
definition: Prefer emptiest bin.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Worst Fit (bin_score), Almost Worst Fit (bin_score)
Works:
1. doi=10.1137/0203025 year=1974 title=Worst-Case Performance Bounds for Simple One-Dimensional Packing Algorithms
   authors=D. S. Johnson, A. Demers, J. D. Ullman, M. R. Garey, R. L. Graham
   venue=SIAM Journal on Computing cited_by=691
   abstract=The following abstract problem models several practical problems in computer science and operations research: given a list L of real numbers between 0 and l, place the elements of L into a minimum number $L^ * $ of “bins” so that no bin contains numbers whose sum exceeds l. Motivated by the likelihood that an excessive amount of computation will be required by any algorithm wh…
2. doi=10.1137/s0895480100369948 year=2001 title=An Optimal Online Algorithm for Bounded Space Variable-Sized Bin Packing
   authors=Steven S. Seiden
   venue=SIAM Journal on Discrete Mathematics cited_by=20
   abstract=An online algorithm for variable-sized bin packing, based on the Harmonic algorithm of Lee and Lee,[J. ACM, 32 (1985), pp. 562--572], is investigated. This algorithm was proposed by Csirik, [Acta Inform., 26 (1989), pp. 697--709], who proved that for all sets of bin sizes, 1.69103 upper bounds its performance ratio. The upper bound is improved in the sense that we give a metho…
3. doi=10.1137/0222004 year=1993 title=Tight Worst-Case Performance Bounds for Next-
                    <i>k</i>
                    -Fit Bin Packing
   authors=Weizhen Mao
   venue=SIAM Journal on Computing cited_by=18
   abstract=The bin packing problem is to pack a list of reals in $( {0,1} ]$ into unit-capacity bins using the minimum number of bins. Let $R[A]$ be the limiting worst value for the ratio ${{A(L)} / {L^ * }}$ as $L^ * $ goes to $\infty $, where $A(L)$ denotes the number of bins used in the approximation algorithm A, and $L^ * $ denotes the minimum number of bins needed to pack L. Obvious…
