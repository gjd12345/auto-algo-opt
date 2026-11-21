def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)

    # Scale-normalised components using current-leg span for invariance.
    span = float(np.max(d_cur) - np.min(d_cur)) if d_cur.size > 1 else 0.0
    norm = span + 1e-12

    dep_span = float(np.max(d_dep) - np.min(d_dep)) if d_dep.size > 1 else 0.0
    dep_norm = dep_span + 1e-12

    d_cur_n = d_cur / norm
    d_dep_n = d_dep / dep_norm

    # Multiplicative savings-style penalty: near customers that are also near
    # the depot are strongly preferred; far-from-depot customers are penalised
    # super-linearly through the product term.
    beta = 0.35
    score = d_cur_n * (1.0 + beta * d_dep_n)

    # Fill-aware demand bonus: reward large demand that fits snugly into the
    # remaining capacity, encouraging better vehicle packing.
    dem = demands[unvisited_nodes].astype(float)
    cap = float(rest_capacity) if rest_capacity > 0.0 else 1.0
    fill = np.clip(dem / cap, 0.0, 1.0)
    score = score - 1e-6 * fill

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])