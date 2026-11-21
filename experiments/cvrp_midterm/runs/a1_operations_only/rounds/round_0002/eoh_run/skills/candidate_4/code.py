def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    base = d_cur - 0.6 * d_dep

    order = np.argsort(base)
    best_pos = int(order[0])
    best_score = float(base[best_pos])

    if order.size > 1:
        second_score = float(base[int(order[1])])
        span = float(np.max(base) - np.min(base))
        if span <= 0.0:
            span = max(abs(best_score), 1.0)
        rel_band = 0.5 * span
        gap = abs(second_score - best_score)
        if gap <= rel_band:
            near_mask = np.abs(base - best_score) <= rel_band
            near_idx = np.nonzero(near_mask)[0]
            if near_idx.size > 1:
                cand_nodes = unvisited_nodes[near_idx]
                cand_demands = demands[cand_nodes]
                fits = cand_demands <= rest_capacity
                if not np.all(fits):
                    cand_idx = near_idx[fits]
                else:
                    cand_idx = near_idx
                if cand_idx.size >= 1:
                    sub_nodes = unvisited_nodes[cand_idx]
                    sub_demands = demands[sub_nodes]
                    sub_dist = distance_matrix[current_node][sub_nodes]
                    max_dem = float(np.max(sub_demands))
                    dem_mask = np.isclose(sub_demands, max_dem)
                    if np.sum(dem_mask) >= 1:
                        sub_nodes2 = sub_nodes[dem_mask]
                        if sub_nodes2.size == 1:
                            return int(sub_nodes2[0])
                        sub_dist2 = sub_dist[dem_mask]
                        min_dist = float(np.min(sub_dist2))
                        dist_mask = np.isclose(sub_dist2, min_dist)
                        if np.sum(dist_mask) >= 1:
                            sub_nodes3 = sub_nodes2[dist_mask]
                            if sub_nodes3.size == 1:
                                return int(sub_nodes3[0])
                            sub_base = base[cand_idx[dem_mask][dist_mask]]
                            return int(sub_nodes3[int(np.argmin(sub_base))])

    return int(unvisited_nodes[best_pos])