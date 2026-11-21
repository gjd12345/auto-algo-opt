def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    dep_from_depot = distance_matrix[depot][unvisited_nodes]
    d_cur_depot = distance_matrix[current_node][depot]
    # Clarke-Wright savings: linking current->node versus returning to depot.
    savings = d_cur_depot + dep_from_depot - cur
    # Replace capacity-utilization factor with a relative-demand term.
    dem = demands[unvisited_nodes]
    dem_max = float(np.max(dem)) if dem.size > 0 else 1.0
    rel_dem = dem / max(dem_max, 1e-9)
    scale = d_cur_depot + float(np.max(dep_from_depot)) + 1e-12
    # Primary score: maximize savings plus relative demand contribution.
    scores = -(savings + 0.5 * rel_dem * scale)
    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    # Secondary: among near-ties, prefer smallest depot-distance-to-current ratio.
    tie_nodes = unvisited_nodes[tied]
    cur_d = distance_matrix[current_node][tie_nodes]
    dep_d = distance_matrix[depot][tie_nodes]
    ratio = dep_d / (cur_d + 1e-9)
    return int(tie_nodes[np.argmin(ratio)])