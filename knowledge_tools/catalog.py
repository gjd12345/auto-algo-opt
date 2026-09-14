"""Frozen secondary-subproblem catalog for literature harvest.

Thirty literature-standard variants per family that already has a research
literature. mixer_split and insertships_routing are repository-specific and
must not be padded to 30.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "subproblem-catalog/v1"
REQUIRE_30 = ("tsp", "cvrp", "online_bin_packing", "knapsack")
DO_NOT_PAD = ("mixer_split", "insertships_routing")
ADAPTER_KINDS = frozenset({
    "next_node_score", "bin_score", "move_selector", "not_mappable",
})
EOH_STATUS = frozenset({"possible", "not_mappable", "not_registered"})


def item(
    sid: str,
    label: str,
    definition: str,
    query: str,
    eoh: str,
    kind: str,
    heuristics: list[tuple[str, str]],
) -> dict[str, Any]:
    if eoh not in EOH_STATUS:
        raise ValueError(f"bad eoh status {eoh} for {sid}")
    if kind not in ADAPTER_KINDS:
        raise ValueError(f"bad adapter kind {kind} for {sid}")
    if eoh != "possible" and kind != "not_mappable":
        raise ValueError(f"{sid}: non-possible eoh_map must use not_mappable adapter")
    if not 1 <= len(heuristics) <= 2:
        raise ValueError(f"{sid}: need 1-2 target heuristics")
    targets = []
    for name, hkind in heuristics:
        if hkind not in ADAPTER_KINDS:
            raise ValueError(f"{sid}: bad heuristic adapter {hkind}")
        targets.append({"name": name, "adapter_kind": hkind})
    return {
        "id": sid,
        "label": label,
        "definition": definition,
        "search_query": query,
        "eoh_map": {
            "status": eoh,
            "adapter_kind": kind if eoh == "possible" else "not_mappable",
        },
        "target_heuristics": targets,
    }


TSP = [
    item("tsp_euclidean", "Euclidean TSP", "Complete graph with Euclidean distances.",
         "Euclidean traveling salesman nearest neighbor heuristic", "possible", "next_node_score",
         [("Nearest Neighbor", "next_node_score"), ("Farthest Insertion", "not_mappable")]),
    item("tsp_asymmetric", "Asymmetric TSP", "Directed distances, d(i,j) may differ from d(j,i).",
         "asymmetric traveling salesman ATSP nearest neighbor heuristic", "possible", "next_node_score",
         [("Directed Nearest Neighbor", "next_node_score"), ("Directed 3-opt", "move_selector")]),
    item("tsp_metric", "Metric TSP", "Distances satisfy the triangle inequality.",
         "metric TSP approximation Christofides nearest neighbor", "possible", "next_node_score",
         [("Nearest Neighbor", "next_node_score"), ("Christofides", "not_mappable")]),
    item("tsp_open", "Open TSP / Hamiltonian path", "Path visits each city once, no return.",
         "open traveling salesman Hamiltonian path heuristic", "possible", "next_node_score",
         [("Path Nearest Neighbor", "next_node_score"), ("Cheapest Insertion path", "not_mappable")]),
    item("tsp_tw", "TSP with time windows", "Visit cities inside time windows.",
         "TSP with time windows insertion heuristic", "not_mappable", "not_mappable",
         [("I1 insertion TSPTW", "not_mappable"), ("Time-window NN", "not_mappable")]),
    item("tsp_sop", "Sequential ordering / precedences", "Precedence constraints on visit order.",
         "sequential ordering problem heuristic SOP", "not_mappable", "not_mappable",
         [("Precedence insertion", "not_mappable"), ("Asymmetric SOP local search", "not_mappable")]),
    item("tsp_clustered", "Clustered TSP", "Cities grouped; visit clusters as units.",
         "clustered traveling salesman heuristic", "possible", "next_node_score",
         [("Cluster-first NN", "next_node_score"), ("Intra-cluster 2-opt", "move_selector")]),
    item("tsp_gtsp", "Generalized TSP", "Visit exactly one city per cluster.",
         "generalized traveling salesman GTSP heuristic", "not_mappable", "not_mappable",
         [("NN among clusters", "not_mappable"), ("GI3 local search", "not_mappable")]),
    item("tsp_prize", "Prize-collecting TSP", "Optional cities with prizes and penalties.",
         "prize collecting TSP heuristic", "not_mappable", "not_mappable",
         [("Prize insertion", "not_mappable"), ("Goemans-Williamson PCTSP", "not_mappable")]),
    item("tsp_orienteering", "Orienteering / selective TSP", "Max prize under a length budget.",
         "orienteering problem heuristic", "not_mappable", "not_mappable",
         [("Prize/distance greedy", "not_mappable"), ("S-algorithm orienteering", "not_mappable")]),
    item("tsp_mtsp", "Multiple TSP", "Several salesmen from a depot.",
         "multiple traveling salesman mTSP heuristic", "not_mappable", "not_mappable",
         [("mTSP NN assignment", "not_mappable"), ("mTSP 2-opt", "not_mappable")]),
    item("tsp_minmax", "Min-max mTSP", "Minimise the longest salesman tour.",
         "min-max multiple TSP heuristic", "not_mappable", "not_mappable",
         [("Balanced NN", "not_mappable"), ("Min-max 2-opt", "not_mappable")]),
    item("tsp_pdp", "TSP with pickups and deliveries", "Paired pickup-delivery.",
         "pickup delivery TSP heuristic", "not_mappable", "not_mappable",
         [("Paired insertion", "not_mappable"), ("PDP local search", "not_mappable")]),
    item("tsp_dynamic", "Dynamic / online TSP", "Cities revealed over time.",
         "online traveling salesman heuristic", "possible", "next_node_score",
         [("Online NN", "next_node_score"), ("Replanning 2-opt", "move_selector")]),
    item("tsp_stochastic", "Stochastic TSP", "Random distances or presence.",
         "stochastic TSP heuristic", "not_mappable", "not_mappable",
         [("Expected-cost NN", "not_mappable"), ("Recourse 2-opt", "not_mappable")]),
    item("tsp_time_dependent", "Time-dependent TSP", "Travel time depends on departure.",
         "time dependent TSP heuristic", "not_mappable", "not_mappable",
         [("Time-dependent NN", "not_mappable"), ("TD 2-opt", "not_mappable")]),
    item("tsp_neighborhoods", "TSP with neighborhoods", "Visit a region not a point.",
         "TSP with neighborhoods heuristic", "not_mappable", "not_mappable",
         [("Region-greedy visit", "not_mappable"), ("TspN sampling", "not_mappable")]),
    item("tsp_bottleneck", "Bottleneck TSP", "Minimise the longest edge.",
         "bottleneck traveling salesman heuristic", "possible", "next_node_score",
         [("Bottleneck NN", "next_node_score"), ("Threshold binary search + MST", "not_mappable")]),
    item("tsp_multiobjective", "Multi-objective TSP", "Several cost functions.",
         "multiobjective TSP heuristic", "not_mappable", "not_mappable",
         [("Weighted-sum NN", "not_mappable"), ("Pareto 2-opt", "not_mappable")]),
    item("tsp_colored", "Colored TSP", "Color/class visit constraints.",
         "colored traveling salesman heuristic", "not_mappable", "not_mappable",
         [("Color-feasible NN", "not_mappable"), ("Colored local search", "not_mappable")]),
    item("tsp_large", "Large-scale Euclidean TSP", "n in thousands; locality matters.",
         "large scale TSP Lin Kernighan heuristic", "possible", "move_selector",
         [("Lin-Kernighan", "not_mappable"), ("Candidate-list 2-opt", "move_selector")]),
    item("tsp_noisy", "Noisy / black-box distances", "Distance oracle is noisy.",
         "noisy TSP heuristic", "not_mappable", "not_mappable",
         [("Robust NN", "not_mappable"), ("Repeated 2-opt", "not_mappable")]),
    item("tsp_forbidden", "Forbidden edges", "Some edges cannot be used.",
         "TSP forbidden edges heuristic", "possible", "next_node_score",
         [("Constrained NN", "next_node_score"), ("Infeasible-edge 2-opt", "move_selector")]),
    item("tsp_covering", "Covering salesman", "A vertex covers neighbors.",
         "covering salesman problem heuristic", "not_mappable", "not_mappable",
         [("Covering greedy", "not_mappable"), ("Set-cover + TSP", "not_mappable")]),
    item("tsp_purchaser", "Traveling purchaser", "Buy items from markets.",
         "traveling purchaser problem heuristic", "not_mappable", "not_mappable",
         [("TPP savings", "not_mappable"), ("Market insertion", "not_mappable")]),
    item("tsp_drone", "TSP with drone", "Truck plus UAV.",
         "TSP with drone heuristic", "not_mappable", "not_mappable",
         [("Truck-drone NN", "not_mappable"), ("Drone launch local search", "not_mappable")]),
    item("tsp_fuel", "Fuel / replenishment TSP", "Must visit refill points.",
         "refueling traveling salesman heuristic", "not_mappable", "not_mappable",
         [("Refuel insertion", "not_mappable"), ("Fuel-feasible NN", "not_mappable")]),
    item("tsp_angular", "Angular-metric TSP", "Cost uses turning angles.",
         "angular metric TSP heuristic", "possible", "next_node_score",
         [("Angle-aware NN", "next_node_score"), ("Or-opt for turning cost", "move_selector")]),
    item("tsp_construct", "Constructive-only TSP", "Build a tour city by city.",
         "nearest neighbor cheapest insertion TSP constructive heuristic", "possible", "next_node_score",
         [("Nearest Neighbor", "next_node_score"), ("Cheapest Insertion", "not_mappable")]),
    item("tsp_local", "Local-search TSP", "Improve a complete tour.",
         "2-opt 3-opt or-opt TSP local search", "possible", "move_selector",
         [("2-opt", "move_selector"), ("Or-opt", "not_mappable")]),
]

CVRP = [
    item("cvrp_basic", "Capacitated VRP", "One depot, capacity, visit each customer once.",
         "capacitated vehicle routing nearest neighbor Clarke Wright", "possible", "next_node_score",
         [("Nearest feasible customer", "next_node_score"), ("Clarke-Wright savings as next-node score", "next_node_score")]),
    item("vrptw", "VRP with time windows", "Customers have time windows.",
         "VRPTW Solomon insertion heuristic", "not_mappable", "not_mappable",
         [("Solomon I1", "not_mappable"), ("Solomon I2", "not_mappable")]),
    item("mdvrp", "Multi-depot VRP", "Several depots.",
         "multi depot VRP heuristic", "not_mappable", "not_mappable",
         [("Depot assignment + NN", "not_mappable"), ("MD savings", "not_mappable")]),
    item("sdvrp", "Split-delivery VRP", "A customer may be split.",
         "split delivery VRP heuristic", "not_mappable", "not_mappable",
         [("Split-delivery savings", "not_mappable"), ("Split local search", "not_mappable")]),
    item("ovrp", "Open VRP", "Routes need not return.",
         "open vehicle routing heuristic", "possible", "next_node_score",
         [("Open NN", "next_node_score"), ("Open savings", "next_node_score")]),
    item("hfvrp", "Heterogeneous fleet VRP", "Vehicle types differ.",
         "heterogeneous fleet VRP heuristic", "not_mappable", "not_mappable",
         [("Type-aware savings", "not_mappable"), ("Fleet mix local search", "not_mappable")]),
    item("fsmvrp", "Fleet size and mix", "Choose fleet composition.",
         "fleet size mix VRP heuristic", "not_mappable", "not_mappable",
         [("Golden FSM constructive", "not_mappable"), ("FSM local search", "not_mappable")]),
    item("vrppd", "VRP with pickups and deliveries", "Paired pickup and delivery.",
         "VRP pickup delivery heuristic", "not_mappable", "not_mappable",
         [("Paired insertion", "not_mappable"), ("PDP VND", "not_mappable")]),
    item("pdptw", "PDPTW", "Pickup-delivery with windows.",
         "pickup delivery time windows heuristic", "not_mappable", "not_mappable",
         [("PDPTW insertion", "not_mappable"), ("PDPTW ALNS", "not_mappable")]),
    item("cvrpb", "VRP with backhauls", "Linehaul then backhaul.",
         "vehicle routing backhauls heuristic", "not_mappable", "not_mappable",
         [("Backhaul insertion", "not_mappable"), ("Linehaul-first NN", "not_mappable")]),
    item("vrpsdp", "Simultaneous pickup and delivery", "Both at the same stop.",
         "VRP simultaneous pickup delivery heuristic", "not_mappable", "not_mappable",
         [("SDP NN", "not_mappable"), ("SDP local search", "not_mappable")]),
    item("pvrp", "Periodic VRP", "Planning over several days.",
         "periodic vehicle routing heuristic", "not_mappable", "not_mappable",
         [("Day assignment + CWS", "not_mappable"), ("Periodic local search", "not_mappable")]),
    item("irp", "Inventory routing", "Routing plus inventory.",
         "inventory routing problem heuristic", "not_mappable", "not_mappable",
         [("IRP greedy replenishment", "not_mappable"), ("IRP local search", "not_mappable")]),
    item("darp", "Dial-a-ride", "Passenger transport with windows.",
         "dial a ride problem heuristic", "not_mappable", "not_mappable",
         [("DARP insertion", "not_mappable"), ("DARP regret", "not_mappable")]),
    item("cvrp_multitrip", "Multi-trip VRP", "A vehicle may do several routes.",
         "multi trip VRP heuristic", "possible", "next_node_score",
         [("Multi-trip NN", "next_node_score"), ("Trip packing + routing", "not_mappable")]),
    item("cvrp_site", "Site-dependent VRP", "Some vehicles cannot serve some sites.",
         "site dependent VRP heuristic", "not_mappable", "not_mappable",
         [("Site-feasible NN", "not_mappable"), ("Restricted savings", "not_mappable")]),
    item("cvrp_td", "Time-dependent VRP", "Travel time varies with clock.",
         "time dependent VRP heuristic", "not_mappable", "not_mappable",
         [("TD NN", "not_mappable"), ("TD local search", "not_mappable")]),
    item("cvrp_stochastic", "Stochastic-demand VRP", "Demands random.",
         "stochastic demand VRP heuristic", "not_mappable", "not_mappable",
         [("Expected-demand NN", "not_mappable"), ("Recourse restocking", "not_mappable")]),
    item("cvrp_dynamic", "Dynamic VRP", "Requests arrive online.",
         "dynamic vehicle routing heuristic", "possible", "next_node_score",
         [("Online feasible NN", "next_node_score"), ("Rolling-horizon 2-opt", "not_mappable")]),
    item("evrp", "Electric VRP", "Charging constraints.",
         "electric vehicle routing heuristic", "not_mappable", "not_mappable",
         [("Charge-feasible NN", "not_mappable"), ("EVRP insertion", "not_mappable")]),
    item("cvrp_2e", "Two-echelon VRP", "Satellites between depot and customers.",
         "two echelon VRP heuristic", "not_mappable", "not_mappable",
         [("Satellite assignment + CWS", "not_mappable"), ("2E-VRP local search", "not_mappable")]),
    item("cvrp_clustered", "Clustered VRP", "Customers in clusters.",
         "clustered VRP heuristic", "possible", "next_node_score",
         [("Cluster-first NN", "next_node_score"), ("Sweep-like angular NN", "next_node_score")]),
    item("cvrp_prize", "Prize-collecting VRP", "Optional customers.",
         "prize collecting VRP heuristic", "not_mappable", "not_mappable",
         [("Prize/distance greedy", "not_mappable"), ("Selective VRP local search", "not_mappable")]),
    item("cvrp_minveh", "Minimise number of vehicles", "Primary objective is fleet size.",
         "minimise vehicles VRP heuristic", "possible", "next_node_score",
         [("Parallel cheapest insertion", "not_mappable"), ("Capacity-tight NN", "next_node_score")]),
    item("dcvrp", "Distance-constrained VRP", "Route length cap.",
         "distance constrained VRP heuristic", "possible", "next_node_score",
         [("Length-feasible NN", "next_node_score"), ("DCVRP savings", "next_node_score")]),
    item("cvrp_loading", "VRP with loading", "LIFO or 3D loading.",
         "VRP loading constraints heuristic", "not_mappable", "not_mappable",
         [("LIFO insertion", "not_mappable"), ("3D packing + routing", "not_mappable")]),
    item("cvrp_mo", "Multi-objective VRP", "Several routing objectives.",
         "multiobjective VRP heuristic", "not_mappable", "not_mappable",
         [("Weighted NN", "not_mappable"), ("Pareto local search", "not_mappable")]),
    item("cvrp_construct", "Constructive CVRP", "Build routes customer by customer.",
         "Clarke Wright savings nearest neighbor VRP constructive", "possible", "next_node_score",
         [("Nearest feasible", "next_node_score"), ("Savings as next-node score", "next_node_score")]),
    item("cvrp_local", "Local-search CVRP", "Improve complete routes.",
         "granular tabu VRP local search", "not_mappable", "not_mappable",
         [("Granular tabu", "not_mappable"), ("Relocate/exchange VND", "not_mappable")]),
    item("cvrp_large", "Large-scale CVRP", "Hundreds of customers.",
         "large scale VRP heuristic", "possible", "next_node_score",
         [("Restricted NN", "next_node_score"), ("Ruin-and-recreate", "not_mappable")]),
]

OBP = [
    item("obp_1d", "1D online bin packing", "Irrevocable assignment of arriving items.",
         "online bin packing First Fit Best Fit Harmonic", "possible", "bin_score",
         [("First Fit", "bin_score"), ("Best Fit", "bin_score")]),
    item("bp_1d_offline", "1D offline bin packing", "Full list known; sorting allowed.",
         "First Fit Decreasing Karmarkar Karp bin packing", "not_mappable", "not_mappable",
         [("First Fit Decreasing", "not_mappable"), ("Karmarkar-Karp", "not_mappable")]),
    item("bp_variable", "Variable-sized bins", "Several bin sizes.",
         "variable sized bin packing heuristic", "not_mappable", "not_mappable",
         [("Any Fit variable bins", "not_mappable"), ("Variable-size FFD", "not_mappable")]),
    item("bp_cardinality", "Cardinality-constrained packing", "Max items per bin.",
         "cardinality constrained bin packing heuristic", "possible", "bin_score",
         [("Cardinality-aware Best Fit", "bin_score"), ("Cardinality FFD", "not_mappable")]),
    item("strip_2d", "2D strip packing", "Pack rectangles into a strip.",
         "two dimensional strip packing heuristic", "not_mappable", "not_mappable",
         [("Bottom-Left", "not_mappable"), ("Best-Fit skyline", "not_mappable")]),
    item("bp_2d", "2D bin packing", "Pack rectangles into bins.",
         "two dimensional bin packing heuristic", "not_mappable", "not_mappable",
         [("Maxrects", "not_mappable"), ("Guillotine 2D", "not_mappable")]),
    item("bp_3d", "3D bin packing", "Pack boxes.",
         "three dimensional bin packing heuristic", "not_mappable", "not_mappable",
         [("Deepest-Bottom-Left", "not_mappable"), ("Extreme-point 3D", "not_mappable")]),
    item("vector_bp", "Vector bin packing", "Multi-dimensional capacities.",
         "vector bin packing heuristic", "not_mappable", "not_mappable",
         [("Vector FFD", "not_mappable"), ("Norm-based Best Fit", "not_mappable")]),
    item("cutting_stock", "1D cutting stock", "Few item types, many copies.",
         "cutting stock heuristic", "not_mappable", "not_mappable",
         [("Pattern generation greedy", "not_mappable"), ("FFD cutting stock", "not_mappable")]),
    item("obp_harmonic", "Harmonic online family", "Size classes and class bins.",
         "Harmonic_M online bin packing Lee Lee", "possible", "bin_score",
         [("Harmonic_M score over residuals", "bin_score"), ("Refined Harmonic", "bin_score")]),
    item("obp_bounded_space", "Bounded-space online packing", "Only k bins open.",
         "bounded space online bin packing heuristic", "possible", "bin_score",
         [("Bounded-space Best Fit", "bin_score"), ("K-bounded Harmonic", "bin_score")]),
    item("bp_fragile", "Fragile objects", "Items cannot support others.",
         "fragile objects bin packing heuristic", "not_mappable", "not_mappable",
         [("Fragile FFD", "not_mappable"), ("Load-limit packing", "not_mappable")]),
    item("bp_colored", "Colored bin packing", "Color constraints.",
         "colored bin packing heuristic", "not_mappable", "not_mappable",
         [("Color-aware FF", "not_mappable"), ("Colored Best Fit", "not_mappable")]),
    item("bp_conflicts", "Bin packing with conflicts", "Some pairs cannot share a bin.",
         "bin packing with conflicts heuristic", "not_mappable", "not_mappable",
         [("Conflict-aware FF", "not_mappable"), ("Graph coloring + packing", "not_mappable")]),
    item("bp_dynamic", "Dynamic packing", "Insert and delete over time.",
         "dynamic bin packing heuristic", "not_mappable", "not_mappable",
         [("Dynamic FF", "not_mappable"), ("Repacking local search", "not_mappable")]),
    item("bp_stochastic", "Stochastic packing", "Item sizes random.",
         "stochastic bin packing heuristic", "not_mappable", "not_mappable",
         [("Expected-size BF", "not_mappable"), ("Distribution-aware Harmonic", "not_mappable")]),
    item("obp_advice", "Online packing with advice", "Limited future bits.",
         "online bin packing advice complexity", "not_mappable", "not_mappable",
         [("Advice-assisted FF", "not_mappable"), ("Advice Harmonic", "not_mappable")]),
    item("bp_mo", "Multi-objective packing", "Bins plus another objective.",
         "multiobjective bin packing heuristic", "not_mappable", "not_mappable",
         [("Weighted FF", "not_mappable"), ("Pareto packing", "not_mappable")]),
    item("obp_irrevocable", "Irrevocable online packing", "No repacking; matches EoH OBP.",
         "irrevocable online bin packing score function", "possible", "bin_score",
         [("Worst Fit", "bin_score"), ("Residual-utilization score", "bin_score")]),
    item("bp_batch", "Batch packing", "Items arrive in batches.",
         "batch bin packing heuristic", "possible", "bin_score",
         [("Batch Best Fit", "bin_score"), ("Sort-within-batch FFD", "not_mappable")]),
    item("bp_types", "Few item types", "Many copies of few sizes.",
         "bin packing item types heuristic", "possible", "bin_score",
         [("Type-aware Best Fit", "bin_score"), ("Grouping Harmonic", "bin_score")]),
    item("obp_lookahead", "k-lookahead online packing", "See k future items.",
         "lookahead online bin packing heuristic", "not_mappable", "not_mappable",
         [("k-lookahead BF", "not_mappable"), ("Lookahead Harmonic", "not_mappable")]),
    item("bp_open_end", "Open-end packing", "Last item may overflow slightly.",
         "open end bin packing heuristic", "not_mappable", "not_mappable",
         [("Open-end FF", "not_mappable"), ("Open-end BF", "not_mappable")]),
    item("bp_guillotine", "Guillotine packing", "Cuts must be guillotine.",
         "guillotine bin packing heuristic", "not_mappable", "not_mappable",
         [("Guillotine BF", "not_mappable"), ("Recursive guillotine", "not_mappable")]),
    item("bp_resource", "Resource-constrained packing", "Extra resources besides size.",
         "resource constrained packing heuristic", "not_mappable", "not_mappable",
         [("Multi-resource BF", "not_mappable"), ("Resource FFD", "not_mappable")]),
    item("obp_bestfit_family", "Best-Fit online family", "Prefer tight residual.",
         "Best Fit online bin packing worst case Johnson", "possible", "bin_score",
         [("Best Fit", "bin_score"), ("Almost Best Fit", "bin_score")]),
    item("obp_worstfit_family", "Worst-Fit online family", "Prefer emptiest bin.",
         "Worst Fit online bin packing", "possible", "bin_score",
         [("Worst Fit", "bin_score"), ("Almost Worst Fit", "bin_score")]),
    item("obp_score", "Score-based online packing", "Learned or designed score over residuals.",
         "online bin packing scoring heuristic residual", "possible", "bin_score",
         [("Residual-utilization score", "bin_score"), ("Piecewise residual score", "bin_score")]),
    item("bp_offline_ffd", "FFD/BFD offline", "Sort then First/Best Fit.",
         "First Fit Decreasing bin packing", "not_mappable", "not_mappable",
         [("First Fit Decreasing", "not_mappable"), ("Best Fit Decreasing", "not_mappable")]),
    item("bp_offline_kk", "Karmarkar-Karp / differencing", "Offline LP or differencing.",
         "Karmarkar Karp bin packing approximation", "not_mappable", "not_mappable",
         [("Karmarkar-Karp differencing", "not_mappable"), ("Multifit", "not_mappable")]),
]

KP = [
    item("kp_01", "0-1 knapsack", "Take or leave each item.",
         "0-1 knapsack greedy heuristic", "not_registered", "not_mappable",
         [("Density greedy", "not_mappable"), ("Greedy + swap", "not_mappable")]),
    item("kp_unbounded", "Unbounded knapsack", "Unlimited copies.",
         "unbounded knapsack heuristic", "not_registered", "not_mappable",
         [("Unbounded density greedy", "not_mappable"), ("Greedy by value", "not_mappable")]),
    item("kp_bounded", "Bounded knapsack", "Bounded copies.",
         "bounded knapsack heuristic", "not_registered", "not_mappable",
         [("Bounded density greedy", "not_mappable"), ("Core algorithm heuristic", "not_mappable")]),
    item("kp_multiple", "Multiple knapsack", "Several knapsacks.",
         "multiple knapsack heuristic", "not_registered", "not_mappable",
         [("MKP greedy assign", "not_mappable"), ("MKP local search", "not_mappable")]),
    item("kp_md", "Multidimensional knapsack", "Several resource constraints.",
         "multidimensional knapsack heuristic", "not_registered", "not_mappable",
         [("Surrogate density greedy", "not_mappable"), ("MDKP local search", "not_mappable")]),
    item("kp_quadratic", "Quadratic knapsack", "Pairwise profits.",
         "quadratic knapsack heuristic", "not_registered", "not_mappable",
         [("QKP greedy", "not_mappable"), ("QKP local search", "not_mappable")]),
    item("kp_mckp", "Multiple-choice knapsack", "Choose from classes.",
         "multiple choice knapsack heuristic", "not_registered", "not_mappable",
         [("MCKP greedy", "not_mappable"), ("Class-wise DP heuristic", "not_mappable")]),
    item("kp_discount", "Discount knapsack", "Discounts on combinations.",
         "discount knapsack heuristic", "not_registered", "not_mappable",
         [("Discount greedy", "not_mappable"), ("Combo local search", "not_mappable")]),
    item("kp_online", "Online knapsack", "Items arrive online.",
         "online knapsack heuristic", "not_registered", "not_mappable",
         [("Threshold online knapsack", "not_mappable"), ("Secretary-style take", "not_mappable")]),
    item("kp_stochastic", "Stochastic knapsack", "Random profits or weights.",
         "stochastic knapsack heuristic", "not_registered", "not_mappable",
         [("Expected-density greedy", "not_mappable"), ("Recourse knapsack", "not_mappable")]),
    item("kp_fuzzy", "Fuzzy knapsack", "Fuzzy weights/profits.",
         "fuzzy knapsack heuristic", "not_registered", "not_mappable",
         [("Fuzzy density greedy", "not_mappable"), ("Defuzzified greedy", "not_mappable")]),
    item("kp_mo", "Multi-objective knapsack", "Several profits.",
         "multiobjective knapsack heuristic", "not_registered", "not_mappable",
         [("Weighted-sum greedy", "not_mappable"), ("Pareto greedy", "not_mappable")]),
    item("subset_sum", "Subset sum", "Hit a target sum.",
         "subset sum heuristic", "not_registered", "not_mappable",
         [("Greedy subset sum", "not_mappable"), ("Differencing subset sum", "not_mappable")]),
    item("kp_collapsing", "Collapsing knapsack", "Capacity depends on selection.",
         "collapsing knapsack heuristic", "not_registered", "not_mappable",
         [("Collapsing greedy", "not_mappable"), ("Collapsing local search", "not_mappable")]),
    item("kp_nonlinear", "Nonlinear knapsack", "Nonlinear profit.",
         "nonlinear knapsack heuristic", "not_registered", "not_mappable",
         [("Nonlinear greedy", "not_mappable"), ("Linearisation heuristic", "not_mappable")]),
    item("kp_setup", "Knapsack with setups", "Class setup costs.",
         "knapsack with setups heuristic", "not_registered", "not_mappable",
         [("Setup-aware greedy", "not_mappable"), ("Class open/close local search", "not_mappable")]),
    item("kp_prec", "Precedence knapsack", "Item precedences.",
         "precedence constrained knapsack heuristic", "not_registered", "not_mappable",
         [("Precedence greedy", "not_mappable"), ("Topo-order greedy", "not_mappable")]),
    item("kp_time", "Time-dependent knapsack", "Profits vary with time.",
         "time dependent knapsack heuristic", "not_registered", "not_mappable",
         [("Time-slot greedy", "not_mappable"), ("TD knapsack local search", "not_mappable")]),
    item("kp_circular", "Circular knapsack", "Circular arrangement.",
         "circular knapsack heuristic", "not_registered", "not_mappable",
         [("Circular greedy", "not_mappable"), ("Break-circle greedy", "not_mappable")]),
    item("kp_group", "Group knapsack", "Groups of items.",
         "group knapsack heuristic", "not_registered", "not_mappable",
         [("Group greedy", "not_mappable"), ("Group local search", "not_mappable")]),
    item("kp_generalized", "Generalized knapsack", "Generalised assignment flavour.",
         "generalized knapsack heuristic", "not_registered", "not_mappable",
         [("GAP greedy", "not_mappable"), ("GAP regret", "not_mappable")]),
    item("kp_compartment", "Compartmentalized knapsack", "Compartments inside the knapsack.",
         "compartmentalized knapsack heuristic", "not_registered", "not_mappable",
         [("Compartment greedy", "not_mappable"), ("Compartment local search", "not_mappable")]),
    item("kp_bilevel", "Bilevel knapsack", "Leader-follower.",
         "bilevel knapsack heuristic", "not_registered", "not_mappable",
         [("Leader greedy", "not_mappable"), ("Reaction heuristic", "not_mappable")]),
    item("kp_robust", "Robust knapsack", "Uncertainty sets.",
         "robust knapsack heuristic", "not_registered", "not_mappable",
         [("Worst-case density greedy", "not_mappable"), ("Budgeted uncertainty greedy", "not_mappable")]),
    item("kp_integer", "Integer knapsack", "Integer copies.",
         "integer knapsack heuristic", "not_registered", "not_mappable",
         [("Integer density greedy", "not_mappable"), ("Rounding heuristic", "not_mappable")]),
    item("kp_minmax", "Min-max knapsack", "Minimise the worst load.",
         "minmax knapsack heuristic", "not_registered", "not_mappable",
         [("Min-max greedy", "not_mappable"), ("Load-balance local search", "not_mappable")]),
    item("kp_assign", "Assignment knapsack", "Assign items to agents with budgets.",
         "assignment knapsack heuristic", "not_registered", "not_mappable",
         [("Assign greedy", "not_mappable"), ("Regret assignment", "not_mappable")]),
    item("kp_order_greedy", "Order-greedy 0-1 (matches main Go solver)",
         "Take items in file order if they fit.",
         "greedy knapsack first fit order", "not_registered", "not_mappable",
         [("Order-greedy take-if-fits", "not_mappable"), ("First-fit knapsack", "not_mappable")]),
    item("kp_density", "Profit/weight density greedy", "Sort by density then take.",
         "knapsack density greedy heuristic", "not_registered", "not_mappable",
         [("Dantzig density greedy", "not_mappable"), ("Critical-item greedy", "not_mappable")]),
    item("kp_dp_fptas", "DP / FPTAS", "Exact or approximate DP, not a constructive EoH elite.",
         "knapsack FPTAS dynamic programming", "not_registered", "not_mappable",
         [("Ibarra-Kim FPTAS", "not_mappable"), ("DP by capacity", "not_mappable")]),
]


def build_catalog() -> dict[str, Any]:
    families = {
        "tsp": {
            "label": "Traveling salesman",
            "registered_eoh": ["tsp_construct", "tsp_2opt"],
            "fill_policy": "require_30",
            "subproblems": TSP,
        },
        "cvrp": {
            "label": "Vehicle routing",
            "registered_eoh": ["cvrp_construct"],
            "fill_policy": "require_30",
            "subproblems": CVRP,
        },
        "online_bin_packing": {
            "label": "Bin packing",
            "registered_eoh": ["obp_online"],
            "fill_policy": "require_30",
            "subproblems": OBP,
        },
        "knapsack": {
            "label": "Knapsack",
            "registered_eoh": [],
            "fill_policy": "require_30",
            "subproblems": KP,
        },
        "mixer_split": {
            "label": "Mixer split",
            "registered_eoh": [],
            "fill_policy": "do_not_pad",
            "subproblems": [],
        },
        "insertships_routing": {
            "label": "Insertships",
            "registered_eoh": [],
            "fill_policy": "do_not_pad",
            "subproblems": [],
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "notes": (
            "Thirty secondary problems per literature-standard family. "
            "mixer_split and insertships_routing must not be padded. "
            "target_heuristics are search/screen hints, not claims that main implements them."
        ),
        "families": families,
    }


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unexpected schema_version {catalog.get('schema_version')!r}")
    families = catalog.get("families")
    if not isinstance(families, dict):
        return ["catalog has no families object"]
    for name in REQUIRE_30:
        spec = families.get(name)
        if not isinstance(spec, dict):
            errors.append(f"missing family {name}")
            continue
        items = spec.get("subproblems") or []
        if len(items) != 30:
            errors.append(f"{name} has {len(items)} subproblems, expected 30")
        ids = [item.get("id") for item in items if isinstance(item, dict)]
        if len(ids) != len(set(ids)):
            errors.append(f"{name} has duplicate subproblem ids")
        if spec.get("fill_policy") != "require_30":
            errors.append(f"{name} fill_policy must be require_30")
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{name} has a non-object subproblem")
                continue
            sid = item.get("id")
            heuristics = item.get("target_heuristics") or []
            if not 1 <= len(heuristics) <= 2:
                errors.append(f"{sid}: need 1-2 target_heuristics")
            eoh = (item.get("eoh_map") or {}).get("status")
            if eoh not in EOH_STATUS:
                errors.append(f"{sid}: bad eoh_map.status {eoh!r}")
    for name in DO_NOT_PAD:
        spec = families.get(name)
        if not isinstance(spec, dict):
            errors.append(f"missing family {name}")
            continue
        items = spec.get("subproblems") or []
        if len(items) >= 30:
            errors.append(f"{name} must not be padded to 30")
        if spec.get("fill_policy") != "do_not_pad":
            errors.append(f"{name} fill_policy must be do_not_pad")
    return errors


def catalog_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# 二级子问题目录",
        "",
        catalog.get("notes") or "",
        "",
        "二级子问题是文献变体，不是新的 EoH `problem_id`。`target_heuristics` 只是检索/筛读提示。",
        "",
    ]
    for name, spec in (catalog.get("families") or {}).items():
        items = spec.get("subproblems") or []
        lines.append(f"## {name} — {spec.get('label')} ({len(items)})")
        lines.append("")
        lines.append(f"fill_policy: `{spec.get('fill_policy')}`; registered_eoh: {spec.get('registered_eoh')}")
        lines.append("")
        if not items:
            lines.append("不凑 30。仓库特有问题，文献目录保持空，沿用 main 上已整理的方法卡。")
            lines.append("")
            continue
        lines.append("| id | 子问题 | eoh_map | 目标启发式 |")
        lines.append("| --- | --- | --- | --- |")
        for item in items:
            heur = ", ".join(
                f"{h.get('name')} ({h.get('adapter_kind')})"
                for h in item.get("target_heuristics") or []
            )
            eoh = item.get("eoh_map") or {}
            lines.append(
                f"| `{item.get('id')}` | {item.get('label')} | "
                f"{eoh.get('status')}/{eoh.get('adapter_kind')} | {heur} |"
            )
        lines.append("")
    return "\n".join(lines)
