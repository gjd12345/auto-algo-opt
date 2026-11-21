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
    d_depot = distance_matrix[depot][unvisited_nodes].astype(float)

    # Balance routes: prefer customers that fill the remaining capacity well,
    # but strongly penalize long detours from the current position.
    cap = float(rest_capacity)
    fill = demand / cap if cap > 0.0 else np.zeros_like(demand)

    # Score: minimize distance to customer, encourage substantial demand delivery,
    # and mildly prefer customers closer to the depot (good route closing).
    score = d_cur + 0.25 * d_depot - 0.5 * d_cur * fill

    return int(unvisited_nodes[np.argmin(score)])