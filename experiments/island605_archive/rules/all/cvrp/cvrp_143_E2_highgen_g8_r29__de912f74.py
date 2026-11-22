def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Start a new route: pick farthest feasible customer
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # When en route, compute angle from depot of current node and candidates
    def polar_angle(node):
        dx = distance_matrix[node][depot]  # approximate x-coordinate proxy
        dy = 0  # not used; we use simple angle via atan2 from distances
        # Use distance matrix to get coordinates? Since no coords given, approximate angle using distances.
        # Fallback: use distance from depot and distance to current_node as proxy for direction.
        return np.arctan2(distance_matrix[node][depot], distance_matrix[current_node][node])

    # Prefer customers with similar polar angle, then nearest
    angles = np.array([polar_angle(u) for u in unvisited_nodes])
    current_angle = polar_angle(current_node)
    angle_diff = np.abs(angles - current_angle)
    angle_diff = np.minimum(angle_diff, 2*np.pi - angle_diff)

    # Normalize angle diff and distance
    max_angle = np.max(angle_diff) + 1e-9
    norm_angle = angle_diff / max_angle

    dists = distance_matrix[current_node][unvisited_nodes]
    max_dist = np.max(dists) + 1e-9
    norm_dist = dists / max_dist

    # Score: weighted combination (0.7 angle similarity, 0.3 distance)
    scores = 0.7 * norm_angle + 0.3 * norm_dist
    best_idx = np.argmin(scores)
    chosen = unvisited_nodes[best_idx]

    # If the closest customer is still very far, consider returning to depot
    closest_dist = np.min(dists)
    if closest_dist > 2 * np.mean(distance_matrix[depot][unvisited_nodes]) and len(unvisited_nodes) > 1:
        # But still pick a customer if capacity allows; otherwise depot
        pass

    return chosen
