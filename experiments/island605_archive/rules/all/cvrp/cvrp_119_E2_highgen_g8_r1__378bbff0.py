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
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start new route: go to farthest customer
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Compute distances
    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]

    # Weighted score: minimize (1.5 * dist_current - 0.5 * dist_depot)
    # This balances proximity with seeding toward far clusters
    scores = 1.5 * dist_current - 0.5 * dist_depot

    # Regret heuristic for tie-breaking among top candidates
    sorted_indices = np.argsort(scores)
    top2 = sorted_indices[:2]
    if len(top2) == 2:
        regret = scores[top2[1]] - scores[top2[0]]
        # If regret is high and rest_capacity is tight, override with nearest
        if regret > 10.0 and rest_capacity < 10:
            return unvisited_nodes[np.argmin(dist_current)]

    best_idx = np.argmin(scores)

    # Nearest neighbor fallback if all scores are degenerate
    if np.max(scores) == np.min(scores):
        return unvisited_nodes[np.argmin(dist_current)]

    return unvisited_nodes[best_idx]
