def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    idx = np.asarray(unvisited_nodes, dtype=int)
    d_cur = distance_matrix[current_node][idx].astype(float)
    d_dep = distance_matrix[depot][idx].astype(float)
    dem = demands[idx].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    fill = np.clip(dem / cap, 0.0, 1.0)
    # Detour-to-progress ratio: how far we travel now per unit of depot-progress
    # made, penalized when the node barely fills the remaining capacity.
    detour = d_cur + 1e-9
    progress = d_dep + 1e-9
    ratio = detour / progress                       # small => heading outward
    scarcity = 1.0 + 2.0 * (1.0 - fill)             # under-filled nodes penalized
    score = ratio * scarcity * (1.0 + 0.5 * d_cur / (d_dep + d_cur + 1e-9))
    # mild absolute-distance tiebreaker keeps routes compact
    score = score * (1.0 + 0.15 * d_cur)
    return int(idx[np.argmin(score)])