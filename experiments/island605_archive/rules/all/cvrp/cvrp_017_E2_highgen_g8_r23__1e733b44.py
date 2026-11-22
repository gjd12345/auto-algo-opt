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
        # Farthest-first seeding
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    # Compute distances from current node to all unvisited nodes
    dists = distance_matrix[current_node][unvisited_nodes]

    # Compute average distance from each unvisited node to all other unvisited nodes
    avg_dists = np.array([
        np.mean(distance_matrix[u][unvisited_nodes])
        for u in unvisited_nodes
    ])

    # Regret score: penalize nodes that are far from current but close to others (high regret if not taken now)
    regret = dists / (avg_dists + 1e-10)

    best_idx = np.argmin(regret)
    best_node = unvisited_nodes[best_idx]

    # Voluntary return to depot if the best node is closer to depot than to current node
    if distance_matrix[current_node][depot] < distance_matrix[current_node][best_node] * 0.7:
        return depot

    return best_node
