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
        # Seed route with farthest customer
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
    else:
        # Regret-based score: distance from current minus average distance to all other unvisited
        current_dists = distance_matrix[current_node][unvisited_nodes]
        # Compute average distance from each candidate to all other unvisited nodes
        avg_other_dists = np.array([
            np.mean(distance_matrix[cand][np.setdiff1d(unvisited_nodes, [cand])])
            if len(unvisited_nodes) > 1 else 0
            for cand in unvisited_nodes
        ])
        # Score: prefer candidates close now (small current_dists)
        # and with high average distance to others (to avoid isolated nodes later)
        scores = avg_other_dists - current_dists
        return unvisited_nodes[np.argmax(scores)]
