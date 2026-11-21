def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Scale-aware combination: pull toward close customers that are also near depot.
    # Use span-normalised score so behaviour is invariant to coordinate scale.
    span = float(np.max(d_cur) - np.min(d_cur)) if d_cur.size > 1 else 0.0
    norm = span + 1e-12

    # Weight depot-distance term; sign favours smaller d_dep (closer to depot).
    alpha = 0.6
    score = (d_cur - alpha * d_dep) / norm

    # Small deterministic tie-breaker: prefer higher demand served now (better packing).
    # Added at relative magnitude well below score resolution.
    dem = demands[unvisited_nodes].astype(float)
    dem_max = float(np.max(dem)) if dem.size > 0 else 1.0
    dem_norm = dem / (dem_max + 1e-12)
    score = score - 1e-9 * dem_norm

    idx = int(np.argmin(score))
    return int(unvisited_nodes[idx])