def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 2:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = unvisited_nodes[0]
    best_ratio = float('inf')

    for u in unvisited_nodes:
        dist_cur = distance_matrix[current_node][u]
        # Average distance from u to all other unvisited nodes
        other_dists = [distance_matrix[u][v] for v in unvisited_nodes if v != u]
        avg_other = sum(other_dists) / len(other_dists) if other_dists else 1.0
        ratio = dist_cur / avg_other if avg_other > 0 else float('inf')
        if ratio < best_ratio:
            best_ratio = ratio
            best_node = u

    return int(best_node)
