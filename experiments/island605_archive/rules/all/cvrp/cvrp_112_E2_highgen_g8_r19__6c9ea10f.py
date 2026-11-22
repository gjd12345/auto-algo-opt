def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # If at depot, seed route toward farthest feasible customer
    if current_node == depot:
        dists_from_depot = distance_matrix[depot, unvisited_nodes]
        farthest_idx = np.argmax(dists_from_depot)
        return unvisited_nodes[farthest_idx]

    # Otherwise, pick nearest feasible customer
    nearest_idx = np.argmin(distance_matrix[current_node][unvisited_nodes])
    candidate = unvisited_nodes[nearest_idx]

    # If no feasible customer is closer than returning to depot, early return
    if distance_matrix[current_node][candidate] > distance_matrix[current_node][depot]:
        return depot

    return candidate
