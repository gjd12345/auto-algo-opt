def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cd = distance_matrix[current_node][depot]

    dem = demands[unvisited_nodes]
    cap = max(rest_capacity, 1e-9)

    if current_node == depot:
        score = -d_dep
        return int(unvisited_nodes[np.argmax(score)])

    scale = max(d_cd, 1e-9)
    prox = d_cur / scale
    save = (d_cd + d_dep - d_cur) / scale
    cap_ratio = np.clip(dem / cap, 0.0, 1.0)

    score = save - 0.55 * prox - 0.15 * (cap_ratio ** 2) * prox
    return int(unvisited_nodes[np.argmax(score)])