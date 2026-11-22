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
    if len(unvisited_nodes) == 0:
        return depot

    # If at depot, start route with farthest customer
    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        farthest_idx = np.argmax(dists_from_depot)
        return unvisited_nodes[farthest_idx]

    # Away from depot: check if returning to depot is beneficial
    # If the nearest feasible customer is farther than the depot, return to depot
    nearest_dist = np.min(distance_matrix[current_node][unvisited_nodes])
    if nearest_dist > distance_matrix[current_node][depot]:
        return depot

    # Otherwise, combine angular similarity (weight 0.3) and distance proximity (weight 0.7)
    import math
    current_angle = math.atan2(
        distance_matrix[depot][current_node],
        1.0
    )
    best_score = -1e9
    best_node = unvisited_nodes[0]
    max_dist = np.max(distance_matrix[current_node][unvisited_nodes])
    for u in unvisited_nodes:
        u_angle = math.atan2(
            distance_matrix[depot][u],
            1.0
        )
        angle_diff = abs(u_angle - current_angle)
        norm_angle = 1.0 - (angle_diff / math.pi)
        dist = distance_matrix[current_node][u]
        norm_dist = 1.0 - (dist / max_dist) if max_dist > 0 else 0.0
        score = 0.3 * norm_angle + 0.7 * norm_dist
        if score > best_score:
            best_score = score
            best_node = u
    return best_node
