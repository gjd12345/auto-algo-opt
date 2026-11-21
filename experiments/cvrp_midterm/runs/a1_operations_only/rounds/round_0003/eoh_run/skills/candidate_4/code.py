def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return int(depot)

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Capacity utilization: prefer nodes filling more of remaining capacity
    safe_rest = rest_capacity if rest_capacity > 0 else 1.0
    util = dem / safe_rest

    # Composite score: distance-from-current, distance-from-depot, capacity fill
    score = d_cur - 0.55 * d_dep - 0.35 * util * (d_cur + 1.0)

    # Rank candidates
    order = np.argsort(score)
    best_pos = int(order[0])
    best_val = float(score[best_pos])

    if order.size > 1:
        second_val = float(score[int(order[1])])
        # Scale-free ratio gate: fire when second-best is very close to best
        denom = abs(best_val) + 1e-9
        ratio = (second_val - best_val) / denom
        if ratio <= 1e-3:
            # Refine among near-ties: maximize demand fill first
            near_thresh = best_val + 1e-3 * denom
            near_mask = score <= near_thresh
            near_idx = np.nonzero(near_mask)[0]
            if near_idx.size > 1:
                sub_dem = dem[near_idx]
                sub_nodes = unvisited_nodes[near_idx]
                # Pick largest demand that fits (all fit by input contract)
                max_dem = float(np.max(sub_dem))
                dem_mask = np.abs(sub_dem - max_dem) <= 1e-9 * (max_dem + 1.0)
                cand_idx = near_idx[dem_mask]
                cand_nodes = sub_nodes[dem_mask]
                if cand_nodes.size == 1:
                    return int(cand_nodes[0])
                # Tie-break on smaller combined distance
                cand_score = score[cand_idx]
                return int(cand_nodes[int(np.argmin(cand_score))])

    return int(unvisited_nodes[best_pos])