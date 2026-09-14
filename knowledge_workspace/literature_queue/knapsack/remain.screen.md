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

family: knapsack

=== kp_assign ===
family: knapsack
label: Assignment knapsack
definition: Assign items to agents with budgets.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Assign greedy (not_mappable), Regret assignment (not_mappable)
Works:
1. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
2. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…
3. doi=10.70675/b3d4919cza920z4e7fz8da1z73415f5d5f20 year=None title=Heuristic Methods for Calculating Dynamic Traffic Assignment
   authors=Mostafa Ameli
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour le calcul d'affectation dynamique du trafic Les systèmes de transport sont caractérisés de manière dynamique non seulement par des interactions non linéaires entre les différents composants, mais également par des boucles de rétroaction entre l'état du réseau et les décisions des utilisateurs. En particulier, la congestion du réseau impacte à la fois…

=== kp_bilevel ===
family: knapsack
label: Bilevel knapsack
definition: Leader-follower.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Leader greedy (not_mappable), Reaction heuristic (not_mappable)
Works:
1. doi=10.1287/ijoc.2015.0676 year=2016 title=Bilevel Knapsack with Interdiction Constraints
   authors=Alberto Caprara, Margarida Carvalho, Andrea Lodi, Gerhard J. Woeginger
   venue=INFORMS Journal on Computing cited_by=81
   abstract=We consider a bilevel integer programming model that extends the classic 0–1 knapsack problem in a very natural way. The model describes a Stackelberg game where the leader’s decision interdicts a subset of the knapsack items for the follower. As this interdiction of items substantially increases the difficulty of the problem, it prevents the application of the classical metho…
2. doi=10.1137/130906593 year=2014 title=A Study on the Computational Complexity of the Bilevel Knapsack Problem
   authors=Alberto Caprara, Margarida Carvalho, Andrea Lodi, Gerhard J. Woeginger
   venue=SIAM Journal on Optimization cited_by=67
   abstract=We analyze the computational complexity of three fundamental variants of the bilevel knapsack problem. All three variants are shown to be complete for the second level of the polynomial hierarchy. We also discuss the somewhat easier situation where the weight and profit coefficients in the knapsack problem are encoded in unary: two of the considered bilevel variants become sol…
3. doi=10.1007/s12532-023-00244-6 year=2023 title=Exact methods for discrete $${\varGamma }$$-robust interdiction problems with an application to the bilevel knapsack problem
   authors=Yasmine Beck, Ivana Ljubić, Martin Schmidt
   venue=Mathematical Programming Computation cited_by=6
   abstract=Abstract Developing solution methods for discrete bilevel problems is known to be a challenging task—even if all parameters of the problem are exactly known. Many real-world applications of bilevel optimization, however, involve data uncertainty. We study discrete min-max problems with a follower who faces uncertainties regarding the parameters of the lower-level problem. Adop…

=== kp_circular ===
family: knapsack
label: Circular knapsack
definition: Circular arrangement.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Circular greedy (not_mappable), Break-circle greedy (not_mappable)
Works:
1. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
2. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…
3. doi=10.47611/jsrhs.v12i4.5660 year=2023 title=Using Heuristic Algorithms to Solve the 0-1 Knapsack Problem
   authors=Sanatan Mishra, David Perkins
   venue=Journal of Student Research cited_by=0
   abstract=The 0-1 Knapsack problem is an NP-complete optimization problem with applications in many places where the most valuable items must be selected for a finite pool. Heuristic algorithms are used to solve that problem, as the exact solutions take far too much time to be useful in such applications. This paper introduces ten novel heuristic algorithms. After that, the paper analyz…

=== kp_collapsing ===
family: knapsack
label: Collapsing knapsack
definition: Capacity depends on selection.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Collapsing greedy (not_mappable), Collapsing local search (not_mappable)
Works:
1. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_compartment ===
family: knapsack
label: Compartmentalized knapsack
definition: Compartments inside the knapsack.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Compartment greedy (not_mappable), Compartment local search (not_mappable)
Works:
1. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_density ===
family: knapsack
label: Profit/weight density greedy
definition: Sort by density then take.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Dantzig density greedy (not_mappable), Critical-item greedy (not_mappable)
Works:
1. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…
2. doi=10.23956/ijermt.v6i7.181 year=2018 title=Clustering Analysis of Greedy Heuristic Method in Zero_One Knapsack Problem
   authors=V. Selvi
   venue=International Journal of Emerging Research in Management and Technology cited_by=0
   abstract=Knapsack problem is a surely understood class of optimization problems, which tries to expand the profit of items in a knapsack without surpassing its capacity, Knapsack can be solved by several algorithms such like Greedy, dynamic programming, Branch &amp; bound etc. The solution to the zero_one knapsack problem (KP) can be viewed as the result of a sequence of decision. Clus…
3. doi=10.22541/au.170670422.24229067/v1 year=2024 title=SOLVING 0 - 1 KNAPSACK PROBLEM BASED ON HYBRID GREEDY FIREWORKS ALGORITHM
   authors=LI Qiuyue
   venue=None cited_by=0
   abstract=Aiming at the classical knapsack problem in combinatorial optimization, in order to improve the local search ability and global search ability of the basic fireworks algorithm, an improved fireworks algorithm is proposed by combining the basic fireworks algorithm, greedy optimization strategy and simulated annealing algorithm. In order to ensure the diversity of the initial po…

=== kp_discount ===
family: knapsack
label: Discount knapsack
definition: Discounts on combinations.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Discount greedy (not_mappable), Combo local search (not_mappable)
Works:
1. doi=10.1108/mip-03-2022-0113 year=2022 title=Absolute number heuristic in discount frames
   authors=Bo Wang
   venue=Marketing Intelligence &amp; Planning cited_by=5
   abstract=Purpose This study examines whether the absolute number heuristic holds for consumers' responses to higher-priced versus lower-priced products. Further, it explores whether the different construal level as induced from presence or absence of a product image can be a boundary condition for the absolute number heuristic. Design/methodology/approach Four experiments were conducte…
2. doi=10.2139/ssrn.4137161 year=2022 title=An Adaptive Grey Wolf Optimization with Differential Evolution Operator for Solving the Discount {0-1} Knapsack Problem
   authors=Zijian Wang, Xi Fang, Fei Gao, Liang Xie, Xianchen Meng
   venue=None cited_by=1
   abstract=The discount {0-1} knapsack problem (D {0-1} KP) is a new variant of the knapsack problem. It is an NP-hard problem and also a binary optimization problem. As a new intelligent algorithm that imitates the leadership function of wolves, the grey wolf optimizer (GWO) can solve NP problems more effectively than accurate algorithms. At the same time, the GWO has fewer parameters,…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_dp_fptas ===
family: knapsack
label: DP / FPTAS
definition: Exact or approximate DP, not a constructive EoH elite.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Ibarra-Kim FPTAS (not_mappable), DP by capacity (not_mappable)
Works:
1. doi=10.1287/opre.16.1.103 year=1968 title=Dynamic Programming Algorithms for the Integer Programming Problem—I: The Integer Programming Problem Viewed as a Knapsack Type Problem
   authors=Jeremy F. Shapiro
   venue=Operations Research cited_by=47
   abstract=Gomory has transformed the integer programming problem into a related group optimization problem which can be more easily solved. An optimal solution to the group problem is optimal for the integer programming problem from which it is derived if the solution is feasible. An algorithm (IP Algorithm I) for solving the group optimization problem is developed, and sufficient condi…
2. doi=10.1145/1345375.1345414 year=2007 title=An alternative dynamic programming solution for the 0/1 knapsack
   authors=Timothy J. Rolfe
   venue=ACM SIGCSE Bulletin cited_by=1
   abstract=The 0/1 knapsack (or knapsack without repetition) has a dynamic programming solution driven by a table in which each item is consecutively considered. The problem can also be approached by generating a table in which the optimal knapsack for each knapsack capacity is generated, modeled on the solution to the integer knapsack (knapsack with repetition) found in Sedgewick [1] an…
3. doi=10.1145/181983.181988 year=1994 title=Dynamic programming algorithms for the knapsack problem
   authors=Moshe Sniedovich
   venue=ACM SIGAPL APL Quote Quad cited_by=1
   abstract=The knapsack problem is one of the "classical" problems in Operations Research. In this paper we present a number of APL codes based on the dynamic programming approach to such problems. Although these codes can be used effectively to solve small knapsack problems, they were developed primarily as teaching aids.

=== kp_fuzzy ===
family: knapsack
label: Fuzzy knapsack
definition: Fuzzy weights/profits.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Fuzzy density greedy (not_mappable), Defuzzified greedy (not_mappable)
Works:
1. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
2. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…
3. doi=10.47611/jsrhs.v12i4.5660 year=2023 title=Using Heuristic Algorithms to Solve the 0-1 Knapsack Problem
   authors=Sanatan Mishra, David Perkins
   venue=Journal of Student Research cited_by=0
   abstract=The 0-1 Knapsack problem is an NP-complete optimization problem with applications in many places where the most valuable items must be selected for a finite pool. Heuristic algorithms are used to solve that problem, as the exact solutions take far too much time to be useful in such applications. This paper introduces ten novel heuristic algorithms. After that, the paper analyz…

=== kp_generalized ===
family: knapsack
label: Generalized knapsack
definition: Generalised assignment flavour.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: GAP greedy (not_mappable), GAP regret (not_mappable)
Works:
1. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_group ===
family: knapsack
label: Group knapsack
definition: Groups of items.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Group greedy (not_mappable), Group local search (not_mappable)
Works:
1. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_integer ===
family: knapsack
label: Integer knapsack
definition: Integer copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Integer density greedy (not_mappable), Rounding heuristic (not_mappable)
Works:
1. doi=10.1287/opre.16.1.103 year=1968 title=Dynamic Programming Algorithms for the Integer Programming Problem—I: The Integer Programming Problem Viewed as a Knapsack Type Problem
   authors=Jeremy F. Shapiro
   venue=Operations Research cited_by=47
   abstract=Gomory has transformed the integer programming problem into a related group optimization problem which can be more easily solved. An optimal solution to the group problem is optimal for the integer programming problem from which it is derived if the solution is feasible. An algorithm (IP Algorithm I) for solving the group optimization problem is developed, and sufficient condi…
2. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…
3. doi=10.2139/ssrn.675602 year=2005 title=Fast Fourier Transform and its Applications to Integer Knapsack Problems
   authors=Yurii Nesterov
   venue=None cited_by=1
   abstract=In this paper we suggest a new efficient technique for solving integer knapsack problems. Our algorithms can be seen as application of Fast Fourier Transform to generating functions of integer polytopes. Using this approach, it is possible to count the number of boolean solutions of a single n-dimensional Diophantine equation [a,x]= b in O(|a|1 ln|a1|ln n) operations. Another…

=== kp_mckp ===
family: knapsack
label: Multiple-choice knapsack
definition: Choose from classes.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: MCKP greedy (not_mappable), Class-wise DP heuristic (not_mappable)
Works:
1. doi=10.1145/2541012.2541014 year=2013 title=A fast and scalable multidimensional multiple-choice knapsack heuristic
   authors=Hamid Shojaei, Twan Basten, Marc Geilen, Azadeh Davoodi
   venue=ACM Transactions on Design Automation of Electronic Systems cited_by=32
   abstract=Many combinatorial optimization problems in the embedded systems and design automation domains involve decision making in multidimensional spaces. The multidimensional multiple-choice knapsack problem (MMKP) is among the most challenging of the encountered optimization problems. MMKP problem instances appear for example in chip multiprocessor runtime resource management and in…
2. doi=10.3390/math10040602 year=2022 title=A Memetic Algorithm with a Novel Repair Heuristic for the Multiple-Choice Multidimensional Knapsack Problem
   authors=Jaeyoung Yang, Yong-Hyuk Kim, Yourim Yoon
   venue=Mathematics cited_by=11
   abstract=We propose a memetic algorithm for the multiple-choice multidimensional knapsack problem (MMKP). In this study, we focus on finding good solutions for the MMKP instances, for which feasible solutions rarely exist. To find good feasible solutions, we introduce a novel repair heuristic based on the tendency function and a genetic search for the function approximation. Even when…
3. doi=10.3390/math13071097 year=2025 title=Solution Methods for the Multiple-Choice Knapsack Problem and Their Applications
   authors=Tibor Szkaliczki
   venue=Mathematics cited_by=8
   abstract=The Knapsack Problem belongs to the best-studied classical problems in combinatorial optimization. The Multiple-choice Knapsack Problem (MCKP) represents a generalization of the problem, with various application fields such as industry, transportation, telecommunication, national defense, bioinformatics, finance, and life. We found a lack of survey papers on MCKP. This paper o…

=== kp_minmax ===
family: knapsack
label: Min-max knapsack
definition: Minimise the worst load.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Min-max greedy (not_mappable), Load-balance local search (not_mappable)
Works:
1. doi=10.1002/nav.20237 year=2007 title=The minmax multidimensional knapsack problem with application to a chance‐constrained problem
   authors=Moshe Kress, Michal Penn, Maria Polukarov
   venue=Naval Research Logistics (NRL) cited_by=9
   abstract=Abstract In this paper we present a new combinatorial problem, called minmax multidimensional knapsack problem (MKP), motivated by a military logistics problem. The logistics problem is a two‐period, two‐level, chance‐constrained problem with recourse. We show that the MKP is NP‐hard and develop a practically efficient combinatorial algorithm for solving it. We also show that…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_mo ===
family: knapsack
label: Multi-objective knapsack
definition: Several profits.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Weighted-sum greedy (not_mappable), Pareto greedy (not_mappable)
Works:
1. doi=10.1287/mnsc.48.12.1603.445 year=2002 title=Approximating Multiobjective Knapsack Problems
   authors=Thomas Erlebach, Hans Kellerer, Ulrich Pferschy
   venue=Management Science cited_by=88
   abstract=For multiobjective optimization problems, it is meaningful to compute a set of solutions covering all possible trade-offs between the different objectives. The multiobjective knapsack problem is a generalization of the classical knapsack problem in which each item has several profit values. For this problem, efficient algorithms for computing a provably good approximation to t…
2. doi=10.18178/ijmlc.2021.11.2.1032 year=2021 title=Multiobjective Heuristic Scheduling of Automated Manufacturing Systems Based on Petri Nets
   authors=Chong Yu, Bo Huang, Jiangen Hao
   venue=International Journal of Machine Learning and Computing cited_by=1
   abstract=In practice, automated manufacturing systems usually have multiple, incommensurate, and conflicting objectives to achieve. To deal with them, this paper proposes an extend Petri nets for the multiobjective scheduling of AMSs. In addition, a multiobjective heuristic A* search within reachability graphs of extended Petri nets is also proposed to schedule these nets. The method c…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_nonlinear ===
family: knapsack
label: Nonlinear knapsack
definition: Nonlinear profit.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Nonlinear greedy (not_mappable), Linearisation heuristic (not_mappable)
Works:
1. doi=10.1142/s0217595912500315 year=2012 title=HEURISTIC AND EXACT SOLUTION METHOD FOR CONVEX NONLINEAR KNAPSACK PROBLEM
   authors=BIN ZHANG, BO CHEN
   venue=Asia-Pacific Journal of Operational Research cited_by=6
   abstract=In this paper, we consider a class of convex nonlinear knapsack problems in which all decision variables are integer and the objective and knapsack functions are nonlinear. This generalized problem is characterized by positive marginal cost (PMC) and increasing marginal loss-cost ratio (IMLCR). By analyzing the structural properties of the problem, we develop an efficient heur…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_online ===
family: knapsack
label: Online knapsack
definition: Items arrive online.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Threshold online knapsack (not_mappable), Secretary-style take (not_mappable)
Works:
1. doi=10.1093/oso/9780198794844.003.0015 year=2018 title=Heuristic evaluation of playability
   authors=Janne Paavilainen, Hannu Korhonen, Elina Koskinen, Kati Alha
   venue=Oxford Scholarship Online cited_by=4
   abstract=The fierce competition in the video games market and new revenue models such as free-to-play emphasize the importance of good playability for first-time user experience and retention. Cost-effective and flexible evaluation methods such as heuristic evaluation is suitable for identifying playability problems in different phases of the game development life cycle. In this chapte…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_order_greedy ===
family: knapsack
label: Order-greedy 0-1 (matches main Go solver)
definition: Take items in file order if they fit.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Order-greedy take-if-fits (not_mappable), First-fit knapsack (not_mappable)
Works:
1. doi=10.1287/opre.27.6.1101 year=1979 title=New Greedy-Like Heuristics for the Multidimensional 0-1 Knapsack Problem
   authors=Richard Loulou, Eleftherios Michaelides
   venue=Operations Research cited_by=82
   abstract=In this paper, we develop four heuristic methods to obtain approximate solutions to the multidimensional 0-1 knapsack problem. The four methods are tested on a number of problems of various sizes. The solutions are compared to the rigorous optimum as well as to a heuristic method of Toyoda. They are statistically better than the latter, with average relative errors of the orde…
2. doi=10.22541/au.172477608.87013147/v1 year=2024 title=Beyond Pseudo-First-Order: A Better Way to Fit Kinetic Data to Determine Ligand-Receptor Binding Parameters in One Single Fit.
   authors=Jacques Durr, Harvey Motulsky
   venue=None cited_by=1
   abstract=Protocols in hormone-receptor kinetics minimize the Hormone’s Bound fraction since minimizing ligand depletion (LD) allows assuming that (H-B)≅H, hence fitting a simplified pseudo-first-order (PFO) equation to obtain both rate constants, kon and koff, total receptor Bmax, and ns, the ligand’s fraction nonspecifically bound (NSB). However, this widespread method still lacks tho…
3. doi=10.29007/fx82 year=2018 title=An Iterated Semi-Greedy Algorithm for the 0-1 Quadratic Knapsack Problem
   authors=Leticia Leonor Pinto Alva, Alexander J. Benavides
   venue=EasyChair Preprints cited_by=1
   abstract=This paper presents a new Iterated Semi-Greedy Algorithm (ISGA) for the 0-1 Quadratic Knapsack Problem.The proposed ISGA is easier to implement, runs faster, and produces comparable results than state-of-the-art methods. Computational evaluation is performed over a benchmark with large instances of 1000 and 2000 objects.

=== kp_prec ===
family: knapsack
label: Precedence knapsack
definition: Item precedences.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Precedence greedy (not_mappable), Topo-order greedy (not_mappable)
Works:
1. doi=10.1287/inte.22.3.100 year=1992 title=Precedence Constrained Routing and Helicopter Scheduling: Heuristic Design
   authors=M. T. Fiala Timlin, W. R. Pulleyblank
   venue=Interfaces cited_by=39
   abstract=Mobil Producing Nigeria has an offshore oil field consisting of approximately 45 platforms. Each day certain platforms must be visited to regulate flow rates and a number of people must be transported between specified pairs of platforms. All transport is performed by helicopter. Mobil wanted to find a route for each daily set of stops that satisfied all the requirements and m…
2. doi=10.1287/ijoc.1030.0050 year=2005 title=A Local-Search-Based Heuristic for the Demand-Constrained Multidimensional Knapsack Problem
   authors=Paola Cappanera, Marco Trubian
   venue=INFORMS Journal on Computing cited_by=38
   abstract=We consider an extension of the 0–1 multidimensional knapsack problem in which there are greater-than-or-equal-to inequalities, called demand constraints, in addition to the standard less-than-or-equal-to constraints. Moreover, the objective function coefficients are not constrained in sign. This problem is worth considering because it is embedded in models of practical applic…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_quadratic ===
family: knapsack
label: Quadratic knapsack
definition: Pairwise profits.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: QKP greedy (not_mappable), QKP local search (not_mappable)
Works:
1. doi=10.1287/ijoc.2013.0555 year=2014 title=A Dynamic Programming Heuristic for the Quadratic Knapsack Problem
   authors=Franklin Djeumou Fomeni, Adam N. Letchford
   venue=INFORMS Journal on Computing cited_by=43
   abstract=It is well known that the standard (linear) knapsack problem can be solved exactly by dynamic programming in 𝒪(nc) time, where n is the number of items and c is the capacity of the knapsack. The quadratic knapsack problem, on the other hand, is NP-hard in the strong sense, which makes it unlikely that it can be solved in pseudo-polynomial time. We show, however, that the dynam…
2. doi=10.29007/fx82 year=2018 title=An Iterated Semi-Greedy Algorithm for the 0-1 Quadratic Knapsack Problem
   authors=Leticia Leonor Pinto Alva, Alexander J. Benavides
   venue=EasyChair Preprints cited_by=1
   abstract=This paper presents a new Iterated Semi-Greedy Algorithm (ISGA) for the 0-1 Quadratic Knapsack Problem.The proposed ISGA is easier to implement, runs faster, and produces comparable results than state-of-the-art methods. Computational evaluation is performed over a benchmark with large instances of 1000 and 2000 objects.
3. doi=10.1007/s10589-026-00811-2 year=2026 title=The quadratic multidimensional knapsack problem: exact, heuristic, and machine learning methods
   authors=Richard J. Forrester, Lucas A. Waddell
   venue=Computational Optimization and Applications cited_by=0
   abstract=Abstract This paper presents a multi-faceted approach to solving the quadratic multidimensional knapsack problem (QMDKP), an NP-hard nonlinear combinatorial optimization problem that has received limited attention in the literature. We introduce a new testbed of QMDKP instances with induced profit-weight correlations and evaluate four linearization strategies for solving the p…

=== kp_robust ===
family: knapsack
label: Robust knapsack
definition: Uncertainty sets.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Worst-case density greedy (not_mappable), Budgeted uncertainty greedy (not_mappable)
Works:
1. doi=10.2139/ssrn.1967411 year=2011 title=Complexity Results and Exact Algorithms for Robust Knapsack Problems
   authors=Fabrice Talla Nobibon, Roel Leus
   venue=None cited_by=1
   abstract=This paper studies the robust knapsack problem, for which solutions are, up to a certain point, immune to data uncertainty. We complement the works found in the literature where uncertainty affects only the profits or only the weights of the items by studying the complexity and approximation of the general setting with uncertainty regarding both the profits and the weights, fo…
2. doi=10.1088/1742-6596/1865/4/042009 year=2021 title=An Efficient Heuristic Algorithm for Solving 0-1 Knapsack Problem
   authors=Hong Yang, Xiong Guo
   venue=Journal of Physics: Conference Series cited_by=1
   abstract=Abstract The model for 0-1 knapsack problem based on greedy strategy and expectation efficiency has some advantages, e.g., quick convergence and low complexity, but it also inherently exists some limitations to be enhanced and improved, such as the restricted greedy and the overmuch calculation on expectation efficiency. To this end, an efficient algorithm is proposed to optim…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_setup ===
family: knapsack
label: Knapsack with setups
definition: Class setup costs.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Setup-aware greedy (not_mappable), Class open/close local search (not_mappable)
Works:
1. doi=10.1111/itor.12381 year=2017 title=Improved dynamic programming and approximation results for the knapsack problem with setups
   authors=Ulrich Pferschy, Rosario Scatamacchia
   venue=International Transactions in Operational Research cited_by=26
   abstract=Abstract In this paper, we consider the 0–1 knapsack problem with setups. Items are grouped into families and if any items of a family are packed, this induces a setup cost as well as a setup resource consumption. We introduce a new dynamic programming algorithm that performs much better than a previous dynamic program and turns out to be also a valid alternative to an exact a…
2. doi=10.1111/itor.13326 year=2023 title=Combining local branching and descent method for solving the multiple‐choice knapsack problem with setups
   authors=Samah Boukhari, Mhand Hifi
   venue=International Transactions in Operational Research cited_by=3
   abstract=Abstract In this paper, the multiple‐choice knapsack problem with setups is tackled with an iterative method, where both local branching and descent method cooperate. First, an iterative procedure is designed for solving a series of mixed integer programming problems combined with a special reduced subproblem; that is, a combined model built by injecting some valid cardinality…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_stochastic ===
family: knapsack
label: Stochastic knapsack
definition: Random profits or weights.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Expected-density greedy (not_mappable), Recourse knapsack (not_mappable)
Works:
1. doi=10.1287/stsy.2019.0055 year=2020 title=Logarithmic Regret in the Dynamic and Stochastic Knapsack Problem with Equal Rewards
   authors=Alessandro Arlotto, Xinchang Xie
   venue=Stochastic Systems cited_by=11
   abstract=We study a dynamic and stochastic knapsack problem in which a decision maker is sequentially presented with items arriving according to a Bernoulli process over n discrete time periods. Items have equal rewards and independent weights that are drawn from a known nonnegative continuous distribution F. The decision maker seeks to maximize the expected total reward of the items t…
2. doi=10.1002/asmb.2389 year=2018 title=Heuristic policies for stochastic knapsack problem with time‐varying random demand
   authors=Yingdong Lu
   venue=Applied Stochastic Models in Business and Industry cited_by=1
   abstract=Abstract In this paper, we consider the classic stochastic (dynamic) knapsack problem, a fundamental mathematical model in revenue management, with general time‐varying random demand. Our main goal is to study the optimal policies, which can be obtained by solving the dynamic programming formulated for the problem, both qualitatively and quantitatively. It is well known that,…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== kp_time ===
family: knapsack
label: Time-dependent knapsack
definition: Profits vary with time.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Time-slot greedy (not_mappable), TD knapsack local search (not_mappable)
Works:
1. doi=10.4028/www.scientific.net/amr.339.332 year=2011 title=Comparison of Heuristic for Flow Shop Scheduling Problems with Sequence Dependent Setup Time
   authors=Parinya Kaweegitbundit
   venue=Advanced Materials Research cited_by=5
   abstract=This paper considers flow shop scheduling problems with sequence dependent setup time. The makespan criterion has been considered. In this paper presented a comparison of three heuristics for solves this problem. The memetic algorithm, genetic algorithm and NEH heuristic have been compared. In the experimental, the result from memetic algorithm is maximum the best solution. Th…
2. doi=10.1101/2020.04.02.20050153 year=2020 title=CoViD–19: Meta-heuristic optimization based forecast method on time dependent bootstrapped data
   authors=Livio Fenga, Carlo Del Castello
   venue=None cited_by=4
   abstract=Abstract A compounded method – exploiting the searching capabilities of an operation research algorithm and the power of bootstrap techniques – is presented. The resulting algorithm has been successfully tested to predict the turning point reached by the epidemic curve followed by the CoViD–19 virus in Italy. Futures lines of research, which include the generalization of the m…
3. doi=10.1002/asmb.2389 year=2018 title=Heuristic policies for stochastic knapsack problem with time‐varying random demand
   authors=Yingdong Lu
   venue=Applied Stochastic Models in Business and Industry cited_by=1
   abstract=Abstract In this paper, we consider the classic stochastic (dynamic) knapsack problem, a fundamental mathematical model in revenue management, with general time‐varying random demand. Our main goal is to study the optimal policies, which can be obtained by solving the dynamic programming formulated for the problem, both qualitatively and quantitatively. It is well known that,…

=== subset_sum ===
family: knapsack
label: Subset sum
definition: Hit a target sum.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Greedy subset sum (not_mappable), Differencing subset sum (not_mappable)
Works:
1. doi=10.31219/osf.io/xhbd6_v1 year=2017 title=Trivial geometric heuristic for subset sum problem
   authors=R U
   venue=None cited_by=0
   abstract=All exact algorithms for solving subset sum problem (SUBSET\_SUM) are exponential (brute force, branch and bound search, dynamic programming which is pseudo-polynomial). To find the approximate solutions both a classical greedy algorithm and its improved variety, and different approximation schemes are used.This paper is an attempt to build another greedy algorithm by transfer…
2. doi=10.31219/osf.io/xhbd6 year=2017 title=Trivial geometric heuristic for subset sum problem
   authors=R U
   venue=None cited_by=0
   abstract=All exact algorithms for solving subset sum problem (SUBSET\_SUM) are exponential (brute force, branch and bound search, dynamic programming which is pseudo-polynomial). To find the approximate solutions both a classical greedy algorithm and its improved variety, and different approximation schemes are used.This paper is an attempt to build another greedy algorithm by transfer…
3. doi=10.31219/osf.io/8dpha year=2024 title=Solving subset sum in polynomial time and proving  P = NP
   authors=Samir Bouftass
   venue=None cited_by=0
   abstract=In this paper, we show that subset sum problem is solvable in polynomial time
