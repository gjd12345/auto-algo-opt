def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return int(depot)

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
        rel_band = 1e-3 * span
        gap = abs(second_score - best_score)
        ratio_gate = False
        denom = max(abs(best_score), 1e-9)
        if abs(second_score) / denom <= 1.5:
            ratio_gate = True
        if gap <= rel_band or ratio_gate:
            near_mask = np.abs(base - best_score) <= max(rel_band, 1e-6 * span)
            near_idx = np.nonzero(near_mask)[0]
            if near_idx.size > 1:
                sub_nodes = unvisited_nodes[near_idx]
                sub_demands = demands[sub_nodes]
                fits = sub_demands <= rest_capacity
                if not np.all(fits):
                    near_idx = near_idx[fits]
                    sub_nodes = sub_nodes[fits]
                    sub_demands = sub_demands[fits]
                if sub_nodes.size >= 1:
                    max_dem = float(np.max(sub_demands))
                    dem_mask = np.isclose(sub_demands, max_dem)
                    cand_idx = near_idx[dem_mask]
                    cand_nodes = sub_nodes[dem_mask]
                    if cand_nodes.size == 1:
                        return int(cand_nodes[0])
                    cand_base = base[cand_idx]
                    min_base = float(np.min(cand_base))
                    base_mask = np.isclose(cand_base, min_base)
                    cand_idx2 = cand_idx[base_mask]
                    cand_nodes2 = cand_nodes[base_mask]
                    if cand_nodes2.size == 1:
                        return int(cand_nodes2[0])
                    cand_dist = distance_matrix[current_node][cand_nodes2]
                    min_dist = float(np.min(cand_dist))
                    dist_mask = np.isclose(cand_dist, min_dist)
                    cand_nodes3 = cand_nodes2[dist_mask]
                    if cand_nodes3.size == 1:
                        return int(cand_nodes3[0])
                    sub_base = base[cand_idx2[dist_mask]]
                    return int(cand_nodes3[int(np.argmin(sub_base))])

    return int(unvisited_nodes[best_pos])