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

family: mixed

=== mdvrp ===
family: cvrp
label: Multi-depot VRP
definition: Several depots.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Depot assignment + NN (not_mappable), MD savings (not_mappable)
Works:
1. doi=10.4018/ijaec.2018010101 year=2018 title=Efficient Golden-Ball Algorithm Based Clustering to solve the Multi-Depot VRP With Time Windows
   authors=Lahcene Guezouli, Mohamed Bensakhria, Samir Abdelhamid
   venue=International Journal of Applied Evolutionary Computation cited_by=6
   abstract=In this article, the authors propose a decision support system which aims to optimize the classical Capacitated Vehicle Routing Problem by considering the existence of multiple available depots and a time window which must not be violated, that they call the Multi-Depot Vehicle Routing Problem with Time Window (MDVRPTW), and with respecting a set of criteria including: schedul…
2. doi=10.3233/978-1-61499-105-2-49 year=2012 title=A Learning Based Evolutionary Algorithm For Distributed Multi-Depot VRP
   authors=Soeanu A., Ray S., Debbabi M., Berger J., Boukhtouta A.
   venue=Frontiers in Artificial Intelligence and Applications cited_by=3
   abstract=Solving multi-depot vehicle routing problem (MDVRP) in centralized setting has known scalability issues. This paper presents an innovative multi-agent and multi-round reinforcement learning procedure over adaptive elitist solutions selected from an evolving population pool, to near optimally solve MDVRP in a distributed setting. The paper contribution is threefold: First, it i…
3. doi=10.4018/ijaie.2017010101 year=2017 title=A New Multi-Criteria Solving Procedure for Multi-Depot FSM-VRP with Time Window
   authors=Lahcene Guezouli, Samir Abdelhamid
   venue=International Journal of Applied Industrial Engineering cited_by=2
   abstract=One of the most important combinatorial optimization problems is the transport problem, which has been associated with many variants such as the HVRP and dynamic problem. The authors propose in this study a decision support system which aims to optimize the classical Capacitated Vehicle Routing Problem by considering the existence of different vehicle types (with distinct capa…

=== ovrp ===
family: cvrp
label: Open VRP
definition: Routes need not return.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Open NN (next_node_score), Open savings (next_node_score)
Works:
1. doi=10.1155/2013/874349 year=2013 title=A Heuristic Approach Based on Clarke‐Wright Algorithm for Open Vehicle Routing Problem
   authors=Tantikorn Pichpibul, Ruengsak Kawtummachai
   venue=The Scientific World Journal cited_by=30
   abstract=We propose a heuristic approach based on the Clarke‐Wright algorithm (CW) to solve the open version of the well‐known capacitated vehicle routing problem in which vehicles are not required to return to the depot after completing service. The proposed CW has been presented in four procedures composed of Clarke‐Wright formula modification, open‐route construction, two‐phase sele…
2. doi=10.26554/sti.2021.6.2.53-57 year=2021 title=Heuristic Approach For Robust Counterpart Open Capacitated Vehicle Routing Problem With Time Windows
   authors=Evi Yuliza, Fitri Maya, Siti Suzlin Supadi
   venue=Science and Technology Indonesia cited_by=6
   abstract=Garbage is one of the environmental problems. The process of transporting garbage sometimes occurs delays such as congestion and engine failure. Robust optimization model called a robust counterpart open capacitated vehicle routing problem (RCOCVRP) with time windows was formulated to get over this delays. This model has formulated with the limitation of vehicle capacity and t…
3. doi=10.70675/37fa3a3cza23dz4ac5zbaa3z1327ba608d7e year=None title=Vehicle routing problems with profits, exact and heuristic approaches
   authors=Racha El-Hajj
   venue=None cited_by=0
   abstract=Problèmes de tournées de véhicules avec profits, méthodes exactes et approchées Nous nous intéressons dans cette thèse à la résolution du problème de tournées sélectives (Team Orienteering Problem - TOP) et ses variantes. Ce problème est une extension du problème de tournées de véhicules en imposan tcertaines limitations de ressources. Nous proposons un algorithme de résolutio…

=== sdvrp ===
family: cvrp
label: Split-delivery VRP
definition: A customer may be split.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Split-delivery savings (not_mappable), Split local search (not_mappable)
Works:
1. doi=10.1287/trsc.1070.0204 year=2008 title=An Optimization-Based Heuristic for the Split Delivery Vehicle Routing Problem
   authors=Claudia Archetti, M. Grazia Speranza, Martin W. P. Savelsbergh
   venue=Transportation Science cited_by=110
   abstract=The split delivery vehicle routing problem is concerned with serving the demand of a set of customers with a fleet of capacitated vehicles at minimum cost. Contrary to what is assumed in the classical vehicle routing problem, a customer can be served by more than one vehicle, if convenient. We present a solution approach that integrates heuristic search with optimization by us…
2. doi=10.1002/net.22238 year=2024 title=A heuristic with a performance guarantee for the commodity constrained split delivery vehicle routing problem
   authors=Matteo Petris, Claudia Archetti, Diego Cattaruzza, Maxime Ogier, Frédéric Semet
   venue=Networks cited_by=8
   abstract=Abstract The commodity constrained split delivery vehicle routing problem (C‐SDVRP) is a routing problem where customer demands are composed of multiple commodities. A fleet of capacitated vehicles must serve customer demands in a way that minimizes the total routing costs. Vehicles can transport any set of commodities and customers are allowed to be visited multiple times. Ho…
3. doi=10.1287/trsc.2022.0353 year=2024 title=Exact and Heuristic Methods for the Split Delivery Vehicle Routing Problem
   authors=Mette Gamst, Richard Martin Lusby, Stefan Ropke
   venue=Transportation Science cited_by=6
   abstract=This paper describes an exact branch-and-cut (B&amp;C) algorithm for the split delivery vehicle routing problem. The underlying model is based on a previously proposed two-index vehicle flow formulation that models a relaxation of the problem. We dynamically separate two well-known classes of valid inequalities, namely capacity and connectivity cuts, and use an in-out algorith…

=== vrptw ===
family: cvrp
label: VRP with time windows
definition: Customers have time windows.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Solomon I1 (not_mappable), Solomon I2 (not_mappable)
Works:
1. doi=10.21203/rs.3.rs-4973948/v1 year=2024 title=Comparative Review of Single-Criteria and Multi-Criteria Optimisation Problems using Meta-heuristic Algorithms.
   authors=Cornelius Okechukwu, Radek Silhavy, Solomon Oyelere, Petr Silhavy
   venue=None cited_by=1
   abstract=Abstract This paper explores using metaheuristic algorithms for single-criteria optimisation problems (SCOP) and multi-criteria optimisation problems (MCOP). It highlights the critical differences between these types, noting that SCOP focusses on a single objective while MCOP deals with conflicting goals. We applied metaheuristic algorithms inspired by natural phenomena to bot…
2. doi=10.37373/jenius.v6i2.1652 year=2025 title=Optimasi rute pengangkutan sampah menggunakan metode VRPTW dan Nearest Insertion Heuristic di Kecamatan Jatisampurna
   authors=Harditriyono Putra, Andary Asvaroza Munita
   venue=JENIUS : Jurnal Terapan Teknik Industri cited_by=0
   abstract=Dinas Lingkungan Hidup melalui Unit Pelaksana Teknis Dinas Lingkungan Hidup (UPTD LH) Kecamatan Jatisampurna bertanggung jawab untuk mengelola pengangkutan sampah rumah tangga di wilayah Kecamatan Jatisampurna. Pengangkutan sampah dilakukan dengan dua metode. Metode pertama adalah pengumpulan dari rumah ke rumah dan dibuang ke TPA Sumur Batu setelah kontainer penuh. Metode ked…
3. doi=10.29303/jm.v7i4.10213 year=2025 title=Evaluating Swarm-Genetics for VRPTW: Robustness Across Seeds and Fleet Efficiency On Solomon Benchmarks
   authors=Aprizal Resky, Zaitun Zaitun, Dhirga Tandi Teppa
   venue=Mandalika Mathematics and Educations Journal cited_by=0
   abstract=The Vehicle Routing Problem with Time Windows (VRPTW) is a challenging NP-hard problem in logistics optimization. This study evaluates a Swarm-Genetics algorithm, a hybrid method combining Particle Swarm Optimization (PSO) and Genetic Algorithm (GA) with swarm regeneration and adaptive parameter control. The algorithm was tested on 57 Solomon benchmark instances (C, R, RC) und…

=== kp_01 ===
family: knapsack
label: 0-1 knapsack
definition: Take or leave each item.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Density greedy (not_mappable), Greedy + swap (not_mappable)
Works:
1. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…
2. doi=10.29007/fx82 year=2018 title=An Iterated Semi-Greedy Algorithm for the 0-1 Quadratic Knapsack Problem
   authors=Leticia Leonor Pinto Alva, Alexander J. Benavides
   venue=EasyChair Preprints cited_by=1
   abstract=This paper presents a new Iterated Semi-Greedy Algorithm (ISGA) for the 0-1 Quadratic Knapsack Problem.The proposed ISGA is easier to implement, runs faster, and produces comparable results than state-of-the-art methods. Computational evaluation is performed over a benchmark with large instances of 1000 and 2000 objects.
3. doi=10.23956/ijermt.v6i7.181 year=2018 title=Clustering Analysis of Greedy Heuristic Method in Zero_One Knapsack Problem
   authors=V. Selvi
   venue=International Journal of Emerging Research in Management and Technology cited_by=0
   abstract=Knapsack problem is a surely understood class of optimization problems, which tries to expand the profit of items in a knapsack without surpassing its capacity, Knapsack can be solved by several algorithms such like Greedy, dynamic programming, Branch &amp; bound etc. The solution to the zero_one knapsack problem (KP) can be viewed as the result of a sequence of decision. Clus…

=== kp_bounded ===
family: knapsack
label: Bounded knapsack
definition: Bounded copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Bounded density greedy (not_mappable), Core algorithm heuristic (not_mappable)
Works:
1. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…
2. doi=10.2139/ssrn.170989 year=1999 title=Complexity, Bounded Rationality, and Heuristic Search
   authors=William Bentley MacLeod
   venue=None cited_by=0
   abstract=This paper explores the use of heuristic search algorithms for modeling human decision making. It is shown that this algorithm is consistent with many observed behavioral regularities, and may help explain deviations from rational choice. The main insight is that the heuristic function can be viewed as formal implementation of one aspect of emotion as discussed in {Descarte's…
3. doi=10.2139/ssrn.6203952 year=2026 title=Knapsack Problem with All-Neighbors  Constraint on Bounded-Treewidth or Chordal Directed Graphs
   authors=Shih-Chieh Liao, Wing-Kai Hon
   venue=None cited_by=0
   abstract=We study the Knapsack Problem under all in-neighbor constraints (KPaN) on directed graphs, where an item can be selected only if all its in-neighbors are also selected. We focus on two special cases: when the underlying undirected graph has bounded treewidth, and when it is chordal. For both, we develop pseudo-polynomial time algorithms that run in time polynomial in the numbe…

=== kp_md ===
family: knapsack
label: Multidimensional knapsack
definition: Several resource constraints.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Surrogate density greedy (not_mappable), MDKP local search (not_mappable)
Works:
1. doi=10.1162/106365605774666886 year=2005 title=Empirical Analysis of Locality, Heritability and Heuristic Bias in Evolutionary Algorithms: A Case Study for the Multidimensional Knapsack Problem
   authors=Günther R. Raidl, Jens Gottlieb
   venue=Evolutionary Computation cited_by=70
   abstract=Our main aim is to provide guidelines and practical help for the design of appropriate representations and operators for evolutionary algorithms (EAs). For this purpose, we propose techniques to obtain a better understanding of various effects in the interplay of the representation and the operators. We study six different representations and associated variation operators in…
2. doi=10.1162/evco_a_00145 year=2016 title=A Case Study of Controlling Crossover in a Selection Hyper-heuristic Framework Using the Multidimensional Knapsack Problem
   authors=John H. Drake, Ender Özcan, Edmund K. Burke
   venue=Evolutionary Computation cited_by=43
   abstract=Hyper-heuristics are high-level methodologies for solving complex problems that operate on a search space of heuristics. In a selection hyper-heuristic framework, a heuristic is chosen from an existing set of low-level heuristics and applied to the current solution to produce a new solution at each point in the search. The use of crossover low-level heuristics is possible in a…
3. doi=10.1108/k-09-2013-0201 year=2014 title=A genetic programming hyper-heuristic for the multidimensional knapsack problem
   authors=John H Drake, Matthew Hyde, Khaled Ibrahim, Ender Ozcan
   venue=Kybernetes cited_by=40
   abstract=Purpose – Hyper-heuristics are a class of high-level search techniques which operate on a search space of heuristics rather than directly on a search space of solutions. The purpose of this paper is to investigate the suitability of using genetic programming as a hyper-heuristic methodology to generate constructive heuristics to solve the multidimensional 0-1 knapsack problem…

=== kp_multiple ===
family: knapsack
label: Multiple knapsack
definition: Several knapsacks.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: MKP greedy assign (not_mappable), MKP local search (not_mappable)
Works:
1. doi=10.1145/2541012.2541014 year=2013 title=A fast and scalable multidimensional multiple-choice knapsack heuristic
   authors=Hamid Shojaei, Twan Basten, Marc Geilen, Azadeh Davoodi
   venue=ACM Transactions on Design Automation of Electronic Systems cited_by=32
   abstract=Many combinatorial optimization problems in the embedded systems and design automation domains involve decision making in multidimensional spaces. The multidimensional multiple-choice knapsack problem (MMKP) is among the most challenging of the encountered optimization problems. MMKP problem instances appear for example in chip multiprocessor runtime resource management and in…
2. doi=10.3390/math10040602 year=2022 title=A Memetic Algorithm with a Novel Repair Heuristic for the Multiple-Choice Multidimensional Knapsack Problem
   authors=Jaeyoung Yang, Yong-Hyuk Kim, Yourim Yoon
   venue=Mathematics cited_by=11
   abstract=We propose a memetic algorithm for the multiple-choice multidimensional knapsack problem (MMKP). In this study, we focus on finding good solutions for the MMKP instances, for which feasible solutions rarely exist. To find good feasible solutions, we introduce a novel repair heuristic based on the tendency function and a genetic search for the function approximation. Even when…
3. doi=10.31219/osf.io/6u3qw year=2021 title=Simulated Annealing Algorithm for the Multiple Choice Multidimensional Knapsack Problem
   authors=Shalin Shah
   venue=None cited_by=1
   abstract=The multiple choice multidimensional knapsack problem (MCMK) is a harder version of the 0/1 knapsack problem, and is ever more complex than the 0/1 multidimensional knapsack problem. In MCMK, there are several groups of items. The objective is to maximize the value (profit) by choosing exactly 1 item from each group such that all the constraints are satisfied. It is difficult…

=== kp_unbounded ===
family: knapsack
label: Unbounded knapsack
definition: Unlimited copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Unbounded density greedy (not_mappable), Greedy by value (not_mappable)
Works:
1. doi=10.3390/math12121878 year=2024 title=An Improved Unbounded-DP Algorithm for the Unbounded Knapsack Problem with Bounded Coefficients
   authors=Yang Yang
   venue=Mathematics cited_by=1
   abstract=Benchmark instances for the unbounded knapsack problem are typically generated according to specific criteria within a given constant range R, and these instances can be referred to as the unbounded knapsack problem with bounded coefficients (UKPB). In order to increase the difficulty of solving these instances, the knapsack capacity C is usually set to a very large value. Whi…
2. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== bp_1d_offline ===
family: online_bin_packing
label: 1D offline bin packing
definition: Full list known; sorting allowed.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: First Fit Decreasing (not_mappable), Karmarkar-Karp (not_mappable)
Works:
1. doi=10.1137/0602019 year=1981 title=A Tight Asymptotic Bound for Next-Fit-Decreasing Bin-Packing
   authors=B. S. Baker, E. G. Coffman, Jr.
   venue=SIAM Journal on Algebraic Discrete Methods cited_by=54
   abstract=In this note we derive a tight asymptotic bound on the relative performance of the Next-Fit-Decreasing approximation rule for classical one-dimensional bin-packing. The proof provides a novel application of certain well-known sequences of unit fractions. Potential applications are mentioned.
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

=== bp_cardinality ===
family: online_bin_packing
label: Cardinality-constrained packing
definition: Max items per bin.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Cardinality-aware Best Fit (bin_score), Cardinality FFD (not_mappable)
Works:
1. doi=10.1137/050639065 year=2006 title=Online Bin Packing with Cardinality Constraints
   authors=Leah Epstein
   venue=SIAM Journal on Discrete Mathematics cited_by=46
   abstract=We consider a one‐dimensional storage system where each container can store a bounded amount of capacity as well as a bounded number of items $k\geq 2$. This defines the (standard) bin packing problem with cardinality constraints, which is an important version of bin packing. Following previous work on the unbounded space online problem, we establish the exact best competitive…
2. doi=10.1007/s00500-022-07118-4 year=2022 title=A hierarchical hyper-heuristic for the bin packing problem
   authors=Francesca Guerriero, Francesco Paolo Saccomanno
   venue=Soft Computing cited_by=18
   abstract=Abstract This paper addresses the two-dimensional irregular bin packing problem, whose main aim is to allocate a given set of irregular pieces to larger rectangular containers (bins), while minimizing the number of bins required to contain all pieces. To solve the problem under study a dynamic hierarchical hyper-heuristic approach is proposed. The main idea of the hyper-heuris…
3. doi=10.3390/electronics14101956 year=2025 title=Neural-Driven Constructive Heuristic for 2D Robotic Bin Packing Problem
   authors=Mariusz Kaleta, Tomasz Śliwiński
   venue=Electronics cited_by=4
   abstract=This study addresses the two-dimensional weakly homogeneous Bin Packing Problem (2D-BPP) in the context of robotic packing, where items must be arranged in a manner feasible for robotic manipulation. Traditional heuristics for this NP-hard problem often lack adaptability across diverse datasets, while metaheuristics typically suffer from slow convergence. To overcome these lim…

=== bp_variable ===
family: online_bin_packing
label: Variable-sized bins
definition: Several bin sizes.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Any Fit variable bins (not_mappable), Variable-size FFD (not_mappable)
Works:
1. doi=10.1137/0215016 year=1986 title=Variable Sized Bin Packing
   authors=D. K. Friesen, M. A. Langston
   venue=SIAM Journal on Computing cited_by=173
   abstract=In the classical bin packing problem one seeks to pack a list of pieces in the minimum space using unit capacity bins. This paper addresses the more general problem in which a fixed collection of bin sizes is allowed. Three efficient approximation algorithms are described and analyzed. They guarantee asymptotic worst-case performance bounds of 2, ${3 / 2}$ and ${4 / 3}$.
2. doi=10.1137/0216012 year=1987 title=An Efficient Approximation Scheme for Variable-Sized Bin Packing
   authors=Frank D. Murgolo
   venue=SIAM Journal on Computing cited_by=60
   abstract=In the classical bin packing problem one is required to pack a given list of items into the smallest possible number of unit-sized bins. Because this problem is NP-complete, researchers have tried to find efficient approximation algorithms that solve this problem in a reasonable amount of time. If we let $A(I)$ be the number of bins used by algorithm A to pack a list of items…
3. doi=10.1137/s0097539702412908 year=2003 title=New Bounds for Variable-Sized Online Bin Packing
   authors=Steven S. Seiden, Rob van Stee, Leah Epstein
   venue=SIAM Journal on Computing cited_by=43
   abstract=In the variable-sized online bin packing problem, one has to assign items to bins one by one. The bins are drawn from some fixed set of sizes, and the goal is to minimize the sum of the sizes of the bins used. We present new algorithms for this problem and show upper bounds for them which improve on the best previous upper bounds. We also show the first general lower bounds fo…

=== obp_1d ===
family: online_bin_packing
label: 1D online bin packing
definition: Irrevocable assignment of arriving items.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: First Fit (bin_score), Best Fit (bin_score)
Works:
1. doi=10.1145/359436.359453 year=1977 title=A comparison of next-fit, first-fit, and best-fit
   authors=Carter Bays
   venue=Communications of the ACM cited_by=59
   abstract=“Next-fit” allocation differs from first-fit in that a first-fit allocator commences its search for free space at a fixed end of memory, whereas a next-fit allocator commences its search wherever it previously stopped searching. This strategy is called “modified first-fit” by Shore [2] and is significantly faster than the first-fit allocator. To evaluate the relative efficienc…
2. doi=10.1145/360933.360949 year=1975 title=On the external storage fragmentation produced by first-fit and best-fit allocation strategies
   authors=John E. Shore
   venue=Communications of the ACM cited_by=42
   abstract=Published comparisons of the external fragmentation produced by first-fit and best-fit memory allocation have not been consistent. Through simulation, a series of experiments were performed in order to obtain better data on the relative performance of first-fit and best-fit and a better understanding of the reasons underlying observed differences. The time-memory-product effic…
3. doi=10.1007/s00453-021-00844-5 year=2021 title=Best Fit Bin Packing with Random Order Revisited
   authors=Susanne Albers, Arindam Khan, Leon Ladewig
   venue=Algorithmica cited_by=17
   abstract=Abstract Best Fit is a well known online algorithm for the bin packing problem, where a collection of one-dimensional items has to be packed into a minimum number of unit-sized bins. In a seminal work, Kenyon [SODA 1996] introduced the (asymptotic) random order ratio as an alternative performance measure for online algorithms. Here, an adversary specifies the items, but the or…

=== strip_2d ===
family: online_bin_packing
label: 2D strip packing
definition: Pack rectangles into a strip.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Bottom-Left (not_mappable), Best-Fit skyline (not_mappable)
Works:
1. doi=10.1287/ijoc.11.4.345 year=1999 title=Heuristic and Metaheuristic Approaches for a Class of Two-Dimensional Bin Packing Problems
   authors=Andrea Lodi, Silvano Martello, Daniele Vigo
   venue=INFORMS Journal on Computing cited_by=264
   abstract=Two-dimensional bin packing problems consist of allocating, without overlapping, a given set of small rectangles (items) to a minimum number of large identical rectangles (bins), with the edges of the items parallel to those of the bins. According to the specific application, the items may either have a fixed orientation or they can be rotated by 90°. In addition, it may or no…
2. doi=10.1287/opre.1060.0293 year=2006 title=A New Bottom-Left-Fill Heuristic Algorithm for the Two-Dimensional Irregular Packing Problem
   authors=Edmund Burke, Robert Hellier, Graham Kendall, Glenn Whitwell
   venue=Operations Research cited_by=142
   abstract=This paper presents a new heuristic algorithm for the two-dimensional irregular stock-cutting problem, which generates significantly better results than the previous state of the art on a wide range of established benchmark problems. The developed algorithm is able to pack shapes with a traditional line representation, and it can also pack shapes that incorporate circular arcs…
3. doi=10.1287/opre.1100.0833 year=2010 title=An Exact Algorithm for the Two-Dimensional Strip-Packing Problem
   authors=Marco Antonio Boschetti, Lorenza Montaletti
   venue=Operations Research cited_by=56
   abstract=This paper considers the two-dimensional strip-packing problem (2SP) in which a set of rectangular items have to be orthogonally packed, without overlapping, into a strip of a given width and infinite height by minimizing the overall height of the packing. The 2SP is NP-hard in the strong sense and finds many practical applications. We propose reduction procedures, lower and u…

=== tsp_asymmetric ===
family: tsp
label: Asymmetric TSP
definition: Directed distances, d(i,j) may differ from d(j,i).
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Directed Nearest Neighbor (next_node_score), Directed 3-opt (move_selector)
Works:
1. doi=10.38032/jea.2024.01.004 year=2024 title=Improvement of the Nearest Neighbor Heuristic Search Algorithm for Traveling Salesman Problem
   authors=Md. Ziaur Rahman, Sakibur Rahamn Sheikh, Ariful Islam, Md. Azizur Rahman
   venue=Journal of Engineering Advancements cited_by=7
   abstract=The Traveling Salesman Problem (TSP) is classified as a non-deterministic polynomial (NP) hard problem, which has found widespread application in several scientific and technological domains. Due to its NP-hard nature, it is very hard to solve effectively and efficiently. Despite this rationale, a multitude of optimization approaches have been proposed and developed by scienti…
2. doi=10.55606/jurrimipa.v2i2.1614 year=2023 title=Perbandingan Algoritma Cheapest Insertion Heuristic Dan Nearest Neighbor Dalam Menyelesaikan Traveling Salesman Problem
   authors=Rizki Putra Sinaga, Faridawaty Marpaung
   venue=JURNAL RISET RUMPUN MATEMATIKA DAN ILMU PENGETAHUAN ALAM cited_by=1
   abstract=The main problem of the Traveling Salesman Problem is that a salesman travels to several places to go with a known distance and then returns to his original place by using the shortest route from his journey, and all the places the salesman goes to are only allowed once. This research focuses on the problem of distributing goods at PT. The Medan Nugraha Ekakurir (JNE) route wi…

=== tsp_metric ===
family: tsp
label: Metric TSP
definition: Distances satisfy the triangle inequality.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Nearest Neighbor (next_node_score), Christofides (not_mappable)
Works:
1. doi=10.1007/s00521-022-07816-y year=2022 title=Solving TSP by using combinatorial Bees algorithm with nearest neighbor method
   authors=Murat Sahin
   venue=Neural Computing and Applications cited_by=33
   abstract=Abstract Bees Algorithm (BA) is a popular meta-heuristic method that has been used in many different optimization areas for years. In this study, a new version of combinatorial BA is proposed and explained in detail to solve Traveling Salesman Problems (TSPs). The nearest neighbor method was used in the population generation section of BA, and the Multi-Insert function was add…
2. doi=10.3390/info7010017 year=2016 title=Nearest Neighbor Search in the Metric Space of a Complex Network for Community Detection
   authors=Suman Saha, Satya Ghrera
   venue=Information cited_by=6
   abstract=The objective of this article is to bridge the gap between two important research directions: (1) nearest neighbor search, which is a fundamental computational tool for large data analysis; and (2) complex network analysis, which deals with large real graphs but is generally studied via graph theoretic analysis or spectral analysis. In this article, we have studied the nearest…
3. doi=10.31219/osf.io/qhg4v year=2024 title=Graph Similarity Metric for Modifying K Nearest Neighbor for Classifying Texts
   authors=Taeho Jo
   venue=None cited_by=0
   abstract=This article proposes the modified KNN (K Nearest Neighbor)algorithm which receives a graph as its input data and is applied tothe text categorization. The graph is more graphical forrepresenting a word and the synergy effect between the textcategorization and the word categorization is expected by combiningthem with each other. In this research, we propose the similaritymetri…

=== tsp_open ===
family: tsp
label: Open TSP / Hamiltonian path
definition: Path visits each city once, no return.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Path Nearest Neighbor (next_node_score), Cheapest Insertion path (not_mappable)
Works:
1. doi=10.1111/itor.12419 year=2017 title=A GRASP heuristic using path‐relinking and restarts for the Steiner traveling salesman problem
   authors=Ruben Interian, Celso C. Ribeiro
   venue=International Transactions in Operational Research cited_by=25
   abstract=Abstract The traveling salesman problem (TSP) is one of the most studied problems in combinatorial optimization. Given a set of nodes and the distances between them, it consists in finding the shortest route that visits each node exactly once and returns to the first. Nevertheless, more flexible and applicable formulations of this problem exist and can be considered. The Stein…
2. doi=10.11591/tijee.v15i2.1554 year=2015 title=Heuristic Approaches to Solve Traveling Salesman Problem
   authors=Malik Muneeb Abid, Iqbal Muhammad
   venue=TELKOMNIKA Indonesian Journal of Electrical Engineering cited_by=5
   abstract=This paper provides the survey of the heuristics solution approaches for the traveling salesman problem (TSP). TSP is easy to understand, however, it is very difficult to solve. Due to complexity involved with exact solution approaches it is hard to solve TSP within feasible time. That’s why different heuristics are generally applied to solve TSP. Heuristics to solve TSP are p…
3. doi=10.1088/1742-6596/1218/1/012038 year=2019 title=New heuristic algorithm for traveling salesman problem
   authors=M L Shahab
   venue=Journal of Physics: Conference Series cited_by=2
   abstract=Abstract Traveling salesman problem (TSP) is a basis for many bigger problems. If we can find an efficient method (that produce a good result in a short time) to solve the TSP, then we will also be able to solve many other problems. In this research, we proposed a new heuristic algorithm for TSP. We used 80 problems from TSPLIB to test the proposed heuristic algorithm. The pro…
