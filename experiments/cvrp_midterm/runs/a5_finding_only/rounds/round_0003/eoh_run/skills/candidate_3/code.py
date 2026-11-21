def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-12
    load_frac = np.clip(dem / cap, 0.0, 1.0)

    # Scale-invariant savings ratio: how much of a detour current->c saves vs depot->c
    # savings_ratio in (-inf, 1], 1 means c lies on the depot->current ray extension
    denom = np.maximum(d_cur + d_dep, 1e-12)
    savings_ratio = (d_dep - d_cur) / denom  # in [-1, 1]

    # Capacity fill factor: prefer candidates whose demand nearly fills remaining cap.
    # Use (1 - load_frac) so a full-fit candidate (load_frac ~ 1) drives factor toward 0.
    fill = 1.0 - load_frac  # in [0, 1]

    # Dimensionless score: base unit-distance (divide out by d_cur + d_dep),
    # then discount by savings_ratio and penalize by fill factor.
    # score = normalized distance * (1 - savings_ratio) * (1 + fill)
    # All terms dimensionless -> invariant to instance scale.
    base = d_cur / denom  # in [0, 1]
    score = base * (1.0 - savings_ratio) * (1.0 + fill)

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])