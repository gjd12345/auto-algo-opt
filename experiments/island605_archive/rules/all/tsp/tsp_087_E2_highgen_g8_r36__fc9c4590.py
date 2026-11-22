def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a TSP greedy construction.

    Args:
        current_node: ID of the current node
        destination_node: ID of the destination (return) node
        unvisited_nodes: array of unvisited node IDs
        distance_matrix: pairwise distance matrix between all nodes
    Returns:
        next_node: ID of the next node to visit
    """
    distances_from_current = distance_matrix[current_node][unvisited_nodes]
    distances_to_dest = distance_matrix[destination_node][unvisited_nodes]
    # Weight: 0.7 * distance from current - 0.3 * distance to dest (to favor nodes close now but far from destination)
    scores = 0.7 * distances_from_current - 0.3 * distances_to_dest
    return int(unvisited_nodes[np.argmin(scores)])
