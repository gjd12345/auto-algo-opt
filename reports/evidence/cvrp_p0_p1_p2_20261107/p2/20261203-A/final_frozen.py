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
    d_cur_depot = distance_matrix[current_node][depot]

    savings = d_cur_depot + to_depot - cur

    dem = demands[unvisited_nodes].astype(float)
    cap = max(float(rest_capacity), 1e-12)
    fill_bonus = (dem / cap) * (d_cur_depot + 1e-9) * 0.5

    depot_penalty = to_depot * 0.15

    scores = savings + fill_bonus - depot_penalty

    return int(unvisited_nodes[int(np.argmax(scores))])