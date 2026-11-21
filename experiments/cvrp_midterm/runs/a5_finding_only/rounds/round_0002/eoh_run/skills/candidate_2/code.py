def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    unv = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][unv].astype(float)
    d_dep = distance_matrix[depot][unv].astype(float)
    dem = demands[unv].astype(float)
    cap = float(rest_capacity) + 1e-9

    # Savings form: how much we save by chaining current->cand->depot
    # instead of current->depot->cand (classic Clarke-Wright saving).
    d_cur_dep = float(distance_matrix[current_node][depot])
    saving = d_cur_dep + d_dep - d_cur

    # Rank-based normalization (scale-free, robust to coordinate scale).
    n = len(unv)
    order_cur = np.argsort(np.argsort(d_cur)).astype(float)
    order_sav = np.argsort(np.argsort(-saving)).astype(float)  # higher saving -> smaller rank
    order_dem = np.argsort(np.argsort(-dem)).astype(float)     # higher demand -> smaller rank
    rank_norm = 1.0 / max(float(n - 1), 1.0)

    r_cur = order_cur * rank_norm      # 0 = closest
    r_sav = order_sav * rank_norm      # 0 = best saving
    r_dem = order_dem * rank_norm      # 0 = highest demand

    load_frac = np.clip(dem / cap, 0.0, 1.0)
    # Favor high-demand items early when capacity is plentiful.
    fill = (1.0 - r_dem) * (1.0 - 0.5 * load_frac)

    score = 0.55 * r_sav + 0.30 * r_cur - 0.40 * fill
    idx = int(np.argmin(score))
    return int(unv[idx])