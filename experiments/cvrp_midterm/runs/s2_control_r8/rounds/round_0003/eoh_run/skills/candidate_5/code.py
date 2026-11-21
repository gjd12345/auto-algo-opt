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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(np.float64)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(np.float64)
    eps = 1e-9

    demand = demands[unvisited_nodes].astype(np.float64)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    fill = np.clip(demand / cap, 0.0, 1.0)

    # Normalize each term to [0,1] then combine additively.
    cur_max = float(np.max(d_cur)) if d_cur.size > 0 else 1.0
    if cur_max <= 0:
        cur_max = 1.0
    near = 1.0 - d_cur / (cur_max + eps)   # prefer close nodes

    dep_max = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    if dep_max <= 0:
        dep_max = 1.0
    radial = d_dep / (dep_max + eps)       # prefer far-from-depot

    fill_lin = fill                        # linear fill pressure

    score = 0.55 * near + 0.25 * radial + 0.20 * fill_lin

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])