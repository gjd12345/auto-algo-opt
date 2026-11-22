import numpy as np

def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    alpha = 1.5  # weight for farthest component
    beta = 0.3   # weight for smoothness penalty

    best_score = -np.inf
    best_node = unvisited_nodes[0]
    current_dists = distance_matrix[current_node][unvisited_nodes]

    # Precompute two smallest distances from current to any node (excluding self)
    sorted_local = np.sort(distance_matrix[current_node])
    min_dist = sorted_local[1]  # smallest non-zero distance

    for i, cand in enumerate(unvisited_nodes):
        dest_dist = distance_matrix[destination_node][cand]
        edge_ratio = current_dists[i] / (min_dist + 1e-10)
        smooth_penalty = max(0, edge_ratio - 1.0)
        score = alpha * dest_dist - beta * smooth_penalty
        if score > best_score:
            best_score = score
            best_node = cand

    return best_node
