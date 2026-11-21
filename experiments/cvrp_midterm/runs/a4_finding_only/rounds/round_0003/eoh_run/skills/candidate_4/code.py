def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale reference: max depot-customer distance (linear in instance scale)
    scale = np.max(d_dep)
    if scale <= 0:
        scale = 1.0

    d_cur_n = d_cur / scale
    d_dep_n = d_dep / scale

    # Clarke-Wright style savings, normalized by insertion length
    savings = d_dep_n + d_dep_n - d_cur_n  # = 2*d_dep_n - d_cur_n
    eps = 1e-9
    savings_ratio = savings / (d_cur_n + eps)

    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0 else 1.0
    mean_dem = np.mean(dem) if len(dem) > 0 else 1.0
    if mean_dem <= 0:
        mean_dem = 1.0
    fit = 1.0 - np.abs(dem - cap * 0.5) / cap  # prefer mid-fill, then closer to full
    # blend absolute fill fraction with relative demand consistency
    util = dem / cap
    fit_score = 0.5 * fit + 0.5 * util

    # Priority: maximize savings ratio, boost by load fit
    score = savings_ratio + 0.4 * fit_score

    idx = int(np.argmax(score))
    best = int(unvisited_nodes[idx])

    # Guard: if returning to depot is cheaper than a detour, do so early
    if d_cur_n[idx] > 2.0 * d_dep_n[idx]:
        return depot

    return best