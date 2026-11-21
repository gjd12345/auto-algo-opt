def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    cur_dist = distance_matrix[current_node][unvisited_nodes]
    depot_dist = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Capacity pressure: prefer larger demands when remaining capacity is tight,
    # but avoid over-prioritizing demand when capacity is plentiful.
    cap = max(float(rest_capacity), 1e-9)
    load_term = dem / cap

    # Blend: nearest neighbor with a mild depot-distance tie-break and load pressure.
    score = cur_dist + 0.15 * depot_dist + 0.5 * load_term * cur_dist

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])