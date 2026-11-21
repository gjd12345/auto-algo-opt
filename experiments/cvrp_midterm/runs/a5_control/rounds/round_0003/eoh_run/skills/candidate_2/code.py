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
    current_node = int(current_node)
    depot = int(depot)
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=int)
    demand = demands[unvisited_nodes].astype(float)

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot_to_cust = distance_matrix[depot][unvisited_nodes].astype(float)
    d_depot_to_cur = float(distance_matrix[depot][current_node])

    cap = float(rest_capacity)
    demand_share = demand / cap if cap > 0.0 else np.zeros_like(demand)

    # Detour cost of inserting this customer on the current leg versus
    # returning to the depot first: larger = worse insertion.
    detour = d_cur + d_depot_to_cust - d_depot_to_cur

    # Normalise by demand share: prefer customers that "pay for" their detour.
    # Small epsilon avoids division blow-ups for zero-demand nodes.
    detour_ratio = detour / (demand_share + 0.1)

    # Angular coherence: prefer customers aligned with the depot->current ray,
    # encouraging radial "spoke" routes rather than zig-zags.
    # Use cosine of the angle at the depot between (depot->current) and
    # (depot->customer), approximated via distances to avoid trig.
    a = d_depot_to_cur
    b = d_depot_to_cust
    c = d_cur
    # law of cosines; guard against degenerate zeros
    denom = 2.0 * np.maximum(a * b, 1e-9)
    cos_angle = (a * a + b * b - c * c) / denom
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    # reward alignment (cos_angle == 1 means same direction)
    alignment_reward = 0.5 * (1.0 - cos_angle)

    score = detour_ratio + 0.4 * alignment_reward * d_cur

    return int(unvisited_nodes[np.argmin(score)])