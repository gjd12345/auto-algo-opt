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
        return 0

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    dem = demands[nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    fill = dem / cap  # fraction of remaining capacity this customer consumes

    # Multiplicative score: prefer near nodes, far-from-depot nodes (to postpone
    # return trips for distant customers), and high fill when capacity is tight.
    # d_cur is the dominant factor; d_dep bonus rewards covering far customers
    # early; fill penalty avoids leaving wasteful slack when capacity is small.
    eps = 1e-9
    score = d_cur * (1.0 + 0.30 * fill) / (d_dep + 1.0 + eps)
    # Add a small absolute term rewarding high fill (batching) at low capacity.
    score = score - 0.05 * fill * (1.0 / (cap + 1.0))

    return int(nodes[int(np.argmin(score))])