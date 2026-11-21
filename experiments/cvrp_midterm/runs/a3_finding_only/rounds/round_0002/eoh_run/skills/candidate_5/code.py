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
    # Scale-normalising span: use the depot's reach as a proportional reference
    # so that all terms stay invariant to instance coordinate scale.
    depot_dists = distance_matrix[depot]

    # Proportional normaliser: max distance from depot among feasible customers.
    if unvisited_nodes.size > 0:
        span = float(np.max(depot_dists[unvisited_nodes]))
    else:
        span = 0.0
    if not np.isfinite(span) or span <= 0.0:
        span = 1.0

    # Travel distance from current node to each candidate (proportional term).
    d_cur = distance_matrix[current_node][unvisited_nodes] / span

    # Return-to-depot distance for each candidate (proportional term).
    d_dep = depot_dists[unvisited_nodes] / span

    # Load factor: prefer filling the vehicle with customers whose demand
    # leaves room for further stops (soft remaining-load pressure).
    cap = float(rest_capacity)
    if cap <= 0.0:
        cap = 1.0
    remaining_after = cap - demands[unvisited_nodes]
    load_frac = np.clip(remaining_after / cap, 0.0, 1.0)

    # Combined priority: minimise travel + a share of the depot pull,
    # minus a small reward for keeping capacity headroom (encourages
    # packing more stops per route without any absolute-scale constant).
    w_depot = 0.30
    w_load = 0.15
    scores = d_cur + w_depot * d_dep - w_load * load_frac

    return int(unvisited_nodes[int(np.argmin(scores))])