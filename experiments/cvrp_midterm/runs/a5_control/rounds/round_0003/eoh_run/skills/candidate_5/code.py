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

    cap = max(float(rest_capacity), 1e-9)

    # Savings from inserting u on the current leg vs a fresh depot round-trip.
    savings = d_depot_cur + d_depot_u - d_cur

    # Efficiency: savings per unit of incremental travel.
    efficiency = savings / (d_cur + 1e-6)

    # Load-tightness: prefer customers that reduce remaining slack significantly.
    tightness = demand / cap

    # Slack-aware depot return penalty: if slack is large, push to fill it.
    slack = (cap - demand) / cap
    slack_penalty = 1.0 / (slack + 1e-3)

    score = efficiency * (1.0 + 0.4 * tightness) + 0.2 * slack_penalty * tightness

    return int(unvisited_nodes[np.argmax(score)])