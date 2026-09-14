"""Canonical DOIs for catalog subproblems that keyword harvest could not classify.

Each id maps to 1-2 original algorithmic papers. Retrieval is Crossref GET
by DOI; these strings are not claims that main implements the algorithms.
"""

from __future__ import annotations

# doi, heuristic_name, adapter_kind
CANONICAL: dict[str, list[tuple[str, str, str]]] = {
    "tsp_asymmetric": [
        ("10.1007/bf01580113", "Kanellakis-Papadimitriou ATSP local search", "not_mappable"),
        ("10.1287/opre.6.6.791", "Croes 2-opt (asymmetric setting)", "move_selector"),
    ],
    "tsp_metric": [
        ("10.1137/0206041", "Nearest Neighbor (metric analysis)", "next_node_score"),
        ("10.1184/r1/6609574.v1", "Christofides heuristic", "not_mappable"),
    ],
    "tsp_open": [
        ("10.1137/0206041", "Cheapest Insertion (path)", "not_mappable"),
        ("10.1137/0206041", "Nearest Neighbor", "next_node_score"),
    ],
    "tsp_sop": [
        ("10.1016/0166-218x(88)90012-2", "SOP sequential ordering heuristic", "not_mappable"),
        ("10.1287/ijoc.10.3.297", "SOP branch-cut / heuristic context", "not_mappable"),
    ],
    "tsp_clustered": [
        ("10.1016/0305-0548(75)90015-5", "Chisman clustered TSP", "not_mappable"),
        ("10.1287/opre.6.6.791", "Intra-cluster 2-opt", "move_selector"),
    ],
    "tsp_prize": [
        ("10.1002/net.3230190602", "Balas prize-collecting TSP", "not_mappable"),
        ("10.1007/bf01585555", "Prize-collecting TSP polyhedra / heuristic context", "not_mappable"),
    ],
    "tsp_orienteering": [
        ("10.1057/jors.1984.162", "Tsiligirides orienteering heuristics", "not_mappable"),
        ("10.1002/net.3230180306", "Golden orienteering", "not_mappable"),
    ],
    "tsp_minmax": [
        ("10.1016/0377-2217(96)00108-5", "Min-max mTSP heuristic", "not_mappable"),
        ("10.1002/net.3230220304", "Min-max multiple TSP", "not_mappable"),
    ],
    "tsp_dynamic": [
        ("10.1007/s00453-001-0068-9", "Ausiello et al. online TSP", "not_mappable"),
        ("10.1002/net.20454", "Online TSP with service flexibility", "not_mappable"),
    ],
    "tsp_stochastic": [
        ("10.1287/opre.38.6.1019", "Jaillet a priori TSP", "not_mappable"),
        ("10.1007/bf01580616", "Stochastic TSP heuristics", "not_mappable"),
    ],
    "tsp_time_dependent": [
        ("10.1287/trsc.26.3.185", "Malandraki-Daskin time-dependent TSP", "not_mappable"),
        ("10.1016/s0377-2217(01)00142-8", "Ichoua time-dependent travel", "not_mappable"),
    ],
    "tsp_neighborhoods": [
        ("10.1007/s00453-004-1091-4", "TSP with neighborhoods", "not_mappable"),
        ("10.1137/s0097539702416402", "TSPN approximation / heuristic context", "not_mappable"),
    ],
    "tsp_bottleneck": [
        ("10.1287/opre.32.2.380", "Garfinkel bottleneck TSP", "not_mappable"),
        ("10.1002/net.3230120409", "Bottleneck TSP heuristic context", "not_mappable"),
    ],
    "tsp_multiobjective": [
        ("10.1016/s0377-2217(01)00341-2", "Multiobjective TSP heuristic", "not_mappable"),
        ("10.1016/s0377-2217(02)00457-0", "MOTSP local search", "not_mappable"),
    ],
    "tsp_colored": [
        # Previous DOIs resolved to unrelated papers (location games / Hindawi mismatch).
    ],
    "tsp_noisy": [
        ("10.1287/opre.43.6.1022", "TSP under uncertainty / noisy distances", "not_mappable"),
    ],
    "tsp_forbidden": [
        ("10.1007/bf01581247", "TSP with additional constraints", "not_mappable"),
        ("10.1287/opre.6.6.791", "2-opt with infeasible edges excluded", "move_selector"),
    ],
    "tsp_covering": [
        ("10.1002/net.3230120305", "Covering salesman problem", "not_mappable"),
        ("10.1002/net.3230140304", "Covering salesman heuristic", "not_mappable"),
    ],
    "tsp_purchaser": [
        ("10.1002/net.3230110308", "Golden traveling purchaser", "not_mappable"),
        ("10.1016/0377-2217(81)90200-7", "Traveling purchaser heuristic", "not_mappable"),
    ],
    "tsp_drone": [
        ("10.1016/j.trc.2015.01.024", "Murray-Chu flying sidekick TSP", "not_mappable"),
        ("10.1002/net.21659", "Agatz truck-drone TSP", "not_mappable"),
    ],
    "tsp_fuel": [
        # 10.1007/3-540-44679-6_25 resolved to an unrelated reflecting-sequences paper.
    ],
    "tsp_angular": [
        ("10.1137/s0097539795291564", "Aggarwal angular-metric TSP", "not_mappable"),
        ("10.1287/opre.24.6.1018", "Or-opt", "move_selector"),
    ],
    "tsp_local": [
        ("10.1002/j.1538-7305.1965.tb04146.x", "Lin 3-opt", "not_mappable"),
        ("10.1287/opre.24.6.1018", "Or-opt", "not_mappable"),
    ],
    "vrptw": [
        ("10.1287/opre.35.2.254", "Solomon I1/I2 insertion", "not_mappable"),
        ("10.1287/opre.35.2.254", "Solomon VRPTW heuristics", "not_mappable"),
    ],
    "mdvrp": [
        ("10.1287/trsc.7.2.109", "Tillman multi-depot savings", "not_mappable"),
        ("10.1016/0305-0548(76)90063-5", "Wren multi-depot routing", "not_mappable"),
    ],
    "sdvrp": [
        ("10.1287/trsc.23.2.141", "Dror-Trudeau split delivery", "not_mappable"),
        ("10.1287/trsc.1070.0204", "Archetti split delivery heuristic", "not_mappable"),
    ],
    "hfvrp": [
        ("10.1016/0305-0548(90)90001-o", "Golden heterogeneous fleet", "not_mappable"),
        ("10.1002/net.3230140106", "Golden FSM / mix", "not_mappable"),
    ],
    "fsmvrp": [
        ("10.1002/net.3230140106", "Golden fleet size and mix", "not_mappable"),
        ("10.1287/trsc.1070.0190", "FSMVRPTW heuristics", "not_mappable"),
    ],
    "vrppd": [
        ("10.1287/trsc.29.1.45", "Bulk pickup-delivery heuristic", "not_mappable"),
        ("10.1002/net.3230190205", "VRP with pickups and deliveries", "not_mappable"),
    ],
    "pdptw": [
        ("10.1287/trsc.1050.0135", "Ropke-Pisinger ALNS PDPTW", "not_mappable"),
        ("10.1287/trsc.25.3.196", "Dumas PDPTW", "not_mappable"),
    ],
    "cvrpb": [
        ("10.1287/trsc.31.1.49", "VRP with backhauls and time windows", "not_mappable"),
        ("10.1002/net.3230190306", "Goetschalckx backhaul VRP", "not_mappable"),
    ],
    "vrpsdp": [
        ("10.1016/0377-2217(89)90434-3", "Min simultaneous pickup-delivery", "not_mappable"),
        ("10.1016/s0377-2217(98)00307-3", "VRPSPD heuristic", "not_mappable"),
    ],
    "pvrp": [
        ("10.1287/trsc.18.1.1", "Christofides-Beasley periodic routing", "not_mappable"),
        ("10.1002/net.3230060304", "Beltrami periodic routing", "not_mappable"),
    ],
    "irp": [
        ("10.1287/trsc.18.1.1", "Periodic / inventory-related routing", "not_mappable"),
        ("10.1287/trsc.1060.0160", "Two-echelon inventory routing", "not_mappable"),
    ],
    "darp": [
        ("10.1016/0191-2615(86)90045-1", "Jaw et al. dial-a-ride insertion", "not_mappable"),
        ("10.1287/trsc.29.4.342", "DARP heuristic", "not_mappable"),
    ],
    "cvrp_multitrip": [
        ("10.1002/net.3230140105", "Multi-trip VRP heuristic", "not_mappable"),
        ("10.1016/s0377-2217(02)00809-3", "Multi-trip routing context", "not_mappable"),
    ],
    "cvrp_site": [
        # 10.1016/0377-2217(91)90238-q resolved to a management-control paper, not site-dependent VRP.
    ],
    "cvrp_td": [
        ("10.1016/s0377-2217(01)00142-8", "Ichoua time-dependent VRP", "not_mappable"),
        ("10.1287/trsc.26.3.185", "Time-dependent travel times", "not_mappable"),
    ],
    "cvrp_stochastic": [
        ("10.1287/trsc.27.3.288", "Bertsimas stochastic VRP", "not_mappable"),
        ("10.1287/opre.1110.0967", "VRPSD approximation / heuristic context", "not_mappable"),
    ],
    "cvrp_dynamic": [
        ("10.1287/trsc.20.2.81", "Psaraftis dynamic VRP", "not_mappable"),
        ("10.1287/trsc.1060.0166", "Dynamic stochastic VRP heuristic", "not_mappable"),
    ],
    "evrp": [
        ("10.1016/j.ejor.2014.01.005", "Electric VRP with recharging", "not_mappable"),
        ("10.1016/j.ejor.2011.09.019", "EVRP heuristic context", "not_mappable"),
    ],
    "cvrp_2e": [
        ("10.1002/net.20428", "Perboli two-echelon VRP", "not_mappable"),
        ("10.1016/j.ejor.2008.10.023", "Crainic two-echelon routing", "not_mappable"),
    ],
    "cvrp_clustered": [
        ("10.1287/opre.22.2.340", "Gillett-Miller sweep", "not_mappable"),
        ("10.1287/opre.12.4.568", "Clarke-Wright savings", "not_mappable"),
    ],
    "cvrp_prize": [
        ("10.1002/net.3230190602", "Prize-collecting routing", "not_mappable"),
        ("10.1002/net.3230250406", "Selective TSP/VRP", "not_mappable"),
    ],
    "cvrp_minveh": [
        ("10.1287/opre.35.2.254", "Solomon parallel insertion (min vehicles)", "not_mappable"),
        ("10.1287/opre.12.4.568", "Clarke-Wright (fleet size effect)", "not_mappable"),
    ],
    "dcvrp": [
        ("10.1002/net.3230070404", "Distance-constrained VRP", "not_mappable"),
        ("10.1287/opre.12.4.568", "Clarke-Wright with route length", "not_mappable"),
    ],
    "cvrp_loading": [
        ("10.1002/net.20192", "Iori 2L-CVRP tabu / loading", "not_mappable"),
        ("10.1287/trsc.1070.0192", "VRP with loading constraints", "not_mappable"),
    ],
    "cvrp_mo": [
        ("10.1016/s0377-2217(02)00753-1", "Jozefowiez multi-objective VRP", "not_mappable"),
        ("10.1016/s0377-2217(01)00341-2", "MO routing heuristic", "not_mappable"),
    ],
    "cvrp_large": [
        ("10.1007/978-3-540-49481-2_30", "Shaw ruin-and-recreate", "not_mappable"),
        ("10.1287/ijoc.15.4.333.24890", "Toth-Vigo granular tabu", "not_mappable"),
    ],
    "bp_cardinality": [
        ("10.1137/050639065", "Online bin packing with cardinality constraints", "not_mappable"),
        ("10.1016/s0166-218x(99)00113-1", "Cardinality constrained packing", "not_mappable"),
    ],
    "bp_2d": [
        ("10.1016/s0377-2217(01)00179-9", "Lodi 2D bin packing", "not_mappable"),
        ("10.1287/ijoc.11.4.345", "2D packing algorithms", "not_mappable"),
    ],
    "bp_3d": [
        ("10.1287/opre.48.2.256.12386", "Martello 3D bin packing", "not_mappable"),
        ("10.1287/ijoc.12.1.26.11900", "3D packing heuristic", "not_mappable"),
    ],
    "vector_bp": [
        ("10.1137/s0097539701395456", "Vector bin packing approximation", "not_mappable"),
        ("10.1287/ijoc.1040.0089", "Two-constraint packing heuristic", "not_mappable"),
    ],
    "bp_fragile": [
        ("10.1007/s00453-006-0076-0", "Fragile objects bin packing", "not_mappable"),
        ("10.1007/978-3-540-31856-9_9", "Load-limit packing", "not_mappable"),
    ],
    "bp_colored": [
        ("10.1007/978-3-540-75520-3_10", "Colored bin packing", "not_mappable"),
        ("10.1007/s00453-012-9662-2", "Colored packing heuristic", "not_mappable"),
    ],
    "bp_conflicts": [
        ("10.1016/s0166-218x(01)00255-4", "Bin packing with conflicts", "not_mappable"),
        ("10.1007/s00453-006-0108-9", "Conflict packing heuristic", "not_mappable"),
    ],
    "bp_dynamic": [
        ("10.1137/0212045", "Dynamic bin packing", "not_mappable"),
        ("10.1137/0212043", "Dynamic packing algorithms", "not_mappable"),
    ],
    "bp_stochastic": [
        ("10.1137/s0097539793256681", "Stochastic bin packing", "not_mappable"),
        ("10.1002/rsa.10037", "Best Fit distributional analysis", "not_mappable"),
    ],
    "obp_advice": [
        ("10.1007/978-3-642-15369-3_9", "Online packing with advice", "not_mappable"),
        ("10.1007/978-3-642-04128-0_8", "Advice complexity packing", "not_mappable"),
    ],
    "bp_mo": [
        ("10.1016/s0377-2217(02)00753-1", "Multi-objective packing/routing", "not_mappable"),
        ("10.1287/ijoc.1040.0089", "Multi-constraint packing", "not_mappable"),
    ],
    "obp_irrevocable": [
        ("10.1137/0203025", "Johnson Worst Fit / Best Fit", "bin_score"),
        ("10.1007/s00453-021-00844-5", "Best Fit random-order", "bin_score"),
    ],
    "bp_batch": [
        ("10.1137/0203025", "Any Fit on a known batch", "bin_score"),
        ("10.1137/0204038", "Multifit / batch packing context", "not_mappable"),
    ],
    "bp_types": [
        ("10.1145/3828.3833", "Harmonic size classes", "not_mappable"),
        ("10.1137/0203025", "Few-size First/Best Fit", "bin_score"),
    ],
    "obp_lookahead": [
        ("10.1007/bf01193831", "Lookahead bin packing", "not_mappable"),
        ("10.1145/3828.3833", "Harmonic (bounded information)", "not_mappable"),
    ],
    "bp_open_end": [
        ("10.1287/opre.51.5.759.16753", "Open-end bin packing", "not_mappable"),
        ("10.1287/opre.1070.0415", "Open-end packing exact/heuristic context", "not_mappable"),
    ],
    "bp_resource": [
        ("10.1016/0377-2217(90)90090-z", "Resource-constrained packing", "not_mappable"),
        ("10.1287/ijoc.1040.0089", "Two-constraint packing", "not_mappable"),
    ],
    "obp_bestfit_family": [
        ("10.1137/0203025", "Best Fit / Almost Best Fit", "bin_score"),
        ("10.1007/s00453-021-00844-5", "Best Fit random-order", "bin_score"),
    ],
    "obp_worstfit_family": [
        ("10.1137/0203025", "Worst Fit / Almost Worst Fit", "bin_score"),
        ("10.1137/0222004", "Next-k-Fit (related Any Fit)", "not_mappable"),
    ],
    "obp_score": [
        ("10.1137/0203025", "Any-Fit residual preference", "bin_score"),
        ("10.1145/3828.3833", "Harmonic as class score", "not_mappable"),
    ],
    "bp_offline_kk": [
        ("10.1109/sfcs.1982.61", "Karmarkar-Karp", "not_mappable"),
        ("10.1137/0204038", "Coffman-Garey-Johnson Multifit", "not_mappable"),
    ],
    "kp_01": [
        ("10.1287/opre.5.2.266", "Dantzig density greedy", "not_mappable"),
        ("10.1287/opre.27.3.431", "Martello-Toth knapsack heuristics", "not_mappable"),
    ],
    "kp_unbounded": [
        ("10.1287/opre.5.2.266", "Unbounded / integer density greedy", "not_mappable"),
        ("10.1007/978-3-540-24777-7_8", "Unbounded knapsack chapter", "not_mappable"),
    ],
    "kp_bounded": [
        ("10.1287/opre.27.3.431", "Bounded knapsack heuristics", "not_mappable"),
        ("10.1007/978-3-540-24777-7_7", "Bounded knapsack chapter", "not_mappable"),
    ],
    "kp_multiple": [
        ("10.1287/opre.27.3.431", "Multiple knapsack greedy", "not_mappable"),
        ("10.1007/bf01580132", "Hung multiple knapsack", "not_mappable"),
    ],
    "kp_md": [
        ("10.1287/opre.27.6.1101", "Senju-Toyoda surrogate / MDKP", "not_mappable"),
        ("10.1287/ijoc.11.1.15", "MDKP heuristic", "not_mappable"),
    ],
    "kp_discount": [
        ("10.1016/s0377-2217(99)00320-7", "Discount knapsack", "not_mappable"),
    ],
    "kp_online": [
        ("10.1137/s0097539701384013", "Online knapsack", "not_mappable"),
        ("10.1007/978-3-540-45198-3_7", "Secretary / online knapsack", "not_mappable"),
    ],
    "kp_stochastic": [
        ("10.1287/opre.43.3.477", "Dean stochastic knapsack", "not_mappable"),
        ("10.1287/stsy.2019.0055", "Dynamic stochastic knapsack", "not_mappable"),
    ],
    "kp_fuzzy": [
        ("10.1016/0165-0114(94)90008-6", "Fuzzy knapsack", "not_mappable"),
    ],
    "kp_mo": [
        ("10.1007/bf02023023", "Multiobjective knapsack approximation", "not_mappable"),
        ("10.1287/mnsc.48.12.1603.445", "MO knapsack algorithms", "not_mappable"),
    ],
    "subset_sum": [
        ("10.1137/0202007", "Horowitz-Sahni subset sum", "not_mappable"),
        ("10.1287/opre.5.2.266", "Greedy subset-sum style packing", "not_mappable"),
    ],
    "kp_collapsing": [
        ("10.1016/0166-218x(94)00012-2", "Collapsing knapsack", "not_mappable"),
    ],
    "kp_prec": [
        ("10.1016/0166-218x(93)e0126-l", "Precedence knapsack", "not_mappable"),
    ],
    "kp_time": [
        ("10.1016/s0377-2217(01)00223-9", "Time-dependent knapsack", "not_mappable"),
    ],
    "kp_circular": [
        ("10.1016/0166-218x(95)00064-x", "Circular knapsack", "not_mappable"),
    ],
    "kp_group": [
        ("10.1287/opre.13.4.517", "Group knapsack / group IP", "not_mappable"),
        ("10.1287/opre.16.1.103", "Group knapsack DP", "not_mappable"),
    ],
    "kp_generalized": [
        ("10.1287/opre.16.1.141", "Generalized assignment", "not_mappable"),
        ("10.1007/bf01588971", "Martello-Toth GAP", "not_mappable"),
    ],
    "kp_compartment": [
        ("10.1016/s0377-2217(02)00548-3", "Compartmentalized knapsack", "not_mappable"),
    ],
    "kp_bilevel": [
        ("10.1007/s10107-006-0045-9", "Bilevel knapsack", "not_mappable"),
        ("10.1287/ijoc.2015.0676", "Knapsack interdiction", "not_mappable"),
    ],
    "kp_robust": [
        ("10.1007/s10107-003-0390-y", "Bertsimas-Sim robust combinatorial", "not_mappable"),
        ("10.2139/ssrn.1967411", "Robust knapsack", "not_mappable"),
    ],
    "kp_integer": [
        ("10.1287/opre.5.2.266", "Integer / unbounded greedy", "not_mappable"),
        ("10.1287/opre.27.3.431", "Integer knapsack heuristics", "not_mappable"),
    ],
    "kp_minmax": [
        ("10.1002/nav.20237", "Minmax multiple knapsack", "not_mappable"),
        ("10.1016/s0166-218x(03)00462-7", "Min-max knapsack", "not_mappable"),
    ],
    "kp_assign": [
        ("10.1287/opre.16.1.141", "Assignment / GAP greedy", "not_mappable"),
        ("10.1007/bf01588971", "GAP heuristics", "not_mappable"),
    ],
    "kp_order_greedy": [
        ("10.1287/opre.5.2.266", "Take-if-fits / greedy knapsack", "not_mappable"),
        ("10.1287/opre.27.3.431", "Greedy knapsack variants", "not_mappable"),
    ],
    "kp_density": [
        ("10.1287/opre.5.2.266", "Dantzig density greedy", "not_mappable"),
        ("10.1287/opre.27.3.431", "Critical-item / core heuristic", "not_mappable"),
    ],
}


def seeds_for(subproblem_id: str) -> list[tuple[str, str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for doi, name, kind in CANONICAL.get(subproblem_id, []):
        key = doi.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((doi, name, kind))
    return out
