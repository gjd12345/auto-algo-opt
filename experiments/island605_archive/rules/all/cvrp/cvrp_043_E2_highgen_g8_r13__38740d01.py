def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # Predefined parameters (tunable)
    alpha = 0.3  # weight for depot-distance term; 1-alpha for angular similarity
    # Note: Real coordinates are unavailable, so we use distance_matrix as a proxy for "angle"
    # by computing relative distances from depot as a simple geometric surrogate.
    # (In practice, replace with actual polar angles if coordinates are known.)
    if current_node == depot:
        # Far-first seeding: pick farthest unvisited customer from depot
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        # Compute scores combining depot-distance (normalized) and angular proxy
        depot_dists = distance_matrix[depot][unvisited_nodes]
        # Angular proxy: use distance from current_node to each unvisited node (normalized)
        curr_dists = distance_matrix[current_node][unvisited_nodes]
        # Normalize to [0,1] to avoid scale bias
        norm_depot = depot_dists / (np.max(depot_dists) + 1e-8)
        norm_curr = curr_dists / (np.max(curr_dists) + 1e-8)
        # Score: high score = desirable (small angular proxy and large depot distance)
        scores = (1 - alpha) * (1 - norm_curr) + alpha * norm_depot
        # Fallback: if all scores equal (e.g., only one node), pick nearest
        best_idx = np.argmax(scores)
        return unvisited_nodes[best_idx]
