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

=== cvrp_clustered ===
family: cvrp
label: Clustered VRP
definition: Customers in clusters.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Cluster-first NN (next_node_score), Sweep-like angular NN (next_node_score)
Works:
1. doi=10.61194/sijl.v2i1.187 year=2024 title=Capacitated Vehicle Routing Problem (CVRP) with Sweep and Nearest Neighbor Algorithm
   authors=Erly Ekayanti, Sugianto, Imaduddin Bachtiar Efendi
   venue=Sinergi International Journal of Logistics cited_by=5
   abstract=The Capacitated Vehicle Routing Problem (CVRP) presents significant challenges in shipping route optimization and logistics management. These challenges include balancing vehicle capacity, minimizing travel distance, and efficiently grouping delivery points, all of which are crucial for enhancing operational efficiency and reducing costs. This research aims to apply a combinat…
2. doi=10.55732/jrt.v3i2.263 year=2017 title=VEHICLE ROUTING PROBLEM DENGAN APLIKASI METODE NEAREST NEIGHBOR
   authors=Waluyo Prasetyo, Muchammad Tamyiz
   venue=Journal of Research and Technology cited_by=4
   abstract=Transportation problem is just like inventory, this is an activity in logistics area. This activity is possible to make some production in one place and to consume them in another place. The aim of this research were to evaluate the existing network distribution model performance and to provide sugestions to proper the networkdistribution model used. The applied metode to achi…
3. doi=10.1088/1742-6596/2421/1/012027 year=2023 title=Study vehicle routing problem using Nearest Neighbor Algorithm
   authors=Rio Ferdiani Harahap, Sawaluddin
   venue=Journal of Physics: Conference Series cited_by=0
   abstract=Abstract Vehicle routing problem (VRP) has a key role in logistics management. VRP plays a role in designing the optimal route used by a number of vehicles placed at the depot to serve a number of customers with known requests. To solve the VRP, the nearest neighbor algorithm used to get the most optimal results. The Nearest Neighbor algorithm is a heuristic method which is do…

=== cvrp_construct ===
family: cvrp
label: Constructive CVRP
definition: Build routes customer by customer.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Nearest feasible (next_node_score), Savings as next-node score (next_node_score)
Works:
1. doi=10.1088/1742-6596/2421/1/012045 year=2023 title=Clarke and Wright Savings Algorithm as Solutions Vehicle Routing Problem with Simultaneous Pickup Delivery (VRPSPD)
   authors=Fadlah Tunnisaki, Sutarman
   venue=Journal of Physics: Conference Series cited_by=7
   abstract=Abstract This study aims to establish the mathematical model Vehicle Routing Problem with Simultaneous Pickup and Delivery (VRPSPD) on 3 kg of LPG gas distribution and its solution using the method of Clarke and Wright Savings . Data used include a list of areas of consumers, service delivery company, the amount of consumer demand, vehicle type and vehicle capacity. The data i…
2. doi=10.24002/ijieem.v1i1.2292 year=2019 title=Proposed Modified Clarke-Wright Saving Algorithm for Capacitated Vehicle Routing Problem
   authors=A.K. Pamosoaji, P.K. Dewa, J.V. Krisnanta
   venue=International Journal of Industrial Engineering and Engineering Management cited_by=4
   abstract=A multi-objective distribution routing algorithm by using modified Clarke and Wright Saving algorithm is presented. The problem to solve is to deliver loads to a number of outlets based load requirement. The objective function to minimize is the distance saving and traveling time of the resulted route started from depot to the outlets and return to the original depot. Problem…
3. doi=10.59953/paperasia.v42i3b.1412 year=2026 title=Harmony Search with Clarke and Wright Savings in Solving the Location-Allocation Vehicle Routing Problem
   authors=Farahanim Misni, Nor Izzati Jaini, Najihah Mohamed
   venue=PaperASIA cited_by=0
   abstract=In the vehicle routing problem, location-allocation is a major issue that needs to be considered. While searching for the shortest route between facilities, the determination of a strategic location to establish the facilities is also important. This implies that in the location-allocation vehicle routing problem, the main objectives are to identify the number and position of…

=== cvrp_dynamic ===
family: cvrp
label: Dynamic VRP
definition: Requests arrive online.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Online feasible NN (next_node_score), Rolling-horizon 2-opt (not_mappable)
Works:
1. doi=10.1287/trsc.1060.0166 year=2006 title=Solving a Dynamic and Stochastic Vehicle Routing Problem with a Sample Scenario Hedging Heuristic
   authors=Lars M. Hvattum, Arne Løkketangen, Gilbert Laporte
   venue=Transportation Science cited_by=154
   abstract=The statement of the standard vehicle routing problem cannot always capture all aspects of real-world applications. As a result, extensions or modifications to the model are warranted. Here we consider the case when customers can call in orders during the daily operations; i.e., both customer locations and demands may be unknown in advance. This is modeled as a combined dynami…
2. doi=10.1002/net.20182 year=2007 title=A branch‐and‐regret heuristic for stochastic and dynamic vehicle routing problems
   authors=Lars Magnus Hvattum, Arne Løkketangen, Gilbert Laporte
   venue=Networks cited_by=59
   abstract=Abstract This paper describes a new Branch‐and‐Regret Heuristic for a class of dynamic and stochastic vehicle routing problems. This work is motivated by a real‐life problem faced by a major transporter in Norway. The heuristic uses stochastic information during the solution process. The new method is shown to be superior to previous heuristics that are uniquely based on a pur…
3. doi=10.47344/sdubnts.v62i1.959 year=2024 title=Stochastic dynamic vehicle routing problem survey
   authors=Yernar Akhmetbek
   venue=Suleyman Demirel University Bulletin Natural and Technical Sciences cited_by=3
   abstract=The present article aims to offer an exhaustive and in-depth investigation of the Stochastic Dynamic Vehicle Routing Problem, which remains a significant challenge in the field of transportation logistics. To achievethis objective, we will undertake a meticulous analysis of the latest cutting-edge techniques and methodologies deployed to tackle this complex optimization proble…

=== cvrp_large ===
family: cvrp
label: Large-scale CVRP
definition: Hundreds of customers.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Restricted NN (next_node_score), Ruin-and-recreate (not_mappable)
Works:
1. doi=10.1088/1757-899x/852/1/012090 year=2020 title=Comparison study between nearest neighbor and farthest insert algorithms for solving VRP model using heuristic method approach
   authors=Wilson Kosasih, Ahmad, Lithrone Laricha Salomon, Febricky
   venue=IOP Conference Series: Materials Science and Engineering cited_by=5
   abstract=Abstract In Indonesia, transportation costs from physical distribution still tend to be high because not all business people can optimize their distribution routes. This paper discusses a comparative study between Nearest Neighbor and Farthest Insert algorithms in solving a Vehicle Routing Problem (VRP) model. Aim of this study is to determine the most optimum distribution rou…
2. doi=10.1101/2021.02.05.429957 year=2021 title=Large-scale tandem mass spectrum clustering using fast nearest neighbor searching
   authors=Wout Bittremieux, Kris Laukens, William Stafford Noble, Pieter C. Dorrestein
   venue=None cited_by=5
   abstract=Abstract Rationale Advanced algorithmic solutions are necessary to process the ever increasing amounts of mass spectrometry data that is being generated. Here we describe the falcon spectrum clustering tool for efficient clustering of millions of MS/MS spectra. Methods falcon succeeds in efficiently clustering large amounts of mass spectral data using advanced techniques for f…
3. doi=10.61194/sijl.v2i1.187 year=2024 title=Capacitated Vehicle Routing Problem (CVRP) with Sweep and Nearest Neighbor Algorithm
   authors=Erly Ekayanti, Sugianto, Imaduddin Bachtiar Efendi
   venue=Sinergi International Journal of Logistics cited_by=5
   abstract=The Capacitated Vehicle Routing Problem (CVRP) presents significant challenges in shipping route optimization and logistics management. These challenges include balancing vehicle capacity, minimizing travel distance, and efficiently grouping delivery points, all of which are crucial for enhancing operational efficiency and reducing costs. This research aims to apply a combinat…

=== cvrp_minveh ===
family: cvrp
label: Minimise number of vehicles
definition: Primary objective is fleet size.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Parallel cheapest insertion (not_mappable), Capacity-tight NN (next_node_score)
Works:
1. doi=10.3390/vehicles7020061 year=2025 title=NeuHH: A Neuromorphic-Inspired Hyper-Heuristic Framework for Solving the Capacitated Single-Allocation p-Hub Location Routing Problem
   authors=Kassem Danach, Hassan Harb, Semaan Amine, Mariem Belhor
   venue=Vehicles cited_by=6
   abstract=This paper introduces a novel neuromorphic-inspired hyper-heuristic framework (NeuHH) for solving the Capacitated Single-Allocation p-Hub Location Routing Problem (CSAp-HLRP), a challenging combinatorial optimization problem that jointly addresses hub location decisions, capacity constraints, and vehicle routing. The proposed framework employs Spiking Neural Networks (SNNs) as…
2. doi=10.1088/1757-899x/852/1/012090 year=2020 title=Comparison study between nearest neighbor and farthest insert algorithms for solving VRP model using heuristic method approach
   authors=Wilson Kosasih, Ahmad, Lithrone Laricha Salomon, Febricky
   venue=IOP Conference Series: Materials Science and Engineering cited_by=5
   abstract=Abstract In Indonesia, transportation costs from physical distribution still tend to be high because not all business people can optimize their distribution routes. This paper discusses a comparative study between Nearest Neighbor and Farthest Insert algorithms in solving a Vehicle Routing Problem (VRP) model. Aim of this study is to determine the most optimum distribution rou…
3. doi=10.1515/comp-2015-0004 year=2015 title=Various heuristic algorithms to minimise the two-page crossing
numbers of graphs
   authors=Hongmei He, Ana Sălăgean, Erkki Mäkinen, Imrich Vrt’o
   venue=Open Computer Science cited_by=3
   abstract=Abstract We propose several new heuristics for the twopage book crossing problem, which are based on recent algorithms for the corresponding one-page problem. Especially, the neural network model for edge allocation is combined for the first time with various one-page algorithms. We investigate the performance of the new heuristics by testing them on various benchmark test sui…

=== cvrp_multitrip ===
family: cvrp
label: Multi-trip VRP
definition: A vehicle may do several routes.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Multi-trip NN (next_node_score), Trip packing + routing (not_mappable)
Works:
1. doi=10.22219/jtiumm.vol20.no2.172-181 year=2019 title=A Cluster-First Route-Second Heuristic Approach to Solve The Multi-Trip Periodic Vehicle Routing Problem
   authors=Annisa Kesy Garside, Nabila Rohmatul Laili
   venue=Jurnal Teknik Industri cited_by=5
   abstract=This paper discusses periodic vehicle routing problems that allow vehicles to travel on multiple trips in a single day. It is known as the Multi-Trip Periodic Vehicles (MTPVRP) Problem Route. Cluster-first route-second (CFRS) heuristics to solve MTPVRP was proposed in this study. In phase 1, customers were divided into clusters using the formulation of integer programming. Pha…
2. doi=10.22219/jtiumm.vol20.no2.68-77 year=2019 title=A Cluster-First Route-Second Heuristic Approach to Solve The Multi-Trip Periodic Vehicle Routing Problem
   authors=Annisa Kesy Garside, Nabila Rohmatul Laili
   venue=Jurnal Teknik Industri cited_by=2
   abstract=This paper discusses periodic vehicle routing problems that allow vehicles to travel on multiple trips in a single day. It is known as the Multi-Trip Periodic Vehicles (MTPVRP) Problem Route. Cluster-first route-second (CFRS) heuristics to solve MTPVRP was proposed in this study. In phase 1, customers were divided into clusters using the formulation of integer programming. Pha…
3. doi=10.21203/rs.3.rs-2761446/v1 year=2023 title=Multi-Trip Multi-Compartment Vehicle Routing Problem with Backhauls
   authors=Sukhpal Ramanand, KAUSHAL KUMAR
   venue=None cited_by=0
   abstract=Abstract The Multi-Trip Multi-Compartment Vehicle Routing Problem with Backhauls (MTMCVRPB) is a complex optimization problem that involves finding the most efficient routes for a heterogeneous fleet of multi-compartment vehicles to transport heterogeneous commodities simultaneously. The problem involves making deliveries and pickups while taking into account capacity constrai…

=== dcvrp ===
family: cvrp
label: Distance-constrained VRP
definition: Route length cap.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Length-feasible NN (next_node_score), DCVRP savings (next_node_score)
Works:
1. doi=10.1007/bf02296341 year=2000 title=Optimal Scaling by Alternating Length-Constrained Nonnegative Least Squares, with Application to Distance-Based Analysis
   authors=Patrick J. F. Groenen, Bart-Jan van Os, Jacqueline J. Meulman
   venue=Psychometrika cited_by=8
   abstract=An important feature of distance-based principal components analysis, is that the variables can be optimally transformed. For monotone spline transformation, a nonnegative least-squares problem with a length constraint has to be solved in each iteration. As an alternative algorithm to Lawson and Hanson (1974), we propose the Alternating Length-Constrained Non-Negative Least-Sq…
2. doi=10.14710/transmisi.22.4.123-129 year=2020 title=ALGORITMA K-NN DENGAN EUCLIDEAN DISTANCE UNTUK PREDIKSI HASIL PENGGERGAJIAN KAYU SENGON
   authors=Anton Yudhana, Sunardi Sunardi, Agus Jaka Sri Hartanta
   venue=Transmisi cited_by=2
   abstract=Industri dengan bahan dasar kayu Sengon (Albizia falcataria) banyak diselenggarakan oleh masyarakat Indonesia untuk keperluan furnitur, instrumen desain interior, bahan kayu plywood, pelapis dinding, plafon, dudukan cor, dan bahan baku kertas. Penggergajian merupakan proses pemotongan batang kayu untuk mendapatkan potongan-potongan yang lebih kecil sesuai dengan variasi dimens…
3. doi=10.1002/eng2.70511 year=2025 title=Crew Rostering in Long‐Distance Freight Railways: A Multi‐Depot
                    <scp>VRP</scp>
                    ‐Based Heuristic Approach
   authors=Franco Collodetti Mazioli, Rodrigo de Alvarenga Rosa, João Henrique Brunow Barbosa, Hendrigo Venes
   venue=Engineering Reports cited_by=0
   abstract=ABSTRACT Efficient crew management is a critical challenge in long‐distance freight rail operations, where shift limits, depot logistics, and labor regulations must be jointly considered. This paper addresses the Railway Crew Rostering Problem by proposing a novel mathematical model inspired by the Vehicle Routing Problem with Multiple Depots and Multiple Trips (VRP‐MD‐MT). Th…

=== bp_batch ===
family: online_bin_packing
label: Batch packing
definition: Items arrive in batches.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Batch Best Fit (bin_score), Sort-within-batch FFD (not_mappable)
Works:
1. doi=10.1111/itor.12030 year=2013 title=An improved best‐fit heuristic for the orthogonal strip packing problem
   authors=Jannes Verstichel, Patrick De Causmaecker, Greet Vanden Berghe
   venue=International Transactions in Operational Research cited_by=25
   abstract=Abstract The best‐fit heuristic is a simple and powerful tool for solving the two‐dimensional orthogonal strip packing problem. It is the most efficient constructive heuristic on a wide range of rectangular strip packing benchmark problems. In this paper, the results of the original best‐fit heuristic are further improved by adding new item orderings and item placement strateg…
2. doi=10.1007/s00453-021-00844-5 year=2021 title=Best Fit Bin Packing with Random Order Revisited
   authors=Susanne Albers, Arindam Khan, Leon Ladewig
   venue=Algorithmica cited_by=17
   abstract=Abstract Best Fit is a well known online algorithm for the bin packing problem, where a collection of one-dimensional items has to be packed into a minimum number of unit-sized bins. In a seminal work, Kenyon [SODA 1996] introduced the (asymptotic) random order ratio as an alternative performance measure for online algorithms. Here, an adversary specifies the items, but the or…
3. doi=10.1002/rsa.10037 year=2002 title=Linear waste of best fit bin packing on skewed distributions
   authors=Claire Kenyon, Michael Mitzenmacher
   venue=Random Structures &amp; Algorithms cited_by=4
   abstract=Abstract We prove that Best Fit bin packing has linear waste on the discrete distribution U { j , k } (where items are drawn uniformly from the set {1/ k , 2/ k , …, j / k }) for sufficiently large k when j = α k and 0.66 ≤ α &lt; 2/3. Our results extend to continuous skewed distributions, where items are drawn uniformly on [0, a ], for 0.66 ≤ a &lt; 2/3. This implies that the…

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
2. doi=10.1007/s00453-021-00844-5 year=2021 title=Best Fit Bin Packing with Random Order Revisited
   authors=Susanne Albers, Arindam Khan, Leon Ladewig
   venue=Algorithmica cited_by=17
   abstract=Abstract Best Fit is a well known online algorithm for the bin packing problem, where a collection of one-dimensional items has to be packed into a minimum number of unit-sized bins. In a seminal work, Kenyon [SODA 1996] introduced the (asymptotic) random order ratio as an alternative performance measure for online algorithms. Here, an adversary specifies the items, but the or…
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
1. doi=10.1111/itor.12030 year=2013 title=An improved best‐fit heuristic for the orthogonal strip packing problem
   authors=Jannes Verstichel, Patrick De Causmaecker, Greet Vanden Berghe
   venue=International Transactions in Operational Research cited_by=25
   abstract=Abstract The best‐fit heuristic is a simple and powerful tool for solving the two‐dimensional orthogonal strip packing problem. It is the most efficient constructive heuristic on a wide range of rectangular strip packing benchmark problems. In this paper, the results of the original best‐fit heuristic are further improved by adding new item orderings and item placement strateg…
2. doi=10.1007/s00453-021-00844-5 year=2021 title=Best Fit Bin Packing with Random Order Revisited
   authors=Susanne Albers, Arindam Khan, Leon Ladewig
   venue=Algorithmica cited_by=17
   abstract=Abstract Best Fit is a well known online algorithm for the bin packing problem, where a collection of one-dimensional items has to be packed into a minimum number of unit-sized bins. In a seminal work, Kenyon [SODA 1996] introduced the (asymptotic) random order ratio as an alternative performance measure for online algorithms. Here, an adversary specifies the items, but the or…
3. doi=10.1002/rsa.10037 year=2002 title=Linear waste of best fit bin packing on skewed distributions
   authors=Claire Kenyon, Michael Mitzenmacher
   venue=Random Structures &amp; Algorithms cited_by=4
   abstract=Abstract We prove that Best Fit bin packing has linear waste on the discrete distribution U { j , k } (where items are drawn uniformly from the set {1/ k , 2/ k , …, j / k }) for sufficiently large k when j = α k and 0.66 ≤ α &lt; 2/3. Our results extend to continuous skewed distributions, where items are drawn uniformly on [0, a ], for 0.66 ≤ a &lt; 2/3. This implies that the…

=== obp_bestfit_family ===
family: online_bin_packing
label: Best-Fit online family
definition: Prefer tight residual.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Best Fit (bin_score), Almost Best Fit (bin_score)
Works:
1. doi=10.1137/s009753979834669x year=2001 title=Variable-Sized Bin Packing: Tight Absolute Worst-Case Performance Ratios for Four Approximation Algorithms
   authors=Chengbin Chu, Rémy La
   venue=SIAM Journal on Computing cited_by=28
   abstract=In this paper we consider a one-dimensional bin packing problem where the bins do not have identical sizes, or a variable-sized bin packing problem, to minimize the bin consumption, i.e., the total size of the opened bins. The identical size problem has been extensively studied in the literature both for static and dynamic settings. The worst-case or average-case performance h…
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

=== obp_bounded_space ===
family: online_bin_packing
label: Bounded-space online packing
definition: Only k bins open.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Bounded-space Best Fit (bin_score), K-bounded Harmonic (bin_score)
Works:
1. doi=10.1137/0406045 year=1993 title=Improved Space for Bounded-Space, On-Line Bin-Packing
   authors=Gerhard Woeginger
   venue=SIAM Journal on Discrete Mathematics cited_by=30
   abstract=The author presents a sequence of linear-time, bounded-space, on-line, bin-packing algorithms that are based on the “HARMONIC” algorithms ${\text{H}}_k $ introduced by Lee and Lee [J. Assoc. Comput. Mach., 32 (1985), pp. 562–572]. The algorithms in this paper guarantee the worst case performance of ${\text{H}}_k $, whereas they only use $O ( \log \log k )$ instead of k active…
2. doi=10.1137/s0895480100369948 year=2001 title=An Optimal Online Algorithm for Bounded Space Variable-Sized Bin Packing
   authors=Steven S. Seiden
   venue=SIAM Journal on Discrete Mathematics cited_by=20
   abstract=An online algorithm for variable-sized bin packing, based on the Harmonic algorithm of Lee and Lee,[J. ACM, 32 (1985), pp. 562--572], is investigated. This algorithm was proposed by Csirik, [Acta Inform., 26 (1989), pp. 697--709], who proved that for all sets of bin sizes, 1.69103 upper bounds its performance ratio. The upper bound is improved in the sense that we give a metho…
3. doi=10.1142/s0129054110007611 year=2010 title=ONE-SPACE BOUNDED ALGORITHMS FOR TWO-DIMENSIONAL BIN PACKING
   authors=FRANCIS Y. L. CHIN, HING-FUNG TING, YONG ZHANG
   venue=International Journal of Foundations of Computer Science cited_by=10
   abstract=In this paper, we study the bounded space variation, especially one-space bounded, of two-dimensional bin packing. A sequence of rectangular items arrive over time, and the following item arrives after the packing of the previous one. The height and width of each item are no more than 1, we need to pack these items into unit square bins of size 1 × 1 where rotation of 90° is a…

=== obp_harmonic ===
family: online_bin_packing
label: Harmonic online family
definition: Size classes and class bins.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Harmonic_M score over residuals (bin_score), Refined Harmonic (bin_score)
Works:
1. doi=10.1145/3828.3833 year=1985 title=A simple on-line bin-packing algorithm
   authors=C. C. Lee, D. T. Lee
   venue=Journal of the ACM cited_by=286
   abstract=The one-dimensional on-line bin-packing problem is considered, A simple O (1)-space and O ( n )-time algorithm, called HARMONIC M , is presented. It is shown that this algorithm can achieve a worst-case performance ratio of less than 1.692, which is better than that of the O ( n )-space and O ( n log n )-time algorithm FIRST FIT. Also shown is that 1.691 … is a lower bound for…
2. doi=10.1137/s0895480100369948 year=2001 title=An Optimal Online Algorithm for Bounded Space Variable-Sized Bin Packing
   authors=Steven S. Seiden
   venue=SIAM Journal on Discrete Mathematics cited_by=20
   abstract=An online algorithm for variable-sized bin packing, based on the Harmonic algorithm of Lee and Lee,[J. ACM, 32 (1985), pp. 562--572], is investigated. This algorithm was proposed by Csirik, [Acta Inform., 26 (1989), pp. 697--709], who proved that for all sets of bin sizes, 1.69103 upper bounds its performance ratio. The upper bound is improved in the sense that we give a metho…
3. doi=10.3390/s20164448 year=2020 title=Smart Pack: Online Autonomous Object-Packing System Using RGB-D Sensor Data
   authors=Young-Dae Hong, Young-Joo Kim, Ki-Baek Lee
   venue=Sensors cited_by=18
   abstract=This paper proposes a novel online object-packing system which can measure the dimensions of every incoming object and calculate its desired position in a given container. Existing object-packing systems have the limitations of requiring the exact information of objects in advance or assuming them as boxes. Thus, this paper is mainly focused on the following two points: (1) Re…

=== obp_irrevocable ===
family: online_bin_packing
label: Irrevocable online packing
definition: No repacking; matches EoH OBP.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Worst Fit (bin_score), Residual-utilization score (bin_score)
Works:
1. doi=10.1137/0222004 year=1993 title=Tight Worst-Case Performance Bounds for Next-
                    <i>k</i>
                    -Fit Bin Packing
   authors=Weizhen Mao
   venue=SIAM Journal on Computing cited_by=18
   abstract=The bin packing problem is to pack a list of reals in $( {0,1} ]$ into unit-capacity bins using the minimum number of bins. Let $R[A]$ be the limiting worst value for the ratio ${{A(L)} / {L^ * }}$ as $L^ * $ goes to $\infty $, where $A(L)$ denotes the number of bins used in the approximation algorithm A, and $L^ * $ denotes the minimum number of bins needed to pack L. Obvious…
2. doi=10.1007/s00453-021-00844-5 year=2021 title=Best Fit Bin Packing with Random Order Revisited
   authors=Susanne Albers, Arindam Khan, Leon Ladewig
   venue=Algorithmica cited_by=17
   abstract=Abstract Best Fit is a well known online algorithm for the bin packing problem, where a collection of one-dimensional items has to be packed into a minimum number of unit-sized bins. In a seminal work, Kenyon [SODA 1996] introduced the (asymptotic) random order ratio as an alternative performance measure for online algorithms. Here, an adversary specifies the items, but the or…
3. doi=10.1002/rsa.10037 year=2002 title=Linear waste of best fit bin packing on skewed distributions
   authors=Claire Kenyon, Michael Mitzenmacher
   venue=Random Structures &amp; Algorithms cited_by=4
   abstract=Abstract We prove that Best Fit bin packing has linear waste on the discrete distribution U { j , k } (where items are drawn uniformly from the set {1/ k , 2/ k , …, j / k }) for sufficiently large k when j = α k and 0.66 ≤ α &lt; 2/3. Our results extend to continuous skewed distributions, where items are drawn uniformly on [0, a ], for 0.66 ≤ a &lt; 2/3. This implies that the…

=== obp_score ===
family: online_bin_packing
label: Score-based online packing
definition: Learned or designed score over residuals.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Residual-utilization score (bin_score), Piecewise residual score (bin_score)
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

=== obp_worstfit_family ===
family: online_bin_packing
label: Worst-Fit online family
definition: Prefer emptiest bin.
eoh_map: {"status": "possible", "adapter_kind": "bin_score"}
target_heuristics: Worst Fit (bin_score), Almost Worst Fit (bin_score)
Works:
1. doi=10.1137/s0895480100369948 year=2001 title=An Optimal Online Algorithm for Bounded Space Variable-Sized Bin Packing
   authors=Steven S. Seiden
   venue=SIAM Journal on Discrete Mathematics cited_by=20
   abstract=An online algorithm for variable-sized bin packing, based on the Harmonic algorithm of Lee and Lee,[J. ACM, 32 (1985), pp. 562--572], is investigated. This algorithm was proposed by Csirik, [Acta Inform., 26 (1989), pp. 697--709], who proved that for all sets of bin sizes, 1.69103 upper bounds its performance ratio. The upper bound is improved in the sense that we give a metho…
2. doi=10.1137/0222004 year=1993 title=Tight Worst-Case Performance Bounds for Next-
                    <i>k</i>
                    -Fit Bin Packing
   authors=Weizhen Mao
   venue=SIAM Journal on Computing cited_by=18
   abstract=The bin packing problem is to pack a list of reals in $( {0,1} ]$ into unit-capacity bins using the minimum number of bins. Let $R[A]$ be the limiting worst value for the ratio ${{A(L)} / {L^ * }}$ as $L^ * $ goes to $\infty $, where $A(L)$ denotes the number of bins used in the approximation algorithm A, and $L^ * $ denotes the minimum number of bins needed to pack L. Obvious…
3. doi=10.2478/fcds-2024-0005 year=2024 title=Online Three-Dimensional Bin Packing: A DRL Algorithm with the Buffer Zone
   authors=Jiawei Zhang, Tianping Shuai
   venue=Foundations of Computing and Decision Sciences cited_by=3
   abstract=Abstract The online 3D bin packing problem(3D-BPP) is widely used in the logistics industry and is of great practical significance for promoting the intelligent transformation of the industry. The heuristic algorithm relies too much on manual experience to formulate more perfect packing rules. In recent years, many scholars solve 3D-BPP via deep reinforcement learning(DRL) alg…

=== tsp_angular ===
family: tsp
label: Angular-metric TSP
definition: Cost uses turning angles.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Angle-aware NN (next_node_score), Or-opt for turning cost (move_selector)
Works:
1. doi=10.2139/ssrn.7378178 year=2026 title=A Sharper Explicit Bound on the Subtour-LP Integrality Gap for Metric TSP
   authors=Zhao Song
   venue=None cited_by=0
   abstract=&lt;div&gt; Karlin, Klein, and Oveis Gharan introduced a randomized better-than-3/2 approximation algorithm for metric TSP [KKO21] and subsequently established the corresponding improvement in the integrality gap of the subtour-elimination LP [KKO22], with an explicit constant ε &amp;gt; 1.00000·10−36. Gurvits, Klein, and Leake subsequently improved the certified saving to 2.1…
2. doi=10.4028/www.scientific.net/amr.694-697.2787 year=2013 title=The Genetic Algorithm with Two Heuristic Rules for TSP
   authors=Yong Wang
   venue=Advanced Materials Research cited_by=0
   abstract=Many complex discrete manufacturing problems, such as manufacturing sequencing problem or machine scheduling problem etc, can be converted into a general traveling salesman problem (TSP). TSP has been proven to be NP-complete. The genetic algorithm is improved with two heuristic rules for TSP. The first heuristic rule is the four vertices and three lines inequality. It is appl…
3. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…

=== tsp_asymmetric ===
family: tsp
label: Asymmetric TSP
definition: Directed distances, d(i,j) may differ from d(j,i).
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Directed Nearest Neighbor (next_node_score), Directed 3-opt (move_selector)
Works:
1. doi=10.1007/s00521-022-07816-y year=2022 title=Solving TSP by using combinatorial Bees algorithm with nearest neighbor method
   authors=Murat Sahin
   venue=Neural Computing and Applications cited_by=33
   abstract=Abstract Bees Algorithm (BA) is a popular meta-heuristic method that has been used in many different optimization areas for years. In this study, a new version of combinatorial BA is proposed and explained in detail to solve Traveling Salesman Problems (TSPs). The nearest neighbor method was used in the population generation section of BA, and the Multi-Insert function was add…
2. doi=10.1159/000156818 year=1994 title=Contrasting Chimpanzees and Bonobos: Nearest Neighbor Distances and Choices
   authors=Frances J. White, Colin A. Chapman
   venue=Folia Primatologica cited_by=29
   abstract=In an effort to understand factors underlying differences in the social organization of Pan troglodytes and P. paniscus, we measured the nearest neighbor distances and choices for chimpanzees in Kibale National Park, Uganda, and for bonobos in Lomako Forest, Zaire. We assume that the spatial organization of a set of individuals should reflect the underlying relationships betwe…
3. doi=10.2307/1934161 year=1971 title=Estimation of Density from a Sample of Joint Point and Nearest‐Neighbor Distances
   authors=C. L. Batcheler
   venue=Ecology cited_by=23
   abstract=Distances are measured from sample points to the nearest member of a population, from that member to its nearest neighbor, and from that neighbor to its nearest neighbor. The point—to—nearest member is used to obtain an estimate of density, which is characteristically unbiased if the population is random, but biased if the population is uniformly or contagiously distributed. T…

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
1. doi=10.7717/peerj-cs.972 year=2022 title=Solving the clustered traveling salesman problem
                    <i>via</i>
                    traveling salesman problem methods
   authors=Yongliang Lu, Jin-Kao Hao, Qinghua Wu
   venue=PeerJ Computer Science cited_by=13
   abstract=The Clustered Traveling Salesman Problem (CTSP) is a variant of the popular Traveling Salesman Problem (TSP) arising from a number of real-life applications. In this work, we explore a transformation approach that solves the CTSP by converting it to the well-studied TSP. For this purpose, we first investigate a technique to convert a CTSP instance to a TSP and then apply power…
2. doi=10.2478/fcds-2023-0020 year=2023 title=Traveling salesman problem parallelization by solving clustered subproblems
   authors=Vadim Romanuke
   venue=Foundations of Computing and Decision Sciences cited_by=3
   abstract=Abstract A method of parallelizing the process of solving the traveling salesman problem is suggested, where the solver is a heuristic algorithm. The traveling salesman problem parallelization is fulfilled by clustering the nodes into a given number of groups. Every group (cluster) is an open-loop subproblem that can be solved independently of other subproblems. Then the solut…
3. doi=10.70675/09043c22zfaa5z4e3bz868bz8ac1958d96f3 year=None title=Exact and anytime heuristic search for the Time Dependent Traveling Salesman Problem with Time Windows
   authors=Romain Fontaine
   venue=None cited_by=0
   abstract=Recherche heuristique exacte et anytime pour résoudre le Voyageur de commerce dépendant du temps avec fenêtres temporelles Le problème du voyageur de commerce (TSP, pour Traveling Salesman Problem) dépendant du temps (TD, pour Time Dependent) est une généralisation du TSP qui permet de prendre en compte les conditions de trafic lors de la planification de tournées en milieu ur…

=== tsp_construct ===
family: tsp
label: Constructive-only TSP
definition: Build a tour city by city.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Nearest Neighbor (next_node_score), Cheapest Insertion (not_mappable)
Works:
1. doi=10.38032/jea.2024.01.004 year=2024 title=Improvement of the Nearest Neighbor Heuristic Search Algorithm for Traveling Salesman Problem
   authors=Md. Ziaur Rahman, Sakibur Rahamn Sheikh, Ariful Islam, Md. Azizur Rahman
   venue=Journal of Engineering Advancements cited_by=7
   abstract=The Traveling Salesman Problem (TSP) is classified as a non-deterministic polynomial (NP) hard problem, which has found widespread application in several scientific and technological domains. Due to its NP-hard nature, it is very hard to solve effectively and efficiently. Despite this rationale, a multitude of optimization approaches have been proposed and developed by scienti…
2. doi=10.1137/s0895480194278246 year=1997 title=Worst Case Length of Nearest Neighbor Tours for the Euclidean Traveling Salesman Problem
   authors=L. Tassiulas
   venue=SIAM Journal on Discrete Mathematics cited_by=5
   abstract=The worst case length of a tour for the Euclidean traveling salesman problem produced by the nearest neighbor (NN) heuristic is studied in this paper. Nearest neighbor tours for a set of arbitrarily located points in the d-dimensional unit cube are considered. A technique is developed for bounding the worst case length of a tour. It is based on identifying sequences of {\it co…
3. doi=10.1239/jap/1395771417 year=2014 title=On the Nearest-Neighbor Algorithm for the Mean-Field Traveling Salesman Problem
   authors=Antar Bandyopadhyay, Farkhondeh Sajadi
   venue=Journal of Applied Probability cited_by=3
   abstract=In this work we consider the mean-field traveling salesman problem , where the intercity distances are taken to be independent and identically distributed with some distribution F . We consider the simplest approximation algorithm, namely, the nearest-neighbor algorithm , where the rule is to move to the nearest nonvisited city. We show that the limiting behavior of the total…

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
1. doi=10.26906/sunz.2024.2.144 year=2024 title=COMPARATIVE ANALYSIS OF THE APPLICATION OF HEURISTIC ALGORITHMS FOR SOLVING THE TSP PROBLEM
   authors=О. Skakalina, A. Kapiton
   venue=Системи управління, навігації та зв’язку. Збірник наукових праць cited_by=2
   abstract=The need to solve the traveling salesman problem (TSP) often arises when solving practically significant optimization problems, such as problems in the field of economics, logistics in the widest range of applications, in chains of technical programs. Quite often, the specifics of these problems require obtaining a solution that is as close to the exact value as possible. But…
2. doi=10.2139/ssrn.7144998 year=2026 title=A Two-Stage Scheduling Heuristic for the Deadline-Constrained Traveling Salesman Problem with a Drone Station (TSP-DS)
   authors=Jiahe Ling
   venue=None cited_by=0
   abstract=This study investigates a deadline-constrained traveling salesman problem with drone stations in which a truck replenishes fixed drone pads and drones serve geographically eligible customers. The objective is to minimize total order tardiness under release times and soft delivery deadlines. A mixed-integer programming formulation jointly determines pad activation, truck routin…
3. doi=10.3233/978-1-61499-927-0-231 year=2018 title=A Heuristic Algorithm to Eliminate Edges for TSP
   authors=Wang Yong, Geng Chang Xin, Wu Yi Wen
   venue=Frontiers in Artificial Intelligence and Applications cited_by=0
   abstract=A heuristic algorithm is provided to trim many edges for reducing the search space of traveling salesman problem (TSP). The heuristic algorithm is designed according to a probability model and the fuzzy numbers plays an important role to enhance the performance. The heuristic algorithm may lose a few edges in some optimal solutions if the parameter N is too small or F is too b…

=== tsp_large ===
family: tsp
label: Large-scale Euclidean TSP
definition: n in thousands; locality matters.
eoh_map: {"status": "possible", "adapter_kind": "move_selector"}
target_heuristics: Lin-Kernighan (not_mappable), Candidate-list 2-opt (move_selector)
Works:
1. doi=10.1287/opre.21.2.498 year=1973 title=An Effective Heuristic Algorithm for the Traveling-Salesman Problem
   authors=S. Lin, B. W. Kernighan
   venue=Operations Research cited_by=2854
   abstract=This paper discusses a highly effective heuristic procedure for generating optimum and near-optimum solutions for the symmetric traveling-salesman problem. The procedure is based on a general approach to heuristics that is believed to have wide applicability in combinatorial optimization problems. The procedure produces optimum solutions for all problems tested, “classical” pr…
2. doi=10.1287/ijoc.15.1.82.15157 year=2003 title=Chained Lin-Kernighan for Large Traveling Salesman Problems
   authors=David Applegate, William Cook, André Rohe
   venue=INFORMS Journal on Computing cited_by=283
   abstract=We discuss several issues that arise in the implementation of Martin, Otto, and Felten's Chained Lin-Kernighan heuristic for large-scale traveling salesman problems. Computational results are presented for TSPLIB instances ranging in size from 11,849 cities up to 85,900 cities; for each of these instances, solutions within 1% of the optimal value can routinely be found in unde…
3. doi=10.1137/0221030 year=1992 title=The Complexity of the Lin–Kernighan Heuristic for the Traveling Salesman Problem
   authors=Christos H. Papadimitriou
   venue=SIAM Journal on Computing cited_by=65
   abstract=It is shown that finding a local optimum solution with respect to the Lin–Kernighan heuristic for the traveling salesman problem is PLS-complete, and thus as hard as any local search problem.

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
2. doi=10.1287/opre.36.3.478 year=1988 title=A Heuristic Algorithm for the Traveling Salesman Location Problem on Networks
   authors=David Simchi-Levi, Oded Berman
   venue=Operations Research cited_by=87
   abstract=In this paper, we present a heuristic for the traveling salesman location problem on a network. Each day the salesman (e.g., a repair vehicle) must visit all the calls that are registered in a service list. Each call is generated with a given probability and the service list contains at most n calls. The heuristic requires O(n 3 ) time to find the location that “minimizes” the…
3. doi=10.1088/1742-6596/1218/1/012038 year=2019 title=New heuristic algorithm for traveling salesman problem
   authors=M L Shahab
   venue=Journal of Physics: Conference Series cited_by=2
   abstract=Abstract Traveling salesman problem (TSP) is a basis for many bigger problems. If we can find an efficient method (that produce a good result in a short time) to solve the TSP, then we will also be able to solve many other problems. In this research, we proposed a new heuristic algorithm for TSP. We used 80 problems from TSPLIB to test the proposed heuristic algorithm. The pro…

=== tsp_open ===
family: tsp
label: Open TSP / Hamiltonian path
definition: Path visits each city once, no return.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Path Nearest Neighbor (next_node_score), Cheapest Insertion path (not_mappable)
Works:
1. doi=10.21070/icecrs.v12i3.1935 year=2024 title=Nearest Neighbor Heuristic Minimizes Logistics Distribution Distance And Travel Time
   authors=Naufal Akmal Christiono, Dewi Komala Sari
   venue=Proceedings of The ICECRS cited_by=0
   abstract=General Background Supply chain systems require strategic management to distribute production outputs continuously and accurately to consumers. Specific Background PT. Laprint Jaya experiences fluctuating shipping volumes and limited delivery fleets, causing complex Single Depot Capacitated Vehicle Routing Problems during dense daily schedules. Knowledge Gap Traditional routin…
2. doi=10.1101/2022.09.08.507181 year=2022 title=<tt>DrTransformer</tt>
                  : Heuristic cotranscriptional RNA folding using the nearest neighbor energy model
   authors=Stefan Badelt, Ronny Lorenz, Ivo L. Hofacker
   venue=None cited_by=0
   abstract=Abstract Background Folding during transcription can have an important influence on the structure and function of ℝNA molecules, as regions closer to the 5’ end can fold into metastable structures before potentially stronger interactions with the 3’ end become available. Thermodynamic ℝNA folding models are not suitable to analyze this problem, as they can only calculate prope…
3. doi=10.31219/osf.io/dxe2j year=2024 title=Table based K Nearest Neighbor for Text Classification
   authors=Taeho Jo
   venue=None cited_by=0
   abstract=This article proposes the modified KNN (K Nearest Neighbor)algorithm which receives a table as its input data and is applied tothe text categorization. The motivations of this research are thesuccessful results from applying the table based algorithms to thetext categorizations in previous works and the expectation ofsynergy effect between the text categorization and the wordc…
