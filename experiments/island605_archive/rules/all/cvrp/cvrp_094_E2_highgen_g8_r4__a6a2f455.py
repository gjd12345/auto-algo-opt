import numpy as np

def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    max_depot_dist = np.max(distance_matrix[depot][unvisited_nodes])
    dist_to_depot = distance_matrix[depot][current_node]

    if current_node == depot or dist_to_depot < 0.3 * max_depot_dist:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        farthest_idx = np.argmax(dists_from_depot)
        return unvisited_nodes[farthest_idx]
    else:
        dist_from_current = distance_matrix[current_node][unvisited_nodes]
        dist_from_depot = distance_matrix[depot][unvisited_nodes]
        score = 0.6 * dist_from_current - 0.4 * dist_from_depot
        best_idx = np.argmin(score)
        return unvisited_nodes[best_idx]
