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

family: tsp

=== tsp_asymmetric ===
family: tsp
label: Asymmetric TSP
definition: Directed distances, d(i,j) may differ from d(j,i).
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Directed Nearest Neighbor (next_node_score), Directed 3-opt (move_selector)
Works:
1. doi=10.1287/opre.6.6.791 year=1958 title=A Method for Solving Traveling-Salesman Problems
   authors=G. A. Croes
   venue=Operations Research cited_by=1207
   abstract=The traveling-salesman problem is a generalized form of the simple problem to find the smallest closed loop that connects a number of points in a plane. Efforts in the past to find an efficient method for solving it have met with only partial success. The present paper describes a method of solution that has the following properties (a) It is applicable to both symmetric and a…
2. doi=10.1007/s00521-022-07816-y year=2022 title=Solving TSP by using combinatorial Bees algorithm with nearest neighbor method
   authors=Murat Sahin
   venue=Neural Computing and Applications cited_by=33
   abstract=Abstract Bees Algorithm (BA) is a popular meta-heuristic method that has been used in many different optimization areas for years. In this study, a new version of combinatorial BA is proposed and explained in detail to solve Traveling Salesman Problems (TSPs). The nearest neighbor method was used in the population generation section of BA, and the Multi-Insert function was add…
3. doi=10.1159/000156818 year=1994 title=Contrasting Chimpanzees and Bonobos: Nearest Neighbor Distances and Choices
   authors=Frances J. White, Colin A. Chapman
   venue=Folia Primatologica cited_by=29
   abstract=In an effort to understand factors underlying differences in the social organization of Pan troglodytes and P. paniscus, we measured the nearest neighbor distances and choices for chimpanzees in Kibale National Park, Uganda, and for bonobos in Lomako Forest, Zaire. We assume that the spatial organization of a set of individuals should reflect the underlying relationships betwe…

=== tsp_bottleneck ===
family: tsp
label: Bottleneck TSP
definition: Minimise the longest edge.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Bottleneck NN (next_node_score), Threshold binary search + MST (not_mappable)
Works:
1. doi=10.1145/2406336.2406345 year=2013 title=A Hybrid Genetic Algorithm for the Bottleneck Traveling Salesman Problem
   authors=Zakir Hussain Ahmed
   venue=ACM Transactions on Embedded Computing Systems cited_by=15
   abstract=The bottleneck traveling salesman problem is to find a Hamiltonian circuit that minimizes the largest cost of any of its arcs in a graph. A simple genetic algorithm (GA) using sequential constructive crossover has been developed to obtain heuristic solution to the problem. The hybrid GA incorporates 2-opt search, another proposed local search and immigration to the simple GA f…
2. doi=10.1287/opre.32.2.380 year=1984 title=An Algorithm for the Bottleneck Traveling Salesman Problem
   authors=Giorgio Carpaneto, Silvano Martello, Paolo Toth
   venue=Operations Research cited_by=12
   abstract=Given a graph with arc costs, the Bottleneck Traveling Salesman Problem is to find a Hamiltonian circuit that minimizes the largest cost of any of its arcs. Lower bounds for the problem (bottleneck assignment problem, bottleneck paths, bottleneck arborescence, cuts) are analyzed and combined to obtain a bounding procedure for a breadth-first branch and bound algorithm. At each…
3. doi=10.1088/1742-6596/1811/1/012068 year=2021 title=Minimizing capacity of Electric Vehicle Battery using Bottleneck Traveling Salesman Problem
   authors=Rio Aurachman, Dyah Putri Saraswari
   venue=Journal of Physics: Conference Series cited_by=2
   abstract=Abstract Electrical vehicle technology has now developed. Various public transportation can start using electric power sources. However, there are battery capacity constraints. When the distance is too far, the battery capacity is not sufficient to provide the required power. In this paper, we will explain how the bottleneck travel salesman problem is applied to minimize batte…

=== tsp_clustered ===
family: tsp
label: Clustered TSP
definition: Cities grouped; visit clusters as units.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Cluster-first NN (next_node_score), Intra-cluster 2-opt (move_selector)
Works:
1. doi=10.1287/opre.6.6.791 year=1958 title=A Method for Solving Traveling-Salesman Problems
   authors=G. A. Croes
   venue=Operations Research cited_by=1207
   abstract=The traveling-salesman problem is a generalized form of the simple problem to find the smallest closed loop that connects a number of points in a plane. Efforts in the past to find an efficient method for solving it have met with only partial success. The present paper describes a method of solution that has the following properties (a) It is applicable to both symmetric and a…
2. doi=10.7717/peerj-cs.972 year=2022 title=Solving the clustered traveling salesman problem
                    <i>via</i>
                    traveling salesman problem methods
   authors=Yongliang Lu, Jin-Kao Hao, Qinghua Wu
   venue=PeerJ Computer Science cited_by=13
   abstract=The Clustered Traveling Salesman Problem (CTSP) is a variant of the popular Traveling Salesman Problem (TSP) arising from a number of real-life applications. In this work, we explore a transformation approach that solves the CTSP by converting it to the well-studied TSP. For this purpose, we first investigate a technique to convert a CTSP instance to a TSP and then apply power…
3. doi=10.2478/fcds-2023-0020 year=2023 title=Traveling salesman problem parallelization by solving clustered subproblems
   authors=Vadim Romanuke
   venue=Foundations of Computing and Decision Sciences cited_by=3
   abstract=Abstract A method of parallelizing the process of solving the traveling salesman problem is suggested, where the solver is a heuristic algorithm. The traveling salesman problem parallelization is fulfilled by clustering the nodes into a given number of groups. Every group (cluster) is an open-loop subproblem that can be solved independently of other subproblems. Then the solut…

=== tsp_colored ===
family: tsp
label: Colored TSP
definition: Color/class visit constraints.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Color-feasible NN (not_mappable), Colored local search (not_mappable)
Works:
1. doi=10.3390/a11100143 year=2018 title=An Algorithm for Mapping the Asymmetric Multiple Traveling Salesman Problem onto Colored Petri Nets
   authors=Furqan Hussain Essani, Sajjad Haider
   venue=Algorithms cited_by=7
   abstract=The Multiple Traveling Salesman Problem is an extension of the famous Traveling Salesman Problem. Finding an optimal solution to the Multiple Traveling Salesman Problem (mTSP) is a difficult task as it belongs to the class of NP-hard problems. The problem becomes more complicated when the cost matrix is not symmetric. In such cases, finding even a feasible solution to the prob…
2. doi=10.70675/09043c22zfaa5z4e3bz868bz8ac1958d96f3 year=None title=Exact and anytime heuristic search for the Time Dependent Traveling Salesman Problem with Time Windows
   authors=Romain Fontaine
   venue=None cited_by=0
   abstract=Recherche heuristique exacte et anytime pour résoudre le Voyageur de commerce dépendant du temps avec fenêtres temporelles Le problème du voyageur de commerce (TSP, pour Traveling Salesman Problem) dépendant du temps (TD, pour Time Dependent) est une généralisation du TSP qui permet de prendre en compte les conditions de trafic lors de la planification de tournées en milieu ur…
3. doi=10.21203/rs.3.rs-3603107/v1 year=2023 title=A Cloud Container-Based Distributed Solving Approach to Superscale Colored Traveling Salesman Problems
   authors=Zhicheng Lin, Jun Li, Yongcui Li
   venue=None cited_by=0
   abstract=Abstract The colored traveling salesman problem (CTSP) generalizes the well-known multiple traveling salesman problem (MTSP) by utilizing colors to describe the accessibility of cities to individual salesmen. Many serial algorithms have been developed to solve CTSP instances. This work presents a distributed solving method for CTSP for the first time. First, a cloud container-…

=== tsp_covering ===
family: tsp
label: Covering salesman
definition: A vertex covers neighbors.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Covering greedy (not_mappable), Set-cover + TSP (not_mappable)
Works:
1. doi=10.1002/net.3230140304 year=1984 title=Euclidean shortest paths in the presence of rectilinear barriers
   authors=D. T. Lee, F. P. Preparata
   venue=Networks cited_by=273
   abstract=Abstract In this paper we address the problem of constructing a Euclidean shortest path between two specified points (source, destination) in the plane, which avoids a given set of barriers. This problem had been solved earlier for polygonal obstacles with the aid of the visibility graph. This approach however, has an Ω(n 2 ) time lower bound, if n is the total number of verti…
2. doi=10.1002/net.3230120305 year=1982 title=Modular decomposition and reliability computation in stochastic transportation networks having cutnodes
   authors=Andrew W. Shogan
   venue=Networks cited_by=12
   abstract=Abstract Consider a flow network having random arc capacities and having associated with each node n a “supply‐demand random variable” Y n whose absolute value equals the supply available at the node when Y n assumes a non‐negative value and the demand required by the node when Y n assumes a nonpositive value. A fundamental problem is the computation of the reliability R , tha…
3. doi=10.2139/ssrn.4167190 year=2022 title=Drone-Assisted Last-Mile Delivery Problem by Covering Salesman Problem with Nodes and Segments
   authors=Hosang Song, Abdullahi  M. Jingi, Xinan Yang
   venue=None cited_by=1
   abstract=Drones attract increasing attention in the last decades as a means for last mile delivery; they are mainly considered as supplement delivery tools that work jointly with trucks. In this paper, we develop a Covering Salesman Problem with Nodes and Segments Using Drones (CSPNS-D) and formulate three Mixed Integer Linear Programming (MILP) models that minimize delivery time in a…

=== tsp_drone ===
family: tsp
label: TSP with drone
definition: Truck plus UAV.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Truck-drone NN (not_mappable), Drone launch local search (not_mappable)
Works:
1. doi=10.1002/net.21659 year=2015 title=A Rolling Horizon Heuristic for the Multiperiod Network Design and Routing Problem
   authors=Dimitri Papadimitriou, Bernard Fortz
   venue=Networks cited_by=9
   abstract=The capacitated fixed‐charge network design (FCND) problem considers the simultaneous optimization of capacity installation and routing of traffic where a fixed cost is paid for opening a link and a linear routing cost is paid for sending traffic flow(s) on that link. The routing decisions must be performed such that the traffic flows remain bounded by the installed link capac…
2. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
3. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…

=== tsp_dynamic ===
family: tsp
label: Dynamic / online TSP
definition: Cities revealed over time.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Online NN (next_node_score), Replanning 2-opt (move_selector)
Works:
1. doi=10.1002/net.20454 year=2011 title=Online traveling salesman problems with service flexibility
   authors=Patrick Jaillet, Xin Lu
   venue=Networks cited_by=35
   abstract=Abstract The traveling salesman problem is a well‐known combinatorial optimization problem. We are concerned here with online versions of this problem defined on metric spaces. One novel aspect in this article is the introduction of a sound theoretical model to incorporate “yes‐no” decisions on which requests to serve, together with an online strategy to visit the accepted req…
2. doi=10.11591/tijee.v15i2.1554 year=2015 title=Heuristic Approaches to Solve Traveling Salesman Problem
   authors=Malik Muneeb Abid, Iqbal Muhammad
   venue=TELKOMNIKA Indonesian Journal of Electrical Engineering cited_by=5
   abstract=This paper provides the survey of the heuristics solution approaches for the traveling salesman problem (TSP). TSP is easy to understand, however, it is very difficult to solve. Due to complexity involved with exact solution approaches it is hard to solve TSP within feasible time. That’s why different heuristics are generally applied to solve TSP. Heuristics to solve TSP are p…
3. doi=10.4028/www.scientific.net/amm.34-35.1180 year=2010 title=Optimization Models and Heuristic Method Based on Simulated Annealing Strategy for Traveling Salesman Problem
   authors=Xu Hao
   venue=Applied Mechanics and Materials cited_by=1
   abstract=The traveling salesman problem (TSP) is a problem in combinatorial optimization studied in operations research and theoretical computer science. In this paper, we presented a novel heuristic simulated annealing algorithm for solving TSP. The algorithm is fully operational in the genetic role of crossover operator, and mutation operator, to achieve a balance between speed and a…

=== tsp_forbidden ===
family: tsp
label: Forbidden edges
definition: Some edges cannot be used.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Constrained NN (next_node_score), Infeasible-edge 2-opt (move_selector)
Works:
1. doi=10.1287/opre.6.6.791 year=1958 title=A Method for Solving Traveling-Salesman Problems
   authors=G. A. Croes
   venue=Operations Research cited_by=1207
   abstract=The traveling-salesman problem is a generalized form of the simple problem to find the smallest closed loop that connects a number of points in a plane. Efforts in the past to find an efficient method for solving it have met with only partial success. The present paper describes a method of solution that has the following properties (a) It is applicable to both symmetric and a…
2. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
3. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…

=== tsp_fuel ===
family: tsp
label: Fuel / replenishment TSP
definition: Must visit refill points.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Refuel insertion (not_mappable), Fuel-feasible NN (not_mappable)
Works:
1. doi=10.11591/tijee.v15i2.1554 year=2015 title=Heuristic Approaches to Solve Traveling Salesman Problem
   authors=Malik Muneeb Abid, Iqbal Muhammad
   venue=TELKOMNIKA Indonesian Journal of Electrical Engineering cited_by=5
   abstract=This paper provides the survey of the heuristics solution approaches for the traveling salesman problem (TSP). TSP is easy to understand, however, it is very difficult to solve. Due to complexity involved with exact solution approaches it is hard to solve TSP within feasible time. That’s why different heuristics are generally applied to solve TSP. Heuristics to solve TSP are p…
2. doi=10.1088/1742-6596/1218/1/012038 year=2019 title=New heuristic algorithm for traveling salesman problem
   authors=M L Shahab
   venue=Journal of Physics: Conference Series cited_by=2
   abstract=Abstract Traveling salesman problem (TSP) is a basis for many bigger problems. If we can find an efficient method (that produce a good result in a short time) to solve the TSP, then we will also be able to solve many other problems. In this research, we proposed a new heuristic algorithm for TSP. We used 80 problems from TSPLIB to test the proposed heuristic algorithm. The pro…
3. doi=10.4028/www.scientific.net/amm.34-35.1180 year=2010 title=Optimization Models and Heuristic Method Based on Simulated Annealing Strategy for Traveling Salesman Problem
   authors=Xu Hao
   venue=Applied Mechanics and Materials cited_by=1
   abstract=The traveling salesman problem (TSP) is a problem in combinatorial optimization studied in operations research and theoretical computer science. In this paper, we presented a novel heuristic simulated annealing algorithm for solving TSP. The algorithm is fully operational in the genetic role of crossover operator, and mutation operator, to achieve a balance between speed and a…

=== tsp_local ===
family: tsp
label: Local-search TSP
definition: Improve a complete tour.
eoh_map: {"status": "possible", "adapter_kind": "move_selector"}
target_heuristics: 2-opt (move_selector), Or-opt (not_mappable)
Works:
1. doi=10.1287/opre.6.6.791 year=1958 title=A Method for Solving Traveling-Salesman Problems
   authors=G. A. Croes
   venue=Operations Research cited_by=1207
   abstract=The traveling-salesman problem is a generalized form of the simple problem to find the smallest closed loop that connects a number of points in a plane. Efforts in the past to find an efficient method for solving it have met with only partial success. The present paper describes a method of solution that has the following properties (a) It is applicable to both symmetric and a…
2. doi=10.47839/ijc.22.1.2878 year=2023 title=Simulated Annealing – 2 Opt Algorithm for Solving Traveling Salesman Problem
   authors=P. H. Gunawan, Iryanto Iryanto
   venue=International Journal of Computing cited_by=5
   abstract=The purpose of this article is to elaborate performance of the hybrid model of Simulated Annealing (SA) and 2 Opt algorithm for solving the traveling salesman problem (TSP). The SA algorithm used in this article is based on the outer and inner loop SA algorithm. The hybrid algorithm has promising results in solving small and medium-scale symmetric traveling salesman problem be…
3. doi=10.21511/dm.18(1).2020.03 year=2020 title=Computer tools for solving the traveling salesman problem
   authors=Juraj Pekár, Ivan Brezina, Jaroslav Kultan, Iryna Ushakova, Oleksandr Dorokhov
   venue=Development Management cited_by=3
   abstract=The task of the traveling salesman, which is to find the shortest or least costly circular route, is one of the most common optimization problems that need to be solved in various fields of practice. The article analyzes and demonstrates various methods for solving this problem using a specific example: heuristic (the nearest neighbor method, the most profitable neighbor metho…

=== tsp_metric ===
family: tsp
label: Metric TSP
definition: Distances satisfy the triangle inequality.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Nearest Neighbor (next_node_score), Christofides (not_mappable)
Works:
1. doi=10.1287/opre.21.2.498 year=1973 title=An Effective Heuristic Algorithm for the Traveling-Salesman Problem
   authors=S. Lin, B. W. Kernighan
   venue=Operations Research cited_by=2854
   abstract=This paper discusses a highly effective heuristic procedure for generating optimum and near-optimum solutions for the symmetric traveling-salesman problem. The procedure is based on a general approach to heuristics that is believed to have wide applicability in combinatorial optimization problems. The procedure produces optimum solutions for all problems tested, “classical” pr…
2. doi=10.1137/0206041 year=1977 title=An Analysis of Several Heuristics for the Traveling Salesman Problem
   authors=Daniel J. Rosenkrantz, Richard E. Stearns, Philip M. Lewis, II
   venue=SIAM Journal on Computing cited_by=736
   abstract=Several polynomial time algorithms finding “good,” but not necessarily optimal, tours for the traveling salesman problem are considered. We measure the closeness of a tour by the ratio of the obtained tour length to the minimal tour length. For the nearest neighbor method, we show the ratio is bounded above by a logarithmic function of the number of nodes. We also provide a lo…
3. doi=10.1287/opre.36.3.478 year=1988 title=A Heuristic Algorithm for the Traveling Salesman Location Problem on Networks
   authors=David Simchi-Levi, Oded Berman
   venue=Operations Research cited_by=87
   abstract=In this paper, we present a heuristic for the traveling salesman location problem on a network. Each day the salesman (e.g., a repair vehicle) must visit all the calls that are registered in a service list. Each call is generated with a given probability and the service list contains at most n calls. The heuristic requires O(n 3 ) time to find the location that “minimizes” the…

=== tsp_minmax ===
family: tsp
label: Min-max mTSP
definition: Minimise the longest salesman tour.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Balanced NN (not_mappable), Min-max 2-opt (not_mappable)
Works:
1. doi=10.1002/net.3230220304 year=1992 title=Complexity results for well‐covered graphs
   authors=Ramesh S. Sankaranarayana, Lorna K. Stewart
   venue=Networks cited_by=69
   abstract=Abstract A graph with n vertices is well covered if every maximal independent set is a maximum independent set and very well covered if every maximal independent set has size n /2. In this work, we study these graphs from an algorithmic complexity point of view. We show that well‐covered graph recognition is co‐NP‐complete and that several other problems are NP‐complete for we…
2. doi=10.3390/drones7070407 year=2023 title=Development of Heuristic Approaches for Last-Mile Delivery TSP with a Truck and Multiple Drones
   authors=Marco Rinaldi, Stefano Primatesta, Martin Bugaj, Ján Rostáš, Giorgio Guglieri
   venue=Drones cited_by=34
   abstract=Unmanned Aerial Vehicles (UAVs) are gaining momentum in many civil and military sectors. An example is represented by the logistics sector, where UAVs have been proven to be able to improve the efficiency of the process itself, as their cooperation with trucks can decrease the delivery time and reduce fuel consumption. In this paper, we first state a mathematical formulation o…
3. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…

=== tsp_neighborhoods ===
family: tsp
label: TSP with neighborhoods
definition: Visit a region not a point.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Region-greedy visit (not_mappable), TspN sampling (not_mappable)
Works:
1. doi=10.1137/s0097539702416402 year=2004 title=Local Search Heuristics for
                    <i>k</i>
                    -Median and Facility Location Problems
   authors=Vijay Arya, Naveen Garg, Rohit Khandekar, Adam Meyerson, Kamesh Munagala, Vinayaka Pandit
   venue=SIAM Journal on Computing cited_by=348
   abstract=We analyze local search heuristics for the metric k-median and facility location problems. We define the locality gap of a local search procedure for a minimization problem as the maximum ratio of a locally optimum solution (obtained using this procedure) to the global optimum. For k-median, we show that local search with swaps has a locality gap of 5. Furthermore, if we permi…
2. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
3. doi=10.4028/www.scientific.net/amr.694-697.2787 year=2013 title=The Genetic Algorithm with Two Heuristic Rules for TSP
   authors=Yong Wang
   venue=Advanced Materials Research cited_by=0
   abstract=Many complex discrete manufacturing problems, such as manufacturing sequencing problem or machine scheduling problem etc, can be converted into a general traveling salesman problem (TSP). TSP has been proven to be NP-complete. The genetic algorithm is improved with two heuristic rules for TSP. The first heuristic rule is the four vertices and three lines inequality. It is appl…

=== tsp_open ===
family: tsp
label: Open TSP / Hamiltonian path
definition: Path visits each city once, no return.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Path Nearest Neighbor (next_node_score), Cheapest Insertion path (not_mappable)
Works:
1. doi=10.1137/0206041 year=1977 title=An Analysis of Several Heuristics for the Traveling Salesman Problem
   authors=Daniel J. Rosenkrantz, Richard E. Stearns, Philip M. Lewis, II
   venue=SIAM Journal on Computing cited_by=736
   abstract=Several polynomial time algorithms finding “good,” but not necessarily optimal, tours for the traveling salesman problem are considered. We measure the closeness of a tour by the ratio of the obtained tour length to the minimal tour length. For the nearest neighbor method, we show the ratio is bounded above by a logarithmic function of the number of nodes. We also provide a lo…
2. doi=10.21070/icecrs.v12i3.1935 year=2024 title=Nearest Neighbor Heuristic Minimizes Logistics Distribution Distance And Travel Time
   authors=Naufal Akmal Christiono, Dewi Komala Sari
   venue=Proceedings of The ICECRS cited_by=0
   abstract=General Background Supply chain systems require strategic management to distribute production outputs continuously and accurately to consumers. Specific Background PT. Laprint Jaya experiences fluctuating shipping volumes and limited delivery fleets, causing complex Single Depot Capacitated Vehicle Routing Problems during dense daily schedules. Knowledge Gap Traditional routin…
3. doi=10.1101/2022.09.08.507181 year=2022 title=<tt>DrTransformer</tt>
                  : Heuristic cotranscriptional RNA folding using the nearest neighbor energy model
   authors=Stefan Badelt, Ronny Lorenz, Ivo L. Hofacker
   venue=None cited_by=0
   abstract=Abstract Background Folding during transcription can have an important influence on the structure and function of ℝNA molecules, as regions closer to the 5’ end can fold into metastable structures before potentially stronger interactions with the 3’ end become available. Thermodynamic ℝNA folding models are not suitable to analyze this problem, as they can only calculate prope…

=== tsp_orienteering ===
family: tsp
label: Orienteering / selective TSP
definition: Max prize under a length budget.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Prize/distance greedy (not_mappable), S-algorithm orienteering (not_mappable)
Works:
1. doi=10.1002/net.3230180306 year=1988 title=Stochastic shortest paths with recourse
   authors=Giovanni Andreatta, Luciano Romeo
   venue=Networks cited_by=61
   abstract=Abstract This paper considers Stochastic Shortest Path (SSP) problems in probabilistic networks. A variety of approaches have already been proposed in the literature. However, unlike in the deterministic case, they are related to distinct models, interpretations and applications. We have chosen to look at the case where detours from the original path must be taken whenever the…
2. doi=10.1051/ro/2020058 year=2021 title=Formulation and a heuristic approach for the orienteering location-routing problem
   authors=Ali Nadizadeh
   venue=RAIRO - Operations Research cited_by=9
   abstract=In this paper, a new version of the location-routing problem (LRP), named orienteering location-routing problem (OLRP) is investigated. The problem is composed of two-well known problems: team orienteering problem (TOP) and LRP. There are some challenging practical applications in logistics, tourism, military operations, and other fields, which can be modeled by OLRP. The prob…
3. doi=10.1017/s0269888919000134 year=2019 title=A multi-objective evolutionary hyper-heuristic algorithm for team-orienteering problem with time windows regarding rescue applications
   authors=Hadi S. Aghdasi, Saeed Saeedvand, Jacky Baltes
   venue=The Knowledge Engineering Review cited_by=6
   abstract=Abstract The team-orienteering problem (TOP) has broad applicability. Examples of possible uses are in factory and automation settings, robot sports teams, and urban search and rescue applications. We chose the rescue domain as a guiding example throughout this paper. Hence, this paper explores a practical variant of TOP with time window (TOPTW) for rescue applications by huma…

=== tsp_prize ===
family: tsp
label: Prize-collecting TSP
definition: Optional cities with prizes and penalties.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Prize insertion (not_mappable), Goemans-Williamson PCTSP (not_mappable)
Works:
1. doi=10.1002/net.3230190602 year=1989 title=The prize collecting traveling salesman problem
   authors=Egon Balas
   venue=Networks cited_by=403
   abstract=Abstract The following is a valid model for an important class of scheduling and routing problems. A salesman who travels between pairs of cities at a cost depending only on the pair, gets a prize in every city that he vitis and pays a penalty to every city that he fails to visit, wishes to minimize his travel costs and net penalties, while visiting enough cities to collect a…
2. doi=10.1137/090771429 year=2011 title=Improved Approximation Algorithms for Prize-Collecting Steiner Tree and TSP
   authors=Aaron Archer, MohammadHossein Bateni, MohammadTaghi Hajiaghayi, Howard Karloff
   venue=SIAM Journal on Computing cited_by=73
   abstract=We study the prize-collecting Steiner tree (PCST), prize-collecting traveling salesman (PCTSP), and prize-collecting path (PC-Path) problems. Given a graph $(V,E)$ with a cost on each edge and a penalty (a.k.a. prize) on each node, the goal is to find a tree (for PCST), cycle (for PCTSP), or path (for PC-Path) that minimizes the sum of the edge costs in the tree/cycle/path and…
3. doi=10.1145/3378571 year=2020 title=A Unified PTAS for Prize Collecting TSP and Steiner Tree Problem in Doubling Metrics
   authors=T.-H. Hubert Chan, Haotian Jiang, Shaofeng H.-C. Jiang
   venue=ACM Transactions on Algorithms cited_by=6
   abstract=We present a unified (randomized) polynomial-time approximation scheme (PTAS) for the prize collecting traveling salesman problem (PCTSP) and the prize collecting Steiner tree problem (PCSTP) in doubling metrics. Given a metric space and a penalty function on a subset of points known as terminals, a solution is a subgraph on points in the metric space whose cost is the weight…

=== tsp_purchaser ===
family: tsp
label: Traveling purchaser
definition: Buy items from markets.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: TPP savings (not_mappable), Market insertion (not_mappable)
Works:
1. doi=10.1002/net.3230110308 year=1981 title=Capacitated arc routing problems
   authors=Bruce L. Golden, Richard T. Wong
   venue=Networks cited_by=454
   abstract=Abstract A capacitated node routing problem, known as the vehicle routing or dispatch problem, has been the focus of much research attention. On the other hand, capacitated arc routing problems have been comparatively neglected. Both classes of problems are extremely rich in theory and applications. Our intent in this paper is to define a capacitated arc routing problem, to pr…
2. doi=10.1287/trsc.2015.0627 year=2016 title=The Stochastic and Dynamic Traveling Purchaser Problem
   authors=E. Angelelli, R. Mansini, M. Vindigni
   venue=Transportation Science cited_by=24
   abstract=In this paper, we analyze a dynamic and stochastic variant of the traveling purchaser problem where quantity available for each product in each market decreases over time according to a stochastic process. The multiobjective nature of the problem is faced through a hierarchical evaluation of the different objectives. We introduce three variants of a heuristic approach using re…
3. doi=10.3390/su141610190 year=2022 title=The Multi-Depot Traveling Purchaser Problem with Shared Resources
   authors=Zahra Sadat Hasanpour Jesri, Kourosh Eshghi, Majid Rafiee, Tom Van Woensel
   venue=Sustainability cited_by=11
   abstract=Using shared resources has created better opportunities in the field of sustainable logistics and procurement. The Multi-Depot Traveling Purchaser Problem under Shared Resources (MDTPPSR) is a new variant of the Traveling Purchaser Problem (TPP) in sustainable inbound logistics. In this problem, each depot can purchase its products using the shared resources of other depots, a…

=== tsp_stochastic ===
family: tsp
label: Stochastic TSP
definition: Random distances or presence.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Expected-cost NN (not_mappable), Recourse 2-opt (not_mappable)
Works:
1. doi=10.1287/opre.38.6.1019 year=1990 title=A Priori Optimization
   authors=Dimitris J. Bertsimas, Patrick Jaillet, Amedeo R. Odoni
   venue=Operations Research cited_by=181
   abstract=Consider a complete graph G = (V, E) in which each node is present with probability p. We are interested in solving combinatorial optimization problems on subsets of nodes which are present with a certain probability. We introduce the idea of a priori optimization as a strategy competitive to the strategy of reoptimization, under which the combinatorial optimization problem is…
2. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
3. doi=10.4028/www.scientific.net/amr.694-697.2787 year=2013 title=The Genetic Algorithm with Two Heuristic Rules for TSP
   authors=Yong Wang
   venue=Advanced Materials Research cited_by=0
   abstract=Many complex discrete manufacturing problems, such as manufacturing sequencing problem or machine scheduling problem etc, can be converted into a general traveling salesman problem (TSP). TSP has been proven to be NP-complete. The genetic algorithm is improved with two heuristic rules for TSP. The first heuristic rule is the four vertices and three lines inequality. It is appl…

=== tsp_time_dependent ===
family: tsp
label: Time-dependent TSP
definition: Travel time depends on departure.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Time-dependent NN (not_mappable), TD 2-opt (not_mappable)
Works:
1. doi=10.1287/trsc.26.3.185 year=1992 title=Time Dependent Vehicle Routing Problems: Formulations, Properties and Heuristic Algorithms
   authors=Chryssi Malandraki, Mark S. Daskin
   venue=Transportation Science cited_by=453
   abstract=The time dependent vehicle routing problem (TDVRP) is defined as follows. A vehicle fleet of fixed capacities serves customers of fixed demands from a central depot. Customers are assigned to vehicles and the vehicles routed so that the total time of the routes is minimized. The travel time between two customers or between a customer and the depot depends on the distance betwe…
2. doi=10.3390/a14010021 year=2021 title=Dynamic Shortest Paths Methods for the Time-Dependent TSP
   authors=Christoph Hansknecht, Imke Joormann, Sebastian Stiller
   venue=Algorithms cited_by=13
   abstract=The time-dependent traveling salesman problem (TDTSP) asks for a shortest Hamiltonian tour in a directed graph where (asymmetric) arc-costs depend on the time the arc is entered. With traffic data abundantly available, methods to optimize routes with respect to time-dependent travel times are widely desired. This holds in particular for the traveling salesman problem, which is…
3. doi=10.4028/www.scientific.net/amr.339.332 year=2011 title=Comparison of Heuristic for Flow Shop Scheduling Problems with Sequence Dependent Setup Time
   authors=Parinya Kaweegitbundit
   venue=Advanced Materials Research cited_by=5
   abstract=This paper considers flow shop scheduling problems with sequence dependent setup time. The makespan criterion has been considered. In this paper presented a comparison of three heuristics for solves this problem. The memetic algorithm, genetic algorithm and NEH heuristic have been compared. In the experimental, the result from memetic algorithm is maximum the best solution. Th…
