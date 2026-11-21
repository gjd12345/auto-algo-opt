def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]
    dem = demands[unvisited_nodes].astype(float)

    # Marginal detour of inserting the customer between current node and depot.
    detour = d_cur + d_dep - d_cur_dep

    # Radial savings weighted by feasibility slack: prefer customers whose
    # demand leaves the vehicle flexible (small dem/cap) and that are far
    # from the depot (high return cost), keeping the remaining route compact.
    slack = cap / (cap + dem)
    savings = d_dep * slack

    # Score: low detour, high savings -> visit early.
    score = detour - 0.8 * savings
    return int(unvisited_nodes[np.argmin(score)])