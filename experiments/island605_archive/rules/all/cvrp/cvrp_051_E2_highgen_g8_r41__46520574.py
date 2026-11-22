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
    if current_node == depot:
        # Seed route with customer farthest from depot
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dist_from_depot)]

    # Parameter alpha controls trade-off: 0 = pure nearest, 1 = pure farthest-from-depot
    alpha = 0.3

    dist_from_depot = distance_matrix[depot][unvisited_nodes]
    dist_from_current = distance_matrix[current_node][unvisited_nodes]

    # Normalize distances to avoid scale issues
    max_depot = dist_from_depot.max() if dist_from_depot.max() > 0 else 1
    max_curr = dist_from_current.max() if dist_from_current.max() > 0 else 1
    norm_depot = dist_from_depot / max_depot
    norm_current = dist_from_current / max_curr

    # Score: high when far from depot and close to current node
    score = alpha * norm_depot - (1 - alpha) * norm_current
    best_idx = np.argmax(score)
    best_node = unvisited_nodes[best_idx]

    # Fallback: if capacity is very tight, use nearest neighbor
    min_demand = demands[unvisited_nodes].min()
    if rest_capacity <= min_demand * 1.5:
        return unvisited_nodes[np.argmin(dist_from_current)]

    return best_node
