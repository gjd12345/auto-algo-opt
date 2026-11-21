def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    max_d = float(np.max(distance_matrix))
    if max_d <= 0.0:
        max_d = 1.0

    # Proximity to current node (higher = closer)
    prox = 1.0 - d_cur / max_d

    # Depot-return savings: how much we save by extending the tour to this node
    # rather than returning to depot now (classic Clarke-Wright style term)
    d_cur_dep = float(distance_matrix[current_node][depot])
    savings = d_cur_dep + d_dep - d_cur
    savings_norm = savings / (max_d + 1e-9)

    # Demand urgency: prefer high-demand nodes so route packs well early
    max_dem = float(np.max(dem)) if dem.size > 0 else 1.0
    if max_dem <= 0.0:
        max_dem = 1.0
    dem_norm = dem / max_dem

    # Capacity tightness: reward filling the truck close to capacity
    fill = 1.0 - (cap - dem) / (cap + 1e-9)
    fill = np.clip(fill, 0.0, 1.0)

    score = 0.40 * prox + 0.30 * savings_norm + 0.20 * dem_norm + 0.10 * fill
    return int(unvisited_nodes[np.argmax(score)])