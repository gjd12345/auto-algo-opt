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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    dem = demands[unvisited_nodes].astype(np.float64)

    # Scale-equivariant reference length: mean depot distance of unvisited set.
    scale = float(np.mean(d_dep))
    if not np.isfinite(scale) or scale <= 0.0:
        scale = 1.0

    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0

    # Numerator: Clarke-Wright savings-like term -- how much closer to depot
    # the customer is relative to the detour it imposes from the current node.
    # Larger saving means inserting this customer is cheaper than returning.
    saving = (d_dep + float(distance_matrix[current_node][depot]) - d_cur) / scale

    # Denominator: proximity penalty -- how far the customer is from current
    # position, plus a mild capacity-utilization bonus folded in multiplicatively.
    proximity = d_cur / scale
    fill = np.clip(dem / cap, 0.0, 1.0)  # 1 = fills vehicle well
    # Shrink proximity when demand fills capacity -> favors full loads.
    prox_eff = proximity * (1.0 + 0.5 * (1.0 - fill))

    # Multiplicative score: maximize saving, minimize effective proximity.
    # A small epsilon prevents division blow-up on coincident points.
    score = prox_eff / (1e-9 + saving)

    return int(unvisited_nodes[int(np.argmin(score))])