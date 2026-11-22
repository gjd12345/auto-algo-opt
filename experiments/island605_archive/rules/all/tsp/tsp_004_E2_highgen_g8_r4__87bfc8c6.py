def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_node = None
    best_score = float('inf')
    for node in unvisited_nodes:
        d_current = distance_matrix[current_node][node]
        d_dest = distance_matrix[destination_node][node]
        # Farthest-insertion component: prefer nodes far from destination to seed distant regions
        far_penalty = -d_dest
        # 2-opt-awareness component: penalize edges that are long relative to local neighbors (approximate smoothness)
        # Compute average distance from current_node to all unvisited nodes as local reference
        avg_local = np.mean(distance_matrix[current_node][unvisited_nodes])
        smooth_penalty = max(0, d_current - 1.5 * avg_local)
        # Combined score: lower is better
        score = d_current + smooth_penalty + far_penalty * 0.5
        if score < best_score:
            best_score = score
            best_node = node
    return best_node
