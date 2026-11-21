def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cur_dist = distance_matrix[current_node][unvisited_nodes]
    depot_dist = distance_matrix[depot][unvisited_nodes]
    node_demands = demands[unvisited_nodes]

    # Capacity pressure: prefer customers that leave less wasted capacity
    cap_denom = rest_capacity if rest_capacity > 1e-9 else 1e-9
    load_ratio = node_demands / cap_denom

    # Weighted combination: nearest, not too far from depot, good capacity fit
    scores = cur_dist + 0.35 * depot_dist + 0.5 * load_ratio

    return int(unvisited_nodes[np.argmin(scores)])