def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    base = d_cur - 0.6 * d_dep
    span = float(d_cur.max() - d_cur.min()) if d_cur.size > 1 else 0.0
    band = 1e-3 * span + 1e-12
    bmin = base.min()
    near = np.where(base <= bmin + band)[0]
    if near.size == 1:
        return int(unvisited_nodes[near[0]])
    # refine inside near-tie band: prefer closest to depot then closest to current
    cand = near
    return int(unvisited_nodes[cand[np.argmin(d_dep[cand])]])