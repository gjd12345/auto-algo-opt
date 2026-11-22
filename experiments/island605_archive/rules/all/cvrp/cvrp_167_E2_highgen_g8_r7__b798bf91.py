def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # At depot: pick farthest feasible customer to seed routes toward distant clusters
        best = unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]
        return int(best)
    else:
        # Savings-based selection: maximize (dist(depot, u) - dist(current, u))
        dist_to_depot = distance_matrix[depot][unvisited_nodes]
        dist_from_current = distance_matrix[current_node][unvisited_nodes]
        savings = dist_to_depot - dist_from_current
        max_saving = np.max(savings)
        candidates = unvisited_nodes[savings == max_saving]
        # Ties broken by nearest distance from current node
        if len(candidates) > 1:
            best = candidates[np.argmin(distance_matrix[current_node][candidates])]
        else:
            best = candidates[0]
        return int(best)
