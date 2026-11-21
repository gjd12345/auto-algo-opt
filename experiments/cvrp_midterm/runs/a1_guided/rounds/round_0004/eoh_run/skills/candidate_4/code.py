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

    nodes = unvisited_nodes
    d_cur = distance_matrix[current_node][nodes]
    d_dep = distance_matrix[depot][nodes]
    dem = demands[nodes]

    # scale-free normalization of each signal across candidates
    cur_span = float(np.max(d_cur) - np.min(d_cur))
    dep_span = float(np.max(d_dep) - np.min(d_dep))
    cur_scale = cur_span if cur_span > 0.0 else 1.0
    dep_scale = dep_span if dep_span > 0.0 else 1.0

    n_cur = (d_cur - np.min(d_cur)) / cur_scale
    n_dep = (d_dep - np.min(d_dep)) / dep_scale

    # capacity utilization: how full the vehicle becomes after serving this node
    cap = rest_capacity if rest_capacity > 0.0 else 1.0
    used = np.clip(dem / cap, 0.0, 1.0)
    # prefer using more of the remaining capacity, but not overflowing
    fit = 1.0 - used

    # continuous multiplicative-ish combination, no tie band
    score = n_cur + 0.55 * n_dep + 0.9 * fit

    return int(nodes[int(np.argmin(score))])