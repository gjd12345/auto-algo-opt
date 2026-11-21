def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Capacity pressure in [0, 1]: how full the vehicle is relative to its capacity.
    total_demand = float(np.sum(demands[unvisited_nodes])) + float(rest_capacity)
    if total_demand > 0:
        pressure = 1.0 - float(rest_capacity) / total_demand
    else:
        pressure = 0.0

    # Distance-balance term: prefer nodes that are close to current AND
    # not too far from depot (so route stays compact and return is cheap).
    # This is a harmonic-style combination (scale-invariant by construction
    # since it uses a ratio of distances).
    eps = 1e-9
    balance = d_cur / (d_cur + d_dep + eps)

    # Regret proxy: use the spread of the node's distance to depot vs current
    # as a measure of how "committal" visiting it now is.
    # Larger spread => visiting now vs later differs more => higher priority.
    spread = np.abs(d_cur - d_dep)
    # Normalize spread by the local distance scale so it is dimensionless.
    local_scale = d_cur + d_dep + eps
    regret = spread / local_scale

    # Depot pull grows with capacity pressure: when nearly full we weight
    # proximity to the depot more heavily so the route closes cheaply.
    depot_pull = d_dep / (d_dep + d_cur + eps)

    # Final composite score: prioritize high regret, then balance, and
    # modulate by capacity-dependent depot pull.  All terms dimensionless.
    score = regret + 0.5 * balance + pressure * depot_pull

    # Cheap second ordering stage: break near-ties by raw closeness to current.
    max_score = float(np.max(score))
    span = float(np.max(score) - np.min(score)) if score.size > 1 else 0.0
    tol = 0.05 * (span + eps)
    near_mask = score >= (max_score - tol)
    candidates = unvisited_nodes[near_mask]
    if candidates.size == 0:
        candidates = unvisited_nodes

    best_idx = int(np.argmin(distance_matrix[current_node][candidates]))
    return int(candidates[best_idx])