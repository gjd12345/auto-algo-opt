def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        far_idx = unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
        return far_idx

    alpha = 0.5
    dists = distance_matrix[current_node][unvisited_nodes]
    savings = (distance_matrix[depot][current_node] +
               distance_matrix[depot][unvisited_nodes] -
               distance_matrix[current_node][unvisited_nodes])
    # Normalize both measures to avoid scale dominance
    max_dist = np.max(dists)
    min_dist = np.min(dists)
    max_sav = np.max(savings)
    min_sav = np.min(savings)
    norm_dist = (dists - min_dist) / (max_dist - min_dist + 1e-10)
    norm_sav = (savings - min_sav) / (max_sav - min_sav + 1e-10)
    scores = alpha * norm_dist - (1 - alpha) * norm_sav
    best_idx = unvisited_nodes[np.argmin(scores)]
    return best_idx
