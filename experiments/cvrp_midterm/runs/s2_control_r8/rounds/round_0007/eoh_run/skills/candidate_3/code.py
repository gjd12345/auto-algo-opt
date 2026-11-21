def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    total_dem = float(np.sum(dem)) if nodes.size > 0 else 0.0
    fill = 1.0 - min(1.0, cap / (cap + total_dem + 1e-9))

    # Savings: how much farther the customer is from depot than from us.
    savings = d_dep - d_cur
    # Demand penalty: prefer lighter customers as capacity shrinks.
    dem_ratio = dem / (cap + 1e-9)

    w_sav = 1.0 - 0.5 * fill
    w_dem = 0.3 + 1.2 * fill

    # Lower score is better: we want large savings (so negative savings helps),
    # small d_cur, and small demand.
    score = d_cur - w_sav * savings + w_dem * d_dep * dem_ratio
    return int(nodes[int(np.argmin(score))])