def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    current_node = int(current_node)
    depot = int(depot)
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=int)

    if unvisited_nodes.size == 0:
        return depot

    demand = demands[unvisited_nodes].astype(float)
    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_depot_u = distance_matrix[depot][unvisited_nodes].astype(float)
    d_depot_cur = float(distance_matrix[depot][current_node])

    cap = float(rest_capacity)

    # Clarke-Wright savings of serving u on the current leg instead of a
    # separate depot round-trip, adjusted for the detour from the current node.
    savings = d_depot_cur + d_depot_u - d_cur

    # Regret-style: how much worse would it be to defer u (the "later" cost
    # is approximated by pure depot round-trip, scaled by remaining slack).
    slack = np.maximum(cap - demand, 0.0) / max(cap, 1e-9)
    regret = savings / (slack + 1e-6)

    # Slight preference for larger fill when regrets tie, to reduce leftover waste.
    fill = demand / max(cap, 1e-9)

    score = regret + 0.05 * fill

    return int(unvisited_nodes[np.argmax(score)])