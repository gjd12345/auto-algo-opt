def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Savings-based seeding: pick customer with largest savings (depot-customer-depot vs direct)
        # Savings = d(depot, u) + d(depot, v) - d(u, v) but here we start route, so pick farthest
        # To be different from far-first, we pick the one with minimal depot distance * demand ratio
        dists = distance_matrix[depot][unvisited_nodes]
        dems = demands[unvisited_nodes]
        # Prefer customers that are far but with low demand (to keep route flexible)
        scores = dists / (dems + 1e-6)
        return unvisited_nodes[np.argmax(scores)]

    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        dist_to_u = distance_matrix[current_node][u]
        demand_u = demands[u]

        # Savings compared to returning to depot now and starting new trip for u
        # Saving = d(current, depot) + d(depot, u) - d(current, u)
        saving = distance_matrix[current_node][depot] + distance_matrix[depot][u] - dist_to_u

        # Capacity urgency: prefer customers that fit well into remaining capacity
        capacity_fill = demand_u / rest_capacity
        urgency = 1.0 - capacity_fill  # higher when demand is small relative to capacity

        # Score: negative savings (to minimize), weighted by urgency
        score = -saving * 0.6 + dist_to_u * (0.4 + 0.2 * urgency)

        if score < best_score:
            best_score = score
            best_node = u

    # Early return if savings from returning now outweigh continuing
    if distance_matrix[current_node][depot] < distance_matrix[current_node][best_node] * 0.7:
        return depot

    return best_node
