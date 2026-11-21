def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    # Triangle-inequality detour ratio in [0, 1]: fraction of the roundtrip
    # through the current node that is "spent" getting from current to node.
    # Scale-invariant by construction (ratio of same-unit distances).
    eps = 1e-12
    detour_ratio = d_cur / (d_cur + d_dep + eps)

    # Directness ratio: prefer nodes close to the depot (small depot leg)
    # relative to the current leg; also scale-invariant.
    direct_ratio = d_dep / (d_cur + d_dep + eps)

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Capacity pressure: how much filling this node relieves the need to
    # return soon. Emphasize nodes whose demand uses a big share of the
    # remaining capacity (they are harder to place later).
    fill = np.clip(dem / cap, 0.0, 1.0)
    # Residual capacity fraction after serving this node.
    residual = np.clip((cap - dem) / cap, 0.0, 1.0)

    # Multiplicative score: minimize detour_ratio, weakly trade off with
    # a depot-proximity term, and penalize leaving awkward residuals.
    geom = (detour_ratio ** 2) * (direct_ratio ** 0.5)
    pressure = 1.0 / (0.5 + fill)  # rewards using capacity well
    penalty = 1.0 + 0.25 * residual  # mild penalty for leaving slack

    score = geom * pressure * penalty
    idx = np.argmin(score)
    return int(unvisited_nodes[idx])