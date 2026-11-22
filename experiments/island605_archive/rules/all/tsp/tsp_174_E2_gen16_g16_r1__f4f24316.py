def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 1:
        return unvisited_nodes[0]

    best_node = None
    best_score = float('inf')

    for candidate in unvisited_nodes:
        direct_dist = distance_matrix[current_node][candidate]
        if direct_dist == 0:
            direct_dist = 1e-10

        # Compute average distance from candidate to all other unvisited nodes
        other_dists = []
        for other in unvisited_nodes:
            if other != candidate:
                dist = distance_matrix[candidate][other]
                if dist == 0:
                    dist = 1e-10
                other_dists.append(dist)

        if len(other_dists) == 0:
            avg_other_dist = 1.0
        else:
            avg_other_dist = sum(other_dists) / len(other_dists)

        # Score: direct distance divided by average other distance (lower is better)
        score = direct_dist / avg_other_dist

        if score < best_score:
            best_score = score
            best_node = candidate

    return best_node if best_node is not None else unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
