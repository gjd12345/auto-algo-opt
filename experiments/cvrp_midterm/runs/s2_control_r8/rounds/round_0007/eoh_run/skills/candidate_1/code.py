def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0 else 1e-9

    # Savings vs returning to depot from current node, then going to the node.
    savings = d_cur + d_dep - distance_matrix[depot][current_node]
    savings = np.maximum(savings, 1e-9)

    # Detour ratio: cost of serving now relative to direct depot trip for this node.
    detour = (d_cur + d_dep) / (2.0 * d_dep + 1e-9)

    # Load pressure: how much of remaining capacity this node would consume.
    load_frac = dem / cap

    # Penalty for stranding: nodes skipped should still fit after taking this one.
    slack = cap - dem
    feasible_after = (dem[:, None] <= slack[:, None])
    # Count how many other unvisited nodes remain feasible if we pick each candidate.
    compat = feasible_after.sum(axis=1).astype(float)
    strand_penalty = 1.0 / (compat + 1e-9)

    # Regret-style score: prefer high savings, low detour, low load usage,
    # but avoid stranding many customers for later.
    score = (detour * (1.0 + load_frac)) / (savings / (d_dep + 1e-9) + 1e-9)
    score = score + 0.15 * strand_penalty - 0.05 * (savings / (d_cur + d_dep + 1e-9))

    return int(nodes[int(np.argmin(score))])