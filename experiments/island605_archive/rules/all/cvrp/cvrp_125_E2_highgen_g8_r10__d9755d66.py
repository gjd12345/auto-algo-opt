def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot and len(unvisited_nodes) > 0:
        far_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[far_idx]
    if current_node == depot:
        return depot
    # Weighted savings with distance-to-depot penalty: savings - 0.5 * dist(depot, candidate)
    weighted = (distance_matrix[current_node][depot] +
                distance_matrix[depot][unvisited_nodes] -
                distance_matrix[current_node][unvisited_nodes] -
                0.5 * distance_matrix[depot][unvisited_nodes])
    best_idx = np.argmax(weighted)
    best_candidate = unvisited_nodes[best_idx]
    if weighted[best_idx] > 0:
        return best_candidate
    nearest_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
    return unvisited_nodes[nearest_idx]
