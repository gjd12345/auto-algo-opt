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

family: cvrp

=== cvrp_2e ===
family: cvrp
label: Two-echelon VRP
definition: Satellites between depot and customers.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Satellite assignment + CWS (not_mappable), 2E-VRP local search (not_mappable)
Works:
1. doi=10.1287/trsc.1060.0160 year=2007 title=An Efficient Heuristic Algorithm for a Two-Echelon Joint Inventory and Routing Problem
   authors=Jaeheon Jung, Kamlesh Mathur
   venue=Transportation Science cited_by=29
   abstract=With an increasing emphasis on coordination in the supply chain, the inventory and distribution decisions, which in most part had been dealt with independently of each other, need to be considered jointly. This research considers a two-echelon distribution system consisting of one warehouse and N retailers that face external demand at a constant rate. Inventories are kept at r…
2. doi=10.3934/jimo.2021225 year=2023 title=An adaptive large neighborhood search heuristic for multi-commodity two-echelon vehicle routing problem with satellite synchronization
   authors=Shengyang Jia, Lei Deng, Quanwu Zhao, Yunkai Chen
   venue=Journal of Industrial and Management Optimization cited_by=29
   abstract=&lt;p style='text-indent:20px;'&gt;In considering route optimization from multiple distribution centers called depots via some intermediate facilities called satellites to final customers with multiple commodities request, we introduce the Multi-Commodity Two-Echelon Vehicle Routing Problem with Satellite Synchronization (MC-2E-VRPSS). The MC-2E-VRPSS involves the transportati…
3. doi=10.1002/net.20428 year=2011 title=Uncertainty feature optimization: An implicit paradigm for problems with noisy data
   authors=Niklaus Eggenberg, Matteo Salani, Michel Bierlaire
   venue=Networks cited_by=7
   abstract=Abstract Optimization problems with noisy data solved using stochastic programming or robust optimization approaches require the explicit characterization of an uncertainty set U that models the nature of the noise. Such approaches depend on the modeling of the uncertainty set and suffer from an erroneous estimation of the noise. In this article, we introduce a framework that…

=== cvrp_clustered ===
family: cvrp
label: Clustered VRP
definition: Customers in clusters.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Cluster-first NN (next_node_score), Sweep-like angular NN (next_node_score)
Works:
1. doi=10.1287/opre.12.4.568 year=1964 title=Scheduling of Vehicles from a Central Depot to a Number of Delivery Points
   authors=G. Clarke, J. W. Wright
   venue=Operations Research cited_by=2836
   abstract=The optimum routing of a fleet of trucks of varying capacities from a central depot to a number of delivery points may require a selection from a very large number of possible routes, if the number of delivery points is also large. This paper, after considering certain theoretical aspects of the problem, develops an iterative procedure that enables the rapid selection of an op…
2. doi=10.1287/opre.22.2.340 year=1974 title=A Heuristic Algorithm for the Vehicle-Dispatch Problem
   authors=Billy E. Gillett, Leland R. Miller
   venue=Operations Research cited_by=796
   abstract=This paper introduces and illustrates an efficient algorithm, called the sweep algorithm, for solving medium- as well as large-scale vehicle-dispatch problems with load and distance constraints for each vehicle. The locations that are used to make up each route are determined according to the polar-coordinate angle for each location. An iterative procedure is then used to impr…
3. doi=10.61194/sijl.v2i1.187 year=2024 title=Capacitated Vehicle Routing Problem (CVRP) with Sweep and Nearest Neighbor Algorithm
   authors=Erly Ekayanti, Sugianto, Imaduddin Bachtiar Efendi
   venue=Sinergi International Journal of Logistics cited_by=5
   abstract=The Capacitated Vehicle Routing Problem (CVRP) presents significant challenges in shipping route optimization and logistics management. These challenges include balancing vehicle capacity, minimizing travel distance, and efficiently grouping delivery points, all of which are crucial for enhancing operational efficiency and reducing costs. This research aims to apply a combinat…

=== cvrp_large ===
family: cvrp
label: Large-scale CVRP
definition: Hundreds of customers.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Restricted NN (next_node_score), Ruin-and-recreate (not_mappable)
Works:
1. doi=10.1287/ijoc.15.4.333.24890 year=2003 title=The Granular Tabu Search and Its Application to the Vehicle-Routing Problem
   authors=Paolo Toth, Daniele Vigo
   venue=INFORMS Journal on Computing cited_by=388
   abstract=We describe a new variant, called granular tabu search, of the well-known tabu-search approach. The method uses an effective intensification/diversification tool that can be successfully applied to a wide class of graph-theoretic and combinatorial-optimization problems. Granular tabu search is based on the use of drastically restricted neighborhoods, not containing the moves t…
2. doi=10.1088/1757-899x/852/1/012090 year=2020 title=Comparison study between nearest neighbor and farthest insert algorithms for solving VRP model using heuristic method approach
   authors=Wilson Kosasih, Ahmad, Lithrone Laricha Salomon, Febricky
   venue=IOP Conference Series: Materials Science and Engineering cited_by=5
   abstract=Abstract In Indonesia, transportation costs from physical distribution still tend to be high because not all business people can optimize their distribution routes. This paper discusses a comparative study between Nearest Neighbor and Farthest Insert algorithms in solving a Vehicle Routing Problem (VRP) model. Aim of this study is to determine the most optimum distribution rou…
3. doi=10.1101/2021.02.05.429957 year=2021 title=Large-scale tandem mass spectrum clustering using fast nearest neighbor searching
   authors=Wout Bittremieux, Kris Laukens, William Stafford Noble, Pieter C. Dorrestein
   venue=None cited_by=5
   abstract=Abstract Rationale Advanced algorithmic solutions are necessary to process the ever increasing amounts of mass spectrometry data that is being generated. Here we describe the falcon spectrum clustering tool for efficient clustering of millions of MS/MS spectra. Methods falcon succeeds in efficiently clustering large amounts of mass spectral data using advanced techniques for f…

=== cvrp_loading ===
family: cvrp
label: VRP with loading
definition: LIFO or 3D loading.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: LIFO insertion (not_mappable), 3D packing + routing (not_mappable)
Works:
1. doi=10.1287/trsc.1070.0192 year=2007 title=Empirical Features of Congested Traffic States and Their Implications for Traffic Modeling
   authors=Martin Schönhof, Dirk Helbing
   venue=Transportation Science cited_by=218
   abstract=We address the controversial issue of traffic flow modeling, whether first-order, second-order, or other traffic models are best supported by empirical facts and theoretical considerations. This is done by a critical discussion of the pros and cons of the different theoretical approaches and by the analysis of a large set of empirical data with new evaluation techniques. Speci…
2. doi=10.1002/net.20192 year=2007 title=A Tabu search heuristic for the vehicle routing problem with two‐dimensional loading constraints
   authors=Michel Gendreau, Manuel Iori, Gilbert Laporte, Silvaro Martello
   venue=Networks cited_by=178
   abstract=Abstract This article addresses the well‐known Capacitated Vehicle Routing Problem (CVRP), in the special case where the demand of a customer consists of a certain number of two‐dimensional weighted items. The problem calls for the minimization of the cost of transportation needed for the delivery of the goods demanded by the customers, and carried out by a fleet of vehicles b…
3. doi=10.4018/ijitwe.335036 year=2023 title=Research on VRP Model Optimization of Cold Chain Logistics Under Low-Carbon Constraints
   authors=Ruixue Ma, Qiang Zhu
   venue=International Journal of Information Technology and Web Engineering cited_by=6
   abstract=The research in this article aims to consider low-carbon factors, through reasonable vehicle allocation and optimization of distribution routes, to achieve high satisfaction and low total cost, and to provide an optimized solution for fresh food distribution companies. In this article, cargo damage cost, energy cost, and carbon emission cost are added to the total cost, and cu…

=== cvrp_minveh ===
family: cvrp
label: Minimise number of vehicles
definition: Primary objective is fleet size.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Parallel cheapest insertion (not_mappable), Capacity-tight NN (next_node_score)
Works:
1. doi=10.1287/opre.35.2.254 year=1987 title=Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints
   authors=Marius M. Solomon
   venue=Operations Research cited_by=3426
   abstract=This paper considers the design and analysis of algorithms for vehicle routing and scheduling problems with time window constraints. Given the intrinsic difficulty of this problem class, approximation methods seem to offer the most promise for practical size problems. After describing a variety of heuristics, we conduct an extensive computational study of their performance. Th…
2. doi=10.1287/opre.12.4.568 year=1964 title=Scheduling of Vehicles from a Central Depot to a Number of Delivery Points
   authors=G. Clarke, J. W. Wright
   venue=Operations Research cited_by=2836
   abstract=The optimum routing of a fleet of trucks of varying capacities from a central depot to a number of delivery points may require a selection from a very large number of possible routes, if the number of delivery points is also large. This paper, after considering certain theoretical aspects of the problem, develops an iterative procedure that enables the rapid selection of an op…
3. doi=10.3390/vehicles7020061 year=2025 title=NeuHH: A Neuromorphic-Inspired Hyper-Heuristic Framework for Solving the Capacitated Single-Allocation p-Hub Location Routing Problem
   authors=Kassem Danach, Hassan Harb, Semaan Amine, Mariem Belhor
   venue=Vehicles cited_by=6
   abstract=This paper introduces a novel neuromorphic-inspired hyper-heuristic framework (NeuHH) for solving the Capacitated Single-Allocation p-Hub Location Routing Problem (CSAp-HLRP), a challenging combinatorial optimization problem that jointly addresses hub location decisions, capacity constraints, and vehicle routing. The proposed framework employs Spiking Neural Networks (SNNs) as…

=== cvrp_mo ===
family: cvrp
label: Multi-objective VRP
definition: Several routing objectives.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Weighted NN (not_mappable), Pareto local search (not_mappable)
Works:
1. doi=10.1088/1757-899x/852/1/012090 year=2020 title=Comparison study between nearest neighbor and farthest insert algorithms for solving VRP model using heuristic method approach
   authors=Wilson Kosasih, Ahmad, Lithrone Laricha Salomon, Febricky
   venue=IOP Conference Series: Materials Science and Engineering cited_by=5
   abstract=Abstract In Indonesia, transportation costs from physical distribution still tend to be high because not all business people can optimize their distribution routes. This paper discusses a comparative study between Nearest Neighbor and Farthest Insert algorithms in solving a Vehicle Routing Problem (VRP) model. Aim of this study is to determine the most optimum distribution rou…
2. doi=10.1155/2013/654074 year=2013 title=A Heuristic Multiobjective Method for Radial Distribution Networks Reconfiguration
   authors=Shahrokh Shojaeian, Ebrahim Ghandehari
   venue=Chinese Journal of Engineering cited_by=4
   abstract=This paper introduces a novel algorithm for radial distribution networks reconfiguration, called “Sifting algorithm.” It not only has a simple structure but also has high speed and accuracy. It works by eliminating infeasible states and reduces the search space and then it uses a simple method to find optimum answer in remaining space. To ensure the effectiveness of this algor…
3. doi=10.1613/jair.4100 year=2013 title=A Case of Pathology in Multiobjective Heuristic Search
   authors=J.L. Pérez de la Cruz, L. Mandow, E. Machuca
   venue=Journal of Artificial Intelligence Research cited_by=3
   abstract=This article considers the performance of the MOA* multiobjective search algorithm with heuristic information. It is shown that in certain cases blind search can be more efficient than perfectly informed search, in terms of both node and label expansions. A class of simple graph search problems is defined for which the number of nodes grows linearly with problem size and the n…

=== cvrp_multitrip ===
family: cvrp
label: Multi-trip VRP
definition: A vehicle may do several routes.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Multi-trip NN (next_node_score), Trip packing + routing (not_mappable)
Works:
1. doi=10.1002/net.3230140105 year=1984 title=Graphs with the smallest number of minimum cut sets
   authors=Derek Smith
   venue=Networks cited_by=15
   abstract=Abstract The number of vertex cut sets of size k in a graph of connectivity k has been used as a measure of network reliability. Let G be a regular graph with N vertices, valency k , connectivity k , and with the minimum number of vertex cut sets with k vertices. The problem of constructing such a graph G for each pair ( N, k ) is known to be difficult. We show how to construc…
2. doi=10.22219/jtiumm.vol20.no2.172-181 year=2019 title=A Cluster-First Route-Second Heuristic Approach to Solve The Multi-Trip Periodic Vehicle Routing Problem
   authors=Annisa Kesy Garside, Nabila Rohmatul Laili
   venue=Jurnal Teknik Industri cited_by=5
   abstract=This paper discusses periodic vehicle routing problems that allow vehicles to travel on multiple trips in a single day. It is known as the Multi-Trip Periodic Vehicles (MTPVRP) Problem Route. Cluster-first route-second (CFRS) heuristics to solve MTPVRP was proposed in this study. In phase 1, customers were divided into clusters using the formulation of integer programming. Pha…
3. doi=10.22219/jtiumm.vol20.no2.68-77 year=2019 title=A Cluster-First Route-Second Heuristic Approach to Solve The Multi-Trip Periodic Vehicle Routing Problem
   authors=Annisa Kesy Garside, Nabila Rohmatul Laili
   venue=Jurnal Teknik Industri cited_by=2
   abstract=This paper discusses periodic vehicle routing problems that allow vehicles to travel on multiple trips in a single day. It is known as the Multi-Trip Periodic Vehicles (MTPVRP) Problem Route. Cluster-first route-second (CFRS) heuristics to solve MTPVRP was proposed in this study. In phase 1, customers were divided into clusters using the formulation of integer programming. Pha…

=== cvrp_site ===
family: cvrp
label: Site-dependent VRP
definition: Some vehicles cannot serve some sites.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Site-feasible NN (not_mappable), Restricted savings (not_mappable)
Works:
1. doi=10.1088/1757-899x/852/1/012090 year=2020 title=Comparison study between nearest neighbor and farthest insert algorithms for solving VRP model using heuristic method approach
   authors=Wilson Kosasih, Ahmad, Lithrone Laricha Salomon, Febricky
   venue=IOP Conference Series: Materials Science and Engineering cited_by=5
   abstract=Abstract In Indonesia, transportation costs from physical distribution still tend to be high because not all business people can optimize their distribution routes. This paper discusses a comparative study between Nearest Neighbor and Farthest Insert algorithms in solving a Vehicle Routing Problem (VRP) model. Aim of this study is to determine the most optimum distribution rou…
2. doi=10.1101/2020.04.02.20050153 year=2020 title=CoViD–19: Meta-heuristic optimization based forecast method on time dependent bootstrapped data
   authors=Livio Fenga, Carlo Del Castello
   venue=None cited_by=4
   abstract=Abstract A compounded method – exploiting the searching capabilities of an operation research algorithm and the power of bootstrap techniques – is presented. The resulting algorithm has been successfully tested to predict the turning point reached by the epidemic curve followed by the CoViD–19 virus in Italy. Futures lines of research, which include the generalization of the m…
3. doi=10.70675/09043c22zfaa5z4e3bz868bz8ac1958d96f3 year=None title=Exact and anytime heuristic search for the Time Dependent Traveling Salesman Problem with Time Windows
   authors=Romain Fontaine
   venue=None cited_by=0
   abstract=Recherche heuristique exacte et anytime pour résoudre le Voyageur de commerce dépendant du temps avec fenêtres temporelles Le problème du voyageur de commerce (TSP, pour Traveling Salesman Problem) dépendant du temps (TD, pour Time Dependent) est une généralisation du TSP qui permet de prendre en compte les conditions de trafic lors de la planification de tournées en milieu ur…

=== cvrp_td ===
family: cvrp
label: Time-dependent VRP
definition: Travel time varies with clock.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: TD NN (not_mappable), TD local search (not_mappable)
Works:
1. doi=10.1287/trsc.26.3.185 year=1992 title=Time Dependent Vehicle Routing Problems: Formulations, Properties and Heuristic Algorithms
   authors=Chryssi Malandraki, Mark S. Daskin
   venue=Transportation Science cited_by=453
   abstract=The time dependent vehicle routing problem (TDVRP) is defined as follows. A vehicle fleet of fixed capacities serves customers of fixed demands from a central depot. Customers are assigned to vehicles and the vehicles routed so that the total time of the routes is minimized. The travel time between two customers or between a customer and the depot depends on the distance betwe…
2. doi=10.4028/www.scientific.net/amr.339.332 year=2011 title=Comparison of Heuristic for Flow Shop Scheduling Problems with Sequence Dependent Setup Time
   authors=Parinya Kaweegitbundit
   venue=Advanced Materials Research cited_by=5
   abstract=This paper considers flow shop scheduling problems with sequence dependent setup time. The makespan criterion has been considered. In this paper presented a comparison of three heuristics for solves this problem. The memetic algorithm, genetic algorithm and NEH heuristic have been compared. In the experimental, the result from memetic algorithm is maximum the best solution. Th…
3. doi=10.1101/2020.04.02.20050153 year=2020 title=CoViD–19: Meta-heuristic optimization based forecast method on time dependent bootstrapped data
   authors=Livio Fenga, Carlo Del Castello
   venue=None cited_by=4
   abstract=Abstract A compounded method – exploiting the searching capabilities of an operation research algorithm and the power of bootstrap techniques – is presented. The resulting algorithm has been successfully tested to predict the turning point reached by the epidemic curve followed by the CoViD–19 virus in Italy. Futures lines of research, which include the generalization of the m…

=== cvrpb ===
family: cvrp
label: VRP with backhauls
definition: Linehaul then backhaul.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Backhaul insertion (not_mappable), Linehaul-first NN (not_mappable)
Works:
1. doi=10.1287/trsc.31.1.49 year=1997 title=A Tabu Search Heuristic for the Vehicle Routing Problem with Backhauls and Time Windows
   authors=Christophe Duhamel, Jean-Yves Potvin, Jean-Marc Rousseau
   venue=Transportation Science cited_by=83
   abstract=This article describes a tabu search heuristic for the vehicle routing problem with backhauls and time windows. In this problem, the set of customers is partitioned into two subsets: linehaul customers where a given quantity of goods is delivered from a central depot, and backhaul customers where a given quantity of goods is collected and transported to the depot. Mixed routes…
2. doi=10.1002/net.3230190306 year=1989 title=How to find a battleship
   authors=Amos Fiat, Adi Shamir
   venue=Networks cited_by=12
   abstract=Abstract Consider a “sea” of M squares which contains (at some unknown location) a “battleship” of K squares. Both the sea and the battleship can assume any rectangular shape. Our goal is to find the battleship by probing at least one of its squares. In this paper we describe a deterministic strategy for this problem which is guaranteed to locate the battleship in at most c 1…
3. doi=10.3390/info11090414 year=2020 title=The Effect of Limited Resources in the Dynamic Vehicle Routing Problem with Mixed Backhauls
   authors=Georgios Ninikas, Ioannis Minis
   venue=Information cited_by=4
   abstract=In the dynamic vehicle routing problem with mixed backhauls (DVRPMB) both pick up orders and delivery orders, not related to each other, are served. The requests of the former arrive dynamically while the latter are known a priori. In this study, we focus on the case of limited fleet, which fulfills all delivery orders, but may not have enough capacity to serve all pick up ord…

=== darp ===
family: cvrp
label: Dial-a-ride
definition: Passenger transport with windows.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: DARP insertion (not_mappable), DARP regret (not_mappable)
Works:
1. doi=10.1287/trsc.29.4.342 year=1995 title=Computational Approaches to Stochastic Vehicle Routing Problems
   authors=Dimitris Bertsimas, Philippe Chervi, Michael Peterson
   venue=Transportation Science cited_by=82
   abstract=We report computational test results for several graph-based a priori heuristics for the Euclidean plane versions of two well-known stochastic optimization problems, the probabilistic traveling salesman problem (PTSP) and the probabilistic (or stochastic) vehicle routing problem (PVRP). These heuristics are termed a priori because they design vehicle routes prior to realizatio…
2. doi=10.1002/net.20335 year=2009 title=A heuristic two‐phase solution approach for the multi‐objective dial‐a‐ride problem
   authors=Sophie N. Parragh, Karl F. Doerner, Richard F. Hartl, Xavier Gandibleux
   venue=Networks cited_by=75
   abstract=Abstract In this article, we develop a heuristic two‐phase solution procedure for the dial‐a‐ride problem with two objectives. Besides the minimum cost objective a client centered objective has been defined. Phase one consists of an iterated variable neighborhood search‐based heuristic, generating approximate weighted sum solutions; phase two is a path relinking module, comput…
3. doi=10.1142/s0217595912500467 year=2013 title=A HYBRID GREEDY RANDOMIZED ADAPTIVE SEARCH HEURISTIC TO SOLVE THE DIAL-A-RIDE PROBLEM
   authors=FRANCESCA GUERRIERO, MARIA ELENA BRUNI, FRANCESCA GRECO
   venue=Asia-Pacific Journal of Operational Research cited_by=18
   abstract=This paper presents a hybrid metaheuristic for solving the static dial-a-ride problem with heterogeneous vehicles and fixed costs. The hybridization combines a reactive greedy randomized adaptive search, used as outer scheme, with a tabu search heuristic in the local search phase. The algorithm is evaluated on well-known instances taken from the literature and on a set of rand…

=== dcvrp ===
family: cvrp
label: Distance-constrained VRP
definition: Route length cap.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Length-feasible NN (next_node_score), DCVRP savings (next_node_score)
Works:
1. doi=10.1287/opre.12.4.568 year=1964 title=Scheduling of Vehicles from a Central Depot to a Number of Delivery Points
   authors=G. Clarke, J. W. Wright
   venue=Operations Research cited_by=2836
   abstract=The optimum routing of a fleet of trucks of varying capacities from a central depot to a number of delivery points may require a selection from a very large number of possible routes, if the number of delivery points is also large. This paper, after considering certain theoretical aspects of the problem, develops an iterative procedure that enables the rapid selection of an op…
2. doi=10.1002/net.3230070404 year=1977 title=A shortest path algorithm for grid graphs
   authors=F. O. Hadlock
   venue=Networks cited_by=96
   abstract=Abstract Grid graphs are a simple class of planar graphs for which the vertices can be assigned integer coordinates so that neighbors agree in one coordinate and differ by one in the other coordinate. Grid graphs arise in applications from the layout design of integrated circuits to idealized models of city street networks. In many applications, a shortest path between two giv…
3. doi=10.1007/bf02296341 year=2000 title=Optimal Scaling by Alternating Length-Constrained Nonnegative Least Squares, with Application to Distance-Based Analysis
   authors=Patrick J. F. Groenen, Bart-Jan van Os, Jacqueline J. Meulman
   venue=Psychometrika cited_by=8
   abstract=An important feature of distance-based principal components analysis, is that the variables can be optimally transformed. For monotone spline transformation, a nonnegative least-squares problem with a length constraint has to be solved in each iteration. As an alternative algorithm to Lawson and Hanson (1974), we propose the Alternating Length-Constrained Non-Negative Least-Sq…

=== evrp ===
family: cvrp
label: Electric VRP
definition: Charging constraints.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Charge-feasible NN (not_mappable), EVRP insertion (not_mappable)
Works:
1. doi=10.3390/a12020045 year=2019 title=A Heuristic Approach for a Real-World Electric Vehicle Routing Problem
   authors=Mengting Zhao, Yuwei Lu
   venue=Algorithms cited_by=59
   abstract=To develop a non-polluting and sustainable city, urban administrators encourage logistics companies to use electric vehicles instead of conventional (i.e., fuel-based) vehicles for transportation services. However, electric energy-based limitations pose a new challenge in designing reasonable visiting routes that are essential for the daily operations of companies. Therefore,…
2. doi=10.3390/wevj15020069 year=2024 title=Heuristic Algorithms for Heterogeneous and Multi-Trip Electric Vehicle Routing Problem with Pickup and Delivery
   authors=Li Wang, Yifan Ding, Zhiyuan Chen, Zhiyuan Su, Yufeng Zhuang
   venue=World Electric Vehicle Journal cited_by=11
   abstract=In light of the widespread use of electric vehicles for urban distribution, this paper delves into the electric vehicle routing problem (EVRP): specifically addressing multiple trips per vehicle, diverse vehicle types, and simultaneous pickup and delivery. The primary objective is to minimize the overall cost, which encompasses travel expenses, waiting times, recharging costs,…
3. doi=10.70675/37fa3a3cza23dz4ac5zbaa3z1327ba608d7e year=None title=Vehicle routing problems with profits, exact and heuristic approaches
   authors=Racha El-Hajj
   venue=None cited_by=0
   abstract=Problèmes de tournées de véhicules avec profits, méthodes exactes et approchées Nous nous intéressons dans cette thèse à la résolution du problème de tournées sélectives (Team Orienteering Problem - TOP) et ses variantes. Ce problème est une extension du problème de tournées de véhicules en imposan tcertaines limitations de ressources. Nous proposons un algorithme de résolutio…

=== fsmvrp ===
family: cvrp
label: Fleet size and mix
definition: Choose fleet composition.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Golden FSM constructive (not_mappable), FSM local search (not_mappable)
Works:
1. doi=10.1111/itor.12379 year=2017 title=An iterative biased‐randomized heuristic for the fleet size and mix vehicle‐routing problem with backhauls
   authors=Javier Belloso, Angel A. Juan, Javier Faulin
   venue=International Transactions in Operational Research cited_by=57
   abstract=Abstract This paper analyzes the fleet mixed vehicle‐routing problem with backhauls, a rich and realistic variant of the popular vehicle‐routing problem in which both delivery and pick‐up customers are served from a central depot using a heterogeneous and configurable fleet of vehicles. After a literature review on the issue and a detailed description of the problem, a solutio…
2. doi=10.1287/trsc.1070.0190 year=2007 title=Heuristic Approaches for the Fleet Size and Mix Vehicle Routing Problem with Time Windows
   authors=Mauro Dell'Amico, Michele Monaci, Corrado Pagani, Daniele Vigo
   venue=Transportation Science cited_by=53
   abstract=The fleet size and mix vehicle routing problem with time windows (FSMVRPTW) is the problem of determining, at the same time, the composition and the routing of a fleet of heterogeneous vehicles aimed to serve a given set of customers. The routing problem requires us to design a set of minimum-cost routes originating and terminating at a central depot and serving customers with…
3. doi=10.1002/net.20331 year=2009 title=Valid inequalities for the fleet size and mix vehicle routing problem with fixed costs
   authors=Roberto Baldacci, Maria Battarra, Daniele Vigo
   venue=Networks cited_by=30
   abstract=Abstract In the well‐known vehicle routing problem (VRP), a set of identical vehicles located at a central depot is to be optimally routed to supply customers with known demands subject to vehicle capacity constraints. An important variant of the VRP arises when a mixed fleet of vehicles, characterized by different capacities and costs, is available for distribution activities…

=== hfvrp ===
family: cvrp
label: Heterogeneous fleet VRP
definition: Vehicle types differ.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Type-aware savings (not_mappable), Fleet mix local search (not_mappable)
Works:
1. doi=10.1002/net.3230140106 year=1984 title=An algorithm for construction of a <i>k</i>‐connected graph with minimum number of edges and quasiminimal diameter
   authors=Ulrich Schumacher
   venue=Networks cited_by=28
   abstract=Abstract Two fundamental considerations in the design of a communication network are reliability and maximum transmission delay. In this paper we give an algorithm for construction of an undirected graph with n vertices in which there are k node‐disjoint paths between any two nodes. The generated graphs will have a minimum number of edges and a diameter which is twice as large…
2. doi=10.4018/ijamc.2016100102 year=2016 title=Quantum Inspired Algorithm for a VRP with Heterogeneous Fleet Mixed Backhauls and Time Windows
   authors=Meryem Berghida, Abdelmadjid Boukra
   venue=International Journal of Applied Metaheuristic Computing cited_by=12
   abstract=This paper presents a new Quantum Inspired Harmony Search algorithm with Variable Population Size QIHSVPS for a complex variant of vehicle routing problem (VRP), called HVRPMBTW (Vehicle Routing Problem with Heterogeneous fleet, Mixed Backhauls and Time Windows). This variant is characterized by a limited number of vehicles with various capacities and costs. The vehicles serve…
3. doi=10.1155/2019/5364201 year=2019 title=A Hybrid Simulated Annealing Heuristic for Multistage Heterogeneous Fleet Scheduling with Fleet Sizing Decisions
   authors=Bing Li, Xinyu Yang, Hua Xuan
   venue=Journal of Advanced Transportation cited_by=11
   abstract=This paper deals with multistage heterogeneous fleet scheduling with fleet sizing decisions (MHFS-FSD). This MHFS-FSD attempts to integrate vehicles allocation and fleet sizing decisions considering the vehicle routing of multiple vehicle types. The problem is formulated as mixed integer programming model. The matrix formulation denoting vehicle allocation scheme is explored a…

=== irp ===
family: cvrp
label: Inventory routing
definition: Routing plus inventory.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: IRP greedy replenishment (not_mappable), IRP local search (not_mappable)
Works:
1. doi=10.1287/trsc.18.1.1 year=1984 title=Network Design and Transportation Planning: Models and Algorithms
   authors=T. L. Magnanti, R. T. Wong
   venue=Transportation Science cited_by=971
   abstract=Numerous transportation applications as diverse as capital investment decision-making, vehicle fleet planning, and traffic light signal setting all involve some form of (discrete choice) network design. In this paper, we review some of the uses and limitations of integer programming-based approaches to network design, and describe several discrete and continuous choice models…
2. doi=10.1287/trsc.2019.0934 year=2020 title=Heuristic Sequence Selection for Inventory Routing Problem
   authors=Ahmed Kheiri
   venue=Transportation Science cited_by=33
   abstract=In this paper, an improved sequence-based selection hyper-heuristic method for the Air Liquide inventory routing problem, the subject of the ROADEF/EURO 2016 challenge, is described. The organizers of the challenge have proposed a real-world problem of inventory routing as a difficult combinatorial optimization problem. An exact method often fails to find a feasible solution t…
3. doi=10.1287/trsc.1060.0160 year=2007 title=An Efficient Heuristic Algorithm for a Two-Echelon Joint Inventory and Routing Problem
   authors=Jaeheon Jung, Kamlesh Mathur
   venue=Transportation Science cited_by=29
   abstract=With an increasing emphasis on coordination in the supply chain, the inventory and distribution decisions, which in most part had been dealt with independently of each other, need to be considered jointly. This research considers a two-echelon distribution system consisting of one warehouse and N retailers that face external demand at a constant rate. Inventories are kept at r…

=== mdvrp ===
family: cvrp
label: Multi-depot VRP
definition: Several depots.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Depot assignment + NN (not_mappable), MD savings (not_mappable)
Works:
1. doi=10.1287/trsc.7.2.109 year=1973 title=Minimum Cost Schedules for a Public Transportation Route—I. Theory
   authors=V. F. Hurdle
   venue=Transportation Science cited_by=49
   abstract=A fleet of vehicles carries passengers in one direction on a public transit route, then returns empty to the dispatch point after a round trip travel time T. The arrival rate of passengers is a known, deterministic, continuous, function of time and the objective is to devise a schedule that minimizes the total cost for passenger waiting time and vehicle operation. It is shown…
2. doi=10.4018/ijaec.2018010101 year=2018 title=Efficient Golden-Ball Algorithm Based Clustering to solve the Multi-Depot VRP With Time Windows
   authors=Lahcene Guezouli, Mohamed Bensakhria, Samir Abdelhamid
   venue=International Journal of Applied Evolutionary Computation cited_by=6
   abstract=In this article, the authors propose a decision support system which aims to optimize the classical Capacitated Vehicle Routing Problem by considering the existence of multiple available depots and a time window which must not be violated, that they call the Multi-Depot Vehicle Routing Problem with Time Window (MDVRPTW), and with respecting a set of criteria including: schedul…
3. doi=10.3233/978-1-61499-105-2-49 year=2012 title=A Learning Based Evolutionary Algorithm For Distributed Multi-Depot VRP
   authors=Soeanu A., Ray S., Debbabi M., Berger J., Boukhtouta A.
   venue=Frontiers in Artificial Intelligence and Applications cited_by=3
   abstract=Solving multi-depot vehicle routing problem (MDVRP) in centralized setting has known scalability issues. This paper presents an innovative multi-agent and multi-round reinforcement learning procedure over adaptive elitist solutions selected from an evolving population pool, to near optimally solve MDVRP in a distributed setting. The paper contribution is threefold: First, it i…

=== pvrp ===
family: cvrp
label: Periodic VRP
definition: Planning over several days.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Day assignment + CWS (not_mappable), Periodic local search (not_mappable)
Works:
1. doi=10.1287/trsc.18.1.1 year=1984 title=Network Design and Transportation Planning: Models and Algorithms
   authors=T. L. Magnanti, R. T. Wong
   venue=Transportation Science cited_by=971
   abstract=Numerous transportation applications as diverse as capital investment decision-making, vehicle fleet planning, and traffic light signal setting all involve some form of (discrete choice) network design. In this paper, we review some of the uses and limitations of integer programming-based approaches to network design, and describe several discrete and continuous choice models…
2. doi=10.1287/trsc.26.2.86 year=1992 title=A Heuristic for the Periodic Vehicle Routing Problem
   authors=M. Gaudioso, G. Paletta
   venue=Transportation Science cited_by=97
   abstract=The paper describes a model for the optimal management of periodic deliveries of a given commodity. The goal is to schedule the deliveries according to feasible combinations of delivery days and to determine the scheduling and routing policies of the vehicles in order to minimize over the planning horizon the maximum number of vehicles simultaneously employed, i.e., the fleet…
3. doi=10.22219/jtiumm.vol20.no2.172-181 year=2019 title=A Cluster-First Route-Second Heuristic Approach to Solve The Multi-Trip Periodic Vehicle Routing Problem
   authors=Annisa Kesy Garside, Nabila Rohmatul Laili
   venue=Jurnal Teknik Industri cited_by=5
   abstract=This paper discusses periodic vehicle routing problems that allow vehicles to travel on multiple trips in a single day. It is known as the Multi-Trip Periodic Vehicles (MTPVRP) Problem Route. Cluster-first route-second (CFRS) heuristics to solve MTPVRP was proposed in this study. In phase 1, customers were divided into clusters using the formulation of integer programming. Pha…

=== sdvrp ===
family: cvrp
label: Split-delivery VRP
definition: A customer may be split.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Split-delivery savings (not_mappable), Split local search (not_mappable)
Works:
1. doi=10.1287/trsc.23.2.141 year=1989 title=Savings by Split Delivery Routing
   authors=Moshe Dror, Pierre Trudeau
   venue=Transportation Science cited_by=353
   abstract=This paper examines a relaxed version of the generic vehicle routing problem. In this version, a delivery to a demand point can be split between any number of vehicles. In spite of this relaxation the problem remains computationally hard. The main contribution of this paper is in demonstrating the potential for cost savings through split deliveries. The solution scheme allowin…
2. doi=10.1287/trsc.1070.0204 year=2008 title=An Optimization-Based Heuristic for the Split Delivery Vehicle Routing Problem
   authors=Claudia Archetti, M. Grazia Speranza, Martin W. P. Savelsbergh
   venue=Transportation Science cited_by=110
   abstract=The split delivery vehicle routing problem is concerned with serving the demand of a set of customers with a fleet of capacitated vehicles at minimum cost. Contrary to what is assumed in the classical vehicle routing problem, a customer can be served by more than one vehicle, if convenient. We present a solution approach that integrates heuristic search with optimization by us…
3. doi=10.1002/net.22238 year=2024 title=A heuristic with a performance guarantee for the commodity constrained split delivery vehicle routing problem
   authors=Matteo Petris, Claudia Archetti, Diego Cattaruzza, Maxime Ogier, Frédéric Semet
   venue=Networks cited_by=8
   abstract=Abstract The commodity constrained split delivery vehicle routing problem (C‐SDVRP) is a routing problem where customer demands are composed of multiple commodities. A fleet of capacitated vehicles must serve customer demands in a way that minimizes the total routing costs. Vehicles can transport any set of commodities and customers are allowed to be visited multiple times. Ho…

=== vrppd ===
family: cvrp
label: VRP with pickups and deliveries
definition: Paired pickup and delivery.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Paired insertion (not_mappable), PDP VND (not_mappable)
Works:
1. doi=10.1287/trsc.1050.0135 year=2006 title=An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows
   authors=Stefan Ropke, David Pisinger
   venue=Transportation Science cited_by=2281
   abstract=The pickup and delivery problem with time windows is the problem of serving a number of transportation requests using a limited amount of vehicles. Each request involves moving a number of goods from a pickup location to a delivery location. Our task is to construct routes that visit all locations such that corresponding pickups and deliveries are placed on the same route, and…
2. doi=10.1287/trsc.29.1.45 year=1995 title=A Network Flow Based Heuristic for Bulk Pickup and Delivery Routing
   authors=Marshall L. Fisher, Baoxing Tang, Zhang Zheng
   venue=Transportation Science cited_by=10
   abstract=We consider a problem in which a fleet of vehicles must be scheduled to pickup and deliver a set of orders in truckload quantities. We describe a new algorithm based on a network flow relaxation which imposes necessary conditions on the flow of empty vehicles from order delivery points to order pickup points. The network flow model provides a lower bound and a nearly feasible…
3. doi=10.1002/net.21917 year=2019 title=A two‐level local search heuristic for pickup and delivery problems in express freight trucking
   authors=Luigi De Giovanni, Nicola Gastaldon, Filippo Sottovia
   venue=Networks cited_by=10
   abstract=Abstract We consider a multiattribute vehicle routing problem inspired by a freight transportation company operating a fleet of heterogeneous trucks. The company offers an express service for requests including multiple pickup and multiple delivery positions spread in a regional area, with associated soft or hard time windows often falling in the same working day. Routes are p…

=== vrptw ===
family: cvrp
label: VRP with time windows
definition: Customers have time windows.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Solomon I1 (not_mappable), Solomon I2 (not_mappable)
Works:
1. doi=10.1287/opre.35.2.254 year=1987 title=Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints
   authors=Marius M. Solomon
   venue=Operations Research cited_by=3426
   abstract=This paper considers the design and analysis of algorithms for vehicle routing and scheduling problems with time window constraints. Given the intrinsic difficulty of this problem class, approximation methods seem to offer the most promise for practical size problems. After describing a variety of heuristics, we conduct an extensive computational study of their performance. Th…
2. doi=10.21203/rs.3.rs-4973948/v1 year=2024 title=Comparative Review of Single-Criteria and Multi-Criteria Optimisation Problems using Meta-heuristic Algorithms.
   authors=Cornelius Okechukwu, Radek Silhavy, Solomon Oyelere, Petr Silhavy
   venue=None cited_by=1
   abstract=Abstract This paper explores using metaheuristic algorithms for single-criteria optimisation problems (SCOP) and multi-criteria optimisation problems (MCOP). It highlights the critical differences between these types, noting that SCOP focusses on a single objective while MCOP deals with conflicting goals. We applied metaheuristic algorithms inspired by natural phenomena to bot…
3. doi=10.37373/jenius.v6i2.1652 year=2025 title=Optimasi rute pengangkutan sampah menggunakan metode VRPTW dan Nearest Insertion Heuristic di Kecamatan Jatisampurna
   authors=Harditriyono Putra, Andary Asvaroza Munita
   venue=JENIUS : Jurnal Terapan Teknik Industri cited_by=0
   abstract=Dinas Lingkungan Hidup melalui Unit Pelaksana Teknis Dinas Lingkungan Hidup (UPTD LH) Kecamatan Jatisampurna bertanggung jawab untuk mengelola pengangkutan sampah rumah tangga di wilayah Kecamatan Jatisampurna. Pengangkutan sampah dilakukan dengan dua metode. Metode pertama adalah pengumpulan dari rumah ke rumah dan dibuang ke TPA Sumur Batu setelah kontainer penuh. Metode ked…
