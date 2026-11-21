def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot
    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = distance_matrix[current_node, depot]
    # Savings gained by inserting node before returning, relative to the leg it replaces.
    savings = stem + to_depot - cur
    score = savings / (cur + 1e-12)
    return int(unvisited_nodes[np.argmax(score)])