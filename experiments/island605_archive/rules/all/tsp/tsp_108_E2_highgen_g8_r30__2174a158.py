def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for node in unvisited_nodes:
        edge_len = distance_matrix[current_node][node]
        if edge_len < 1e-10:
            return int(node)

        other_nodes = unvisited_nodes[unvisited_nodes != node]
        if len(other_nodes) == 0:
            return int(node)

        min_dest_dist = distance_matrix[node][destination_node]
        avg_other_dist = np.mean(distance_matrix[node][other_nodes])

        # Score: low min_dest_dist + avg_other_dist (combined "proximity" to destination and central) divided by edge_len
        score = (min_dest_dist + avg_other_dist) / (edge_len + 1e-10)

        if score > best_score:
            best_score = score
            best_node = node

    if best_node is not None:
        return int(best_node)
    else:
        return int(unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])])
