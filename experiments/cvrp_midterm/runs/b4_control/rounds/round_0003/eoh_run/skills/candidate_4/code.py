def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    # Marginal detour relative to returning to depot (regret-style)
    detour = d_cur + d_dep - distance_matrix[current_node][depot]

    # Load imbalance after service: prefer leaving either nearly full or
    # nearly empty to avoid awkward residual capacity.
    load_after = (cap - dem) / cap
    imbalance = np.abs(load_after - 0.5) + np.abs(load_after - 0.5) ** 2

    # Urgency: large demands should be served while capacity allows.
    urgency = dem / cap

    # Stranding penalty: how many other feasible customers become
    # infeasible if we take this one (approximate via demand counts).
    total_dem = dem.sum()
    remaining_after = cap - dem
    stranded = np.zeros(unvisited_nodes.size)
    for i in range(unvisited_nodes.size):
        rem = remaining_after[i]
        if rem <= 0:
            stranded[i] = 0.0
        else:
            others = dem.copy()
            others[i] = np.inf
            stranded[i] = np.sum(others <= rem) / max(1.0, unvisited_nodes.size - 1)

    # Combine: minimize detour, prefer decent depot proximity, penalize
    # stranding and imbalance, reward urgency mildly.
    score = (
        detour
        - 0.25 * d_dep
        + 0.30 * imbalance * detour
        - 0.40 * urgency * d_cur
        + 0.50 * stranded * detour
    )
    return int(unvisited_nodes[np.argmin(score)])