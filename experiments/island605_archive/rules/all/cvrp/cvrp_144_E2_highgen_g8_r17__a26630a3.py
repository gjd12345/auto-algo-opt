def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    # Parameter: threshold for switching from far-first to savings-based selection
    FAR_THRESHOLD = 0.15  # fraction of max distance from depot to consider "near depot"
    SAVINGS_WEIGHT = 0.7  # weight for savings criterion vs nearest distance

    # If starting a new route or very close to depot, seed toward distant clusters
    depot_dist = distance_matrix[current_node][depot]
    if current_node == depot or depot_dist < FAR_THRESHOLD * distance_matrix.max():
        depot_dists = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(depot_dists)]
    else:
        # Compute savings: saving = distance(depot, u) + distance(depot, v) - distance(u, v)
        # where u = current_node, v = candidate
        candidate_dists = distance_matrix[current_node][unvisited_nodes]
        depot_to_candidate = distance_matrix[depot][unvisited_nodes]
        depot_to_current = distance_matrix[depot][current_node]
        savings = depot_to_current + depot_to_candidate - candidate_dists
        # Normalize savings and distances to combine them
        max_savings = savings.max()
        max_dist = candidate_dists.max()
        if max_savings > 0 and max_dist > 0:
            scores = SAVINGS_WEIGHT * (savings / max_savings) - (1 - SAVINGS_WEIGHT) * (candidate_dists / max_dist)
        else:
            scores = -candidate_dists  # fallback to nearest
        return unvisited_nodes[np.argmax(scores)]
