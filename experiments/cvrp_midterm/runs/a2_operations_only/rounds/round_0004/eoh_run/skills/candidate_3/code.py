def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 0 else 1e-9
    # distance-from-depot term replaced by a capacity-aware fill term
    fill = (dem / cap) * d_dep
    score = d_cur - fill
    return unvisited_nodes[np.argmin(score)]