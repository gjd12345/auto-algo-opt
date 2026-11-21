def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    dem = demands[unvisited_nodes].astype(float)

    # Geometric proxy for angular position: use squared distances to build a
    # cosine-like quantity via the law of cosines with the depot as origin.
    d_cd = float(distance_matrix[current_node][depot])
    denom = 2.0 * max(d_cd, 1e-9) * np.maximum(d_dep, 1e-9)
    cos_theta = (d_cd * d_cd + d_dep * d_dep - d_cur * d_cur) / denom
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    # Prefer continuing in the current rotational sense: choose direction that
    # reduces angular deviation (i.e. larger cosine means more "ahead").
    angular_score = cos_theta

    # Radial continuity: prefer candidates whose depot-distance is close to the
    # current node's depot distance (keeps the route sweeping, not zig-zagging).
    r_cur = float(distance_matrix[depot][current_node])
    radial_gap = np.abs(d_dep - r_cur) / (r_cur + 1e-9)

    # Light load term: mildly favor filling the vehicle.
    load_frac = (cap - dem) / cap

    score = angular_score - 0.35 * radial_gap + 0.10 * load_frac
    return int(unvisited_nodes[np.argmax(score)])