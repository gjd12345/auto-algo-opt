def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_to_dest = distance_matrix[destination_node][unvisited_nodes]
    dist_from_cur = distance_matrix[current_node][unvisited_nodes]

    min_cur_dist = np.min(dist_from_cur)
    max_dest_dist = np.max(dist_to_dest)
    if max_dest_dist == 0:
        max_dest_dist = 1
    if min_cur_dist == 0:
        min_cur_dist = 1

    scores = []
    for i in range(len(unvisited_nodes)):
        regret = dist_from_cur[i] - min_cur_dist
        farness = dist_to_dest[i] / max_dest_dist
        # Combine: prefer far from destination, but penalize high regret relative to farness
        score = farness / (1 + regret / min_cur_dist)
        scores.append(score)

    best_idx = np.argmax(scores)
    return unvisited_nodes[best_idx]
