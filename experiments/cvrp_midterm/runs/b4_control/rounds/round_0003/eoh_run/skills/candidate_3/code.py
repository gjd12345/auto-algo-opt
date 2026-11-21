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

    # Detour saving of inserting the customer on the current route rather
    # than serving it via a separate depot round-trip.
    saving = d_dep - d_cur
    saving = np.maximum(saving, 0.0) + d_dep

    # Efficiency: saving per unit demand, damped by remaining capacity usage.
    demand_ratio = dem / (cap + 1e-9)
    efficiency = saving / (dem + 1e-9)

    # Fill pressure: prefer using more capacity when close to full.
    load_util = 1.0 - demand_ratio

    # Blend efficiency with a mild nearest-neighbor pull.
    score = -(efficiency * (0.5 + 0.5 * load_util)) + 0.15 * d_cur / (d_dep + 1e-9)

    return int(unvisited_nodes[np.argmax(score)])