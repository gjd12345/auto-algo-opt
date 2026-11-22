def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('inf')

    for candidate in unvisited_nodes:
        direct_dist = distance_matrix[current_node][candidate]
        dest_dist = distance_matrix[candidate][destination_node]

        # Average distance from candidate to all other unvisited nodes
        other_dists = [distance_matrix[candidate][other] for other in unvisited_nodes if other != candidate]
        avg_other_dist = np.mean(other_dists) if other_dists else 0.0

        # Penalize if direct distance is larger than candidate's average connections
        penalty = 1.0
        if direct_dist > avg_other_dist:
            penalty = 1.0 + (direct_dist - avg_other_dist) / (avg_other_dist + 1e-6)

        # Score: weighted combination of direct distance and destination proximity
        score = direct_dist * penalty - 0.5 * dest_dist

        if score < best_score:
            best_score = score
            best_node = candidate

    return best_node
