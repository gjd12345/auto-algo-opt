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
    stem = distance_matrix[current_node, depot]
    # Savings if we insert this customer via the depot stem
    savings = stem + to_depot - cur
    # Utilization weighting: full vehicle favors far customers
    load = demands[unvisited_nodes]
    total_demand = float(np.sum(demands))
    util = 1.0 - rest_capacity / (total_demand + 1e-12)
    util = float(np.clip(util, 0.0, 1.0))
    weight = 1.0 + util * to_depot / (stem + 1e-12)
    score = weight * savings / (stem + 1e-12)
    return int(unvisited_nodes[np.argmax(score)])