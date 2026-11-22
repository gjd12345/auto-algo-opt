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
    import numpy as np

    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    avg_dists_to_others = np.array([
        np.mean(distance_matrix[node][[n for n in unvisited_nodes if n != node]])
        for node in unvisited_nodes
    ])
    avg_dists_to_others = np.maximum(avg_dists_to_others, 1e-10)

    ratios = dists_from_current / avg_dists_to_others

    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(dists_from_current)]

    return unvisited_nodes[np.argmin(ratios)]
