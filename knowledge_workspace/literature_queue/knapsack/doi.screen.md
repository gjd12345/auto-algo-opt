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

=== kp_01 ===
family: knapsack
label: 0-1 knapsack
definition: Take or leave each item.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Density greedy (not_mappable), Greedy + swap (not_mappable)
Works:
1. doi=10.1287/opre.5.2.266 year=1957 title=Discrete-Variable Extremum Problems
   authors=George B. Dantzig
   venue=Operations Research cited_by=648
   abstract=This paper reviews some recent successes in the use of linear programming methods for the solution of discrete-variable extremum problems. One example of the use of the multistage approach of dynamic programming for this purpose is also discussed.
2. doi=10.1287/opre.27.3.431 year=1979 title=The Status of Nonlinear Programming Software
   authors=Allan D. Waren, Leon S. Lasdon
   venue=Operations Research cited_by=52
   abstract=Desirable features of software for solving nonlinear optimization problems are discussed, and several available codes for solving NLPs are described in terms of these features. Codes are classified by algorithm type. Addresses where codes may be obtained are given. The paper concludes with a brief survey of available computational experience with several classes of algorithms…
3. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…

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

=== kp_bounded ===
family: knapsack
label: Bounded knapsack
definition: Bounded copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Bounded density greedy (not_mappable), Core algorithm heuristic (not_mappable)
Works:
1. doi=10.1287/opre.27.3.431 year=1979 title=The Status of Nonlinear Programming Software
   authors=Allan D. Waren, Leon S. Lasdon
   venue=Operations Research cited_by=52
   abstract=Desirable features of software for solving nonlinear optimization problems are discussed, and several available codes for solving NLPs are described in terms of these features. Codes are classified by algorithm type. Addresses where codes may be obtained are given. The paper concludes with a brief survey of available computational experience with several classes of algorithms…
2. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…
3. doi=10.2139/ssrn.170989 year=1999 title=Complexity, Bounded Rationality, and Heuristic Search
   authors=William Bentley MacLeod
   venue=None cited_by=0
   abstract=This paper explores the use of heuristic search algorithms for modeling human decision making. It is shown that this algorithm is consistent with many observed behavioral regularities, and may help explain deviations from rational choice. The main insight is that the heuristic function can be viewed as formal implementation of one aspect of emotion as discussed in {Descarte's…

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

=== kp_density ===
family: knapsack
label: Profit/weight density greedy
definition: Sort by density then take.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Dantzig density greedy (not_mappable), Critical-item greedy (not_mappable)
Works:
1. doi=10.1287/opre.5.2.266 year=1957 title=Discrete-Variable Extremum Problems
   authors=George B. Dantzig
   venue=Operations Research cited_by=648
   abstract=This paper reviews some recent successes in the use of linear programming methods for the solution of discrete-variable extremum problems. One example of the use of the multistage approach of dynamic programming for this purpose is also discussed.
2. doi=10.1287/opre.27.3.431 year=1979 title=The Status of Nonlinear Programming Software
   authors=Allan D. Waren, Leon S. Lasdon
   venue=Operations Research cited_by=52
   abstract=Desirable features of software for solving nonlinear optimization problems are discussed, and several available codes for solving NLPs are described in terms of these features. Codes are classified by algorithm type. Addresses where codes may be obtained are given. The paper concludes with a brief survey of available computational experience with several classes of algorithms…
3. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…

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
1. doi=10.1287/opre.13.4.517 year=1965 title=An Additive Algorithm for Solving Linear Programs with Zero-One Variables
   authors=Egon Balas
   venue=Operations Research cited_by=504
   abstract=An algorithm is proposed for solving linear programs with variables constrained to take only one of the values 0 or 1. It starts by setting all the n variables equal to 0, and consists of a systematic procedure of successively assigning to certain variables the value 1, in such a way that after trying a (small) part of all the 2 n possible combinations, one obtains either an o…
2. doi=10.1287/opre.16.1.103 year=1968 title=Dynamic Programming Algorithms for the Integer Programming Problem—I: The Integer Programming Problem Viewed as a Knapsack Type Problem
   authors=Jeremy F. Shapiro
   venue=Operations Research cited_by=47
   abstract=Gomory has transformed the integer programming problem into a related group optimization problem which can be more easily solved. An optimal solution to the group problem is optimal for the integer programming problem from which it is derived if the solution is feasible. An algorithm (IP Algorithm I) for solving the group optimization problem is developed, and sufficient condi…
3. doi=10.22531/muglajsci.469475 year=2019 title=COMPARISON OF CLASSIC AND GREEDY HEURISTIC ALGORITHM RESULTS IN INTEGER PROGRAMMING: KNAPSACK PROBLEMS
   authors=Burcu DURMUŞ, Öznur İŞÇİ GÜNERİ, Aynur İNCEKIRIK
   venue=Mugla Journal of Science and Technology cited_by=4
   abstract=This study is designed to investigate the comparison of Greedy and classic algorithm solution results and the results of solution algorithms for integer linear programming (ILP) problems. The purpose of the study is to examine the heuristic Greedy algorithm that solves the ILP problems and to reveal the differences and similarities between the classic and heuristic Greedy algo…

=== kp_integer ===
family: knapsack
label: Integer knapsack
definition: Integer copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Integer density greedy (not_mappable), Rounding heuristic (not_mappable)
Works:
1. doi=10.1287/opre.5.2.266 year=1957 title=Discrete-Variable Extremum Problems
   authors=George B. Dantzig
   venue=Operations Research cited_by=648
   abstract=This paper reviews some recent successes in the use of linear programming methods for the solution of discrete-variable extremum problems. One example of the use of the multistage approach of dynamic programming for this purpose is also discussed.
2. doi=10.1287/opre.27.3.431 year=1979 title=The Status of Nonlinear Programming Software
   authors=Allan D. Waren, Leon S. Lasdon
   venue=Operations Research cited_by=52
   abstract=Desirable features of software for solving nonlinear optimization problems are discussed, and several available codes for solving NLPs are described in terms of these features. Codes are classified by algorithm type. Addresses where codes may be obtained are given. The paper concludes with a brief survey of available computational experience with several classes of algorithms…
3. doi=10.1287/opre.16.1.103 year=1968 title=Dynamic Programming Algorithms for the Integer Programming Problem—I: The Integer Programming Problem Viewed as a Knapsack Type Problem
   authors=Jeremy F. Shapiro
   venue=Operations Research cited_by=47
   abstract=Gomory has transformed the integer programming problem into a related group optimization problem which can be more easily solved. An optimal solution to the group problem is optimal for the integer programming problem from which it is derived if the solution is feasible. An algorithm (IP Algorithm I) for solving the group optimization problem is developed, and sufficient condi…

=== kp_md ===
family: knapsack
label: Multidimensional knapsack
definition: Several resource constraints.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Surrogate density greedy (not_mappable), MDKP local search (not_mappable)
Works:
1. doi=10.1287/ijoc.11.1.15 year=1999 title=Neural Networks for Combinatorial Optimization: A Review of More Than a Decade of Research
   authors=Kate A. Smith
   venue=INFORMS Journal on Computing cited_by=302
   abstract=It has been over a decade since neural networks were first applied to solve combinatorial optimization problems. During this period, enthusiasm has been erratic as new approaches are developed and (sometimes years later) their limitations are realized. This article briefly summarizes the work that has been done and presents the current standing of neural networks for combinato…
2. doi=10.1287/opre.27.6.1101 year=1979 title=New Greedy-Like Heuristics for the Multidimensional 0-1 Knapsack Problem
   authors=Richard Loulou, Eleftherios Michaelides
   venue=Operations Research cited_by=82
   abstract=In this paper, we develop four heuristic methods to obtain approximate solutions to the multidimensional 0-1 knapsack problem. The four methods are tested on a number of problems of various sizes. The solutions are compared to the rigorous optimum as well as to a heuristic method of Toyoda. They are statistically better than the latter, with average relative errors of the orde…
3. doi=10.1162/106365605774666886 year=2005 title=Empirical Analysis of Locality, Heritability and Heuristic Bias in Evolutionary Algorithms: A Case Study for the Multidimensional Knapsack Problem
   authors=Günther R. Raidl, Jens Gottlieb
   venue=Evolutionary Computation cited_by=70
   abstract=Our main aim is to provide guidelines and practical help for the design of appropriate representations and operators for evolutionary algorithms (EAs). For this purpose, we propose techniques to obtain a better understanding of various effects in the interplay of the representation and the operators. We study six different representations and associated variation operators in…

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

=== kp_multiple ===
family: knapsack
label: Multiple knapsack
definition: Several knapsacks.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: MKP greedy assign (not_mappable), MKP local search (not_mappable)
Works:
1. doi=10.1287/opre.27.3.431 year=1979 title=The Status of Nonlinear Programming Software
   authors=Allan D. Waren, Leon S. Lasdon
   venue=Operations Research cited_by=52
   abstract=Desirable features of software for solving nonlinear optimization problems are discussed, and several available codes for solving NLPs are described in terms of these features. Codes are classified by algorithm type. Addresses where codes may be obtained are given. The paper concludes with a brief survey of available computational experience with several classes of algorithms…
2. doi=10.1145/2541012.2541014 year=2013 title=A fast and scalable multidimensional multiple-choice knapsack heuristic
   authors=Hamid Shojaei, Twan Basten, Marc Geilen, Azadeh Davoodi
   venue=ACM Transactions on Design Automation of Electronic Systems cited_by=32
   abstract=Many combinatorial optimization problems in the embedded systems and design automation domains involve decision making in multidimensional spaces. The multidimensional multiple-choice knapsack problem (MMKP) is among the most challenging of the encountered optimization problems. MMKP problem instances appear for example in chip multiprocessor runtime resource management and in…
3. doi=10.3390/math10040602 year=2022 title=A Memetic Algorithm with a Novel Repair Heuristic for the Multiple-Choice Multidimensional Knapsack Problem
   authors=Jaeyoung Yang, Yong-Hyuk Kim, Yourim Yoon
   venue=Mathematics cited_by=11
   abstract=We propose a memetic algorithm for the multiple-choice multidimensional knapsack problem (MMKP). In this study, we focus on finding good solutions for the MMKP instances, for which feasible solutions rarely exist. To find good feasible solutions, we introduce a novel repair heuristic based on the tendency function and a genetic search for the function approximation. Even when…

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
1. doi=10.1287/opre.5.2.266 year=1957 title=Discrete-Variable Extremum Problems
   authors=George B. Dantzig
   venue=Operations Research cited_by=648
   abstract=This paper reviews some recent successes in the use of linear programming methods for the solution of discrete-variable extremum problems. One example of the use of the multistage approach of dynamic programming for this purpose is also discussed.
2. doi=10.1287/opre.27.6.1101 year=1979 title=New Greedy-Like Heuristics for the Multidimensional 0-1 Knapsack Problem
   authors=Richard Loulou, Eleftherios Michaelides
   venue=Operations Research cited_by=82
   abstract=In this paper, we develop four heuristic methods to obtain approximate solutions to the multidimensional 0-1 knapsack problem. The four methods are tested on a number of problems of various sizes. The solutions are compared to the rigorous optimum as well as to a heuristic method of Toyoda. They are statistically better than the latter, with average relative errors of the orde…
3. doi=10.1287/opre.27.3.431 year=1979 title=The Status of Nonlinear Programming Software
   authors=Allan D. Waren, Leon S. Lasdon
   venue=Operations Research cited_by=52
   abstract=Desirable features of software for solving nonlinear optimization problems are discussed, and several available codes for solving NLPs are described in terms of these features. Codes are classified by algorithm type. Addresses where codes may be obtained are given. The paper concludes with a brief survey of available computational experience with several classes of algorithms…

=== kp_stochastic ===
family: knapsack
label: Stochastic knapsack
definition: Random profits or weights.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Expected-density greedy (not_mappable), Recourse knapsack (not_mappable)
Works:
1. doi=10.1287/opre.43.3.477 year=1995 title=A New Scenario Decomposition Method for Large-Scale Stochastic Optimization
   authors=John M. Mulvey, Andrzej Ruszczyński
   venue=Operations Research cited_by=281
   abstract=A novel parallel decomposition algorithm is developed for large, multistage stochastic optimization problems. The method decomposes the problem into subproblems that correspond to scenarios. The subproblems are modified by separable quadratic terms to coordinate the scenario solutions. Convergence of the coordination procedure is proven for linear programs. Subproblems are sol…
2. doi=10.1287/stsy.2019.0055 year=2020 title=Logarithmic Regret in the Dynamic and Stochastic Knapsack Problem with Equal Rewards
   authors=Alessandro Arlotto, Xinchang Xie
   venue=Stochastic Systems cited_by=11
   abstract=We study a dynamic and stochastic knapsack problem in which a decision maker is sequentially presented with items arriving according to a Bernoulli process over n discrete time periods. Items have equal rewards and independent weights that are drawn from a known nonnegative continuous distribution F. The decision maker seeks to maximize the expected total reward of the items t…
3. doi=10.1002/asmb.2389 year=2018 title=Heuristic policies for stochastic knapsack problem with time‐varying random demand
   authors=Yingdong Lu
   venue=Applied Stochastic Models in Business and Industry cited_by=1
   abstract=Abstract In this paper, we consider the classic stochastic (dynamic) knapsack problem, a fundamental mathematical model in revenue management, with general time‐varying random demand. Our main goal is to study the optimal policies, which can be obtained by solving the dynamic programming formulated for the problem, both qualitatively and quantitatively. It is well known that,…

=== kp_unbounded ===
family: knapsack
label: Unbounded knapsack
definition: Unlimited copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Unbounded density greedy (not_mappable), Greedy by value (not_mappable)
Works:
1. doi=10.1287/opre.5.2.266 year=1957 title=Discrete-Variable Extremum Problems
   authors=George B. Dantzig
   venue=Operations Research cited_by=648
   abstract=This paper reviews some recent successes in the use of linear programming methods for the solution of discrete-variable extremum problems. One example of the use of the multistage approach of dynamic programming for this purpose is also discussed.
2. doi=10.3390/math12121878 year=2024 title=An Improved Unbounded-DP Algorithm for the Unbounded Knapsack Problem with Bounded Coefficients
   authors=Yang Yang
   venue=Mathematics cited_by=1
   abstract=Benchmark instances for the unbounded knapsack problem are typically generated according to specific criteria within a given constant range R, and these instances can be referred to as the unbounded knapsack problem with bounded coefficients (UKPB). In order to increase the difficulty of solving these instances, the knapsack capacity C is usually set to a very large value. Whi…
3. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des…

=== subset_sum ===
family: knapsack
label: Subset sum
definition: Hit a target sum.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Greedy subset sum (not_mappable), Differencing subset sum (not_mappable)
Works:
1. doi=10.1287/opre.5.2.266 year=1957 title=Discrete-Variable Extremum Problems
   authors=George B. Dantzig
   venue=Operations Research cited_by=648
   abstract=This paper reviews some recent successes in the use of linear programming methods for the solution of discrete-variable extremum problems. One example of the use of the multistage approach of dynamic programming for this purpose is also discussed.
2. doi=10.1137/0202007 year=1973 title=On the Number of Nonscalar Multiplications Necessary to Evaluate Polynomials
   authors=Michael S. Paterson, Larry J. Stockmeyer
   venue=SIAM Journal on Computing cited_by=248
   abstract=We present algorithms which use only $O(\sqrt n )$ nonscalar multiplications (i.e. multiplications involving “x” on both sides) to evaluate polynomials of degree n, and proofs that at least $\sqrt n $ are required. These results have practical application in the evaluation of matrix polynomials with scalar coefficients, since the “matrix $ \times $ matrix” multiplications are…
3. doi=10.31219/osf.io/xhbd6_v1 year=2017 title=Trivial geometric heuristic for subset sum problem
   authors=R U
   venue=None cited_by=0
   abstract=All exact algorithms for solving subset sum problem (SUBSET\_SUM) are exponential (brute force, branch and bound search, dynamic programming which is pseudo-polynomial). To find the approximate solutions both a classical greedy algorithm and its improved variety, and different approximation schemes are used.This paper is an attempt to build another greedy algorithm by transfer…
