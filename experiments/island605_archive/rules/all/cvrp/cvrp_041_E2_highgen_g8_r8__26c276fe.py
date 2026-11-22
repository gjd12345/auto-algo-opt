def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    import numpy as np

    if len(unvisited_nodes) == 0:
        return depot

    if current_node == depot:
        # Seed with farthest customer to reach distant clusters
        return unvisited_nodes[np.argmax(distance_matrix[depot, unvisited_nodes])]

    alpha = 0.3  # weight for farthest-from-depot component
    beta = 0.7   # weight for nearest-to-current component

    # Normalize distances for stable scoring
    dist_from_depot = distance_matrix[depot, unvisited_nodes]
    dist_from_current = distance_matrix[current_node, unvisited_nodes]

    max_depot = np.max(dist_from_depot) if np.max(dist_from_depot) > 0 else 1
    max_current = np.max(dist_from_current) if np.max(dist_from_current) > 0 else 1

    depot_score = dist_from_depot / max_depot
    current_score = 1.0 - (dist_from_current / max_current)  # invert so nearer is higher

    combined = alpha * depot_score + beta * current_score
    best_idx = unvisited_nodes[np.argmax(combined)]
    return best_idx
