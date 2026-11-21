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
    to_depot = distance_matrix[unvisited_nodes, depot]
    stem = float(distance_matrix[current_node, depot])
    # Savings from replacing the current->depot leg with current->node->depot.
    savings = stem + to_depot - cur
    # Scale-free normaliser: the smaller of the two replaced legs (cur, to_depot).
    # Using the min keeps the ratio bounded and independent of coordinate scale.
    denom = np.minimum(cur, to_depot) + 1e-12
    base = savings / denom
    # Demand-pressure multiplier: prefer candidates that fill remaining capacity.
    cap = rest_capacity if rest_capacity > 1e-12 else 1.0
    dem = demands[unvisited_nodes] / cap
    # Saturating factor in (0, 1]: approaches 1 as demand fills capacity.
    pressure = dem / (1.0 + dem)
    score = base * (1.0 + pressure)
    return int(unvisited_nodes[int(np.argmax(score))])