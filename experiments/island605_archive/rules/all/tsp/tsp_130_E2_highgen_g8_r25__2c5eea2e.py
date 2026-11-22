def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    import numpy as np

    n = len(unvisited_nodes)
    if n <= 1:
        return unvisited_nodes[0]

    # Find centroid as node with minimum total distance to all unvisited nodes
    best_centroid = unvisited_nodes[0]
    best_total_dist = np.inf
    for u in unvisited_nodes:
        total_dist = np.sum(distance_matrix[u][unvisited_nodes])
        if total_dist < best_total_dist:
            best_total_dist = total_dist
            best_centroid = u

    best_score = -np.inf
    best_node = unvisited_nodes[0]

    for u in unvisited_nodes:
        dist_cu = distance_matrix[current_node][u]
        dist_uc = distance_matrix[u][best_centroid]

        # Compute a proxy for minimum spanning tree cost: average of two smallest distances from u to other unvisited nodes (excluding u itself)
        other_dists = distance_matrix[u][unvisited_nodes]
        sorted_dists = np.sort(other_dists)
        if len(sorted_dists) >= 2:
            mst_proxy = sorted_dists[0] + sorted_dists[1]
        elif len(sorted_dists) == 1:
            mst_proxy = sorted_dists[0]
        else:
            mst_proxy = 0.0

        # Score: penalize long edge from current node, reward proximity to centroid and high mst proxy (connection cost to others)
        score = dist_uc + 0.7 * mst_proxy - 1.2 * dist_cu

        if score > best_score:
            best_score = score
            best_node = u

    return best_node
