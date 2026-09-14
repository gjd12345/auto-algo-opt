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

family: cvrp

=== cvrp_basic ===
label: Capacitated VRP
definition: One depot, capacity, visit each customer once.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Nearest feasible customer (next_node_score), Clarke-Wright savings as next-node score (next_node_score)
Works:
1. doi=10.61194/sijl.v2i1.187 year=2024 title=Capacitated Vehicle Routing Problem (CVRP) with Sweep and Nearest Neighbor Algorithm
   authors=Erly Ekayanti, Sugianto, Imaduddin Bachtiar Efendi
   venue=Sinergi International Journal of Logistics cited_by=5
   abstract=The Capacitated Vehicle Routing Problem (CVRP) presents significant challenges in shipping route optimization and logistics management. These challenges include balancing vehicle capacity, minimizing travel distance, and efficiently grouping delivery points, all of which are crucial for enhancing operational efficiency and reducing costs. This research aims to apply a combination of the Sweep and Nearest Neighbor algorithms to address the CVRP, seeking to improve route efficiency and manage vehicle capacity effectively. The Sweep algorithm is employed to cluster pickup points based on their polar angle from the depot, facilitating efficient grouping and optimal vehicle capacity management.…
2. doi=10.26760/mindjournal.v11i1.1-14 year=2026 title=Penerapan Algoritma Clarke and Wright Saving dalam Capacitated Vehicle Routing Problem dengan Optimasi Nearest Neighbor untuk Rute Terpendek
   authors=FARREL ADI IBRAHIM, YUSUP MIFTAHUDDIN, MUHAMMAD ICHWAN, SURYA REZA PUTRA, WIRAWAN HADIWIBOWO
   venue=MIND Journal cited_by=0
   abstract=Abstrak Distribusi merupakan komponen krusial dalam aktivitas logistik karena berperan dalam kelancaran proses pengiriman. Penelitian ini bertujuan menyusun rute distribusi dengan jarak terpendek berdasarkan kapasitas kendaraan, menggunakan algoritma Clarke and Wright Saving untuk membentuk rute awal serta algoritma Nearest Neighbor untuk mengatur urutan kunjungan. Pendekatan penelitian dilakukan secara kuantitatif melalui perhitungan algoritmik dengan memanfaatkan data lokasi pelanggan dan jumlah permintaan. Temuan penelitian menunjukkan bahwa rute usulan memiliki total jarak tempuh 151.69 km untuk mendistribusikan 300 ekor ayam beku, atau 18.97 km (11.12%) lebih pendek dibandingkan rute a…
3. doi=10.2306/scienceasia1513-1874.2012.38.307 year=2012 title=An improved Clarke and Wright savings algorithm for the capacitated vehicle routing problem
   authors=Tantikorn Pichpibul, Ruengsak Kawtummachai
   venue=ScienceAsia cited_by=60
   abstract=(missing)
4. doi=10.1145/3665065.3665076 year=2024 title=Capacitated Electric Vehicle Routing Problem using adaptive NEH with Nearest Neighbor Subtours
   authors=Andrew Struthers, Donald Davendra
   venue=2024 8th International Conference on Intelligent Systems Metaheuristics &amp; Swarm Intelligence (ISMSI) cited_by=1
   abstract=(missing)
5. doi=10.32614/cran.package.heumilkr year=2024 title=heumilkr: Heuristic Capacitated Vehicle Routing Problem Solver
   authors=Lukas Schneiderbauer
   venue=CRAN: Contributed Packages cited_by=0
   abstract=(missing)

=== mdvrp ===
label: Multi-depot VRP
definition: Several depots.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Depot assignment + NN (not_mappable), MD savings (not_mappable)
Works:
1. doi=10.1002/eng2.70511/v1/review1 year=2025 title=Review for "Crew Rostering in Long-Distance Freight Railways: A Multi-Depot VRP-Based Heuristic Approach"
   authors=
   venue=None cited_by=0
   abstract=(missing)
2. doi=10.1002/eng2.70511/v1/review2 year=2025 title=Review for "Crew Rostering in Long-Distance Freight Railways: A Multi-Depot VRP-Based Heuristic Approach"
   authors=
   venue=None cited_by=0
   abstract=(missing)
3. doi=10.1002/eng2.70511/v1/review3 year=2025 title=Review for "Crew Rostering in Long-Distance Freight Railways: A Multi-Depot VRP-Based Heuristic Approach"
   authors=
   venue=None cited_by=0
   abstract=(missing)
4. doi=10.1002/eng2.70511/v2/decision1 year=2025 title=Decision letter for "Crew Rostering in Long-Distance Freight Railways: A Multi-Depot VRP-Based Heuristic Approach"
   authors=
   venue=None cited_by=0
   abstract=(missing)
5. doi=10.1002/eng2.70511/v2/review1 year=2025 title=Review for "Crew Rostering in Long-Distance Freight Railways: A Multi-Depot VRP-Based Heuristic Approach"
   authors=
   venue=None cited_by=0
   abstract=(missing)

=== ovrp ===
label: Open VRP
definition: Routes need not return.
eoh_map: {"status": "possible", "adapter_kind": "next_node_score"}
target_heuristics: Open NN (next_node_score), Open savings (next_node_score)
Works:
1. doi=10.70675/37fa3a3cza23dz4ac5zbaa3z1327ba608d7e year=None title=Vehicle routing problems with profits, exact and heuristic approaches
   authors=Racha El-Hajj
   venue=None cited_by=0
   abstract=Problèmes de tournées de véhicules avec profits, méthodes exactes et approchées Nous nous intéressons dans cette thèse à la résolution du problème de tournées sélectives (Team Orienteering Problem - TOP) et ses variantes. Ce problème est une extension du problème de tournées de véhicules en imposan tcertaines limitations de ressources. Nous proposons un algorithme de résolution exacte basé sur la programmation linéaire en nombres entiers (PLNE) en ajoutant plusieurs inégalités valides capables d’accélérer la résolution. D’autre part, en considérant des périodes de travail strictes pour chaque véhicule durant sa tournée, nous traitons une des variantes du TOP qui est le problème de tournées…
2. doi=10.1109/cec.2017.7969477 year=2017 title=Learning heuristic selection using a Time Delay Neural Network for Open Vehicle Routing
   authors=Raras Tyasnurita, Ender Ozcan, Robert John
   venue=2017 IEEE Congress on Evolutionary Computation (CEC) cited_by=30
   abstract=(missing)
3. doi=10.21236/ada013639 year=1975 title=Vehicle Routing Problems: Formulations and Heuristic Solution Techniques
   authors=Bruce L. Golden
   venue=None cited_by=17
   abstract=(missing)
4. doi=10.4186/ejth.2012.4.3.57 year=2012 title=Heuristic for Open Vehicle Routing Problem to Reduce Transportation Cost
   authors=อรประไพ จารุพัฒน์, ปวีณา เชาวลิตวงศ์
   venue=วารสารวิศวกรรมศาสตร์ cited_by=0
   abstract=(missing)
5. doi=10.1002/eng2.70198/v2/review1 year=2025 title=Review for "Performance Evaluation of Emerging Meta‐Heuristic Algorithms on Vehicle Routing Problem"
   authors=
   venue=None cited_by=0
   abstract=(missing)

=== sdvrp ===
label: Split-delivery VRP
definition: A customer may be split.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Split-delivery savings (not_mappable), Split local search (not_mappable)
Works:
1. doi=10.1016/j.endm.2018.07.025 year=2018 title=A branch and price approach for the Split Pickup and Split Delivery VRP
   authors=Marco Casazza, Alberto Ceselli, Roberto Wolfler Calvo
   venue=Electronic Notes in Discrete Mathematics cited_by=11
   abstract=(missing)
2. doi=10.1109/cac67268.2025.11486744 year=2025 title=Adaptive Large Neighborhood Search for Multi-depot Commodity-constrained Split Delivery VRP
   authors=Man Zhang, Wenjuan Gu, Yufeng Zhuang
   venue=2025 China Automation Congress (CAC) cited_by=0
   abstract=(missing)
3. doi=10.1109/itme.2008.4744006 year=2008 title=An improved tabu search for the Split Delivery VRP
   authors=Degang Xu, Renbin Xiao, Shengxuan Wang
   venue=2008 IEEE International Symposium on IT in Medicine and Education cited_by=0
   abstract=(missing)
4. doi=10.1109/ccis59572.2023.10263006 year=2023 title=KALNS for a Multi-depot Split Delivery VRP with Customers’ Multi-Requirement
   authors=Xianghu Meng, Haoran Pei, Jing Tang
   venue=2023 IEEE 9th International Conference on Cloud Computing and Intelligent Systems (CCIS) cited_by=0
   abstract=(missing)
5. doi=10.1002/eng2.70511/v1/review1 year=2025 title=Review for "Crew Rostering in Long-Distance Freight Railways: A Multi-Depot VRP-Based Heuristic Approach"
   authors=
   venue=None cited_by=0
   abstract=(missing)

=== vrptw ===
label: VRP with time windows
definition: Customers have time windows.
eoh_map: {"status": "not_mappable", "adapter_kind": "not_mappable"}
target_heuristics: Solomon I1 (not_mappable), Solomon I2 (not_mappable)
Works:
1. doi=10.37373/jenius.v6i2.1652 year=2025 title=Optimasi rute pengangkutan sampah menggunakan metode VRPTW dan Nearest Insertion Heuristic di Kecamatan Jatisampurna
   authors=Harditriyono Putra, Andary Asvaroza Munita
   venue=JENIUS : Jurnal Terapan Teknik Industri cited_by=0
   abstract=Dinas Lingkungan Hidup melalui Unit Pelaksana Teknis Dinas Lingkungan Hidup (UPTD LH) Kecamatan Jatisampurna bertanggung jawab untuk mengelola pengangkutan sampah rumah tangga di wilayah Kecamatan Jatisampurna. Pengangkutan sampah dilakukan dengan dua metode. Metode pertama adalah pengumpulan dari rumah ke rumah dan dibuang ke TPA Sumur Batu setelah kontainer penuh. Metode kedua adalah pengumpulan dari dua stasiun pemindahan yang disebut stasiun Betawi Permai dan stasiun Bumi Eraska, dimana sampah dikumpulkan dari rumah ke rumah oleh petugas dari daerah sekitar kedua stasiun pemindahan tersebut sebelum diangkut ke TPA Sumur Batu. Berdasarkan kedua metode tersebut, UPTD LH membutuhkan sembil…
2. doi=10.1016/j.ejor.2011.12.005 year=2012 title=Vehicle routing with multiple deliverymen: Modeling and heuristic approaches for the VRPTW
   authors=Vitória Pureza, Reinaldo Morabito, Marc Reimann
   venue=European Journal of Operational Research cited_by=83
   abstract=(missing)
3. doi=10.7717/peerj-cs.2586/table-6 year=None title=Table 6: Results of VRPTW instances in Solomon.
   authors=
   venue=None cited_by=0
   abstract=(missing)
4. doi=10.7717/peerj-cs.2586/supp-1 year=None title=Supplemental Information 1: New solutions for VRPTW instances in Solomon.
   authors=
   venue=None cited_by=0
   abstract=(missing)
5. doi=10.1109/hicss.2009.16 year=2009 title=A Hybrid Meta-Heuristic for the VRPTW with Cluster-Dependent Tour Starts in the Newspaper Industry
   authors=
   venue=2009 42nd Hawaii International Conference on System Sciences cited_by=0
   abstract=(missing)
