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

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    base = d_cur - 0.6 * d_dep

    order = np.argsort(base)
    best_idx = order[0]
    best_score = base[best_idx]

    span = float(base[order[-1]] - base[order[0]])
    band = 1e-2 * span + 1e-12

    near = order[base[order] <= best_score + band]
    if near.size <= 1:
        return int(unvisited_nodes[best_idx])

    near_nodes = unvisited_nodes[near]
    slack = rest_capacity - demands[near_nodes]
    feasible = slack >= 0
    if not np.any(feasible):
        return int(unvisited_nodes[best_idx])

    # refine: balance capacity fit with route-closing cost
    scale = span if span > 0.0 else 1.0
    fit = np.where(feasible, slack / (rest_capacity + 1e-12), np.inf)
    close_cost = distance_matrix[depot][near_nodes] / scale
    score = fit + 0.15 * close_cost
    score = np.where(feasible, score, np.inf)
    pick_local = int(np.argmin(score))
    return int(near_nodes[pick_local])