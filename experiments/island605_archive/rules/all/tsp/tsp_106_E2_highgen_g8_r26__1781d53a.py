def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_candidate = None
    best_score = -float('inf')

    for u in unvisited_nodes:
        dist_current_u = distance_matrix[current_node][u]
        if dist_current_u == 0:
            return u

        # Average distance from u to all other unvisited nodes
        avg_dist_to_others = 0.0
        count = 0
        for v in unvisited_nodes:
            if v != u:
                avg_dist_to_others += distance_matrix[u][v]
                count += 1
        if count > 0:
            avg_dist_to_others /= count
        else:
            avg_dist_to_others = 0

        # Also consider destination node
        if destination_node not in unvisited_nodes:
            avg_dist_to_others += distance_matrix[u][destination_node]
            avg_dist_to_others /= (count + 1) if count > 0 else 1

        # Score: ratio of average centrality to direct distance
        if dist_current_u > 0:
            score = avg_dist_to_others / dist_current_u
        else:
            score = float('inf')

        if score > best_score:
            best_score = score
            best_candidate = u

    if best_candidate is None:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    return best_candidate
