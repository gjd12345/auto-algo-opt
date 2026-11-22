def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    current_dists = distance_matrix[current_node][unvisited_nodes]
    depot_dists = distance_matrix[depot][unvisited_nodes]
    node_demands = demands[unvisited_nodes]

    # Avoid division by zero
    current_dists_safe = np.where(current_dists == 0, 1e-10, current_dists)

    # Quadratic ratio: (depot_dist / current_dist)^2
    ratio = (depot_dists / current_dists_safe) ** 2

    # Linear capacity pressure: encourage using capacity when rest_capacity is low
    capacity_pressure = 1.0 + (rest_capacity - node_demands) / (rest_capacity + 1e-10)

    # Reward = ratio * capacity_pressure
    reward = ratio * capacity_pressure

    best_idx = np.argmax(reward)
    return unvisited_nodes[best_idx]
