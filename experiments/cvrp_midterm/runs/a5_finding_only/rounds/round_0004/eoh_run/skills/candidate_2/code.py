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
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    # Savings of linking current->candidate instead of current->depot->candidate,
    # relative to the direct depot detour (a radial round-trip).
    cur_dep = float(distance_matrix[current_node][depot])
    savings = (cur_dep + d_dep) - d_cur  # classic Clarke-Wright savings

    # Radial detour scale (round trip from depot to candidate): normaliser.
    radial = 2.0 * d_dep + 1e-12

    # Scale-invariant, capacity-aware ratio score.
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9
    load_frac = np.clip(dem / cap, 0.0, 1.0)

    # Favour candidates with large savings per unit of detour, but only when
    # they use the remaining capacity well (high packing reduces waste).
    savings_ratio = savings / radial
    pack_bonus = 0.5 * load_frac

    # Score: high savings_ratio and high packing are good -> maximize.
    score = savings_ratio + pack_bonus - 0.25 * load_frac * load_frac

    # If no candidate offers positive savings, return to depot early.
    if np.max(score) <= 0.0 and np.max(savings) <= 0.0:
        return depot

    idx = int(np.argmax(score))
    return int(unvisited_nodes[idx])