def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    span = float(np.max(d_cur) - np.min(d_cur)) if d_cur.size > 1 else 0.0
    norm = span + 1e-12

    # Stronger weight on current-node proximity, weaker depot pull than the parent.
    alpha = 0.35
    base = (d_cur - alpha * d_dep) / norm

    # Capacity pressure: when little capacity remains, bias toward filling it fully.
    cap_frac = rest_capacity / (rest_capacity + 1e-12)
    dem = demands[unvisited_nodes].astype(float)
    fill = dem / (rest_capacity + 1e-12)
    load_term = 1e-3 * (fill - cap_frac)

    score = base - load_term

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])