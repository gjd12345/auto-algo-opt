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
    if unvisited_nodes.size == 1:
        return int(unvisited_nodes[0])

    cur = int(current_node)
    dep = int(depot)

    d_cur = distance_matrix[cur][unvisited_nodes].astype(float)
    d_depot = distance_matrix[dep][unvisited_nodes].astype(float)
    d_cur_depot = float(distance_matrix[cur][dep])

    # Absolute Clarke-Wright savings: primary signal.
    savings = d_cur_depot + d_depot - d_cur

    # Detect near-ties among the top candidates to refine with a normalized score.
    order = np.argsort(-savings)
    best_saving = float(savings[order[0]])
    tol = 0.02 * max(abs(best_saving), 1e-9) + 1e-12
    tie_mask = savings >= (best_saving - tol)

    if int(tie_mask.sum()) <= 1:
        return int(unvisited_nodes[order[0]])

    # Normalized secondary ranking applied only within the near-tie set.
    dem = demands[unvisited_nodes].astype(float)
    cap_scale = max(float(rest_capacity), 1e-9)

    route_scale = np.maximum(d_cur + d_depot, 1e-9)
    normalized_saving = savings / route_scale

    demand_penalty = dem / cap_scale
    local_score = normalized_saving - 0.1 * demand_penalty

    tie_indices = np.nonzero(tie_mask)[0]
    best_local = tie_indices[np.argmax(local_score[tie_indices])]

    return int(unvisited_nodes[best_local])