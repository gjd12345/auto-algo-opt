def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Scale-invariant load ratio in [0,1]: how much of remaining capacity this node consumes.
    cap = rest_capacity if rest_capacity > 0 else 1.0
    load_ratio = dem / cap

    # Primary: nearest distance. Secondary: prefer customers whose depot distance is
    # small relative to the current leg (saves a long deadhead back) and that fill
    # capacity well. Both secondary terms are dimensionless multipliers, so the
    # rule is invariant to re-expression of the distance scale.
    depot_rel = d_dep / (d_cur + 1e-9)

    score = d_cur * (1.0 + 0.3 * depot_rel - 0.2 * load_ratio)

    return int(unvisited_nodes[np.argmin(score)])