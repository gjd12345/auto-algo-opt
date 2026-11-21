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
    if unvisited_nodes.size == 0:
        return depot

    demand = demands[unvisited_nodes].astype(float)
    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot = distance_matrix[depot][unvisited_nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    fill = np.clip(demand / cap, 0.0, 1.0)

    # New parameterization: emphasize proximity to current node strongly,
    # add moderate depot-closeness pull, and use a sharp fill bonus to
    # pack routes more tightly (larger weight on near-full fills).
    score = 0.75 * d_cur + 0.45 * d_depot - 0.9 * fill * fill * d_depot

    return int(unvisited_nodes[np.argmin(score)])