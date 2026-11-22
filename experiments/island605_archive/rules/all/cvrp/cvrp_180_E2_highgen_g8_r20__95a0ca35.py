def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Weight that shifts from exploration (high weight on depot distance) to exploitation (high weight on current distance)
    capacity_ratio = rest_capacity / np.max(demands[unvisited_nodes]) if np.max(demands[unvisited_nodes]) > 0 else 0
    alpha = min(1.0, capacity_ratio / 5.0)  # gradually reduce exploration as capacity depletes

    # Compute score: higher is better
    from_depot = distance_matrix[depot][unvisited_nodes]
    from_current = distance_matrix[current_node][unvisited_nodes]

    # Normalize to avoid scale dominance
    max_depot = np.max(from_depot) if np.max(from_depot) > 0 else 1
    max_current = np.max(from_current) if np.max(from_current) > 0 else 1

    scores = alpha * (from_depot / max_depot) - (1 - alpha) * (from_current / max_current)

    # Pick the customer with highest score (far from depot and close to current, weighted)
    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
