def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    dist_current = distance_matrix[current_node][unvisited_nodes]
    dist_depot = distance_matrix[depot][unvisited_nodes]
    savings = dist_depot - dist_current

    max_savings = np.max(savings) if len(savings) > 0 else 1.0
    max_savings = max(max_savings, 1e-8)
    norm_savings = savings / max_savings

    max_dist = np.max(dist_current) + 1e-8
    norm_dist = dist_current / max_dist

    if rest_capacity < 0.2 * np.max(demands[unvisited_nodes]) or len(unvisited_nodes) == 1:
        return unvisited_nodes[np.argmin(dist_current)]

    savings_weight = 0.7 if rest_capacity > 0.6 * np.max(demands) else 0.3
    scores = savings_weight * norm_savings + (1 - savings_weight) * (1 - norm_dist)

    return unvisited_nodes[np.argmax(scores)]
