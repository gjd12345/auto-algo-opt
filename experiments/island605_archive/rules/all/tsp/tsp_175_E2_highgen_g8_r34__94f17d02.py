import numpy as np

def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = float('inf')

    for node in unvisited_nodes:
        direct_dist = distance_matrix[current_node][node]

        # Compute average distance from candidate to all other unvisited nodes (excluding self)
        other_unvisited = unvisited_nodes[unvisited_nodes != node]
        if len(other_unvisited) > 0:
            avg_dist_to_others = np.mean(distance_matrix[node][other_unvisited])
        else:
            avg_dist_to_others = 0.0

        # Score: direct distance divided by average distance to others (avoid division by zero)
        if avg_dist_to_others > 0:
            score = direct_dist / avg_dist_to_others
        else:
            score = float('inf')

        if score < best_score:
            best_score = score
            best_node = node

    return best_node
