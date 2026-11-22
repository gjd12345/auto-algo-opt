def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # Tunable parameter: alpha controls depot-distance influence (alpha > 0)
    alpha = 0.7

    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]
    else:
        d_current_u = distance_matrix[current_node][unvisited_nodes]
        d_depot_u = distance_matrix[depot][unvisited_nodes]
        ratio = d_current_u / (d_depot_u ** alpha + 1e-10)
        best_idx = np.argmin(ratio)
        return unvisited_nodes[best_idx]
