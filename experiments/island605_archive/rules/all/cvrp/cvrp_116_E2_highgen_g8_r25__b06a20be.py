def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    # If no unvisited nodes remain, return to depot
    if len(unvisited_nodes) == 0:
        return depot

    # When at depot or early in route, seed with farthest feasible customer
    if current_node == depot or np.all(distance_matrix[current_node][unvisited_nodes] < 1e-9):
        farthest_idx = np.argmax(distance_matrix[depot][unvisited_nodes])
        return unvisited_nodes[farthest_idx]

    # Once away from depot, switch to nearest neighbor to stay efficient
    nearest_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
    candidate = unvisited_nodes[nearest_idx]

    # If the candidate is closer than returning to depot, use it
    if distance_matrix[current_node][candidate] <= distance_matrix[current_node][depot]:
        return candidate

    # Otherwise, check if any other feasible customer is worth visiting
    sorted_indices = np.argsort(distance_matrix[current_node][unvisited_nodes])
    for idx in sorted_indices:
        if distance_matrix[current_node][unvisited_nodes[idx]] < distance_matrix[current_node][depot]:
            return unvisited_nodes[idx]

    # No better option: return to depot
    return depot
