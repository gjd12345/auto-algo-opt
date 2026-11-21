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
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes]

    # Clarke-Wright style savings: detour saved vs going via depot
    # (from current node, going to j instead of back through depot)
    saving = d_cur + d_dep - distance_matrix[depot][current_node]

    # Normalize saving by the candidate's own depot distance (scale-free)
    # -> "savings ratio": prefer customers that are far from depot but
    #    close to the current node (strong consolidation incentive).
    denom = d_dep + 1e-9
    ratio = saving / denom

    # Capacity-fullness tiebreak, fully scale-free in [0,1):
    # reward customers whose demand nearly fills remaining capacity,
    # penalize tiny demands that waste a trip slot.
    cap = max(rest_capacity, 1e-9)
    fill = dem / cap  # fraction of remaining capacity consumed
    fill = np.clip(fill, 0.0, 1.0)
    # variance-based shape: prefer fill close to 1 but not exceeding
    fill_bonus = fill * fill  # convex, favors big fills

    # Combined score: maximize ratio (savings per unit depot distance),
    # break ties by preferring near-full capacity use.
    score = ratio + 0.75 * fill_bonus - 0.05 * (dem / (cap + dem))

    return int(unvisited_nodes[np.argmax(score)])