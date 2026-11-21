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
    d_cur_depot = float(distance_matrix[current_node][depot])

    cap = float(rest_capacity)
    if cap <= 0.0:
        return int(depot)

    fill = demand / cap

    # Clarke-Wright style savings: inserting node between current node and
    # depot saves the direct return leg relative to the detour.
    savings = d_cur_depot + d_depot - d_cur

    # Prefer high savings and near-full utilization of remaining capacity.
    score = savings + fill * (d_cur_depot + 0.5 * d_depot)

    # If this single delivery would empty the vehicle exactly, favour it.
    exact = np.where(np.isclose(demand, cap), 1.0, 0.0)
    score = score + exact * (d_cur_depot + d_depot)

    return int(unvisited_nodes[np.argmax(score)])