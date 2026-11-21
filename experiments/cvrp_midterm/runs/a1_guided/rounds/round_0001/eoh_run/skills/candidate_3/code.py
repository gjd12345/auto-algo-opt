def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if unvisited_nodes.size == 0:
        return depot

    cur = distance_matrix[current_node][unvisited_nodes]
    dep = distance_matrix[depot][unvisited_nodes]
    base = cur - 0.6 * dep

    best_idx = int(np.argmin(base))
    best_score = base[best_idx]

    span = float(np.max(base) - np.min(base))
    band = 1e-3 * (span + 1e-12)

    # Widen the gate at unit scale so refinement fires more often
    # (relative band stays scale-free; widen factor helps small-span cases).
    if span > 0.0:
        rel_gap = band / span
        if rel_gap < 1e-2:
            band = 1e-2 * span

    tied = np.where(base <= best_score + band)[0]
    if tied.size <= 1:
        return int(unvisited_nodes[best_idx])

    # Refine: prefer better capacity fit (smaller demand relative to capacity),
    # secondary tie-break by slightly preferring closer customers.
    tied_nodes = unvisited_nodes[tied]
    cap = rest_capacity if rest_capacity > 0 else 1.0
    fit = demands[tied_nodes] / cap
    # Combined refinement: capacity fit primarily, then base distance.
    refine = fit + 1e-6 * base[tied]
    pick = int(tied[int(np.argmin(refine))])
    return int(unvisited_nodes[pick])