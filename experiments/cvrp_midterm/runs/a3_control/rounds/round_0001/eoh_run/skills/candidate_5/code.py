def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_depot = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    load_frac = 1.0 - (rest_capacity - dem) / np.maximum(rest_capacity, 1e-9)

    score = 1.0 * d_cur + 0.3 * d_depot - 0.2 * dem

    return int(unvisited_nodes[np.argmin(score)])