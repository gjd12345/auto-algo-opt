def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        # Seed route: farthest feasible customer from depot
        distances_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_from_depot)]
    else:
        capacity_ratio = rest_capacity / (demands.max() * 2 + 1e-6)
        if capacity_ratio > 0.4:
            # Savings-based: max (dist(depot,u) + dist(depot,current) - dist(current,u))
            savings = (distance_matrix[depot][unvisited_nodes] +
                       distance_matrix[depot][current_node] -
                       distance_matrix[current_node][unvisited_nodes])
            return unvisited_nodes[np.argmax(savings)]
        else:
            # Low capacity: return to depot unless nearest customer is very close
            nearest = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
            if distance_matrix[current_node][nearest] < distance_matrix[current_node][depot] * 0.7:
                return nearest
            else:
                return depot