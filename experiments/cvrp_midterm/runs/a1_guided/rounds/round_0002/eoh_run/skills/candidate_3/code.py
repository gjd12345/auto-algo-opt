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
    dem = demands[unvisited_nodes]

    total_dem = float(np.sum(demands)) if demands.size > 0 else 1.0
    cap_frac = rest_capacity / max(total_dem, 1e-12)

    # Adaptive depot weight: when capacity is tight, stay near the depot;
    # when capacity is plentiful, explore further (mirrors the 0.6 anchor).
    w = 0.6 + 0.4 * (1.0 - min(max(cap_frac, 0.0), 1.0))

    # Look-ahead: projected detour cost if we serve this node then must
    # eventually return to depot; folded into one continuous score.
    slack = rest_capacity - dem
    slack_frac = slack / max(rest_capacity, 1e-12)
    # Penalty grows as slack shrinks (near-full load = risky to detour).
    fit_pen = 1.0 / (1.0 + slack_frac)

    score = d_cur - w * d_dep + 0.25 * fit_pen * d_dep

    return int(unvisited_nodes[np.argmin(score)])