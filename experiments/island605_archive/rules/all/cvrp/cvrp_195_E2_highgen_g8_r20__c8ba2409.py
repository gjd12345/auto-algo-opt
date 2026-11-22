def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    # Compute savings: (distance from depot to customer * 2) - (distance from current to customer + distance from customer to depot)
    depot_dist = distance_matrix[depot][unvisited_nodes]
    cur_dist = distance_matrix[current_node][unvisited_nodes]
    savings = 2 * depot_dist - (cur_dist + depot_dist)
    # Select customer with maximum savings
    best_idx = unvisited_nodes[np.argmax(savings)]
    return best_idx
