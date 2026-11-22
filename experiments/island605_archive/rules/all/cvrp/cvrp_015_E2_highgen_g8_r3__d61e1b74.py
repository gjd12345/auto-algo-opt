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
        # Seed route: farthest customer from depot
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[farthest_idx]

    # Calculate distances from current node to all unvisited nodes
    dists = distance_matrix[current_node][unvisited_nodes]

    # Calculate average distance from each unvisited node to all other unvisited nodes
    best_ratio = float('inf')
    best_customer = unvisited_nodes[0]
    for i, candidate in enumerate(unvisited_nodes):
        other_dists = distance_matrix[candidate][unvisited_nodes]
        avg_other_dist = np.mean(other_dists)
        ratio = dists[i] / (avg_other_dist + 1e-10)
        if ratio < best_ratio:
            best_ratio = ratio
            best_customer = candidate

    # Return to depot if selected customer is disproportionately far
    if distance_matrix[current_node][best_customer] > distance_matrix[current_node][depot] * 1.2:
        return depot

    return best_customer
