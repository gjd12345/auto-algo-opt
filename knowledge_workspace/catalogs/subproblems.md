# 二级子问题目录

Thirty secondary problems per literature-standard family. mixer_split and insertships_routing must not be padded. target_heuristics are search/screen hints, not claims that main implements them.

二级子问题是文献变体，不是新的 EoH `problem_id`。`target_heuristics` 只是检索/筛读提示。

## tsp — Traveling salesman (30)

fill_policy: `require_30`; registered_eoh: ['tsp_construct', 'tsp_2opt']

| id | 子问题 | eoh_map | 目标启发式 |
| --- | --- | --- | --- |
| `tsp_euclidean` | Euclidean TSP | possible/next_node_score | Nearest Neighbor (next_node_score), Farthest Insertion (not_mappable) |
| `tsp_asymmetric` | Asymmetric TSP | possible/next_node_score | Directed Nearest Neighbor (next_node_score), Directed 3-opt (move_selector) |
| `tsp_metric` | Metric TSP | possible/next_node_score | Nearest Neighbor (next_node_score), Christofides (not_mappable) |
| `tsp_open` | Open TSP / Hamiltonian path | possible/next_node_score | Path Nearest Neighbor (next_node_score), Cheapest Insertion path (not_mappable) |
| `tsp_tw` | TSP with time windows | not_mappable/not_mappable | I1 insertion TSPTW (not_mappable), Time-window NN (not_mappable) |
| `tsp_sop` | Sequential ordering / precedences | not_mappable/not_mappable | Precedence insertion (not_mappable), Asymmetric SOP local search (not_mappable) |
| `tsp_clustered` | Clustered TSP | possible/next_node_score | Cluster-first NN (next_node_score), Intra-cluster 2-opt (move_selector) |
| `tsp_gtsp` | Generalized TSP | not_mappable/not_mappable | NN among clusters (not_mappable), GI3 local search (not_mappable) |
| `tsp_prize` | Prize-collecting TSP | not_mappable/not_mappable | Prize insertion (not_mappable), Goemans-Williamson PCTSP (not_mappable) |
| `tsp_orienteering` | Orienteering / selective TSP | not_mappable/not_mappable | Prize/distance greedy (not_mappable), S-algorithm orienteering (not_mappable) |
| `tsp_mtsp` | Multiple TSP | not_mappable/not_mappable | mTSP NN assignment (not_mappable), mTSP 2-opt (not_mappable) |
| `tsp_minmax` | Min-max mTSP | not_mappable/not_mappable | Balanced NN (not_mappable), Min-max 2-opt (not_mappable) |
| `tsp_pdp` | TSP with pickups and deliveries | not_mappable/not_mappable | Paired insertion (not_mappable), PDP local search (not_mappable) |
| `tsp_dynamic` | Dynamic / online TSP | possible/next_node_score | Online NN (next_node_score), Replanning 2-opt (move_selector) |
| `tsp_stochastic` | Stochastic TSP | not_mappable/not_mappable | Expected-cost NN (not_mappable), Recourse 2-opt (not_mappable) |
| `tsp_time_dependent` | Time-dependent TSP | not_mappable/not_mappable | Time-dependent NN (not_mappable), TD 2-opt (not_mappable) |
| `tsp_neighborhoods` | TSP with neighborhoods | not_mappable/not_mappable | Region-greedy visit (not_mappable), TspN sampling (not_mappable) |
| `tsp_bottleneck` | Bottleneck TSP | possible/next_node_score | Bottleneck NN (next_node_score), Threshold binary search + MST (not_mappable) |
| `tsp_multiobjective` | Multi-objective TSP | not_mappable/not_mappable | Weighted-sum NN (not_mappable), Pareto 2-opt (not_mappable) |
| `tsp_colored` | Colored TSP | not_mappable/not_mappable | Color-feasible NN (not_mappable), Colored local search (not_mappable) |
| `tsp_large` | Large-scale Euclidean TSP | possible/move_selector | Lin-Kernighan (not_mappable), Candidate-list 2-opt (move_selector) |
| `tsp_noisy` | Noisy / black-box distances | not_mappable/not_mappable | Robust NN (not_mappable), Repeated 2-opt (not_mappable) |
| `tsp_forbidden` | Forbidden edges | possible/next_node_score | Constrained NN (next_node_score), Infeasible-edge 2-opt (move_selector) |
| `tsp_covering` | Covering salesman | not_mappable/not_mappable | Covering greedy (not_mappable), Set-cover + TSP (not_mappable) |
| `tsp_purchaser` | Traveling purchaser | not_mappable/not_mappable | TPP savings (not_mappable), Market insertion (not_mappable) |
| `tsp_drone` | TSP with drone | not_mappable/not_mappable | Truck-drone NN (not_mappable), Drone launch local search (not_mappable) |
| `tsp_fuel` | Fuel / replenishment TSP | not_mappable/not_mappable | Refuel insertion (not_mappable), Fuel-feasible NN (not_mappable) |
| `tsp_angular` | Angular-metric TSP | possible/next_node_score | Angle-aware NN (next_node_score), Or-opt for turning cost (move_selector) |
| `tsp_construct` | Constructive-only TSP | possible/next_node_score | Nearest Neighbor (next_node_score), Cheapest Insertion (not_mappable) |
| `tsp_local` | Local-search TSP | possible/move_selector | 2-opt (move_selector), Or-opt (not_mappable) |

## cvrp — Vehicle routing (30)

fill_policy: `require_30`; registered_eoh: ['cvrp_construct']

| id | 子问题 | eoh_map | 目标启发式 |
| --- | --- | --- | --- |
| `cvrp_basic` | Capacitated VRP | possible/next_node_score | Nearest feasible customer (next_node_score), Clarke-Wright savings as next-node score (next_node_score) |
| `vrptw` | VRP with time windows | not_mappable/not_mappable | Solomon I1 (not_mappable), Solomon I2 (not_mappable) |
| `mdvrp` | Multi-depot VRP | not_mappable/not_mappable | Depot assignment + NN (not_mappable), MD savings (not_mappable) |
| `sdvrp` | Split-delivery VRP | not_mappable/not_mappable | Split-delivery savings (not_mappable), Split local search (not_mappable) |
| `ovrp` | Open VRP | possible/next_node_score | Open NN (next_node_score), Open savings (next_node_score) |
| `hfvrp` | Heterogeneous fleet VRP | not_mappable/not_mappable | Type-aware savings (not_mappable), Fleet mix local search (not_mappable) |
| `fsmvrp` | Fleet size and mix | not_mappable/not_mappable | Golden FSM constructive (not_mappable), FSM local search (not_mappable) |
| `vrppd` | VRP with pickups and deliveries | not_mappable/not_mappable | Paired insertion (not_mappable), PDP VND (not_mappable) |
| `pdptw` | PDPTW | not_mappable/not_mappable | PDPTW insertion (not_mappable), PDPTW ALNS (not_mappable) |
| `cvrpb` | VRP with backhauls | not_mappable/not_mappable | Backhaul insertion (not_mappable), Linehaul-first NN (not_mappable) |
| `vrpsdp` | Simultaneous pickup and delivery | not_mappable/not_mappable | SDP NN (not_mappable), SDP local search (not_mappable) |
| `pvrp` | Periodic VRP | not_mappable/not_mappable | Day assignment + CWS (not_mappable), Periodic local search (not_mappable) |
| `irp` | Inventory routing | not_mappable/not_mappable | IRP greedy replenishment (not_mappable), IRP local search (not_mappable) |
| `darp` | Dial-a-ride | not_mappable/not_mappable | DARP insertion (not_mappable), DARP regret (not_mappable) |
| `cvrp_multitrip` | Multi-trip VRP | possible/next_node_score | Multi-trip NN (next_node_score), Trip packing + routing (not_mappable) |
| `cvrp_site` | Site-dependent VRP | not_mappable/not_mappable | Site-feasible NN (not_mappable), Restricted savings (not_mappable) |
| `cvrp_td` | Time-dependent VRP | not_mappable/not_mappable | TD NN (not_mappable), TD local search (not_mappable) |
| `cvrp_stochastic` | Stochastic-demand VRP | not_mappable/not_mappable | Expected-demand NN (not_mappable), Recourse restocking (not_mappable) |
| `cvrp_dynamic` | Dynamic VRP | possible/next_node_score | Online feasible NN (next_node_score), Rolling-horizon 2-opt (not_mappable) |
| `evrp` | Electric VRP | not_mappable/not_mappable | Charge-feasible NN (not_mappable), EVRP insertion (not_mappable) |
| `cvrp_2e` | Two-echelon VRP | not_mappable/not_mappable | Satellite assignment + CWS (not_mappable), 2E-VRP local search (not_mappable) |
| `cvrp_clustered` | Clustered VRP | possible/next_node_score | Cluster-first NN (next_node_score), Sweep-like angular NN (next_node_score) |
| `cvrp_prize` | Prize-collecting VRP | not_mappable/not_mappable | Prize/distance greedy (not_mappable), Selective VRP local search (not_mappable) |
| `cvrp_minveh` | Minimise number of vehicles | possible/next_node_score | Parallel cheapest insertion (not_mappable), Capacity-tight NN (next_node_score) |
| `dcvrp` | Distance-constrained VRP | possible/next_node_score | Length-feasible NN (next_node_score), DCVRP savings (next_node_score) |
| `cvrp_loading` | VRP with loading | not_mappable/not_mappable | LIFO insertion (not_mappable), 3D packing + routing (not_mappable) |
| `cvrp_mo` | Multi-objective VRP | not_mappable/not_mappable | Weighted NN (not_mappable), Pareto local search (not_mappable) |
| `cvrp_construct` | Constructive CVRP | possible/next_node_score | Nearest feasible (next_node_score), Savings as next-node score (next_node_score) |
| `cvrp_local` | Local-search CVRP | not_mappable/not_mappable | Granular tabu (not_mappable), Relocate/exchange VND (not_mappable) |
| `cvrp_large` | Large-scale CVRP | possible/next_node_score | Restricted NN (next_node_score), Ruin-and-recreate (not_mappable) |

## online_bin_packing — Bin packing (30)

fill_policy: `require_30`; registered_eoh: ['obp_online']

| id | 子问题 | eoh_map | 目标启发式 |
| --- | --- | --- | --- |
| `obp_1d` | 1D online bin packing | possible/bin_score | First Fit (bin_score), Best Fit (bin_score) |
| `bp_1d_offline` | 1D offline bin packing | not_mappable/not_mappable | First Fit Decreasing (not_mappable), Karmarkar-Karp (not_mappable) |
| `bp_variable` | Variable-sized bins | not_mappable/not_mappable | Any Fit variable bins (not_mappable), Variable-size FFD (not_mappable) |
| `bp_cardinality` | Cardinality-constrained packing | possible/bin_score | Cardinality-aware Best Fit (bin_score), Cardinality FFD (not_mappable) |
| `strip_2d` | 2D strip packing | not_mappable/not_mappable | Bottom-Left (not_mappable), Best-Fit skyline (not_mappable) |
| `bp_2d` | 2D bin packing | not_mappable/not_mappable | Maxrects (not_mappable), Guillotine 2D (not_mappable) |
| `bp_3d` | 3D bin packing | not_mappable/not_mappable | Deepest-Bottom-Left (not_mappable), Extreme-point 3D (not_mappable) |
| `vector_bp` | Vector bin packing | not_mappable/not_mappable | Vector FFD (not_mappable), Norm-based Best Fit (not_mappable) |
| `cutting_stock` | 1D cutting stock | not_mappable/not_mappable | Pattern generation greedy (not_mappable), FFD cutting stock (not_mappable) |
| `obp_harmonic` | Harmonic online family | possible/bin_score | Harmonic_M score over residuals (bin_score), Refined Harmonic (bin_score) |
| `obp_bounded_space` | Bounded-space online packing | possible/bin_score | Bounded-space Best Fit (bin_score), K-bounded Harmonic (bin_score) |
| `bp_fragile` | Fragile objects | not_mappable/not_mappable | Fragile FFD (not_mappable), Load-limit packing (not_mappable) |
| `bp_colored` | Colored bin packing | not_mappable/not_mappable | Color-aware FF (not_mappable), Colored Best Fit (not_mappable) |
| `bp_conflicts` | Bin packing with conflicts | not_mappable/not_mappable | Conflict-aware FF (not_mappable), Graph coloring + packing (not_mappable) |
| `bp_dynamic` | Dynamic packing | not_mappable/not_mappable | Dynamic FF (not_mappable), Repacking local search (not_mappable) |
| `bp_stochastic` | Stochastic packing | not_mappable/not_mappable | Expected-size BF (not_mappable), Distribution-aware Harmonic (not_mappable) |
| `obp_advice` | Online packing with advice | not_mappable/not_mappable | Advice-assisted FF (not_mappable), Advice Harmonic (not_mappable) |
| `bp_mo` | Multi-objective packing | not_mappable/not_mappable | Weighted FF (not_mappable), Pareto packing (not_mappable) |
| `obp_irrevocable` | Irrevocable online packing | possible/bin_score | Worst Fit (bin_score), Residual-utilization score (bin_score) |
| `bp_batch` | Batch packing | possible/bin_score | Batch Best Fit (bin_score), Sort-within-batch FFD (not_mappable) |
| `bp_types` | Few item types | possible/bin_score | Type-aware Best Fit (bin_score), Grouping Harmonic (bin_score) |
| `obp_lookahead` | k-lookahead online packing | not_mappable/not_mappable | k-lookahead BF (not_mappable), Lookahead Harmonic (not_mappable) |
| `bp_open_end` | Open-end packing | not_mappable/not_mappable | Open-end FF (not_mappable), Open-end BF (not_mappable) |
| `bp_guillotine` | Guillotine packing | not_mappable/not_mappable | Guillotine BF (not_mappable), Recursive guillotine (not_mappable) |
| `bp_resource` | Resource-constrained packing | not_mappable/not_mappable | Multi-resource BF (not_mappable), Resource FFD (not_mappable) |
| `obp_bestfit_family` | Best-Fit online family | possible/bin_score | Best Fit (bin_score), Almost Best Fit (bin_score) |
| `obp_worstfit_family` | Worst-Fit online family | possible/bin_score | Worst Fit (bin_score), Almost Worst Fit (bin_score) |
| `obp_score` | Score-based online packing | possible/bin_score | Residual-utilization score (bin_score), Piecewise residual score (bin_score) |
| `bp_offline_ffd` | FFD/BFD offline | not_mappable/not_mappable | First Fit Decreasing (not_mappable), Best Fit Decreasing (not_mappable) |
| `bp_offline_kk` | Karmarkar-Karp / differencing | not_mappable/not_mappable | Karmarkar-Karp differencing (not_mappable), Multifit (not_mappable) |

## knapsack — Knapsack (30)

fill_policy: `require_30`; registered_eoh: []

| id | 子问题 | eoh_map | 目标启发式 |
| --- | --- | --- | --- |
| `kp_01` | 0-1 knapsack | not_registered/not_mappable | Density greedy (not_mappable), Greedy + swap (not_mappable) |
| `kp_unbounded` | Unbounded knapsack | not_registered/not_mappable | Unbounded density greedy (not_mappable), Greedy by value (not_mappable) |
| `kp_bounded` | Bounded knapsack | not_registered/not_mappable | Bounded density greedy (not_mappable), Core algorithm heuristic (not_mappable) |
| `kp_multiple` | Multiple knapsack | not_registered/not_mappable | MKP greedy assign (not_mappable), MKP local search (not_mappable) |
| `kp_md` | Multidimensional knapsack | not_registered/not_mappable | Surrogate density greedy (not_mappable), MDKP local search (not_mappable) |
| `kp_quadratic` | Quadratic knapsack | not_registered/not_mappable | QKP greedy (not_mappable), QKP local search (not_mappable) |
| `kp_mckp` | Multiple-choice knapsack | not_registered/not_mappable | MCKP greedy (not_mappable), Class-wise DP heuristic (not_mappable) |
| `kp_discount` | Discount knapsack | not_registered/not_mappable | Discount greedy (not_mappable), Combo local search (not_mappable) |
| `kp_online` | Online knapsack | not_registered/not_mappable | Threshold online knapsack (not_mappable), Secretary-style take (not_mappable) |
| `kp_stochastic` | Stochastic knapsack | not_registered/not_mappable | Expected-density greedy (not_mappable), Recourse knapsack (not_mappable) |
| `kp_fuzzy` | Fuzzy knapsack | not_registered/not_mappable | Fuzzy density greedy (not_mappable), Defuzzified greedy (not_mappable) |
| `kp_mo` | Multi-objective knapsack | not_registered/not_mappable | Weighted-sum greedy (not_mappable), Pareto greedy (not_mappable) |
| `subset_sum` | Subset sum | not_registered/not_mappable | Greedy subset sum (not_mappable), Differencing subset sum (not_mappable) |
| `kp_collapsing` | Collapsing knapsack | not_registered/not_mappable | Collapsing greedy (not_mappable), Collapsing local search (not_mappable) |
| `kp_nonlinear` | Nonlinear knapsack | not_registered/not_mappable | Nonlinear greedy (not_mappable), Linearisation heuristic (not_mappable) |
| `kp_setup` | Knapsack with setups | not_registered/not_mappable | Setup-aware greedy (not_mappable), Class open/close local search (not_mappable) |
| `kp_prec` | Precedence knapsack | not_registered/not_mappable | Precedence greedy (not_mappable), Topo-order greedy (not_mappable) |
| `kp_time` | Time-dependent knapsack | not_registered/not_mappable | Time-slot greedy (not_mappable), TD knapsack local search (not_mappable) |
| `kp_circular` | Circular knapsack | not_registered/not_mappable | Circular greedy (not_mappable), Break-circle greedy (not_mappable) |
| `kp_group` | Group knapsack | not_registered/not_mappable | Group greedy (not_mappable), Group local search (not_mappable) |
| `kp_generalized` | Generalized knapsack | not_registered/not_mappable | GAP greedy (not_mappable), GAP regret (not_mappable) |
| `kp_compartment` | Compartmentalized knapsack | not_registered/not_mappable | Compartment greedy (not_mappable), Compartment local search (not_mappable) |
| `kp_bilevel` | Bilevel knapsack | not_registered/not_mappable | Leader greedy (not_mappable), Reaction heuristic (not_mappable) |
| `kp_robust` | Robust knapsack | not_registered/not_mappable | Worst-case density greedy (not_mappable), Budgeted uncertainty greedy (not_mappable) |
| `kp_integer` | Integer knapsack | not_registered/not_mappable | Integer density greedy (not_mappable), Rounding heuristic (not_mappable) |
| `kp_minmax` | Min-max knapsack | not_registered/not_mappable | Min-max greedy (not_mappable), Load-balance local search (not_mappable) |
| `kp_assign` | Assignment knapsack | not_registered/not_mappable | Assign greedy (not_mappable), Regret assignment (not_mappable) |
| `kp_order_greedy` | Order-greedy 0-1 (matches main Go solver) | not_registered/not_mappable | Order-greedy take-if-fits (not_mappable), First-fit knapsack (not_mappable) |
| `kp_density` | Profit/weight density greedy | not_registered/not_mappable | Dantzig density greedy (not_mappable), Critical-item greedy (not_mappable) |
| `kp_dp_fptas` | DP / FPTAS | not_registered/not_mappable | Ibarra-Kim FPTAS (not_mappable), DP by capacity (not_mappable) |

## mixer_split — Mixer split (0)

fill_policy: `do_not_pad`; registered_eoh: []

不凑 30。仓库特有问题，文献目录保持空，沿用 main 上已整理的方法卡。

## insertships_routing — Insertships (0)

fill_policy: `do_not_pad`; registered_eoh: []

不凑 30。仓库特有问题，文献目录保持空，沿用 main 上已整理的方法卡。
