def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return 0
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    base = d_cur - 0.6 * d_dep
    order = np.argsort(base)
    sorted_base = base[order]
    span = float(sorted_base[-1] - sorted_base[0]) if sorted_base.size > 1 else 0.0
    band = 1e-3 * span
    best = sorted_base[0]
    # near-tie candidates
    tie_mask = sorted_base <= best + band
    tie_idx = order[tie_mask]
    if tie_idx.size > 1:
        cand_nodes = unvisited_nodes[tie_idx]
        cand_demands = demands[cand_nodes]
        # capacity-fit refinement: prefer higher demand, tie-break by base score then distance
        cand_base = base[tie_idx]
        # sort by (-demand, base)
        ref_order = np.argsort(np.column_stack((-cand_demands, cand_base)), axis=0)
        # np.column_stack + argsort along axis 0 doesn't lexicographically sort rows directly;
        # do manual lexicographic via stable sorts
        idx = np.arange(tie_idx.size)
        # primary: base ascending (stable)
        idx = idx[np.argsort(cand_base, kind='stable')]
        # secondary: demand descending (stable)
        idx = idx[np.argsort(-cand_demands[idx], kind='stable')]
        chosen = cand_nodes[idx[0]]
        return int(chosen)
    return int(unvisited_nodes[order[0]])