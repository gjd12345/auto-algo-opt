def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Compute savings: distance(current, depot) + distance(depot, node) - distance(current, node)
    dist_to_depot = distance_matrix[current_node][depot]
    distances_current = distance_matrix[current_node][unvisited_nodes]
    distances_depot = distance_matrix[depot][unvisited_nodes]
    savings = dist_to_depot + distances_depot - distances_current

    # For each feasible node, compute regret: difference between best and second-best savings
    # across all unvisited nodes as possible predecessors (using depot as fallback)
    best_savings = np.max(savings)
    second_best_savings = np.partition(savings, -2)[-2] if len(savings) >= 2 else best_savings
    regret = savings - second_best_savings  # positive for the best, zero/negative for others

    # Weight savings by regret: prefer high regret * high savings
    weighted_score = savings * np.maximum(regret, 0)  # only nodes with positive regret get a boost
    max_weighted = np.max(weighted_score)
    best_indices = np.where(weighted_score == max_weighted)[0]

    if len(best_indices) == 1:
        return unvisited_nodes[best_indices[0]]
    else:
        # Tie-break by max savings, then nearest distance
        best_savings_idx = best_indices[np.argmax(savings[best_indices])]
        return unvisited_nodes[best_savings_idx]
