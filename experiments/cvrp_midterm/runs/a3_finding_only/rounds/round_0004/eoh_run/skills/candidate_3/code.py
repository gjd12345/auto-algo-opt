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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cur_dep = distance_matrix[current_node][depot]
    dem = demands[unvisited_nodes]

    cap = max(rest_capacity, 1e-9)

    span = np.max(d_cur) if d_cur.size > 0 else 0.0
    if span <= 0:
        # all candidates coincident with current node: fall back to depot-proximity
        span = np.max(d_dep) if d_dep.size > 0 else 0.0
    if span <= 0:
        span = 1.0

    # Clarke-Wright style saving: how much cheaper it is to chain cur->n->depot
    # versus going cur->depot->n. Prefers nodes that are "on the way back".
    saving = d_cur_dep + d_dep - d_cur

    # Capacity pressure: fraction of remaining capacity this demand consumes,
    # in [0,1). Prefers larger demands late in the route to reduce leftover trips.
    util = dem / (cap + dem)

    # Scale-invariant normalization: divide length terms by span so the rule
    # is stable under uniform coordinate rescaling.
    score = d_cur / span - 0.6 * saving / span + 0.35 * util

    return int(unvisited_nodes[np.argmin(score)])