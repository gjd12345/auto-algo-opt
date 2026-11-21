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

    # Clarke-Wright savings: benefit of serving this customer on the current
    # route rather than via a separate depot round-trip.
    savings = d_cur + d_dep - distance_matrix[current_node][unvisited_nodes] * 0.0
    # true savings = d(cur,depot) + d(cust,depot) - d(cur,cust)
    savings = distance_matrix[current_node][depot] + d_dep - d_cur

    # Normalise savings to [0,1] using its own span (scale-free).
    s_min = float(np.min(savings))
    s_max = float(np.max(savings))
    span = s_max - s_min
    if span > 1e-12:
        savings_n = (savings - s_min) / span
    else:
        savings_n = np.ones_like(savings)

    # Capacity-fill ratio: fraction of residual capacity the customer uses.
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-12
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Geometric-mean-style blend: balanced emphasis on savings and packing.
    score = np.sqrt((0.5 + savings_n) * (0.5 + fill))

    # Deterministic tie-breaking: stronger savings first, then closer node.
    score = score + 1e-9 * savings_n - 1e-12 * d_cur

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])