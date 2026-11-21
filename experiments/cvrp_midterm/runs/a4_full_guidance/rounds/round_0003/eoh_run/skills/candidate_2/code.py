def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    eps = 1e-9
    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]

    # Polar-angle term: use squared distances to form a scale-free cosine
    # between the radial direction of each candidate and the current node.
    # cos_theta = (d_cur^2 + d_dep^2 - d_between^2) / (2 * d_cur * d_dep),
    # but we avoid the between-leg by using a triangle-free proxy: the ratio
    # d_dep / (d_cur + d_dep) measures how "outward" the candidate sits
    # relative to the current position. Higher means more radially aligned.
    radial = d_dep / (d_cur + d_dep + eps)

    # Angular pressure: preferred candidates are those whose depot-distance
    # is close to the current node's depot-distance (same radial shell),
    # which keeps routes from zig-zagging across shells.
    cur_dep = distance_matrix[depot][current_node]
    shell = np.abs(d_dep - cur_dep) / (cur_dep + d_dep + eps)

    # Primary score combines outward alignment against shell mismatch.
    score = radial - 0.5 * shell

    s_max = np.max(score)
    s_min = np.min(score)
    span = s_max - s_min
    tol = 0.05 * span
    near = score >= (s_max - tol)
    candidates = unvisited_nodes[near]
    if candidates.size == 0:
        candidates = unvisited_nodes

    cand_cur = distance_matrix[current_node][candidates]
    best = candidates[int(np.argmin(cand_cur))]
    return int(best)