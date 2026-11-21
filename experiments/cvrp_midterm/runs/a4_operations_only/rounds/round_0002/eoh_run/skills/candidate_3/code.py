def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    max_dep = float(np.max(dep)) if dep.size > 0 else 1.0
    if max_dep <= 0.0:
        max_dep = 1.0

    cap = float(rest_capacity) if rest_capacity > 0.0 else 1e-9

    # Closeness ratio: how much of the tour leg is spent closing on the depot.
    # 1 means the candidate is on the direct path away from current toward depot;
    # large values mean the candidate is "forward" relative to the depot direction.
    leg = cur + 1e-9
    forward = (cur + dep) / leg  # in [1, ...], reward forward progress

    # Route-balance reward: prefer candidates that leave a small residual gap
    # relative to capacity, scaled by their demand (fills vehicles evenly).
    residual = cap - dem
    balance = 1.0 - (residual / cap) ** 2  # in [0,1], 1 = tight fit

    # Depot-relative pull: slightly prefer candidates near the depot for the
    # end-of-tour effect, normalized so scale is comparable across instances.
    depot_pull = dep / max_dep

    # Single additive score: maximize (we take negative for argmin-style choice)
    score = forward + 2.0 * balance - 0.25 * depot_pull

    return int(unvisited_nodes[int(np.argmax(score))])