def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    d_0cur = float(distance_matrix[depot][current_node])

    demand = demands[unvisited_nodes].astype(np.float64)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    fill = np.clip(demand / cap, 0.0, 1.0)

    eps = 1e-9

    savings = d_0cur + d_dep - d_cur
    round_trip = d_0cur + d_dep + eps
    sav_norm = savings / round_trip

    fill_pressure = np.sqrt(fill)

    dmax = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    if dmax <= 0:
        dmax = 1.0
    radial = d_dep / dmax

    score = (sav_norm + 1.0) * (1.0 + 0.25 * fill_pressure) * (1.0 + 0.20 * radial)

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])