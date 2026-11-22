def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('-inf')

    for u in unvisited_nodes:
        d_current = distance_matrix[current_node][u]
        d_dest = distance_matrix[u][destination_node]

        # Ratio: far from destination / close to current
        ratio_dest_current = d_dest / (d_current + 1e-9)

        # Average distance to two nearest unvisited neighbors
        distances_to_others = [distance_matrix[u][v] for v in unvisited_nodes if v != u]
        if len(distances_to_others) >= 2:
            distances_to_others.sort()
            avg_nn_dist = (distances_to_others[0] + distances_to_others[1]) / 2.0
        elif len(distances_to_others) == 1:
            avg_nn_dist = distances_to_others[0]
        else:
            avg_nn_dist = 1.0

        # Ratio: avg neighbor distance / distance to current
        ratio_smoothness = avg_nn_dist / (d_current + 1e-9)

        # Sigmoid-like transformation
        sig1 = 1.0 / (1.0 + np.exp(-ratio_dest_current))
        sig2 = 1.0 / (1.0 + np.exp(-ratio_smoothness))

        score = sig1 * sig2

        if score > best_score:
            best_score = score
            best_node = u

    if best_node is None:
        best_node = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    return best_node
