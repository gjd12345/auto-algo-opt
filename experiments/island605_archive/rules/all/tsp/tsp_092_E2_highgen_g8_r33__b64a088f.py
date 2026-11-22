def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_unvisited = len(unvisited_nodes)
    if n_unvisited <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dists_from_current = distance_matrix[current_node][unvisited_nodes]
    dists_from_dest = distance_matrix[destination_node][unvisited_nodes]

    sorted_dists = np.sort(dists_from_current)
    median_near = sorted_dists[min(2, n_unvisited - 1)]
    detour_penalty = np.maximum(0, dists_from_current - 2.0 * median_near)

    # Reward closeness to current, penalize long detours, slightly reward distance from destination
    score = -0.7 * dists_from_current + 0.4 * dists_from_dest - 0.6 * detour_penalty

    best_idx = np.argmax(score)
    return int(unvisited_nodes[best_idx])
