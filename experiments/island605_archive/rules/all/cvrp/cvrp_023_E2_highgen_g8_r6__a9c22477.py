def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        if len(unvisited_nodes) == 0:
            return depot
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[farthest_idx]

    # Compute polar angles from depot for current node and each candidate
    EPS = 1e-10
    angle_current = np.arctan2(distance_matrix[current_node][1] - distance_matrix[depot][1],
                               distance_matrix[current_node][0] - distance_matrix[depot][0] + EPS)
    node_coords = np.array([[distance_matrix[u][0], distance_matrix[u][1]] for u in unvisited_nodes])
    depot_coords = np.array([distance_matrix[depot][0], distance_matrix[depot][1]])
    angles = np.arctan2(node_coords[:, 1] - depot_coords[1], node_coords[:, 0] - depot_coords[0] + EPS)
    angle_diff = np.abs(angles - angle_current)
    angle_diff = np.minimum(angle_diff, 2 * np.pi - angle_diff)

    # Capacity stress factor: higher when rest_capacity is low relative to average demand
    avg_demand = np.mean(demands[unvisited_nodes]) if len(unvisited_nodes) > 0 else 1
    capacity_stress = np.exp(-rest_capacity / (avg_demand + EPS))

    # For each candidate, compute:
    # 1. Distance from current node
    dist_current = distance_matrix[current_node][unvisited_nodes]
    # 2. Angular penalty (penalize large angle differences)
    angular_penalty = angle_diff / np.pi
    # 3. Depot regret: how much worse is visiting from depot later vs now
    depot_dist = distance_matrix[depot][unvisited_nodes]
    regret = depot_dist - dist_current
    regret = np.maximum(regret, 0)
    # 4. Demand penalty: discourage high-demand items when capacity is stressed
    demand_penalty = demands[unvisited_nodes] / (rest_capacity + EPS) * capacity_stress

    # Composite score: lower is better
    scores = (0.4 * dist_current + 0.2 * angular_penalty * np.mean(dist_current)
              - 0.3 * regret + 0.1 * demand_penalty * np.mean(dist_current))

    best_idx = np.argmin(scores)
    candidate = unvisited_nodes[best_idx]

    if rest_capacity < demands[candidate] + 1e-6:
        return depot

    return candidate
