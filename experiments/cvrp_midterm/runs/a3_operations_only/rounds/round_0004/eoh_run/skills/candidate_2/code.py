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
    unvisited = np.asarray(unvisited_nodes, dtype=np.int64)
    if unvisited.size == 0:
        return 0

    d_cur = distance_matrix[current_node][unvisited]
    d_dep = distance_matrix[depot][unvisited]
    dem = demands[unvisited]

    cap = max(rest_capacity, 1e-9)
    fill = np.clip(dem / cap, 0.0, 1.0)

    # Additive insertion/regret-style score (not a ratio like savings):
    # cost of inserting this node = distance from current + detour to depot,
    # minus a reward for serving far customers, plus a convex penalty for
    # consuming a large fraction of the remaining capacity.
    insert_cost = d_cur + 0.5 * d_dep
    far_reward = 0.6 * d_dep
    cap_penalty = (fill * fill) * (0.5 * cap + 1.0)

    scores = insert_cost - far_reward + cap_penalty

    best = int(np.argmin(scores))

    # Second ordering stage: near-tie band resolved by a composite of
    # nearest-neighbor distance and depot proximity (depot-closeness helps
    # preserve possibility of a short return leg).
    span = np.abs(scores[best]) + 1.0
    cutoff = scores[best] + 0.06 * span
    close_mask = scores <= cutoff
    if np.sum(close_mask) > 1:
        close = unvisited[close_mask]
        close_d = distance_matrix[current_node][close]
        close_dep = distance_matrix[depot][close]
        secondary = close_d + 0.25 * close_dep
        return int(close[np.argmin(secondary)])
    return int(unvisited[best])