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
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    # Get coordinates (assuming distance_matrix is Euclidean from coordinates)
    # If distance matrix is not directly from coordinates, we approximate via distances
    # Compute distances to destination for each candidate
    dists_to_dest = distance_matrix[destination_node][unvisited_nodes]
    dists_from_current = distance_matrix[current_node][unvisited_nodes]

    # Compute "angle penalty" using law of cosines:
    # For triangle current-candidate-destination, score = -d(current,candidate) + 0.5*d(candidate,destination)
    # Lower d(current,candidate) and higher d(candidate,destination) preferred (keep going away from destination initially)
    scores = -dists_from_current + 0.5 * dists_to_dest

    return unvisited_nodes[np.argmax(scores)]
