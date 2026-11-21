def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    dep_from_depot = distance_matrix[depot][unvisited_nodes]
    d_cur_depot = distance_matrix[current_node][depot]
    # Classic Clarke-Wright savings: how much we save by linking current->node
    # instead of going back to depot from current and out to node.
    savings = d_cur_depot + dep_from_depot - cur
    cap = max(rest_capacity, 1e-9)
    util = demands[unvisited_nodes] / cap
    # Primary score: maximize savings, boosted slightly by capacity utilization
    scores = -(savings + 0.5 * util * (d_cur_depot + float(np.max(dep_from_depot)) + 1e-12))
    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    # Secondary: among near-ties, pick the node closest to current node
    tie_nodes = unvisited_nodes[tied]
    dists = distance_matrix[current_node][tie_nodes]
    return int(tie_nodes[np.argmin(dists)])