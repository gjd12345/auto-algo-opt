def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # Seed from depot: prefer moderately distant customers (not farthest)
    if current_node == depot:
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        # Use median distance as threshold to avoid extremes
        median_dist = np.median(dist_from_depot)
        # Select the feasible customer closest to the median distance
        best_idx = np.argmin(np.abs(dist_from_depot - median_dist))
        return unvisited_nodes[best_idx]

    # En route: combine nearest neighbor with angular consistency
    candidates = unvisited_nodes
    dists = distance_matrix[current_node][candidates]
    # Compute angular similarity (cosine of angle between vector from depot to current and to candidate)
    vec_current = np.array([distance_matrix[depot][current_node], 0])  # simplified proxy
    # Use dot product with depot-to-candidate vector as a proxy for angular alignment
    angles = distance_matrix[depot][candidates]  # proxy: larger means further from depot, more aligned if current also far
    # Normalize distances and angles
    max_dist = np.max(dists) if np.max(dists) > 0 else 1
    max_angle = np.max(angles) if np.max(angles) > 0 else 1
    # Score: 0.7 * normalized distance + 0.3 * (1 - normalized angle) to favor nearby and similar direction
    scores = 0.7 * (dists / max_dist) + 0.3 * (1 - angles / max_angle)
    best_idx = np.argmin(scores)
    best_customer = candidates[best_idx]
    best_dist = dists[best_idx]

    # Return to depot only if nearest feasible customer is farther than 1.5 * average route distance to depot
    depot_dist = distance_matrix[current_node][depot]
    avg_customer_dist = np.mean(distance_matrix[current_node][unvisited_nodes]) if len(unvisited_nodes) > 0 else 0
    if depot_dist < best_dist * 0.6 and depot_dist < avg_customer_dist * 0.8:
        return depot

    return best_customer
