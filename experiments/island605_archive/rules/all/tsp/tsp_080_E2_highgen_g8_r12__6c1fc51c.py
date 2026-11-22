def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_unvisited = len(unvisited_nodes)
    if n_unvisited <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    distances = distance_matrix[current_node][unvisited_nodes]
    max_dist = distances.max()
    if max_dist == 0:
        return unvisited_nodes[0]

    # Compute average distance from each candidate to all other unvisited nodes
    candidate_coords = unvisited_nodes
    avg_farness = np.zeros(n_unvisited)
    for i, u in enumerate(unvisited_nodes):
        others = np.delete(candidate_coords, i)
        avg_farness[i] = np.mean(distance_matrix[u][others])

    # Score: normalized distance from current (inverted) + normalized average farness
    norm_dist = distances / max_dist
    norm_far = avg_farness / (avg_farness.max() + 1e-10)
    scores = (1 - norm_dist) + 0.5 * norm_far

    # Prefer smoother edges for medium distances
    for i, u in enumerate(unvisited_nodes):
        if distances[i] < 0.3 * max_dist:
            scores[i] += 0.2
        elif distances[i] > 0.7 * max_dist:
            scores[i] -= 0.1

    return unvisited_nodes[np.argmax(scores)]
