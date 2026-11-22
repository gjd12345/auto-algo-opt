def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    dists_current = distance_matrix[current_node][unvisited_nodes]
    dists_dest = distance_matrix[destination_node][unvisited_nodes]
    # Weighted score: penalize closeness to destination (to visit far nodes early) and penalize large current edges
    scores = dists_current - 0.5 * dists_dest  # negative score encourages far-from-dest, near-to-current
    return unvisited_nodes[np.argmin(scores)]
