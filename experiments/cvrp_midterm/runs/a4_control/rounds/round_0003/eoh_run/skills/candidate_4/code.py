def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep_cur = distance_matrix[depot][current_node]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = max(rest_capacity, 1e-9)

    # Clarke-Wright savings: gain from servicing candidate after current instead of a separate depot leg
    savings = d_dep_cur + d_dep - d_cur

    # Capacity slack reward: prefer candidates that consume a moderate fraction,
    # leaving room to keep chaining (peak reward near 40% of remaining capacity)
    frac = dem / cap
    slack = 1.0 - np.abs(frac - 0.4)

    # Directional coherence: reward candidates roughly aligned with the current
    # radial vector from depot (extends outward sweep), penalize sharp turns.
    eps = 1e-9
    cos_cur = (d_dep_cur * d_dep_cur - d_dep * d_dep - d_cur * d_cur) / (2.0 * np.maximum(d_cur, eps) * np.maximum(d_dep_cur, eps))
    cos_cur = np.clip(cos_cur, -1.0, 1.0)

    scores = savings + 0.35 * d_dep * slack + 0.15 * d_cur * cos_cur

    return int(unvisited_nodes[np.argmax(scores)])