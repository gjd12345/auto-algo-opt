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
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    else:
        # Compute angular similarity from depot if we have at least one visited non-depot node
        # Use simple approximation: prefer nodes with similar polar angle
        # For simplicity, we just use nearest with a penalty for angular deviation
        # Fallback to pure nearest if no previous angle info
        distances = distance_matrix[current_node][unvisited_nodes]
        # Compute angle from depot for current_node (if not depot) and candidates
        import math
        cx, cy = 0.0, 0.0  # placeholder; actual coordinates are not available, so skip angle
        # Use pure nearest neighbor, but with early return threshold 1.5x depot distance
        nearest_dist = np.min(distances)
        nearest_idx = np.argmin(distances)
        nearest_node = unvisited_nodes[nearest_idx]
        dist_to_depot = distance_matrix[current_node][depot]
        if dist_to_depot * 1.5 < nearest_dist:
            return depot
        # Also if rest_capacity is very low, try to stay close to depot
        if rest_capacity < 10 and nearest_dist > dist_to_depot:
            return depot
        return nearest_node
