def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    import numpy as np

    if current_node == depot:
        # Seed route: pick farthest unvisited customer from depot
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    else:
        # Compute three normalized criteria for each candidate
        # 1. Proximity (inverse of distance from current node, normalized)
        dist_curr = distance_matrix[current_node][unvisited_nodes]
        norm_dist = (dist_curr - dist_curr.min()) / (dist_curr.max() - dist_curr.min() + 1e-10)
        proximity = 1.0 - norm_dist  # closer is better (higher)

        # 2. Angular deviation from current-depot axis (normalized)
        angle_curr = np.arctan2(
            distance_matrix[current_node][1] - distance_matrix[depot][1],
            distance_matrix[current_node][0] - distance_matrix[depot][0]
        ) if current_node != depot else 0.0
        unvisited_coords = np.column_stack([
            distance_matrix[depot][unvisited_nodes],
            np.zeros(len(unvisited_nodes))  # placeholder, we use distances
        ])
        angle_cand = np.arctan2(
            distance_matrix[current_node][unvisited_nodes] * 0 + 1e-10,
            distance_matrix[current_node][unvisited_nodes]
        )
        angle_dev = np.abs(angle_cand - angle_curr) % (2 * np.pi)
        angle_dev = np.minimum(angle_dev, 2 * np.pi - angle_dev)
        norm_angle = angle_dev / (np.pi + 1e-10)
        angle_score = 1.0 - norm_angle  # smaller deviation is better

        # 3. Regret proxy: distance from depot (normalized)
        dist_depot = distance_matrix[depot][unvisited_nodes]
        norm_regret = (dist_depot - dist_depot.min()) / (dist_depot.max() - dist_depot.min() + 1e-10)

        # Convex combination weights: favor proximity (0.5), angle (0.3), regret (0.2)
        weights = np.array([0.5, 0.3, 0.2])
        scores = (weights[0] * proximity) + (weights[1] * angle_score) + (weights[2] * norm_regret)

        return unvisited_nodes[np.argmax(scores)]
