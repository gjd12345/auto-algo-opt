def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction.

    Args:
        current_node:    index of the current node (0 = depot)
        depot:           index of the depot (always 0)
        unvisited_nodes: array of feasible unvisited customer indices
                         (already filtered to satisfy remaining capacity)
        rest_capacity:   remaining vehicle capacity
        demands:         demand of every node (index 0 = depot demand = 0)
        distance_matrix: pairwise Euclidean distance matrix
    Returns:
        Index of the next node to visit, or 0 to return to the depot early.
    """
    if unvisited_nodes.size == 0:
        return 0

    nodes = np.asarray(unvisited_nodes)
    dem = demands[nodes].astype(float)

    d_cur = distance_matrix[current_node][nodes].astype(float)
    d_dep = distance_matrix[depot][nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])

    d_all = distance_matrix[nodes][:, nodes].astype(float)
    scale = float(np.max(d_all)) if d_all.size > 0 else 1.0
    if scale <= 0.0:
        scale = 1.0

    rest = float(rest_capacity)
    if rest <= 0.0:
        rest = 1.0

    if current_node == depot:
        # Seed: minimal normalized radial distance while favoring larger demands
        # (fill quickly so routes terminate early and depot pull dominates less).
        # Use a "route elongation" view: going depot->j creates triangle with
        # depot->depot = 0, so elongated = d_dep. Blend in load fraction.
        rel_dem = dem / rest
        rel_dist = d_dep / scale
        score = rel_dist - 0.35 * rel_dem
        return int(nodes[int(np.argmin(score))])

    # Route-elongation criterion at mid-route:
    # Going from i (current) to j extends the open route by d(i,j) but avoids
    # returning i->depot and starting depot->j, i.e. the savings leg.
    # Define elongation ratio rho = d(i,j) / (d(0,i) + d(0,j)):
    # small rho => j lies nearly on the depot triangle => good detour.
    axis = d_cur_dep + d_dep
    rho = d_cur / np.maximum(axis, 1e-12)

    # Residual-capacity acceptance: prefer j whose demand does not leave a
    # large stranded remainder relative to rest (soft, dimensionless).
    resid = rest - dem
    resid_frac = resid / rest  # in [0,1]; 0 means perfect fill
    fill_bonus = -0.10 * (1.0 - np.minimum(np.abs(resid_frac), 1.0))

    # Elongation growth: also penalize length consumed relative to scale.
    grow = 0.05 * (d_cur / scale)

    score = rho + fill_bonus + grow
    best_k = int(np.argmin(score))

    # Voluntary early-return gate: if the chosen detour is a poor triangle
    # extension (rho too large), go home instead of bridging to a far node.
    # rho close to 1 means d(i,j) ~ d(0,i)+d(0,j): node lies opposite depot.
    tau = 0.72
    if float(rho[best_k]) > tau:
        return 0

    return int(nodes[best_k])