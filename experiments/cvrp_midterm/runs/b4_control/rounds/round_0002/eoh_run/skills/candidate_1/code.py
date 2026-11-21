def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if unvisited_nodes.size == 0:
        return depot

    cap = float(rest_capacity)
    if cap <= 0.0:
        return depot

    d_cur = distance_matrix[current_node][unvisited_nodes]
    d_dep = distance_matrix[depot][unvisited_nodes]
    d_cd = float(distance_matrix[current_node][depot])
    dem = demands[unvisited_nodes].astype(float)

    # Clarke-Wright savings of inserting candidate between current node and depot
    savings = d_cd + d_dep - d_cur

    # Fill ratio after serving the candidate
    fill = (cap - dem) / cap

    # Prefer high savings, low remaining return cost, and good packing
    score = savings - 0.25 * d_dep + 0.5 * fill
    return int(unvisited_nodes[np.argmax(score)])