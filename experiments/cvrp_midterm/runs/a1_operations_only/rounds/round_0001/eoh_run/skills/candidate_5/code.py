def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    cur_dist = distance_matrix[current_node][unvisited_nodes]
    dep_dist = distance_matrix[depot][unvisited_nodes]
    base = cur_dist - 0.6 * dep_dist

    span = float(np.max(base) - np.min(base))
    band = 1e-3 * span

    best_val = float(np.min(base))
    if band > 0.0:
        mask = base <= best_val + band
    else:
        mask = base <= best_val

    candidates = unvisited_nodes[mask]
    if candidates.size == 1:
        return int(candidates[0])

    cand_demands = demands[candidates]
    slack = rest_capacity - cand_demands
    # Prefer filling the vehicle: smaller slack is better.
    order = np.argsort(slack)
    return int(candidates[order[0]])