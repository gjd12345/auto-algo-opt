def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    eps = 1e-9

    # Primary: depot distance as a multiplicative weight on current-node proximity.
    # This is a product form (distinct from ratio d_dep/d_cur and additive d_dep-d_cur).
    score = d_dep * (1.0 / (d_cur + eps))

    s_max = float(np.max(score))
    # Scale-invariant (multiplicative) near-tie band: candidates within a relative
    # fraction of the best score. Independent of coordinate scale.
    band = score >= (s_max * 0.85)
    candidates = unvisited_nodes[band]
    if candidates.size == 0:
        candidates = unvisited_nodes

    cand_demands = demands[candidates]
    cand_dep = distance_matrix[depot][candidates]
    cand_cur = distance_matrix[current_node][candidates]

    # Secondary: capacity slack preserved per unit of depot distance, blended with
    # the routing savings gain so both capacity and distance inform the tie-break.
    slack = rest_capacity - cand_demands
    savings_gain = cand_dep - cand_cur
    secondary = (slack * (savings_gain + 1.0)) / (cand_dep + 1.0)

    best_idx = int(np.argmax(secondary))
    return int(candidates[best_idx])