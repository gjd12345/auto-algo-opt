def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot:
        return unvisited_nodes[np.argmax(distance_matrix[depot][unvisited_nodes])]

    dist_cur = distance_matrix[current_node][unvisited_nodes]
    dist_to_depot = distance_matrix[current_node][depot]

    # Compute sum of distances from each candidate to all other unvisited nodes
    sum_dist_to_others = np.zeros(len(unvisited_nodes))
    for i, cand in enumerate(unvisited_nodes):
        other_mask = np.arange(len(unvisited_nodes)) != i
        sum_dist_to_others[i] = np.sum(distance_matrix[cand][unvisited_nodes[other_mask]])

    # Ratio: distance from current to candidate / sum of candidate's distances to others
    ratio = dist_cur / (sum_dist_to_others + 1e-10)
    best_idx = np.argmin(ratio)
    best_ratio = ratio[best_idx]

    # Compare to returning to depot: ratio of depot-return distance to sum of depot distances to all
    depot_sum = np.sum(distance_matrix[depot][unvisited_nodes])
    depot_ratio = dist_to_depot / (depot_sum + 1e-10)

    # If best ratio is worse than returning to depot, close route
    if best_ratio > depot_ratio:
        return depot

    return unvisited_nodes[best_idx]
