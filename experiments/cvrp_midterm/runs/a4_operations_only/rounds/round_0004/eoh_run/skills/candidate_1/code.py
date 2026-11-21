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
    cur = distance_matrix[current_node][unvisited_nodes]
    cap = max(rest_capacity, 1e-9)
    # Demand-fill ratio per candidate
    fill = demands[unvisited_nodes] / cap
    max_fill = float(np.max(fill)) if fill.size > 0 else 1.0
    if max_fill <= 0:
        max_fill = 1.0
    # Primary: closest current distance, with larger demand-fill preferred
    scores = cur - 0.5 * (fill / max_fill)
    order = np.argsort(scores)
    best_score = scores[order[0]]
    tol = 1e-9 + 1e-6 * (abs(best_score) + 1.0)
    tied = order[scores[order] <= best_score + tol]
    if tied.size == 1:
        return int(unvisited_nodes[tied[0]])
    tie_nodes = unvisited_nodes[tied]
    # Secondary: prefer larger demand density (demand / distance to current)
    dists = distance_matrix[current_node][tie_nodes]
    safe_dists = np.where(dists <= 1e-12, 1e-12, dists)
    density = demands[tie_nodes] / safe_dists
    best_density_idx = int(np.argmax(density))
    candidates = tie_nodes[density >= density[best_density_idx] - 1e-12]
    # Final tie-break: shorter distance to current node
    cand_dists = distance_matrix[current_node][candidates]
    return int(candidates[np.argmin(cand_dists)])