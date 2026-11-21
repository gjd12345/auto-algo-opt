def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) + 1e-9

    # relative quantities (scale-invariant)
    scale = d_cur + d_dep + 1e-9
    near_frac = d_cur / scale          # how close to current node (0..1)
    depot_frac = d_dep / scale         # how close to depot (0..1)

    # capacity fill: prefer candidates whose demand fits snugly (low residual after serving)
    residual_frac = np.clip((cap - dem) / cap, 0.0, 1.0)

    # combine: prioritize proximity to current node, moderately penalize depot pull,
    # and penalize leaving a large relative residual capacity
    score = 1.0 * near_frac + 0.35 * depot_frac + 0.9 * residual_frac

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])