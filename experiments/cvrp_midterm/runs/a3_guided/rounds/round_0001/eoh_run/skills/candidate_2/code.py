def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cd = distance_matrix[current_node][depot]

    span = float(max(d_dep.max(), d_cur.max()))
    eps = 1e-9 + 1e-6 * span
    denom = max(d_cd, eps)

    # Scale-invariant detour ratio replaces the absolute distance-to-depot term.
    detour_ratio = (d_cur + d_dep - d_cd) / denom

    dem = demands[unvisited_nodes].astype(float)

    primary = d_cur + detour_ratio

    # Secondary ordering stage: within a cheap relative near-tie band,
    # prefer the larger demand-to-detour ratio.
    p_min = primary.min()
    tie_band = p_min * 1e-6 + eps
    close = np.where(primary - p_min <= tie_band)[0]

    if close.size > 1:
        ratios = dem[close] / (d_cur[close] + eps)
        best = close[np.argmax(ratios)]
    else:
        best = int(np.argmin(primary))

    return int(unvisited_nodes[best])