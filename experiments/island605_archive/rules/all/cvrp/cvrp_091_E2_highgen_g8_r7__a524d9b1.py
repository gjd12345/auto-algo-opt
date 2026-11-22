def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot
    if current_node == depot:
        # Seed route: farthest from depot, with tie-breaking by smallest angle from origin
        dists = distance_matrix[depot][unvisited_nodes]
        max_dist = np.max(dists)
        farthest = unvisited_nodes[dists == max_dist]
        if len(farthest) == 1:
            return farthest[0]
        # Compute polar angle for tie-breaking
        angles = np.arctan2(distance_matrix[farthest, 1], distance_matrix[farthest, 0])  # dummy coordinates
        return farthest[np.argmin(angles)]
    else:
        best_score = -1e9
        best_candidate = depot
        # Precompute previous direction from depot to current node (or last segment direction)
        prev_direction = np.array([distance_matrix[current_node, 1], distance_matrix[current_node, 0]])  # dummy
        for candidate in unvisited_nodes:
            # Savings: cost_depot - cost_current
            cost_current = distance_matrix[current_node][candidate] + distance_matrix[candidate][depot]
            cost_depot = distance_matrix[depot][candidate] + distance_matrix[candidate][depot]
            savings = cost_depot - cost_current
            # Direction penalty: angular deviation from previous segment (using dummy coordinates)
            cand_coord = np.array([distance_matrix[candidate, 1], distance_matrix[candidate, 0]])
            if np.linalg.norm(prev_direction) > 0:
                dot = np.dot(prev_direction, cand_coord)
                norm = np.linalg.norm(prev_direction) * np.linalg.norm(cand_coord)
                angle = np.arccos(np.clip(dot / norm, -1.0, 1.0))
            else:
                angle = 0.0
            penalty = angle / np.pi  # normalized to [0,1]
            # Composite score: high savings, low angular deviation
            score = savings - 2.0 * penalty * distance_matrix[current_node][candidate]
            if score > best_score:
                best_score = score
                best_candidate = candidate
        return best_candidate if best_candidate != depot else unvisited_nodes[0]
