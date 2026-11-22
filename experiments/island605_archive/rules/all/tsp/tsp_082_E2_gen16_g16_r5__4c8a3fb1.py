def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for u in unvisited_nodes:
        cost_now = distance_matrix[current_node][u]
        if cost_now == 0:
            continue

        others = [v for v in unvisited_nodes if v != u]
        if len(others) > 0:
            min_future = min(distance_matrix[u][v] for v in others)
            avg_future = np.mean([distance_matrix[u][v] for v in others])
        else:
            min_future = 0
            avg_future = 0

        min_ratio = min_future / (cost_now + 1e-6)
        avg_ratio = avg_future / (cost_now + 1e-6)
        composite = 1.2 * min_ratio + 1.8 * avg_ratio

        # Cosine similarity bonus: reward direction diversity from destination
        u_vec = distance_matrix[current_node][u]
        dest_vec = distance_matrix[current_node][destination_node]
        if u_vec > 0 and dest_vec > 0:
            cos_sim = (cost_now**2 + dest_vec**2 - distance_matrix[u][destination_node]**2) / (2 * cost_now * dest_vec + 1e-6)
            cos_sim = max(-1, min(1, cos_sim))
            angle_bonus = (1 - abs(cos_sim)) * 0.2
        else:
            angle_bonus = 0

        score = composite + angle_bonus

        if score > best_score:
            best_score = score
            best_node = u

    return best_node
