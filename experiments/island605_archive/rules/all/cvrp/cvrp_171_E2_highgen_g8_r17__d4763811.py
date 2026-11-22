def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    savings = np.array([
        distance_matrix[depot][u] + distance_matrix[current_node][depot] - distance_matrix[current_node][u]
        for u in unvisited_nodes
    ])
    if np.max(savings) > 0:
        return unvisited_nodes[np.argmax(savings)]
    else:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
