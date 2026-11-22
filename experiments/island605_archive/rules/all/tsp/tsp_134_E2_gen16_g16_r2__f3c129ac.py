def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    distances = distance_matrix[current_node][unvisited_nodes]
    # Compute Boltzmann weights (inverse temperature parameter)
    beta = 1.0 / (np.mean(distances) + 1e-10)
    weights = np.exp(-beta * distances)
    prob = weights / np.sum(weights)

    # Compute potential: average distance from candidate to all other unvisited nodes
    potentials = np.array([
        np.mean(distance_matrix[node][np.setdiff1d(unvisited_nodes, node)])
        if len(unvisited_nodes) > 1 else 0.0
        for node in unvisited_nodes
    ])

    # Normalize potentials to [0,1]
    pot_min, pot_max = potentials.min(), potentials.max()
    if pot_max > pot_min:
        potentials_norm = (potentials - pot_min) / (pot_max - pot_min)
    else:
        potentials_norm = np.zeros_like(potentials)

    # Combined score: high probability (short distance) and high potential (connectivity)
    score = prob * (1.0 + potentials_norm)

    return int(unvisited_nodes[np.argmax(score)])
