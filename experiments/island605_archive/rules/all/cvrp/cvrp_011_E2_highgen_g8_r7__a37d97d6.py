def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        distances_to_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(distances_to_depot)]
    else:
        median_demand = np.median(demands[demands > 0])
        if rest_capacity < median_demand:
            return depot
        distances_from_current = distance_matrix[current_node][unvisited_nodes].astype(float)
        depot_distances = distance_matrix[depot][unvisited_nodes].astype(float)
        ratios = np.divide(distances_from_current, depot_distances, out=np.full_like(distances_from_current, np.inf), where=depot_distances != 0)
        return unvisited_nodes[np.argmin(ratios)]
