def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    dists_to_depot = distance_matrix[depot][unvisited_nodes]
    savings = dists_to_depot - dists_from_current

    # Add a small random perturbation to break ties and diversify selection
    rng = np.random.default_rng(42)
    perturbation = rng.uniform(0, 1e-6, size=len(unvisited_nodes))

    composite = savings + perturbation
    best_idx = np.argmax(composite)
    if composite[best_idx] > 1e-9:
        return unvisited_nodes[best_idx]
    else:
        return unvisited_nodes[np.argmin(dists_from_current)]
