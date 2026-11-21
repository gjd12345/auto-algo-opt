def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[depot][unvisited_nodes]
    # Savings-style score: prefer nodes that are close to current node but also
    # relatively close to the depot (small d(cur,n) but not pulling route outward).
    score = cur + 0.5 * to_depot
    return int(unvisited_nodes[np.argmin(score)])