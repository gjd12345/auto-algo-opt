def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Scale-invariant combination:
    # - favor nearby customers (small d_cur)
    # - favor customers whose depot detour is small relative to their distance
    #   (encourage returning via a compact route)
    # - lightly penalize large demands when capacity is tight
    scale = np.max(d_cur) + np.max(d_dep) + 1e-12

    # detour: extra distance to return via depot compared to going direct
    detour = np.maximum(d_dep - d_cur, 0.0)

    cap_frac = np.clip(rest_capacity / (rest_capacity + dem + 1e-12), 0.0, 1.0)
    load_pen = (1.0 - cap_frac) * (dem / (np.max(dem) + 1e-12))

    score = (d_cur / scale) + 0.5 * (detour / scale) + 0.3 * load_pen

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])