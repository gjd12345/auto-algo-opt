def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Normalise load pressure: closer to full remaining capacity -> stronger penalty on depot proximity
    cap = rest_capacity if rest_capacity > 0 else 1.0
    load_pressure = np.clip(dem / cap, 0.0, 1.0)

    # Reward far-from-depot nodes when load pressure is high (fill up route before returning)
    score = d_cur - 0.35 * d_dep * (0.5 + load_pressure)

    return int(unvisited_nodes[np.argmin(score)])