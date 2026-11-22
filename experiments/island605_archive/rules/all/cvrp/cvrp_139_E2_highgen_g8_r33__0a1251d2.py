def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    distances = distance_matrix[current_node][unvisited_nodes]

    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]

    # Compute savings from pairing with depot
    savings_depot = distance_matrix[current_node][depot] + distance_matrix[depot][unvisited_nodes] - distances

    # For each candidate, compute savings from pairing with the closest other feasible customer (seed)
    # Seed is the unvisited node (other than itself) that maximizes savings with the candidate
    n = len(unvisited_nodes)
    best_savings = np.zeros(n)
    second_best_savings = np.zeros(n)
    for i, candidate in enumerate(unvisited_nodes):
        # Distances from candidate to all other unvisited nodes
        other_distances = distance_matrix[candidate][unvisited_nodes]
        # Savings = dist(candidate, depot) + dist(other, depot) - dist(candidate, other)
        pair_savings = distance_matrix[candidate][depot] + distance_matrix[depot][unvisited_nodes] - other_distances
        # Exclude self
        pair_savings[i] = -np.inf
        sorted_savings = np.sort(pair_savings)[::-1]
        best_savings[i] = sorted_savings[0] if len(sorted_savings) > 0 else 0
        second_best_savings[i] = sorted_savings[1] if len(sorted_savings) > 1 else 0

    # Regret = best_savings - second_best_savings (from pairing perspective)
    regret = best_savings - second_best_savings

    # Final score = savings_depot + regret (emphasize both immediate savings and future regret)
    score = savings_depot + regret

    # Select candidate with highest score; break ties by nearest distance
    max_score = np.max(score)
    candidates_with_max_score = np.where(score == max_score)[0]
    best_idx = candidates_with_max_score[np.argmin(distances[candidates_with_max_score])]

    return unvisited_nodes[best_idx]
