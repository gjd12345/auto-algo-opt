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
        # Seed route: farthest from depot
        if len(unvisited_nodes) == 0:
            return depot
        distances_from_depot = distance_matrix[depot, unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    else:
        # Compute polar angles from depot for all unvisited nodes
        depot_x, depot_y = 0.0, 0.0  # assuming depot is at origin
        # Use coordinates from distance matrix (assuming indices match)
        # Here we approximate angle using distance matrix entries
        # Actually compute angle from depot to each node using distance matrix (not possible directly)
        # Instead, use a geometric proxy: angle = arctan2(y, x) but we don't have coordinates.
        # So fallback to nearest neighbor within same angular zone defined by current node.
        # Use distance from current node to unvisited nodes, sorted by angle similarity.
        unvisited_list = unvisited_nodes.tolist()
        best_node = None
        best_score = float('inf')
        for u in unvisited_list:
            # Local distance
            local_dist = distance_matrix[current_node, u]
            # Angular deviation from depot direction of current node
            # Approximate by comparing distances to depot
            dist_to_depot_u = distance_matrix[depot, u]
            dist_to_depot_cur = distance_matrix[depot, current_node]
            angle_diff = abs(dist_to_depot_u - dist_to_depot_cur) / (dist_to_depot_cur + 1e-8)
            score = local_dist + 0.3 * angle_diff * dist_to_depot_cur
            if score < best_score:
                best_score = score
                best_node = u
        return best_node if best_node is not None else depot
