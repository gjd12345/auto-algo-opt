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
        # Seed route: pick farthest feasible customer from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        # Weighted score: nearest neighbor with depot-distance similarity penalty
        best_node = None
        best_score = float('inf')
        current_depot_dist = distance_matrix[depot][current_node]
        for u in unvisited_nodes:
            dist = distance_matrix[current_node][u]
            depot_dist_diff = abs(distance_matrix[depot][u] - current_depot_dist)
            score = dist + 0.3 * depot_dist_diff
            if score < best_score:
                best_score = score
                best_node = u
        return best_node
