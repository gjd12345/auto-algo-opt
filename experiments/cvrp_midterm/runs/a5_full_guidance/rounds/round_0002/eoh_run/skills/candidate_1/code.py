def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return depot
    if rest_capacity <= 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    denom = d_cur + d_dep
    denom = np.where(denom <= 0, 1.0, denom)
    proximity = d_cur / denom  # scale-free, in [0, 1]

    dem = demands[unvisited_nodes].astype(float)
    util = dem / rest_capacity  # capacity utilisation of this candidate

    # Priority: high utilisation and high proximity are both good for
    # packing the vehicle efficiently without wandering far.
    eps = 1e-9
    score = util / (proximity + eps)

    order = np.argsort(-score)
    best = order[0]
    best_score = score[best]

    # Break exact/near-exact ties (relative to best score) by raw distance.
    rel_window = 1e-6 * (abs(best_score) + 1.0)
    chosen = best
    best_d = d_cur[best]
    for idx in order[1:]:
        if best_score - score[idx] > rel_window:
            break
        if d_cur[idx] < best_d:
            best_d = d_cur[idx]
            chosen = idx

    return unvisited_nodes[chosen]