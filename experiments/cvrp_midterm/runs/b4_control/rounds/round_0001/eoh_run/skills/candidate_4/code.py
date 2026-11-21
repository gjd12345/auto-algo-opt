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
    # Distance from current node to each candidate
    d_cur = distance_matrix[current_node][unvisited_nodes]
    # Distance from each candidate back to the depot
    d_dep = distance_matrix[depot][unvisited_nodes]
    # Demand of each candidate
    dem = demands[unvisited_nodes]

    # Score: prefer close nodes, but also prefer nodes that are far from depot
    # (so we don't leave far-away nodes for later, which increases distance),
    # and prefer nodes that use up more capacity when capacity is tight.
    # Normalize demand component by current remaining capacity.
    cap = max(rest_capacity, 1e-9)
    demand_ratio = dem / cap

    # Weighted combination (tuned for balance)
    score = d_cur - 0.3 * d_dep + 5.0 * demand_ratio

    # Return candidate with minimum score
    return int(unvisited_nodes[np.argmin(score)])