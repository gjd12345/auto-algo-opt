def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    # If few nodes remain, fall back to nearest neighbor
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    best_node = None
    best_score = -float('inf')

    for node in unvisited_nodes:
        # Distance from current to candidate
        d_curr = distance_matrix[current_node][node]
        # Distance from candidate to destination (encourage far seeds early)
        d_dest = distance_matrix[node][destination_node]
        # 2-opt awareness: penalty if edge is long compared to neighbors
        # Use average distance of candidate to its three nearest neighbors (excluding current)
        neighbor_dists = []
        for other in unvisited_nodes:
            if other != node:
                neighbor_dists.append(distance_matrix[node][other])
        if len(neighbor_dists) >= 3:
            local_avg = np.mean(sorted(neighbor_dists)[:3])
        elif len(neighbor_dists) > 0:
            local_avg = np.mean(neighbor_dists)
        else:
            local_avg = d_curr
        # Penalty ratio: if d_curr is much larger than local average
        penalty = d_curr / (local_avg + 1e-10)

        # Composite score: encourage larger d_dest (farthest), but penalize long d_curr relative to local
        score = d_dest - 0.5 * d_curr - 0.3 * penalty

        if score > best_score:
            best_score = score
            best_node = node

    return best_node
