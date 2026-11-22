import numpy as np

def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    dist_depot = distance_matrix[depot][unvisited_nodes]
    dist_current = distance_matrix[current_node][unvisited_nodes]

    max_depot = dist_depot.max()
    min_depot = dist_depot.min()
    max_current = dist_current.max()
    min_current = dist_current.min()

    norm_depot = (dist_depot - min_depot) / (max_depot - min_depot + 1e-10)
    norm_current = (dist_current - min_current) / (max_current - min_current + 1e-10)

    total_nodes = len(demands) - 1
    visited_count = total_nodes - len(unvisited_nodes)
    progress = min(visited_count / 10.0, 1.0) if total_nodes > 0 else 0.0

    alpha = 0.8 * np.exp(-2.0 * progress) + 0.2
    score = alpha * norm_depot + (1 - alpha) * (1 - norm_current)

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
