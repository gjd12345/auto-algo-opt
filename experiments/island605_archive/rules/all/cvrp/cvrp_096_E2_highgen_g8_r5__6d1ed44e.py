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
        # Seed route: prefer farthest customers from depot to reach distant clusters
        depot_dists = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(depot_dists)]
    else:
        # Check threshold: if remaining capacity < 30% of max demand, return to depot early
        max_demand = demands[unvisited_nodes].max() if len(unvisited_nodes) > 0 else 0
        if rest_capacity < 0.3 * max_demand and len(unvisited_nodes) > 0:
            # Return to depot
            return depot
        # Otherwise: weighted combination: 0.4 * depot distance - 0.6 * current distance
        depot_dists = distance_matrix[depot][unvisited_nodes]
        current_dists = distance_matrix[current_node][unvisited_nodes]
        scores = 0.4 * depot_dists - 0.6 * current_dists
        return unvisited_nodes[np.argmax(scores)]
