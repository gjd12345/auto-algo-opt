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
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]
    # Weighted combination: prefer nodes close to current but far from depot
    # alpha = 0.7 emphasises distance to current, beta = 0.3 emphasises inverse distance from depot
    alpha = 0.7
    beta = 0.3
    # Normalise distances to avoid scale dominance
    max_cur = np.max(dist_current) if np.max(dist_current) > 0 else 1.0
    max_dep = np.max(dist_depot) if np.max(dist_depot) > 0 else 1.0
    score = alpha * (dist_current / max_cur) - beta * (dist_depot / max_dep)
    return unvisited_nodes[np.argmin(score)]
