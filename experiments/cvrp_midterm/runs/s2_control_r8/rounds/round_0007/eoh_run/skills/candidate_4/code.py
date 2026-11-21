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

    eps = 1e-9

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    d_0cur = float(distance_matrix[depot][current_node])

    demand = demands[unvisited_nodes].astype(np.float64)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Clarke-Wright style savings normalized by a smooth leg scale
    savings = d_0cur + d_dep - d_cur
    leg_scale = d_0cur + d_cur + eps
    sav_norm = savings / leg_scale

    # Fill pressure: fraction of current capacity consumed by this node
    fill = np.clip(demand / cap, 0.0, 1.0)

    # Radial term: far-from-depot nodes consume more (far-first tendency)
    dmax = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    if dmax <= 0:
        dmax = 1.0
    radial = d_dep / dmax

    # Adaptive weighting based on how full the vehicle is.
    # Early in a route (low used_capacity) emphasize savings and far-first;
    # late in a route (high used_capacity) emphasize packing fill.
    used = 1.0 - fill  # unused fraction of capacity is high earlier
    w_fill = 0.55 * (1.0 - used) + 0.15
    w_rad = 0.25 * used + 0.05
    w_sav = 1.0

    score = w_sav * sav_norm + w_fill * fill + w_rad * radial

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])