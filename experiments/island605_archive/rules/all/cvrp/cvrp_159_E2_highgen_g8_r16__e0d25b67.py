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
    import numpy as np

    best_node = unvisited_nodes[0]
    best_savings = -np.inf

    for u in unvisited_nodes:
        # Savings = dist(depot, u) + dist(current, depot) - dist(current, u)
        savings = distance_matrix[depot][u] + distance_matrix[current_node][depot] - distance_matrix[current_node][u]
        # Deterministic tie-break using node index as tiny perturbation
        savings += 1e-9 * u
        if savings > best_savings:
            best_savings = savings
            best_node = u

    return best_node
