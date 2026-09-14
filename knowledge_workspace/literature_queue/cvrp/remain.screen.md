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
3. doi=10.70675/6efe1282zb27fz4752zbd40z47d5121fb4ff year=None title=Inventory routing problems on two-echelon systems : exact and heuristic methods for the tactical and operational problems
   authors=Katyanne Farias de Araújo
   venue=None cited_by=0
   abstract=Inventory Routing Problems dans les systèmes à deux échelons : méthodes exactes et heuristiques pour les problèmes tactique et opérationnel Les activités de transport et de gestion des stocks ont un impact important les unes sur les autres. Assurer un niveau de stock idéal peut demander des livraisons fréquentes, ce qui entraîne des coûts logistiques élevés. Pour optimiser les…

=== cvrp_loading ===
family: cvrp
label: VRP with loading
definition: LIFO or 3D loading.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: LIFO insertion (not_mappable), 3D packing + routing (not_mappable)
Works:
1. doi=10.1002/net.20192 year=2007 title=A Tabu search heuristic for the vehicle routing problem with two‐dimensional loading constraints
   authors=Michel Gendreau, Manuel Iori, Gilbert Laporte, Silvaro Martello
   venue=Networks cited_by=178
   abstract=Abstract This article addresses the well‐known Capacitated Vehicle Routing Problem (CVRP), in the special case where the demand of a customer consists of a certain number of two‐dimensional weighted items. The problem calls for the minimization of the cost of transportation needed for the delivery of the goods demanded by the customers, and carried out by a fleet of vehicles b…
2. doi=10.4018/ijitwe.335036 year=2023 title=Research on VRP Model Optimization of Cold Chain Logistics Under Low-Carbon Constraints
   authors=Ruixue Ma, Qiang Zhu
   venue=International Journal of Information Technology and Web Engineering cited_by=6
   abstract=The research in this article aims to consider low-carbon factors, through reasonable vehicle allocation and optimization of distribution routes, to achieve high satisfaction and low total cost, and to provide an optimized solution for fresh food distribution companies. In this article, cargo damage cost, energy cost, and carbon emission cost are added to the total cost, and cu…
3. doi=10.4028/www.scientific.net/amr.945-949.3438 year=2014 title=VRP Problem Research with Workshop Road Constraints Based on Tabu Search
   authors=Yun Jie Feng, Hai Ping Zhu, Fei He
   venue=Advanced Materials Research cited_by=1
   abstract=Aiming at general constraints in vehicle routing problem in workshop, this paper improve and simplify some relative constraints to make it more in line with real conditions in workshop. Different situations are discussed and experimentally computed respectively. The results show that tabu search is effective to get satisfactory algorithmic solutions, and this problem can be ex…

=== cvrp_local ===
family: cvrp
label: Local-search CVRP
definition: Improve complete routes.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Granular tabu (not_mappable), Relocate/exchange VND (not_mappable)
Works:
1. doi=10.1287/ijoc.15.4.333.24890 year=2003 title=The Granular Tabu Search and Its Application to the Vehicle-Routing Problem
   authors=Paolo Toth, Daniele Vigo
   venue=INFORMS Journal on Computing cited_by=388
   abstract=We describe a new variant, called granular tabu search, of the well-known tabu-search approach. The method uses an effective intensification/diversification tool that can be successfully applied to a wide class of graph-theoretic and combinatorial-optimization problems. Granular tabu search is based on the use of drastically restricted neighborhoods, not containing the moves t…
2. doi=10.5755/j01.itc.35.3.11770 year=2006 title=ITERATED TABU SEARCH: AN IMPROVEMENT TO STANDARD TABU SEARCH
   authors=Alfonsas Misevicius, Antanas Lenkevicius, Dalius Rubliauskas
   venue=Information Technology And Control cited_by=16
   abstract=The goal of this paper is to discuss the tabu search (TS) meta-heuristic and its enhancement for combinatorial optimization problems. Firstly, the issues related to the principles and specific features of the standard TS are concerned. Further, a promising extension to the classical tabu search scheme is introduced. The most important component of this extension is a special k…
3. doi=10.5267/j.ijiec.2021.6.001 year=2022 title=A granular tabu search for the refrigerated vehicle routing problem with homogeneous fleet
   authors=John Willmer Escobar, José Luis Ramírez Duque, Rafael García-Cáceres
   venue=International Journal of Industrial Engineering Computations cited_by=10
   abstract=The Refrigerated Capacitated Vehicle Routing Problem (RCVRP) considers a homogeneous fleet with a refrigerated system to decide the selection of routes to be performed according to customers' requirements. The aim is to keep the energy consumption of the routes as low as possible. We use a thermodynamic model to understand the unloading of products from trucks and the variable…

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

=== cvrp_prize ===
family: cvrp
label: Prize-collecting VRP
definition: Optional customers.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Prize/distance greedy (not_mappable), Selective VRP local search (not_mappable)
Works:
1. doi=10.1002/net.3230190602 year=1989 title=The prize collecting traveling salesman problem
   authors=Egon Balas
   venue=Networks cited_by=403
   abstract=Abstract The following is a valid model for an important class of scheduling and routing problems. A salesman who travels between pairs of cities at a cost depending only on the pair, gets a prize in every city that he vitis and pays a penalty to every city that he fails to visit, wishes to minimize his travel costs and net penalties, while visiting enough cities to collect a…
2. doi=10.1002/net.3230250406 year=1995 title=The prize collecting traveling salesman problem: II. Polyhedral results
   authors=Egon Balas
   venue=Networks cited_by=35
   abstract=Abstract The task of developing daily schedules for a steel rolling mill has been formulated as a Prize Collecting Traveling Salesman (PCTS) Problem, in which a salesman who gets a prize for every city he visits seeks a minimum‐cost tour including enough cities to collect a required amount of prize money. This paper addresses the facial structure of the PCTS polytope, the conv…
3. doi=10.1088/1757-899x/852/1/012090 year=2020 title=Comparison study between nearest neighbor and farthest insert algorithms for solving VRP model using heuristic method approach
   authors=Wilson Kosasih, Ahmad, Lithrone Laricha Salomon, Febricky
   venue=IOP Conference Series: Materials Science and Engineering cited_by=5
   abstract=Abstract In Indonesia, transportation costs from physical distribution still tend to be high because not all business people can optimize their distribution routes. This paper discusses a comparative study between Nearest Neighbor and Farthest Insert algorithms in solving a Vehicle Routing Problem (VRP) model. Aim of this study is to determine the most optimum distribution rou…

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

=== cvrp_stochastic ===
family: cvrp
label: Stochastic-demand VRP
definition: Demands random.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Expected-demand NN (not_mappable), Recourse restocking (not_mappable)
Works:
1. doi=10.1287/opre.1110.0967 year=2012 title=Technical Note—Approximation Algorithms for VRP with Stochastic Demands
   authors=Anupam Gupta, Viswanath Nagarajan, R. Ravi
   venue=Operations Research cited_by=29
   abstract=We consider the vehicle routing problem with stochastic demands (VRPSD). We give randomized approximation algorithms achieving approximation guarantees of 1 + α for split-delivery VRPSD, and 2 + α for unsplit-delivery VRPSD; here α is the best approximation guarantee for the traveling salesman problem. These bounds match the best known for even the respective deterministic pro…
2. doi=10.30656/jsmi.v6i2.4813 year=2022 title=Tabu search heuristic for inventory routing problem with stochastic demand and time windows
   authors=Meilinda Fitriani Nur Maghfiroh, Anak Agung Ngurah Perwira Redi
   venue=Jurnal Sistem dan Manajemen Industri cited_by=3
   abstract=This study proposes the hybridization of tabu search (TS) and variable neighbourhood descent (VND) for solving the Inventory Routing Problems with Stochastic Demand and Time Windows (IRPSDTW). Vendor Managed Inventory (VMI) is among the most used approaches for managing supply chains comprising multiple stakeholders, and implementing VMI require addressing the Inventory Routin…
3. doi=10.3390/app16062838 year=2026 title=Deep Learning-Enhanced Proactive Strategy: LSTM and VRP/ACO for Autonomous Replenishment and Demand Forecasting in Shared Logistics
   authors=Martin Straka, Kristína Kleinová
   venue=Applied Sciences cited_by=2
   abstract=At present, the global logistics sector faces critical challenges, including rising energy costs and pressure to reduce CO2 emissions. Traditional linear supply chains are becoming inefficient, necessitating a transition toward shared logistics based on the principles of the sharing economy. This paper presents a progressive three-layer architecture that transforms conventiona…

=== cvrp_td ===
family: cvrp
label: Time-dependent VRP
definition: Travel time varies with clock.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: TD NN (not_mappable), TD local search (not_mappable)
Works:
1. doi=10.4028/www.scientific.net/amr.339.332 year=2011 title=Comparison of Heuristic for Flow Shop Scheduling Problems with Sequence Dependent Setup Time
   authors=Parinya Kaweegitbundit
   venue=Advanced Materials Research cited_by=5
   abstract=This paper considers flow shop scheduling problems with sequence dependent setup time. The makespan criterion has been considered. In this paper presented a comparison of three heuristics for solves this problem. The memetic algorithm, genetic algorithm and NEH heuristic have been compared. In the experimental, the result from memetic algorithm is maximum the best solution. Th…
2. doi=10.1101/2020.04.02.20050153 year=2020 title=CoViD–19: Meta-heuristic optimization based forecast method on time dependent bootstrapped data
   authors=Livio Fenga, Carlo Del Castello
   venue=None cited_by=4
   abstract=Abstract A compounded method – exploiting the searching capabilities of an operation research algorithm and the power of bootstrap techniques – is presented. The resulting algorithm has been successfully tested to predict the turning point reached by the epidemic curve followed by the CoViD–19 virus in Italy. Futures lines of research, which include the generalization of the m…
3. doi=10.3390/su172411308 year=2025 title=Urban Pickup-and-Delivery VRP with Soft Time Windows Under Travel-Time Uncertainty: An Empirical Comparison of Robust and Deterministic Approaches
   authors=Daniel Kubek
   venue=Sustainability cited_by=1
   abstract=Urban freight pickup-and-delivery services operate in road networks where travel times are highly variable due to congestion, incidents, and operational restrictions. Such variability threatens the punctuality of deliveries and complicates the design of reliable service schedules. This paper examines an urban pickup-and-delivery vehicle routing problem with soft time windows u…

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
2. doi=10.3390/info11090414 year=2020 title=The Effect of Limited Resources in the Dynamic Vehicle Routing Problem with Mixed Backhauls
   authors=Georgios Ninikas, Ioannis Minis
   venue=Information cited_by=4
   abstract=In the dynamic vehicle routing problem with mixed backhauls (DVRPMB) both pick up orders and delivery orders, not related to each other, are served. The requests of the former arrive dynamically while the latter are known a priori. In this study, we focus on the case of limited fleet, which fulfills all delivery orders, but may not have enough capacity to serve all pick up ord…
3. doi=10.4018/978-1-61692-852-0.ch608 year=2011 title=Meta-heuristic Approach to Solve Mixed Vehicle Routing Problem with Backhauls in Enterprise Information System of Service Industry
   authors=S. P. Anbuudayasankar, K. Ganesh, Tzong-Ru Lee
   venue=Enterprise Information Systems cited_by=2
   abstract=This chapter presents the development of simulated annealing (SA) for a health care application which is modeled as Single Depot Vehicle routing problem called Mixed Vehicle Routing Problem with Backhauls (MVRPB), an extension of Vehicle Routing Problem with Backhauls (VRPB). This variant involves both delivery and pick-up customers and sequence of visiting the customers is mi…

=== darp ===
family: cvrp
label: Dial-a-ride
definition: Passenger transport with windows.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: DARP insertion (not_mappable), DARP regret (not_mappable)
Works:
1. doi=10.1002/net.20335 year=2009 title=A heuristic two‐phase solution approach for the multi‐objective dial‐a‐ride problem
   authors=Sophie N. Parragh, Karl F. Doerner, Richard F. Hartl, Xavier Gandibleux
   venue=Networks cited_by=75
   abstract=Abstract In this article, we develop a heuristic two‐phase solution procedure for the dial‐a‐ride problem with two objectives. Besides the minimum cost objective a client centered objective has been defined. Phase one consists of an iterated variable neighborhood search‐based heuristic, generating approximate weighted sum solutions; phase two is a path relinking module, comput…
2. doi=10.1142/s0217595912500467 year=2013 title=A HYBRID GREEDY RANDOMIZED ADAPTIVE SEARCH HEURISTIC TO SOLVE THE DIAL-A-RIDE PROBLEM
   authors=FRANCESCA GUERRIERO, MARIA ELENA BRUNI, FRANCESCA GRECO
   venue=Asia-Pacific Journal of Operational Research cited_by=18
   abstract=This paper presents a hybrid metaheuristic for solving the static dial-a-ride problem with heterogeneous vehicles and fixed costs. The hybridization combines a reactive greedy randomized adaptive search, used as outer scheme, with a tabu search heuristic in the local search phase. The algorithm is evaluated on well-known instances taken from the literature and on a set of rand…
3. doi=10.3390/a12020039 year=2019 title=A Hybrid Adaptive Large Neighborhood Heuristic for a Real-Life Dial-a-Ride Problem
   authors=Slim Belhaiza
   venue=Algorithms cited_by=15
   abstract=The transportation of elderly and impaired people is commonly solved as a Dial-A-Ride Problem (DARP). The DARP aims to design pick-up and delivery vehicle routing schedules. Its main objective is to accommodate as many users as possible with a minimum operation cost. It adds realistic precedence and transit time constraints on the pairing of vehicles and customers. This paper…

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
1. doi=10.4018/ijamc.2016100102 year=2016 title=Quantum Inspired Algorithm for a VRP with Heterogeneous Fleet Mixed Backhauls and Time Windows
   authors=Meryem Berghida, Abdelmadjid Boukra
   venue=International Journal of Applied Metaheuristic Computing cited_by=12
   abstract=This paper presents a new Quantum Inspired Harmony Search algorithm with Variable Population Size QIHSVPS for a complex variant of vehicle routing problem (VRP), called HVRPMBTW (Vehicle Routing Problem with Heterogeneous fleet, Mixed Backhauls and Time Windows). This variant is characterized by a limited number of vehicles with various capacities and costs. The vehicles serve…
2. doi=10.1155/2019/5364201 year=2019 title=A Hybrid Simulated Annealing Heuristic for Multistage Heterogeneous Fleet Scheduling with Fleet Sizing Decisions
   authors=Bing Li, Xinyu Yang, Hua Xuan
   venue=Journal of Advanced Transportation cited_by=11
   abstract=This paper deals with multistage heterogeneous fleet scheduling with fleet sizing decisions (MHFS-FSD). This MHFS-FSD attempts to integrate vehicles allocation and fleet sizing decisions considering the vehicle routing of multiple vehicle types. The problem is formulated as mixed integer programming model. The matrix formulation denoting vehicle allocation scheme is explored a…
3. doi=10.23917/jiti.v21i1.17430 year=2022 title=Solving the Capacitated Vehicle Routing Problem with Heterogeneous Fleet Using Heuristic Algorithm in Poultry Distribution
   authors=Yulinda Uswatun Kasanah, Nabila Noor Qisthani, Aswan Munang
   venue=Jurnal Ilmiah Teknik Industri cited_by=2
   abstract=The problem that is often experienced in the delivery of goods from distributor to the destination is the delivery route that is not sufficient with the vehicle's capacity. This matter is crucial because it can affect the clients' trust on the shippers in the distributor. This problem can be analyzed using Capacitated Vehicle Routing Problem (CVRP) with Clarke and Wright Algor…

=== irp ===
family: cvrp
label: Inventory routing
definition: Routing plus inventory.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: IRP greedy replenishment (not_mappable), IRP local search (not_mappable)
Works:
1. doi=10.1287/trsc.2019.0934 year=2020 title=Heuristic Sequence Selection for Inventory Routing Problem
   authors=Ahmed Kheiri
   venue=Transportation Science cited_by=33
   abstract=In this paper, an improved sequence-based selection hyper-heuristic method for the Air Liquide inventory routing problem, the subject of the ROADEF/EURO 2016 challenge, is described. The organizers of the challenge have proposed a real-world problem of inventory routing as a difficult combinatorial optimization problem. An exact method often fails to find a feasible solution t…
2. doi=10.1287/trsc.1060.0160 year=2007 title=An Efficient Heuristic Algorithm for a Two-Echelon Joint Inventory and Routing Problem
   authors=Jaeheon Jung, Kamlesh Mathur
   venue=Transportation Science cited_by=29
   abstract=With an increasing emphasis on coordination in the supply chain, the inventory and distribution decisions, which in most part had been dealt with independently of each other, need to be considered jointly. This research considers a two-echelon distribution system consisting of one warehouse and N retailers that face external demand at a constant rate. Inventories are kept at r…
3. doi=10.3390/su142013563 year=2022 title=The Integrated Production-Inventory-Routing Problem with Reverse Logistics and Remanufacturing: A Two-Phase Decomposition Heuristic
   authors=Zakaria Chekoubi, Wajdi Trabelsi, Nathalie Sauer, Ilias Majdouline
   venue=Sustainability cited_by=23
   abstract=Sustainable supply chains depend on three critical decisions: production, inventory management, and distribution with reverse flows. To achieve an effective level of operational performance, policymakers must consider all these decisions, especially in Closed-Loop Supply Chains (CLSCs) with remanufacturing option. In this research paper, we address the Integrated Production-In…

=== pdptw ===
family: cvrp
label: PDPTW
definition: Pickup-delivery with windows.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: PDPTW insertion (not_mappable), PDPTW ALNS (not_mappable)
Works:
1. doi=10.1287/trsc.1050.0135 year=2006 title=An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows
   authors=Stefan Ropke, David Pisinger
   venue=Transportation Science cited_by=2281
   abstract=The pickup and delivery problem with time windows is the problem of serving a number of transportation requests using a limited amount of vehicles. Each request involves moving a number of goods from a pickup location to a delivery location. Our task is to construct routes that visit all locations such that corresponding pickups and deliveries are placed on the same route, and…
2. doi=10.2139/ssrn.6819120 year=2026 title=A Temporal-Network Constraint Programming Model for the Pickup and Delivery Problem with Time Windows
   authors=Timothy Roch, Primous Pomalegni
   venue=None cited_by=0
   abstract=We study the single-vehicle pickup and delivery problem with time windows (PDPTW), in which each pickup must precede its corresponding dropoff and all service starts must lie within prescribed time windows. We present a constraint programming (CP) formulation based on successor variables, a global Circuit constraint, position variables for route order, and conditional differen…
3. doi=10.2139/ssrn.6205944 year=2026 title=Exact Pruned Route Enumeration with Set Partitioning for Multi-Pickup and Delivery Problem with Time Windows
   authors=Conor Kikkert, Michael Forbes
   venue=None cited_by=0
   abstract=The multi-pickup and delivery problem with time windows (MPDPTW) arises in on-demand logistics applications where each delivery corresponds to one or more pickups, all of which must be completed before the delivery. Existing exact methods rely on large mixed-integer formulations with many variables and constraints that require extensive branching and cutting strategies. This p…

=== pvrp ===
family: cvrp
label: Periodic VRP
definition: Planning over several days.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Day assignment + CWS (not_mappable), Periodic local search (not_mappable)
Works:
1. doi=10.1287/trsc.26.2.86 year=1992 title=A Heuristic for the Periodic Vehicle Routing Problem
   authors=M. Gaudioso, G. Paletta
   venue=Transportation Science cited_by=97
   abstract=The paper describes a model for the optimal management of periodic deliveries of a given commodity. The goal is to schedule the deliveries according to feasible combinations of delivery days and to determine the scheduling and routing policies of the vehicles in order to minimize over the planning horizon the maximum number of vehicles simultaneously employed, i.e., the fleet…
2. doi=10.22219/jtiumm.vol20.no2.172-181 year=2019 title=A Cluster-First Route-Second Heuristic Approach to Solve The Multi-Trip Periodic Vehicle Routing Problem
   authors=Annisa Kesy Garside, Nabila Rohmatul Laili
   venue=Jurnal Teknik Industri cited_by=5
   abstract=This paper discusses periodic vehicle routing problems that allow vehicles to travel on multiple trips in a single day. It is known as the Multi-Trip Periodic Vehicles (MTPVRP) Problem Route. Cluster-first route-second (CFRS) heuristics to solve MTPVRP was proposed in this study. In phase 1, customers were divided into clusters using the formulation of integer programming. Pha…
3. doi=10.22219/jtiumm.vol20.no2.68-77 year=2019 title=A Cluster-First Route-Second Heuristic Approach to Solve The Multi-Trip Periodic Vehicle Routing Problem
   authors=Annisa Kesy Garside, Nabila Rohmatul Laili
   venue=Jurnal Teknik Industri cited_by=2
   abstract=This paper discusses periodic vehicle routing problems that allow vehicles to travel on multiple trips in a single day. It is known as the Multi-Trip Periodic Vehicles (MTPVRP) Problem Route. Cluster-first route-second (CFRS) heuristics to solve MTPVRP was proposed in this study. In phase 1, customers were divided into clusters using the formulation of integer programming. Pha…

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

=== vrpsdp ===
family: cvrp
label: Simultaneous pickup and delivery
definition: Both at the same stop.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: SDP NN (not_mappable), SDP local search (not_mappable)
Works:
1. doi=10.1051/ro/2018024 year=2018 title=A selective adaptive large neighborhood search heuristic for the profitable tour problem with simultaneous pickup and delivery services
   authors=Hayet Chentli, Rachid Ouafi, Wahiba Ramdane Cherif-Khettaf
   venue=RAIRO - Operations Research cited_by=15
   abstract=The Vehicle Routing Problem with Simultaneous Pickups and Deliveries (VRPSPD) is a variant of the Vehicle Routing Problem . In this variant, an unlimited fleet of capacitated vehicles is used to satisfy both pickup and delivery demands of each customer simultaneously. In many practical situations, such a fleet is costly. The present study extends the VRPSPD by assuming a fixed…
2. doi=10.29099/ijair.v2i2.71 year=2018 title=A Modified Meta-Heuristic Approach for Vehicle Routing Problem with Simultaneous Pickup and Delivery
   authors=Alfian Faiz, Subiyanto Subiyanto, Ulfah Mediaty Arief
   venue=International Journal of Artificial Intelligence Research cited_by=4
   abstract=The aim of this work is to develop an intelligent optimization software based on enhanced VNS meta-heuristic to tackle Vehicle Routing Problem with Simultaneous Pickup and Delivery (VRPSPD). An optimization system developed based on enhanced Variable Neighborhood Search with Perturbation Mechanism and Adaptive Selection Mechanism as the simple but effective optimization approa…
3. doi=10.3390/su172411308 year=2025 title=Urban Pickup-and-Delivery VRP with Soft Time Windows Under Travel-Time Uncertainty: An Empirical Comparison of Robust and Deterministic Approaches
   authors=Daniel Kubek
   venue=Sustainability cited_by=1
   abstract=Urban freight pickup-and-delivery services operate in road networks where travel times are highly variable due to congestion, incidents, and operational restrictions. Such variability threatens the punctuality of deliveries and complicates the design of reliable service schedules. This paper examines an urban pickup-and-delivery vehicle routing problem with soft time windows u…
