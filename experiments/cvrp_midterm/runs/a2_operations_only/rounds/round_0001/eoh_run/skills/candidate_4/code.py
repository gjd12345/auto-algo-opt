def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Replace distance-to-current term with a blend of current and depot distance.
    score = 0.7 * d_cur + 0.3 * d_dep
    return int(unvisited_nodes[np.argmin(score)])