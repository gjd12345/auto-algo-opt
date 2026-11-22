def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    if demands[unvisited_nodes].max() > rest_capacity:
        return depot

    dist_to_current = distance_matrix[current_node][unvisited_nodes]
    dist_to_depot = distance_matrix[depot][unvisited_nodes]

    # Savings: cost of going now vs going to depot then to customer
    savings = dist_to_depot - dist_to_current
    savings = (savings - np.min(savings)) / (np.max(savings) - np.min(savings) + 1e-10)

    # Straightness: angle proxy using distances from depot and current node
    # Prefer nodes that are "ahead" relative to depot position
    straightness = dist_to_depot / (dist_to_current + dist_to_depot + 1e-10)
    straightness = (straightness - np.min(straightness)) / (np.max(straightness) - np.min(straightness) + 1e-10)

    # Demand density: demand per unit distance from current (urgency)
    density = demands[unvisited_nodes] / (dist_to_current + 1e-10)
    density = (density - np.min(density)) / (np.max(density) - np.min(density) + 1e-10)

    # Adaptive weight: when capacity is low, favor density; when high, favor savings
    capacity_ratio = 1.0 - (rest_capacity / np.max(demands[unvisited_nodes] + 1e-10))
    capacity_ratio = np.clip(capacity_ratio, 0.0, 1.0)

    score = (1.0 - capacity_ratio) * (0.5 * savings + 0.3 * straightness) + capacity_ratio * (0.7 * density + 0.2 * savings)

    best_idx = np.argmax(score)
    return unvisited_nodes[best_idx]
