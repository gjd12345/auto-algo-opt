def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    import numpy as np

    dists = distance_matrix[current_node][unvisited_nodes]
    dest_dists = distance_matrix[destination_node][unvisited_nodes]

    # Use median as a robust local baseline
    median_dist = np.median(dists) if len(dists) > 0 else 1.0

    # Avoid division by zero
    median_dist = max(median_dist, 1e-8)

    best_score = float('inf')
    best_node = unvisited_nodes[0]

    for u, d_current, d_dest in zip(unvisited_nodes, dists, dest_dists):
        # Penalty if edge is significantly longer than median
        penalty = 1.0
        if d_current > 2.0 * median_dist:
            penalty = 3.0
        elif d_current > 1.5 * median_dist:
            penalty = 2.0

        # Reward visiting nodes far from destination early (higher d_dest gives lower score)
        score = d_current * penalty - 0.5 * d_dest

        if score < best_score:
            best_score = score
            best_node = u

    return best_node
