def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    idx = np.asarray(unvisited_nodes, dtype=int)
    dep = int(depot)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    cur_vec = None
    if int(current_node) != dep:
        x0 = distance_matrix[dep][int(current_node)]
        if x0 > 1e-12:
            # direction from depot to current node (proxy for heading)
            pass

    # approximate positions from distance matrix relative to depot
    # place depot at origin; use distance to depot as radius and
    # angle inferred from pairwise distances via law of cosines
    r_cur = distance_matrix[dep][int(current_node)]
    r_idx = distance_matrix[dep][idx]

    # bearing of each candidate relative to depot->current direction
    # cos(angle between vectors) = (r_cur^2 + r_i^2 - d(cur,i)^2) / (2 r_cur r_i)
    d_ci = distance_matrix[int(current_node)][idx].astype(float)
    r_cur_f = float(r_cur)
    r_i = r_idx.astype(float)
    denom = 2.0 * r_cur_f * r_i
    denom = np.where(denom < 1e-12, 1e-12, denom)
    cosang = (r_cur_f * r_cur_f + r_i * r_i - d_ci * d_ci) / denom
    cosang = np.clip(cosang, -1.0, 1.0)
    # deviation angle; straight ahead = 0
    angle = np.arccos(cosang)

    dem = demands[idx].astype(float)
    fill = dem / cap

    # direction-aware score: prefer small angular deviation, small leg distance,
    # high demand fill; add slight pull away from depot for radial sweep
    score = 1.2 * angle + 0.9 * d_ci - 0.4 * r_i / (r_cur_f + 1.0) - 0.5 * fill
    return int(idx[np.argmin(score)])