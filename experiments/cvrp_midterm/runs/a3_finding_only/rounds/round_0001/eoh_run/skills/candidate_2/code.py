def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # span-based scale normalization (invariant to coordinate scaling)
    scale = np.max(distance_matrix)
    if scale <= 0:
        scale = 1.0

    # capacity-aware weight on depot distance: fuller loads favor nearer-to-depot customers
    total_cap = rest_capacity + np.sum(dem)
    if total_cap <= 0:
        total_cap = 1.0
    load_frac = rest_capacity / total_cap  # high when vehicle is still empty-ish

    # weight increases as remaining capacity shrinks relative to remaining demand
    w_depot = 0.7 * (1.0 - load_frac) + 0.1

    score = (d_cur + w_depot * d_dep) / scale
    return int(unvisited_nodes[np.argmin(score)])