def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_dep_cur = distance_matrix[current_node][depot]

    span = d_cur.max() + d_dep.max()
    if span <= 0:
        return int(unvisited_nodes[np.argmin(d_cur)])

    load_frac = demands[unvisited_nodes] / max(rest_capacity, 1e-12)
    score = (d_cur + d_dep - 0.5 * d_dep_cur) / span + 0.05 * load_frac
    return int(unvisited_nodes[np.argmin(score)])