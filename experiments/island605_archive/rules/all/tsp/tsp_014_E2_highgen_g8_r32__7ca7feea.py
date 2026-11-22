def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_from_current = distance_matrix[current_node][unvisited_nodes]
    dist_from_dest = distance_matrix[destination_node][unvisited_nodes]

    # Cheapest insertion cost: cost to insert node between current and destination
    insertion_cost = dist_from_current + dist_from_dest - distance_matrix[current_node][destination_node]
    insertion_cost = np.maximum(insertion_cost, 0)

    # Farthest bonus: favor nodes far from destination
    farthest_bonus = dist_from_dest

    # Weighted score: lower insertion cost is better, higher farthest bonus is better
    alpha = 0.4  # weight for insertion cost
    beta = 0.6   # weight for farthest bonus
    score = alpha * insertion_cost - beta * farthest_bonus
    best_idx = np.argmin(score)
    return unvisited_nodes[best_idx]
