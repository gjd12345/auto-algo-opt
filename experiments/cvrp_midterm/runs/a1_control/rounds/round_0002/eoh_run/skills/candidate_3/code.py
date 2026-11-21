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

    # Detour cost of inserting this customer now, relative to a straight
    # current -> depot -> customer path (i.e. extra distance paid to serve it).
    detour = cur_d + depot_d - distance_matrix[current_node][depot]
    detour = np.maximum(detour, 1e-9)

    # Fill efficiency: fraction of remaining capacity this customer consumes,
    # boosted when it nearly exhausts capacity (better packing, fewer routes).
    fill = dem / (rest_capacity + 1e-9)
    after = np.maximum(rest_capacity - dem, 0.0)
    near_full_bonus = 1.0 / (1.0 + after / (rest_capacity + 1e-9))

    # Depot pull: penalize customers far from depot to keep routes compact.
    depot_pull = depot_d / (distance_matrix[current_node][depot] + 1e-9)

    # Value per unit detour: maximize (demand packed + packing bonus) / detour,
    # tempered by a depot-compactness factor.
    value = (fill + 0.5 * near_full_bonus) / (detour / (cur_d + 1e-9))
    score = value / (1.0 + 0.3 * depot_pull)

    idx = int(np.argmax(score))
    node = int(unvisited_nodes[idx])
    return node