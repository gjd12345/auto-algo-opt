import numpy as np

def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n = len(unvisited_nodes)
    if n == 1:
        return unvisited_nodes[0]

    best_score = -float('inf')
    best_node = None

    for u in unvisited_nodes:
        d_cur = distance_matrix[current_node][u]
        others = [v for v in unvisited_nodes if v != u]
        dists = np.array([distance_matrix[u][v] for v in others])

        if len(dists) >= 2:
            mean_dist = np.mean(dists)
            std_dist = np.std(dists)
            if std_dist > 1e-10:
                z_score = (d_cur - mean_dist) / std_dist
            else:
                z_score = 0.0
            variance_penalty = np.var(dists) / (mean_dist + 1e-10)
        elif len(dists) == 1:
            z_score = (d_cur - dists[0]) / (dists[0] + 1e-10)
            variance_penalty = 0.0
        else:
            z_score = 0.0
            variance_penalty = 0.0

        # Prefer negative z-score (shorter than average), penalize high variance
        score = -z_score - 0.3 * variance_penalty

        if score > best_score:
            best_score = score
            best_node = u

    if best_node is None:
        best_node = unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]
    return best_node
