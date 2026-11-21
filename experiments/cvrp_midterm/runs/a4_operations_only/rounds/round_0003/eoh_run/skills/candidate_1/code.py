def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
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
    dep = distance_matrix[depot][unvisited_nodes]
    mean_dep = float(np.mean(dep)) if dep.size > 0 else 1.0
    if mean_dep <= 0:
        mean_dep = 1.0
    # Primary: closest current distance with stronger depot-distance penalty
    scores = cur - 0.75 * (dep / mean_dep)
    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    cap = max(rest_capacity, 1e-9)
    tie_nodes = unvisited_nodes[tied]
    ratio = demands[tie_nodes] / cap
    best_ratio_idx = int(np.argmax(ratio))
    candidates = tie_nodes[ratio >= ratio[best_ratio_idx] - 1e-12]
    dists = distance_matrix[current_node][candidates]
    return int(candidates[np.argmin(dists)])