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
        return depot

    nodes = np.asarray(unvisited_nodes)
    d_cur = distance_matrix[current_node][nodes].astype(np.float64)
    d_dep = distance_matrix[depot][nodes].astype(np.float64)
    dem = demands[nodes].astype(np.float64)

    dmin = float(np.min(d_cur))
    dmax = float(np.max(d_cur)) if d_cur.size > 1 else dmin + 1.0
    span = dmax - dmin

    cap = float(rest_capacity) if rest_capacity > 0 else 1.0

    # Adaptive near-cluster shell: tight when already moving, wider from depot.
    if current_node == depot:
        tol_frac = 0.35
    else:
        tol_frac = 0.15
    tol = dmin + tol_frac * span + 1e-9

    mask = d_cur <= tol
    if not np.any(mask):
        mask = np.ones_like(d_cur, dtype=bool)

    # Center of mass of candidate positions in "distance-from-depot" space
    # gives a radial reference; penalize being on the far edge of the shell.
    shell_dep = d_dep[mask]
    ref = float(np.mean(shell_dep)) if shell_dep.size > 0 else 0.0
    spread = float(np.std(shell_dep)) if shell_dep.size > 0 else 1.0
    if spread <= 1e-9:
        spread = 1.0

    # Demand capture, normalized by remaining capacity and pushed toward
    # efficiently closing out capacity (mild superlinear in fill).
    fill = np.clip(dem / cap, 0.0, 1.0)
    demand_gain = fill * (1.0 + fill)  # in [0, 2]

    # Radial deviation: prefer nodes near the shell's radial center, slight
    # preference to farther nodes to avoid stranding them early.
    radial_dev = (d_dep - ref) / spread
    radial_term = 1.0 - 0.15 * np.minimum(np.abs(radial_dev), 3.0) \
                  + 0.05 * np.clip(radial_dev, -1.0, 1.0)

    # Distance penalty within the near shell: shorter hops preferred but not
    # dominant — let demand and radial shape the choice.
    prox = 1.0 - 0.5 * (d_cur - dmin) / (tol - dmin + 1e-9)
    prox = np.clip(prox, 0.0, 1.0)

    score = demand_gain * radial_term * (0.5 + 0.5 * prox)
    score = np.where(mask, score, -np.inf)

    idx = int(np.argmax(score))
    return int(nodes[idx])