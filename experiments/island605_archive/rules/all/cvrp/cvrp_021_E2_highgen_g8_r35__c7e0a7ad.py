def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        far_idx = unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
        if demands[far_idx] <= rest_capacity:
            return far_idx
    candidates = unvisited_nodes
    dist_current = distance_matrix[current_node][candidates]
    dist_depot = distance_matrix[depot][candidates]
    savings = dist_depot - dist_current
    demands_cand = demands[candidates]
    min_dist = np.min(dist_current)
    mask = dist_current <= min_dist * 1.1
    if np.any(mask):
        best_idx = candidates[mask][np.argmax(savings[mask])]
    else:
        best_idx = candidates[np.argmax(savings)]
    if distance_matrix[current_node][best_idx] >= distance_matrix[current_node][depot]:
        return depot
    return best_idx
