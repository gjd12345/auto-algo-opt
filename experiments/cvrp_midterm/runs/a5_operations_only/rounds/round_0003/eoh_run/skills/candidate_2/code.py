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

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    cap = float(rest_capacity) if rest_capacity > 1e-12 else 1e-12
    eps = 1e-9

    # Normalized savings efficiency: savings relative to total detour length.
    # savings = d_cur_depot + d_dep - d_cur ; detour cost ~ d_cur + d_dep
    d_cur_depot = float(distance_matrix[current_node][depot])
    savings = d_cur_depot + d_dep - d_cur
    detour = d_cur + d_dep + eps
    efficiency = savings / detour  # in roughly (-1, 1]

    # Hyperbolic capacity pressure: prefers demand that fits snugly in remaining capacity.
    # demand gap relative to remaining capacity (0 = perfect fit).
    fit = np.abs(dem - cap) / (cap + eps)
    pressure = 1.0 / (1.0 + fit)

    # Combined primary score: maximize efficiency and capacity pressure while
    # keeping near-neighbor distance small.
    primary = -(1.0 * efficiency + 0.9 * pressure) + 0.05 * (d_cur / (cap + eps))

    best_val = primary.min()
    tol = 1e-9
    close_mask = primary <= best_val + tol
    close = np.where(close_mask)[0]

    if close.size > 1:
        candidates = unvisited_nodes[close]
        # Secondary: prefer closer depot proximity plus a small pull toward the current node.
        secondary = (distance_matrix[depot][candidates].astype(float)
                     + 0.5 * distance_matrix[current_node][candidates].astype(float))
        return int(candidates[int(np.argmin(secondary))])

    return int(unvisited_nodes[int(np.argmin(primary))])