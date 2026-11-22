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

    n = len(unvisited_nodes)
    if n == 0:
        return depot

    dists_current = distance_matrix[current_node][unvisited_nodes]
    scores = np.zeros(n)
    for i, candidate in enumerate(unvisited_nodes):
        dists_to_others = distance_matrix[candidate][unvisited_nodes]
        avg_dist_to_others = np.mean(dists_to_others)
        scores[i] = avg_dist_to_others - dists_current[i]

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
