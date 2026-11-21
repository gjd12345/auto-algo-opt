def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Estimate total remaining demand to gauge capacity pressure
    total_rem_dem = float(np.sum(dem)) if dem.size > 0 else 1.0
    if total_rem_dem <= 0.0:
        total_rem_dem = 1.0

    # Capacity fill reward: prefer nodes whose demand fits well with remaining capacity
    # (larger relative demand is rewarded, but never exceeding rest_capacity by construction)
    cap_frac = rest_capacity if rest_capacity > 0.0 else 1.0
    fill = dem / cap_frac  # in [0, 1] since unvisited_nodes are feasible

    # Depot-distance saving signal (classic Clarke-Wright-like term)
    saving = d_dep

    # Directional coherence: angle between (depot->current) and (current->cand)
    # Project candidate displacement onto the outward radial direction from depot to current.
    cur_vec = distance_matrix[depot][current_node]
    # Use distances as proxy: encourage moving away from depot early, back later
    pressure = rest_capacity / (total_rem_dem + 1e-12)  # >1 means plenty of capacity left
    away_gain = np.clip(d_dep - d_cur, -1e9, 1e9)
    # When capacity is tight, prioritize returning toward depot-favorable nodes.

    # Combined score (lower is better):
    #   - d_cur : local travel cost
    #   - small weight on d_dep : keep near depot when capacity is tight
    #   - reward high fill nodes (negative sign) when capacity is abundant
    score = (d_cur
             + 0.4 * d_dep
             - 0.6 * saving * np.clip(1.0 - fill, 0.0, 1.0)
             + 0.25 * np.abs(0.5 - fill) * pressure)

    # Blend a mild angular preference: candidates roughly in the direction away from depot
    # while capacity is high; when pressure is low (tight capacity) pull slightly inward.
    score = score - 0.15 * pressure * away_gain

    return int(unvisited_nodes[int(np.argmin(score))])