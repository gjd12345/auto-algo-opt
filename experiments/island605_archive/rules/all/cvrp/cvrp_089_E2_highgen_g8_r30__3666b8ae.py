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
    if current_node == depot:
        # Starting a new route: seed with farthest customer to push routes outward
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[farthest_idx]

    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    n = len(unvisited_nodes)
    # Compute savings: (distance from depot to candidate + distance from candidate back to depot)
    # minus (distance from current to candidate + distance from candidate back to depot)
    # = distance(depot, candidate) - distance(current, candidate)
    # We use a simplified savings = distance(depot, candidate) - distance(current, candidate)
    # Larger savings means it's much better to visit now than from depot later
    savings = distance_matrix[depot][unvisited_nodes] - distance_matrix[current_node][unvisited_nodes]

    # Also consider capacity pressure: prefer customers with higher demand when rest_capacity is tight
    demand_factor = demands[unvisited_nodes] / rest_capacity if rest_capacity > 0 else 0
    # Combine: prefer high savings, and slightly prefer high demand when capacity is limited
    score = savings + 0.1 * demand_factor

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
