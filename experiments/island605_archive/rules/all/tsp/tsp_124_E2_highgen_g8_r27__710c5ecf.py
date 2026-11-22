def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    best_score = -float('inf')
    best_node = unvisited_nodes[0]
    alpha = 0.4  # weight for regret
    beta = 0.4   # weight for distance penalty
    gamma = 0.2  # weight for smoothness penalty

    # For simplicity, use a dummy previous node vector (assume previous was toward origin)
    # In a real implementation, you would need to pass previous_node as argument
    # Here we approximate smoothness by penalizing candidates that create large distance relative to a local baseline
    import numpy as np

    for candidate in unvisited_nodes:
        dist_current_candidate = distance_matrix[current_node][candidate]

        other_dists = [distance_matrix[candidate][other] for other in unvisited_nodes if other != candidate]
        if len(other_dists) >= 2:
            sorted_dists = sorted(other_dists)
            best = sorted_dists[0]
            second_best = sorted_dists[1]
            regret = second_best - best
        else:
            regret = 0

        if len(other_dists) > 0:
            avg_dist = sum(other_dists) / len(other_dists)
        else:
            avg_dist = dist_current_candidate

        normalized_dist = dist_current_candidate / (avg_dist + 1e-10)

        # Smoothness penalty: prefer candidates whose distance is close to median of other distances from candidate
        if len(other_dists) >= 3:
            sorted_other = sorted(other_dists)
            median_dist = sorted_other[len(sorted_other)//2]
            smoothness_penalty = abs(dist_current_candidate - median_dist) / (median_dist + 1e-10)
        else:
            smoothness_penalty = 0

        score = alpha * regret - beta * normalized_dist - gamma * smoothness_penalty

        if score > best_score:
            best_score = score
            best_node = candidate

    return int(best_node)
