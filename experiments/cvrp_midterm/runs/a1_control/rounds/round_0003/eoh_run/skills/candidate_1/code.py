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

    cur_d = distance_matrix[current_node][unvisited_nodes]
    depot_d = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Clarke-Wright style saving for inserting node before returning to depot.
    saving = distance_matrix[current_node][depot] + depot_d - cur_d

    # Stronger emphasis on savings, moderate depot-distance term, mild load penalty.
    demand_factor = 1.0 + dem / (rest_capacity + 1.0)
    score = cur_d - 0.85 * saving + 0.15 * depot_d / demand_factor + 0.1 * dem

    idx = int(np.argmin(score))
    node = int(unvisited_nodes[idx])
    return node