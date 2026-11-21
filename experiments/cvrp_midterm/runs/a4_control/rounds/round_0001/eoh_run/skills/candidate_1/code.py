def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]
    total_cap = rest_capacity + 0.0
    # Route-remaining capacity fraction after serving node
    rem_after = rest_capacity - dem
    # Penalize customers that leave little capacity (encourages fuller routes)
    load_term = (dem / (rest_capacity + 1e-9)) * 0.5
    # Encourage proximity to depot when capacity is nearly exhausted
    near_end = (1.0 - rest_capacity / (total_cap + 1e-9))
    score = d_cur + 0.3 * d_dep * near_end - 0.2 * dem / (rem_after + 1e-9) * 0.0 + load_term * 0.1
    return int(unvisited_nodes[np.argmin(score)])