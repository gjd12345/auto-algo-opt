def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    idx = np.asarray(unvisited_nodes, dtype=int)
    d_cur = distance_matrix[current_node][idx]
    d_dep = distance_matrix[depot][idx]
    dem = demands[idx].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    fill = dem / cap               
    savings = d_dep - d_cur        

    # Rebalanced parameters: emphasize proximity to current node,
    # moderate depot avoidance, stronger fill weighting, and stronger savings term.
    score = 1.20 * d_cur - 0.15 * d_dep + 1.10 * (1.0 - fill) * d_cur - 0.30 * savings
    return int(idx[np.argmin(score)])