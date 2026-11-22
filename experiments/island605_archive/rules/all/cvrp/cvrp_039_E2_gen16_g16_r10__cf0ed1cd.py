import numpy as np

def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        dists = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists)]

    remaining_demands = demands[unvisited_nodes]
    slack_ratio = (rest_capacity - remaining_demands) / (rest_capacity + 1e-8)
    slack_penalty = np.where(slack_ratio < 0.3, 1.0 - 0.5 * slack_ratio, 1.0)

    insertion_cost = distance_matrix[current_node][unvisited_nodes]
    regret = distance_matrix[current_node][depot] + distance_matrix[depot][unvisited_nodes] - insertion_cost
    combined = insertion_cost * slack_penalty - 0.6 * regret

    best_idx = np.argmin(combined)
    return unvisited_nodes[best_idx]
