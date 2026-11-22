def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('inf')
    max_dist = np.max(distance_matrix) + 1e-9
    for u in unvisited_nodes:
        d_current = distance_matrix[current_node][u]
        d_dest = distance_matrix[destination_node][u]
        # Weighted score: balance farthest-first and smoothness with different weights
        score = 0.6 * d_current + 0.4 * (max_dist - d_dest)
        if score < best_score:
            best_score = score
            best_node = u
    return best_node
