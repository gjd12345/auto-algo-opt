def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    current_node = int(current_node)
    depot = int(depot)
    unvisited_nodes = np.asarray(unvisited_nodes, dtype=int)
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes].astype(float)
    d_dep = distance_matrix[depot][unvisited_nodes].astype(float)
    d_cur_dep = float(distance_matrix[current_node][depot])
    demand = demands[unvisited_nodes].astype(float)

    # Clarke-Wright style savings: benefit of linking current -> node -> depot
    # instead of current -> depot plus node -> depot separately.
    savings = d_cur_dep + d_dep - d_cur

    # Fill ratio in [0,1]; larger chunks reduce route count pressure.
    fill = np.clip(demand / (cap + 1e-12), 0.0, 1.0)

    # Urgency: far-from-depot and high-fill customers are cheaper to merge now.
    urgency = 1.0 + fill

    # Composite benefit to maximize.
    benefit = savings * urgency

    return int(unvisited_nodes[np.argmax(benefit)])