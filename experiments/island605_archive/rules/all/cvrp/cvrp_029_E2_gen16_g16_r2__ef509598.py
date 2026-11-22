def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    half_capacity = np.sum(demands) / len(demands) * 2  # adaptive threshold
    if rest_capacity > half_capacity:
        # Savings-based score: prefer customers where visiting from current is much cheaper than returning to depot
        dist_to_depot = distance_matrix[unvisited_nodes, depot]
        dist_from_current = distance_matrix[current_node, unvisited_nodes]
        savings = dist_to_depot - dist_from_current
        return unvisited_nodes[np.argmax(savings)]
    else:
        # Low capacity: pure nearest-neighbor to finish route efficiently
        dist_from_current = distance_matrix[current_node, unvisited_nodes]
        return unvisited_nodes[np.argmin(dist_from_current)]
