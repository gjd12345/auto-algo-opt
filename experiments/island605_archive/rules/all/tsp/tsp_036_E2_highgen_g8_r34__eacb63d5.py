import numpy as np

def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    cur_dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    alpha = 1.2  # weight for penalizing large current distance
    beta = 0.8   # weight for rewarding proximity to destination

    # Regret-based score: penalize if current distance is large relative to destination distance
    scores = alpha * cur_dists - beta * dest_dists

    return unvisited_nodes[np.argmin(scores)]
