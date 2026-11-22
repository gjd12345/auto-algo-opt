def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    
    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_dest = distance_matrix[destination_node][unvisited_nodes]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        sum_dist = dist_from_current + dist_from_dest
        ratio = np.where(sum_dist > 0, dist_from_dest / sum_dist, np.inf)
    max_ratio = np.max(ratio[ratio < np.inf]) if np.any(np.isfinite(ratio)) else 1.0
    penalty_farthest = 1 - (ratio / max_ratio)
    
    avg_neighbor_dist = np.array([
        np.mean(distance_matrix[candidate][[n for n in unvisited_nodes if n != candidate]])
        if len(unvisited_nodes) > 1 else 1.0
        for candidate in unvisited_nodes
    ])
    edge_ratio = np.where(avg_neighbor_dist > 0, dist_from_current / avg_neighbor_dist, np.inf)
    max_edge = np.max(edge_ratio[np.isfinite(edge_ratio)]) if np.any(np.isfinite(edge_ratio)) else 1.0
    penalty_smooth = edge_ratio / max_edge
    
    combined = 0.6 * penalty_farthest + 0.4 * penalty_smooth
    best_idx = np.argmin(combined)
    return unvisited_nodes[best_idx]