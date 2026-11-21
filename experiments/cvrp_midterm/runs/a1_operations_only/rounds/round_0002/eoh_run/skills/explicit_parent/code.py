def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur_dep = distance_matrix[current_node][depot]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur = distance_matrix[current_node][unvisited_nodes]

    base = d_cur - 0.6 * d_dep

    order = np.argsort(base)
    best_idx = int(order[0])

    if order.size > 1:
        best_score = base[best_idx]
        second_score = base[int(order[1])]
        span = float(np.max(base) - np.min(base))
        if span <= 0.0:
            span = 1.0
        rel_band = 1e-3 * span
        if abs(second_score - best_score) <= rel_band:
            near_mask = np.abs(base - best_score) <= rel_band
            near_idx = np.nonzero(near_mask)[0]
            if near_idx.size > 1:
                cand_nodes = unvisited_nodes[near_idx]
                cand_demands = demands[cand_nodes]
                fits = cand_demands <= rest_capacity
                if np.any(fits):
                    cand_idx = near_idx[fits.astype(bool)]
                    if cand_idx.size == 1:
                        return int(unvisited_nodes[int(cand_idx[0])])
                    sub_nodes = unvisited_nodes[cand_idx]
                    sub_demands = demands[sub_nodes]
                    sub_dist = distance_matrix[current_node][sub_nodes]
                    # Prefer largest demand, then smallest distance, then best base score
                    max_dem = float(np.max(sub_demands))
                    dem_mask = np.isclose(sub_demands, max_dem)
                    if np.sum(dem_mask) == 1:
                        chosen = int(np.nonzero(dem_mask)[0][0])
                        return int(sub_nodes[chosen])
                    sub2_nodes = sub_nodes[dem_mask]
                    sub2_dist = sub_dist[dem_mask]
                    min_dist = float(np.min(sub2_dist))
                    dist_mask = np.isclose(sub2_dist, min_dist)
                    if np.sum(dist_mask) == 1:
                        chosen = int(np.nonzero(dist_mask)[0][0])
                        return int(sub2_nodes[chosen])
                    # Last tie-break: best base score among remaining
                    sub2_base = base[cand_idx[dem_mask]]
                    final_local = int(np.argmin(sub2_base))
                    return int(sub2_nodes[final_local])

    return int(unvisited_nodes[best_idx])