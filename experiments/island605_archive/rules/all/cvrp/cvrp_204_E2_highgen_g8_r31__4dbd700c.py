def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    depot_dist = distance_matrix[depot]
    current_dist = distance_matrix[current_node]

    savings = depot_dist[current_node] + depot_dist[unvisited_nodes] - current_dist[unvisited_nodes]

    # Capacity penalty: favor customers that better fill remaining capacity
    capacity_fill = demands[unvisited_nodes] / rest_capacity
    # Penalty proportional to how much capacity would remain after serving
    # i.e., prefer customers with high demand relative to rest_capacity
    penalty = (1 - capacity_fill) * rest_capacity / (rest_capacity + 1e-6)

    # Weighted score: savings - 0.2 * penalty (to discourage wasting capacity)
    scores = savings - 0.2 * penalty

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
