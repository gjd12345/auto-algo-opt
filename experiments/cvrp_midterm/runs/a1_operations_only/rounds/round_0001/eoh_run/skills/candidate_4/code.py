def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    nodes = np.asarray(unvisited_nodes, dtype=np.int64)
    if nodes.size == 0:
        return int(depot)

    d_cur = distance_matrix[current_node][nodes].astype(np.float64)
    d_dep = distance_matrix[depot][nodes].astype(np.float64)
    base = d_cur - 0.6 * d_dep

    order = np.argsort(base)
    best_idx = int(order[0])

    span = float(base.max() - base.min())
    if span <= 0.0:
        span = 1.0
    band = 1e-3 * span
    best_score = float(base[best_idx])

    tie_mask = base <= best_score + band
    if int(tie_mask.sum()) > 1:
        cand = nodes[tie_mask]
        cand_base = base[tie_mask]
        cand_dem = demands[cand].astype(np.float64)
        # Prefer demand that fits remaining capacity closely (higher is better fit,
        # but do not exceed capacity). Small penalty keeps base ordering as tiebreak.
        denom = max(rest_capacity, 1e-9)
        fit = cand_dem / denom
        # Slight preference for larger fill, and among those, lower base score.
        refined = fit - 1e-6 * cand_base
        pick = int(np.argmax(refined))
        return int(cand[pick])

    return int(nodes[best_idx])