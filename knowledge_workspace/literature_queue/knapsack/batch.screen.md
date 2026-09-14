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

family: knapsack

=== kp_01 ===
label: 0-1 knapsack
definition: Take or leave each item.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Density greedy (not_mappable), Greedy + swap (not_mappable)
Works:
1. doi=10.23956/ijermt.v6i7.181 year=2018 title=Clustering Analysis of Greedy Heuristic Method in Zero_One Knapsack Problem
   authors=V. Selvi
   venue=International Journal of Emerging Research in Management and Technology cited_by=0
   abstract=Knapsack problem is a surely understood class of optimization problems, which tries to expand the profit of items in a knapsack without surpassing its capacity, Knapsack can be solved by several algorithms such like Greedy, dynamic programming, Branch &amp; bound etc. The solution to the zero_one knapsack problem (KP) can be viewed as the result of a sequence of decision. Clustering is the process of resolving that type of applications. Different clustering application for grouping elements with equal priority. In this paper we are introducing greedy heuristic algorithm for solving zero_one knapsack problem. We will exhibit a relative investigation of the Greedy, dynamic programming, B&amp;…
2. doi=10.1016/0167-6377(92)90065-b year=1992 title=A total-value greedy heuristic for the integer knapsack problem
   authors=Rajeev Kohli, Ramesh Krishnamurti
   venue=Operations Research Letters cited_by=12
   abstract=(missing)
3. doi=10.1016/0377-2217(92)90179-d year=1992 title=A complementary greedy heuristic for the knapsack problem
   authors=D.J. White
   venue=European Journal of Operational Research cited_by=2
   abstract=(missing)
4. doi=10.2139/ssrn.1342562 year=2009 title=Subsidies, Knapsack Auctions and Dantzig's Greedy Heuristic
   authors=Ludwig Ensthaler, Thomas Giebe
   venue=SSRN Electronic Journal cited_by=1
   abstract=(missing)
5. doi=10.52202/066390-0035 year=2022 title=OPTIMISATION OF A FLEXIBLE MANUFACTURING SYSTEM THROUGH THE APPLICATION OF GREEDY KNAPSACK HEURISTIC
   authors=M. Dewa
   venue=33rd Annual Southern African Institute for Industrial Engineering Conference (SAIIE33) cited_by=0
   abstract=(missing)

=== kp_bounded ===
label: Bounded knapsack
definition: Bounded copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Bounded density greedy (not_mappable), Core algorithm heuristic (not_mappable)
Works:
1. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des solutions puis la reconstruction. En partant de ce principe, trois algorithmes approchés ont été étudiés, en partant d'une approche mono-solution vers des approches à base de population. Dans une première partie, un algorithme réactif a été proposé ; il s'appuie sur deux phases imbriquées dans une recherche itérative…
2. doi=10.2139/ssrn.170989 year=1999 title=Complexity, Bounded Rationality, and Heuristic Search
   authors=William Bentley MacLeod
   venue=None cited_by=0
   abstract=This paper explores the use of heuristic search algorithms for modeling human decision making. It is shown that this algorithm is consistent with many observed behavioral regularities, and may help explain deviations from rational choice. The main insight is that the heuristic function can be viewed as formal implementation of one aspect of emotion as discussed in {Descarte's Error} by Antonio Damasio. Consistent with Damasio's observations, it is shown that the quality of decision making is very sensitive to the nature of the heuristic ("emotion"), and hence this may help us better understand the role of emotion in rational choice theory.
3. doi=10.2139/ssrn.6203952 year=2026 title=Knapsack Problem with All-Neighbors  Constraint on Bounded-Treewidth or Chordal Directed Graphs
   authors=Shih-Chieh Liao, Wing-Kai Hon
   venue=None cited_by=0
   abstract=We study the Knapsack Problem under all in-neighbor constraints (KPaN) on directed graphs, where an item can be selected only if all its in-neighbors are also selected. We focus on two special cases: when the underlying undirected graph has bounded treewidth, and when it is chordal. For both, we develop pseudo-polynomial time algorithms that run in time polynomial in the number $n$ of vertices and the total profit~$Q$, using dynamic programming over nice tree decompositions and clique trees, respectively. For the bounded treewidth case, our first algorithm improves the running time of the state-of-the-art result, and our second algorithm reduces the $Q^2$ factor to $Q$ in the running time (…
4. doi=10.1007/978-3-540-24777-7_7 year=2004 title=The Bounded Knapsack Problem
   authors=Hans Kellerer, Ulrich Pferschy, David Pisinger
   venue=Knapsack Problems cited_by=7
   abstract=(missing)
5. doi=10.2139/ssrn.1342562 year=2009 title=Subsidies, Knapsack Auctions and Dantzig's Greedy Heuristic
   authors=Ludwig Ensthaler, Thomas Giebe
   venue=SSRN Electronic Journal cited_by=1
   abstract=(missing)

=== kp_md ===
label: Multidimensional knapsack
definition: Several resource constraints.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Surrogate density greedy (not_mappable), MDKP local search (not_mappable)
Works:
1. doi=10.1007/springerreference_72490 year=None title=Multidimensional Knapsack Problems
   authors=
   venue=SpringerReference cited_by=20
   abstract=(missing)
2. doi=10.1007/s11590-020-01611-1 year=2020 title=A randomized heuristic repair for the multidimensional knapsack problem
   authors=Jean P. Martins, Bruno C. Ribas
   venue=Optimization Letters cited_by=10
   abstract=(missing)
3. doi=10.1109/icpci.2012.6486459 year=2012 title=Hybrid heuristic algorithm for the multidimensional knapsack problem
   authors=Can Atılgan, Urfat Nuriyev
   venue=2012 IV International Conference "Problems of Cybernetics and Informatics" (PCI) cited_by=3
   abstract=(missing)
4. doi=10.1109/cis.2017.00020 year=2017 title=BPSOBDE: A Binary Version of Hybrid Heuristic Algorithm for Multidimensional Knapsack Problems
   authors=Li Zhang, Hong Li
   venue=2017 13th International Conference on Computational Intelligence and Security (CIS) cited_by=1
   abstract=(missing)
5. doi=10.3406/ecoap.1974.2989 year=1974 title=Heuristic Methods for the Multidimensional 0/1 Knapsack Problem
   authors=Willy S. Herroelen
   venue=Économie appliquée cited_by=0
   abstract=(missing)

=== kp_multiple ===
label: Multiple knapsack
definition: Several knapsacks.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: MKP greedy assign (not_mappable), MKP local search (not_mappable)
Works:
1. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des solutions puis la reconstruction. En partant de ce principe, trois algorithmes approchés ont été étudiés, en partant d'une approche mono-solution vers des approches à base de population. Dans une première partie, un algorithme réactif a été proposé ; il s'appuie sur deux phases imbriquées dans une recherche itérative…
2. doi=10.1007/978-3-642-38679-4_55 year=2013 title=Improved Swap Heuristic for the Multiple Knapsack Problem
   authors=Yacine Laalaoui
   venue=Lecture Notes in Computer Science cited_by=4
   abstract=(missing)
3. doi=10.46254/ap03.20220384 year=None title=Efficient mat heuristic for solving the Multiple-Choice Knapsack Problem with Setup
   authors=
   venue=Proceedings of the International Conference on Industrial Engineering and Operations Management cited_by=2
   abstract=(missing)
4. doi=10.1504/ijcsyse.2015.077065 year=2015 title=Efficient heuristic for very large 0/1 multiple knapsack problems
   authors=Yacine Laalaoui, Hedi Mhalla
   venue=International Journal of Computational Systems Engineering cited_by=2
   abstract=(missing)
5. doi=10.11648/j.ijiis.20150402.11 year=2015 title=Local Search Heuristic for Multiple Knapsack Problem
   authors=Balbal Samir
   venue=International Journal of Intelligent Information Systems cited_by=1
   abstract=(missing)

=== kp_unbounded ===
label: Unbounded knapsack
definition: Unlimited copies.
eoh_map: {"status": "not_registered", "adapter_kind": "not_mappable"}
target_heuristics: Unbounded density greedy (not_mappable), Greedy by value (not_mappable)
Works:
1. doi=10.3390/math12121878 year=2024 title=An Improved Unbounded-DP Algorithm for the Unbounded Knapsack Problem with Bounded Coefficients
   authors=Yang Yang
   venue=Mathematics cited_by=1
   abstract=Benchmark instances for the unbounded knapsack problem are typically generated according to specific criteria within a given constant range R, and these instances can be referred to as the unbounded knapsack problem with bounded coefficients (UKPB). In order to increase the difficulty of solving these instances, the knapsack capacity C is usually set to a very large value. While current efficient algorithms primarily center on the Fast Fourier Transform (FFT) and (min,+)-convolution method, there is a simpler method worth considering. In this paper, based on the basic Unbounded-DP algorithm, we utilize a recent branch and bound (B&amp;B) result and basic theory of linear Diophantine equatio…
2. doi=10.70675/77bb03b1z6f68z47dbz931cze0d45ddac1f0 year=None title=Heuristic methods for solving knapsack type problems
   authors=Thekra Al-Douri
   venue=None cited_by=0
   abstract=Méthodes heuristiques pour les problèmes de type knapsack Les travaux de recherche de cette thèse s'articulent autour de la résolution du problème du sac à dos en min-max avec de multiples scénarios (en anglais, max-min knapsack problem with multi-scenarios). Cette thèse propose trois approches, plutôt complémentaires, en s'appuyant principalement sur l'aspect perturbation des solutions puis la reconstruction. En partant de ce principe, trois algorithmes approchés ont été étudiés, en partant d'une approche mono-solution vers des approches à base de population. Dans une première partie, un algorithme réactif a été proposé ; il s'appuie sur deux phases imbriquées dans une recherche itérative…
3. doi=10.1007/978-3-540-24777-7_8 year=2004 title=The Unbounded Knapsack Problem
   authors=Hans Kellerer, Ulrich Pferschy, David Pisinger
   venue=Knapsack Problems cited_by=4
   abstract=(missing)
4. doi=10.2139/ssrn.1342562 year=2009 title=Subsidies, Knapsack Auctions and Dantzig's Greedy Heuristic
   authors=Ludwig Ensthaler, Thomas Giebe
   venue=SSRN Electronic Journal cited_by=1
   abstract=(missing)
5. doi=10.1007/978-3-540-76796-1_10 year=None title=The Unbounded Knapsack Problem
   authors=T. C. Hu, Leo Landa, Man-Tak Shing
   venue=Research Trends in Combinatorial Optimization cited_by=0
   abstract=(missing)
