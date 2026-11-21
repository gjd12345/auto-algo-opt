def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    eps = 1e-12
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_dep_cur = distance_matrix[depot][current_node]
    dem = demands[unvisited_nodes].astype(float)

    cap = max(rest_capacity, 1e-9)
    frac = np.clip(dem / cap, 0.0, 1.0)

    # Proximity term: short hops are good, but scaled by how much capacity remains
    # (when nearly full, distance matters more; when empty, we can roam).
    prox = d_cur / (1.0 + d_dep + eps)
    # Capacity pressure: strongly prefer filling the vehicle to avoid a short-trip penalty
    pressure = 0.6 + 0.8 * frac

    # Polar sweep term: angle of candidate around depot relative to current angle,
    # keep moving forward in angular order to form a coherent tour.
    ang_cur = np.arctan2(current_node - depot if current_node != depot else 0.0, 1.0)
    # Use vectors to compute actual angle difference
    cur_vec_x = distance_matrix[depot][current_node]  # proxy magnitude (not exact coords)
    # Approximate angular cost using law of cosines with depot distance and current radius
    r_cur = max(d_dep_cur, eps)
    r_c = np.maximum(d_dep, eps)
    cos_gap = (r_cur * r_cur + r_c * r_c - d_cur * d_cur) / (2.0 * r_cur * r_c)
    cos_gap = np.clip(cos_gap, -1.0, 1.0)

    # Reward mild angular turns (cos close to 1 means straight radial continuation)
    sweep = cos_gap - 0.5 * (1.0 - cos_gap)

    # Combine: prefer close-but-productive candidates, penalize long jumps
    scores = pressure * 1.0 / (prox + eps) + 0.25 * sweep + 0.15 * d_dep ** 0.5 * frac

    return int(unvisited_nodes[np.argmax(scores)])