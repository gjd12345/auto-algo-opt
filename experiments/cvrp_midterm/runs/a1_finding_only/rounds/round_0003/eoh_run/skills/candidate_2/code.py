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

    # Savings proxy: closing a triangle via this customer vs going to depot.
    savings = d_dep - d_cur  # larger -> more promising detour
    span = float(np.max(savings) - np.min(savings)) if savings.size > 1 else 0.0
    savings_n = (savings - np.min(savings)) / (span + 1e-12)

    # Capacity-fill ratio: prefer customers that use up residual capacity.
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-12
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Multiplicative blend: savings amplified by packing tightness.
    urgency = (0.5 + savings_n) * (0.5 + fill)

    # Tie-break by smaller current-distance, deterministic.
    urgency = urgency - 1e-9 * d_cur

    idx = int(np.argmax(urgency))
    return int(unvisited_nodes[idx])