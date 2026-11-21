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
    d_0cur = float(distance_matrix[depot][current_node])

    demand = demands[unvisited_nodes].astype(np.float64)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    fill = np.clip(demand / cap, 0.0, 1.0)

    eps = 1e-9

    # Clarke-Wright savings, normalized by the travel cost of the new leg
    savings = d_0cur + d_dep - d_cur
    leg = d_cur + d_dep + eps

    # Tightness after serving the node: smaller means better packing
    slack = np.clip(1.0 - fill, 0.0, 1.0)
    tightness = 1.0 - slack * slack   # convex reward for filling the truck

    # Radial far-first term normalized by the farthest candidate
    dmax = float(np.max(d_dep)) if d_dep.size > 0 else 1.0
    if dmax <= 0:
        dmax = 1.0
    radial = d_dep / dmax

    # Additive composite: savings term dominates via small weight on cost,
    # tightness and radial act as bounded tilts. Score is higher = better.
    score = (savings / leg) + 0.45 * tightness + 0.25 * radial

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])