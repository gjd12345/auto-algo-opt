import numpy as np

def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Savings: distance(current, depot) + distance(depot, customer) - distance(current, customer)
    dist_to_depot = distance_matrix[current_node][depot]
    savings = dist_to_depot + distance_matrix[depot][unvisited_nodes] - distance_matrix[current_node][unvisited_nodes]

    # Select customer with highest savings (largest reduction in total distance)
    best_idx = np.argmax(savings)
    return int(unvisited_nodes[best_idx])
