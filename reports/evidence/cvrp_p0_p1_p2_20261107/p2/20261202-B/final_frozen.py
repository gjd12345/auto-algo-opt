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

    cur = distance_matrix[current_node][unvisited_nodes]
    to_depot = distance_matrix[depot][unvisited_nodes]
    savings = distance_matrix[current_node][depot] + to_depot - cur

    d_cur_depot = distance_matrix[current_node][depot]
    if d_cur_depot < 1e-12:
        d_cur_depot = 1e-12
    nn_term = 1.0 - cur / d_cur_depot

    d = demands[unvisited_nodes]
    cap = rest_capacity if rest_capacity > 1e-12 else 1e-12
    fill_term = d / cap

    score = savings / (d_cur_depot + 1e-12) + 0.5 * nn_term + 0.5 * fill_term

    return int(unvisited_nodes[np.argmax(score)])