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
1. doi=10.2139/ssrn.4167190 year=2022 title=Drone-Assisted Last-Mile Delivery Problem by Covering Salesman Problem with Nodes and Segments
   authors=Hosang Song, Abdullahi  M. Jingi, Xinan Yang
   venue=None cited_by=1
   abstract=Drones attract increasing attention in the last decades as a means for last mile delivery; they are mainly considered as supplement delivery tools that work jointly with trucks. In this paper, we develop a Covering Salesman Problem with Nodes and Segments Using Drones (CSPNS-D) and formulate three Mixed Integer Linear Programming (MILP) models that minimize delivery time in a…
2. doi=10.2139/ssrn.7133062 year=2026 title=Two Variants of the Covering Salesman Problem with Nodes and Segments for Solving the Close-Enough Traveling Salesman Problem
   authors=Hosang Song, Güneş Erdoğan, Gilbert Laporte, Maria Battarra, Alistair Brandon-Jones
   venue=None cited_by=0
   abstract=This paper introduces two variants of the Covering Salesman Problem with Nodes and Segments (CSPNS), which aims to find a minimum-length tour that visits a subset of nodes, while ensuring that every customer is covered within distance from visited nodes or traversed edges: the Geometric CSPNS (Geo-CSPNS) and the Generalized CSPNS (Gen- CSPNS). The Geo-CSPNS models the CSPNS on…
3. doi=10.70675/09043c22zfaa5z4e3bz868bz8ac1958d96f3 year=None title=Exact and anytime heuristic search for the Time Dependent Traveling Salesman Problem with Time Windows
   authors=Romain Fontaine
   venue=None cited_by=0
   abstract=Recherche heuristique exacte et anytime pour résoudre le Voyageur de commerce dépendant du temps avec fenêtres temporelles Le problème du voyageur de commerce (TSP, pour Traveling Salesman Problem) dépendant du temps (TD, pour Time Dependent) est une généralisation du TSP qui permet de prendre en compte les conditions de trafic lors de la planification de tournées en milieu ur…

=== tsp_drone ===
family: tsp
label: TSP with drone
definition: Truck plus UAV.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Truck-drone NN (not_mappable), Drone launch local search (not_mappable)
Works:
1. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
2. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…
3. doi=10.2139/ssrn.6528923 year=2026 title=Complexity analysis of the Line-TSP with Drone Transports
   authors=Anna  Katharina Janiszczak, Stefan Bock
   venue=None cited_by=0
   abstract=Since last-mile distribution processes in urban areas are rapidly expanding, several novel delivery concepts have been proposed in recent years to improve their efficiency. Among these innovative concepts, the integration of unmanned aerial vehicles (drones) plays a prominent role, as they can enable simultaneous deliveries. However, due to limited experience and complexity av…

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

=== tsp_gtsp ===
family: tsp
label: Generalized TSP
definition: Visit exactly one city per cluster.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: NN among clusters (not_mappable), GI3 local search (not_mappable)
Works:
1. doi=10.1287/opre.46.3.330 year=1998 title=A Generalized Insertion Heuristic for the Traveling Salesman Problem with Time Windows
   authors=Michel Gendreau, Alain Hertz, Gilbert Laporte, Mihnea Stan
   venue=Operations Research cited_by=161
   abstract=This article describes a generalized insertion heuristic for the Traveling Salesman Problem with Time Windows in which the objective is the minimization of travel times. The algorithm gradually builds a route by inserting at each step a vertex in its neighbourhood on the current route, and performing a local reoptimization. This is done while checking the feasibility of the re…
2. doi=10.1002/net.20421 year=2010 title=A multistart heuristic for the equality generalized traveling salesman problem
   authors=Valentina Cacchiani, Albert Einstein Fernandes Muritiba, Marcos Negreiros, Paolo Toth
   venue=Networks cited_by=13
   abstract=Abstract We study the equality generalized traveling salesman problem (E‐GTSP), which is a variant of the well‐known traveling salesman problem. We are given an undirected graph G = ( V,E ), with set of vertices V and set of edges E , each with an associated cost. The set of vertices is partitioned into clusters. E‐GTSP is to find an elementary cycle visiting exactly one verte…
3. doi=10.1142/s1793005726500432 year=2025 title=A Novel Heuristic for the Generalized Traveling Salesman Problems with Imprecise Cost Matrices
   authors=Prasanta Dutta, Indadul Khan, Krishnendu Basuli, Manas Kumar Maiti
   venue=New Mathematics and Natural Computation cited_by=2
   abstract=A meta-heuristic approach with multiple perturbation rules is proposed to solve the generalized traveling salesman problems in different environments. The proposed approach consists of two phases. The first phase is devoted for the sequencing of the groups and in the second phase one node is selected from each group to minimize the tour cost. In the first stage a group sequenc…

=== tsp_minmax ===
family: tsp
label: Min-max mTSP
definition: Minimise the longest salesman tour.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Balanced NN (not_mappable), Min-max 2-opt (not_mappable)
Works:
1. doi=10.3390/drones7070407 year=2023 title=Development of Heuristic Approaches for Last-Mile Delivery TSP with a Truck and Multiple Drones
   authors=Marco Rinaldi, Stefano Primatesta, Martin Bugaj, Ján Rostáš, Giorgio Guglieri
   venue=Drones cited_by=34
   abstract=Unmanned Aerial Vehicles (UAVs) are gaining momentum in many civil and military sectors. An example is represented by the logistics sector, where UAVs have been proven to be able to improve the efficiency of the process itself, as their cooperation with trucks can decrease the delivery time and reduce fuel consumption. In this paper, we first state a mathematical formulation o…
2. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
3. doi=10.4028/www.scientific.net/amr.694-697.2787 year=2013 title=The Genetic Algorithm with Two Heuristic Rules for TSP
   authors=Yong Wang
   venue=Advanced Materials Research cited_by=0
   abstract=Many complex discrete manufacturing problems, such as manufacturing sequencing problem or machine scheduling problem etc, can be converted into a general traveling salesman problem (TSP). TSP has been proven to be NP-complete. The genetic algorithm is improved with two heuristic rules for TSP. The first heuristic rule is the four vertices and three lines inequality. It is appl…

=== tsp_mtsp ===
family: tsp
label: Multiple TSP
definition: Several salesmen from a depot.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: mTSP NN assignment (not_mappable), mTSP 2-opt (not_mappable)
Works:
1. doi=10.14743/apem2021.2.392 year=2021 title=Improved Genetic Algorithm (VNS-GA) using polar coordinate classification for workload balanced multiple Traveling Salesman Problem (mTSP)
   authors=Y.D. Wang, X.C. Lu, J.R. Shen
   venue=Advances in Production Engineering &amp; Management cited_by=10
   abstract=The multiple traveling salesman problem (mTSP) is an extension of the traveling salesman problem (TSP), which has wider applications in real life than the traveling salesman problem such as transportation and delivery, task allocation, etc. In this paper, an improved genetic algorithm (VNS-GA) that uses polar coordinate classification to generate the initial solutions is propo…
2. doi=10.17977/um055v1i12020p10-17 year=2020 title=TWO PHASE HEURISTIC ALGORITHM (TPHA) PADA MULTIPLE TRAVELLING SALESMAN PROBLEM (MTSP) DAN IMPLEMENTASI PROGRAMNYA
   authors=Rahma Try Iriani, Sapti Wahyuningsih, Darmawan Satyananda
   venue=Jurnal Kajian Matematika dan Aplikasinya (JKMA) cited_by=0
   abstract=Multiple Traveling Salesman Problem (MTSP) is one variant of Traveling Salesman Problem (TSP) which involves several salesmen in making a trip to visit several customers. In this article, the Two-Phase Heuristic Algorithm (TPHA) is used to solve MTSP problems. The algorithm classifies customers into several regions using the K-Means algorithm, which will then find a route solu…
3. doi=10.70675/09043c22zfaa5z4e3bz868bz8ac1958d96f3 year=None title=Exact and anytime heuristic search for the Time Dependent Traveling Salesman Problem with Time Windows
   authors=Romain Fontaine
   venue=None cited_by=0
   abstract=Recherche heuristique exacte et anytime pour résoudre le Voyageur de commerce dépendant du temps avec fenêtres temporelles Le problème du voyageur de commerce (TSP, pour Traveling Salesman Problem) dépendant du temps (TD, pour Time Dependent) est une généralisation du TSP qui permet de prendre en compte les conditions de trafic lors de la planification de tournées en milieu ur…

=== tsp_multiobjective ===
family: tsp
label: Multi-objective TSP
definition: Several cost functions.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Weighted-sum NN (not_mappable), Pareto 2-opt (not_mappable)
Works:
1. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
2. doi=10.5539/jmr.v8n3p1 year=2016 title=Heuristic Algorithms for Solving Multiobjective Transportation Problems
   authors=Ali Musaddak Delphi
   venue=Journal of Mathematics Research cited_by=2
   abstract=&lt;p&gt;In this paper, we proposed three heuristic algorithms to solve multiobjective transportation problems, the first heuristic algorithm used to minimize two objective functions (total flow time and total late work), the second one used to minimize two objective functions (total flow time and total tardiness) and the last one used to minimize three objective functions (to…
3. doi=10.18178/ijmlc.2021.11.2.1032 year=2021 title=Multiobjective Heuristic Scheduling of Automated Manufacturing Systems Based on Petri Nets
   authors=Chong Yu, Bo Huang, Jiangen Hao
   venue=International Journal of Machine Learning and Computing cited_by=1
   abstract=In practice, automated manufacturing systems usually have multiple, incommensurate, and conflicting objectives to achieve. To deal with them, this paper proposes an extend Petri nets for the multiobjective scheduling of AMSs. In addition, a multiobjective heuristic A* search within reachability graphs of extended Petri nets is also proposed to schedule these nets. The method c…

=== tsp_neighborhoods ===
family: tsp
label: TSP with neighborhoods
definition: Visit a region not a point.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Region-greedy visit (not_mappable), TspN sampling (not_mappable)
Works:
1. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
2. doi=10.4028/www.scientific.net/amr.694-697.2787 year=2013 title=The Genetic Algorithm with Two Heuristic Rules for TSP
   authors=Yong Wang
   venue=Advanced Materials Research cited_by=0
   abstract=Many complex discrete manufacturing problems, such as manufacturing sequencing problem or machine scheduling problem etc, can be converted into a general traveling salesman problem (TSP). TSP has been proven to be NP-complete. The genetic algorithm is improved with two heuristic rules for TSP. The first heuristic rule is the four vertices and three lines inequality. It is appl…
3. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…

=== tsp_noisy ===
family: tsp
label: Noisy / black-box distances
definition: Distance oracle is noisy.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Robust NN (not_mappable), Repeated 2-opt (not_mappable)
Works:
1. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
2. doi=10.4028/www.scientific.net/amr.694-697.2787 year=2013 title=The Genetic Algorithm with Two Heuristic Rules for TSP
   authors=Yong Wang
   venue=Advanced Materials Research cited_by=0
   abstract=Many complex discrete manufacturing problems, such as manufacturing sequencing problem or machine scheduling problem etc, can be converted into a general traveling salesman problem (TSP). TSP has been proven to be NP-complete. The genetic algorithm is improved with two heuristic rules for TSP. The first heuristic rule is the four vertices and three lines inequality. It is appl…
3. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…

=== tsp_orienteering ===
family: tsp
label: Orienteering / selective TSP
definition: Max prize under a length budget.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Prize/distance greedy (not_mappable), S-algorithm orienteering (not_mappable)
Works:
1. doi=10.1051/ro/2020058 year=2021 title=Formulation and a heuristic approach for the orienteering location-routing problem
   authors=Ali Nadizadeh
   venue=RAIRO - Operations Research cited_by=9
   abstract=In this paper, a new version of the location-routing problem (LRP), named orienteering location-routing problem (OLRP) is investigated. The problem is composed of two-well known problems: team orienteering problem (TOP) and LRP. There are some challenging practical applications in logistics, tourism, military operations, and other fields, which can be modeled by OLRP. The prob…
2. doi=10.1017/s0269888919000134 year=2019 title=A multi-objective evolutionary hyper-heuristic algorithm for team-orienteering problem with time windows regarding rescue applications
   authors=Hadi S. Aghdasi, Saeed Saeedvand, Jacky Baltes
   venue=The Knowledge Engineering Review cited_by=6
   abstract=Abstract The team-orienteering problem (TOP) has broad applicability. Examples of possible uses are in factory and automation settings, robot sports teams, and urban search and rescue applications. We chose the rescue domain as a guiding example throughout this paper. Hence, this paper explores a practical variant of TOP with time window (TOPTW) for rescue applications by huma…
3. doi=10.1609/socs.v17i1.31537 year=2024 title=Heuristic Search for the Orienteering Problem with Time-Varying Reward
   authors=Chao Cao, Jinyun Xu, Ji Zhang, Howie Choset, Zhongqiang Ren
   venue=Proceedings of the International Symposium on Combinatorial Search cited_by=5
   abstract=The Orienteering Problem (OP) seeks a path on a graph to maximize total rewards collected subject to a path length budget. Typically, a reward is achieved by visiting a vertex in the graph, and such a reward is constant for all time. This paper considers a variant of OP where the reward of each vertex is an arbitrary time-dependent function, and hence the name time-varying rew…

=== tsp_pdp ===
family: tsp
label: TSP with pickups and deliveries
definition: Paired pickup-delivery.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Paired insertion (not_mappable), PDP local search (not_mappable)
Works:
1. doi=10.1287/trsc.1050.0135 year=2006 title=An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows
   authors=Stefan Ropke, David Pisinger
   venue=Transportation Science cited_by=2281
   abstract=The pickup and delivery problem with time windows is the problem of serving a number of transportation requests using a limited amount of vehicles. Each request involves moving a number of goods from a pickup location to a delivery location. Our task is to construct routes that visit all locations such that corresponding pickups and deliveries are placed on the same route, and…
2. doi=10.3390/drones7070407 year=2023 title=Development of Heuristic Approaches for Last-Mile Delivery TSP with a Truck and Multiple Drones
   authors=Marco Rinaldi, Stefano Primatesta, Martin Bugaj, Ján Rostáš, Giorgio Guglieri
   venue=Drones cited_by=34
   abstract=Unmanned Aerial Vehicles (UAVs) are gaining momentum in many civil and military sectors. An example is represented by the logistics sector, where UAVs have been proven to be able to improve the efficiency of the process itself, as their cooperation with trucks can decrease the delivery time and reduce fuel consumption. In this paper, we first state a mathematical formulation o…
3. doi=10.1287/trsc.29.1.45 year=1995 title=A Network Flow Based Heuristic for Bulk Pickup and Delivery Routing
   authors=Marshall L. Fisher, Baoxing Tang, Zhang Zheng
   venue=Transportation Science cited_by=10
   abstract=We consider a problem in which a fleet of vehicles must be scheduled to pickup and deliver a set of orders in truckload quantities. We describe a new algorithm based on a network flow relaxation which imposes necessary conditions on the flow of empty vehicles from order delivery points to order pickup points. The network flow model provides a lower bound and a nearly feasible…

=== tsp_prize ===
family: tsp
label: Prize-collecting TSP
definition: Optional cities with prizes and penalties.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Prize insertion (not_mappable), Goemans-Williamson PCTSP (not_mappable)
Works:
1. doi=10.1137/090771429 year=2011 title=Improved Approximation Algorithms for Prize-Collecting Steiner Tree and TSP
   authors=Aaron Archer, MohammadHossein Bateni, MohammadTaghi Hajiaghayi, Howard Karloff
   venue=SIAM Journal on Computing cited_by=73
   abstract=We study the prize-collecting Steiner tree (PCST), prize-collecting traveling salesman (PCTSP), and prize-collecting path (PC-Path) problems. Given a graph $(V,E)$ with a cost on each edge and a penalty (a.k.a. prize) on each node, the goal is to find a tree (for PCST), cycle (for PCTSP), or path (for PC-Path) that minimizes the sum of the edge costs in the tree/cycle/path and…
2. doi=10.1145/3378571 year=2020 title=A Unified PTAS for Prize Collecting TSP and Steiner Tree Problem in Doubling Metrics
   authors=T.-H. Hubert Chan, Haotian Jiang, Shaofeng H.-C. Jiang
   venue=ACM Transactions on Algorithms cited_by=6
   abstract=We present a unified (randomized) polynomial-time approximation scheme (PTAS) for the prize collecting traveling salesman problem (PCTSP) and the prize collecting Steiner tree problem (PCSTP) in doubling metrics. Given a metric space and a penalty function on a subset of points known as terminals, a solution is a subgraph on points in the metric space whose cost is the weight…
3. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…

=== tsp_purchaser ===
family: tsp
label: Traveling purchaser
definition: Buy items from markets.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: TPP savings (not_mappable), Market insertion (not_mappable)
Works:
1. doi=10.1287/trsc.2015.0627 year=2016 title=The Stochastic and Dynamic Traveling Purchaser Problem
   authors=E. Angelelli, R. Mansini, M. Vindigni
   venue=Transportation Science cited_by=24
   abstract=In this paper, we analyze a dynamic and stochastic variant of the traveling purchaser problem where quantity available for each product in each market decreases over time according to a stochastic process. The multiobjective nature of the problem is faced through a hierarchical evaluation of the different objectives. We introduce three variants of a heuristic approach using re…
2. doi=10.3390/su141610190 year=2022 title=The Multi-Depot Traveling Purchaser Problem with Shared Resources
   authors=Zahra Sadat Hasanpour Jesri, Kourosh Eshghi, Majid Rafiee, Tom Van Woensel
   venue=Sustainability cited_by=11
   abstract=Using shared resources has created better opportunities in the field of sustainable logistics and procurement. The Multi-Depot Traveling Purchaser Problem under Shared Resources (MDTPPSR) is a new variant of the Traveling Purchaser Problem (TPP) in sustainable inbound logistics. In this problem, each depot can purchase its products using the shared resources of other depots, a…
3. doi=10.2139/ssrn.4773935 year=2024 title=Preprocessing Algorithms for the Traveling Purchaser Problem
   authors=Finn Meissner
   venue=None cited_by=0
   abstract=A frequently investigated generalization of the Traveling Salesman Problem is the Traveling Purchaser Problem (TPP). Due to the development of technologies and algorithms, increasingly complex variations of the problem can be solved while computation times shorten. Yet additional room for improvement is offered before applying the algorithms. Due to the structure of the TPP, a…

=== tsp_sop ===
family: tsp
label: Sequential ordering / precedences
definition: Precedence constraints on visit order.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Precedence insertion (not_mappable), Asymmetric SOP local search (not_mappable)
Works:
1. doi=10.5784/22-1-36 year=2006 title=A sequential insertion heuristic for the initial solution to a constrained vehicle routing problem
   authors=JW Joubert, SJ Claasen
   venue=ORiON cited_by=9
   abstract=The Vehicle Routing Problem (VRP) is a well-researched problem in the Operations Research literature. It is the view of the authors of this paper that the various VRP variants have been researched in isolation. This paper embodies an attempt to integrate three specific variants of the VRP, namely the VRP with multiple time windows, the VRP with a heterogeneous fleet, and the V…
2. doi=10.2139/ssrn.4071356 year=2022 title=A Parallel Branch-and-Bound Algorithm with History-Based Domination and its Application to the Sequential Ordering Problem
   authors=Taspon Gonggiatgul, Ghassan Shobaki, Pinar Muyan-Ozcelik
   venue=None cited_by=0
   abstract=In this paper, we describe the first parallel Branch-and-Bound (B&amp;B) algorithm with a history-based domination technique. Although history-based domination substantially speeds up a B&amp;B search, it makes parallelization much more challenging. Our algorithm is also the first parallel B&amp;B algorithm for the Sequential Ordering Problem. To effectively explore the soluti…
3. doi=10.2139/ssrn.6618026 year=2026 title=Automated Reinforcement Learning with Bayesian Hyperparameter Optimization and Invalid Action Masking for the Sequential Ordering Problem
   authors=Kerollan Ramos, André  Luiz Ottoni, Thomas  Vargas Barsante Pinto, Allan  Erlikhman Medeiros Santos
   venue=None cited_by=0
   abstract=The Sequential Ordering Problem (SOP) presents a significant challenge in Combinatorial Optimization (CO) due to its strict precedence constraints, rendering exact methods computationally prohibitive for large-scale instances. While Reinforcement Learning (RL) offers a promising alternative, its effectiveness is often hindered by the difficulty of tuning interacting hyperparam…

=== tsp_stochastic ===
family: tsp
label: Stochastic TSP
definition: Random distances or presence.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Expected-cost NN (not_mappable), Recourse 2-opt (not_mappable)
Works:
1. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
2. doi=10.4028/www.scientific.net/amr.694-697.2787 year=2013 title=The Genetic Algorithm with Two Heuristic Rules for TSP
   authors=Yong Wang
   venue=Advanced Materials Research cited_by=0
   abstract=Many complex discrete manufacturing problems, such as manufacturing sequencing problem or machine scheduling problem etc, can be converted into a general traveling salesman problem (TSP). TSP has been proven to be NP-complete. The genetic algorithm is improved with two heuristic rules for TSP. The first heuristic rule is the four vertices and three lines inequality. It is appl…
3. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…

=== tsp_time_dependent ===
family: tsp
label: Time-dependent TSP
definition: Travel time depends on departure.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Time-dependent NN (not_mappable), TD 2-opt (not_mappable)
Works:
1. doi=10.3390/a14010021 year=2021 title=Dynamic Shortest Paths Methods for the Time-Dependent TSP
   authors=Christoph Hansknecht, Imke Joormann, Sebastian Stiller
   venue=Algorithms cited_by=13
   abstract=The time-dependent traveling salesman problem (TDTSP) asks for a shortest Hamiltonian tour in a directed graph where (asymmetric) arc-costs depend on the time the arc is entered. With traffic data abundantly available, methods to optimize routes with respect to time-dependent travel times are widely desired. This holds in particular for the traveling salesman problem, which is…
2. doi=10.4028/www.scientific.net/amr.339.332 year=2011 title=Comparison of Heuristic for Flow Shop Scheduling Problems with Sequence Dependent Setup Time
   authors=Parinya Kaweegitbundit
   venue=Advanced Materials Research cited_by=5
   abstract=This paper considers flow shop scheduling problems with sequence dependent setup time. The makespan criterion has been considered. In this paper presented a comparison of three heuristics for solves this problem. The memetic algorithm, genetic algorithm and NEH heuristic have been compared. In the experimental, the result from memetic algorithm is maximum the best solution. Th…
3. doi=10.1101/2020.04.02.20050153 year=2020 title=CoViD–19: Meta-heuristic optimization based forecast method on time dependent bootstrapped data
   authors=Livio Fenga, Carlo Del Castello
   venue=None cited_by=4
   abstract=Abstract A compounded method – exploiting the searching capabilities of an operation research algorithm and the power of bootstrap techniques – is presented. The resulting algorithm has been successfully tested to predict the turning point reached by the epidemic curve followed by the CoViD–19 virus in Italy. Futures lines of research, which include the generalization of the m…
