def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    dem = demands[unvisited_nodes].astype(float)

    cap = rest_capacity if rest_capacity > 1e-12 else 1e-12

    # distance term: blend of distance to current node and distance to depot
    # (both are lengths in the same units, so the blend stays scale-free)
    w = 0.5
    dist_term = d_cur + w * d_dep

    # relative fill term: fraction of remaining capacity consumed (scale-free)
    fill_term = dem / cap

    # primary score: prefer close nodes, penalise large relative draws
    # weight on fill is small so distance dominates; scale-free
    scale = np.mean(dist_term) if dist_term.size else 1.0
    if scale <= 1e-12:
        scale = 1.0

    primary = dist_term + 0.1 * scale * fill_term

    # secondary ordering: among near-ties, use savings (2*depot - d_cur - d_dep)
    order = np.argsort(primary)
    best_idx = order[0]
    if primary.size > 1:
        tol = 1e-9 * scale + 0.0
        # near-tie gate that is relative to scale (scale-invariant)
        gate = 0.02 * scale
        near = np.where(primary <= primary[best_idx] + gate)[0]
        if near.size > 1:
            savings = 2.0 * d_dep[near] - d_cur[near] - d_dep[near]
            best_idx = near[np.argmax(savings)]

    return int(unvisited_nodes[best_idx])