import numpy as np

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
    if len(unvisited_nodes) == 0:
        return depot

    # Compute regret for each unvisited node
    # Regret = difference between best insertion cost and second-best insertion cost
    # Insertion cost = distance from current to node + distance from node to next preferred start

    # For each candidate, consider two alternatives:
    # 1) Serve now: cost = distance_matrix[current_node][candidate]
    # 2) Defer and start a new route from depot: cost = distance_matrix[current_node][depot] + distance_matrix[depot][candidate]

    now_costs = distance_matrix[current_node][unvisited_nodes]
    defer_costs = distance_matrix[current_node][depot] + distance_matrix[depot][unvisited_nodes]

    # If we serve now, the alternative is either deferring or going to another customer first
    # We compute a simple regret: min(now_cost, defer_cost) vs second best option
    costs = np.column_stack((now_costs, defer_costs))
    sorted_costs = np.sort(costs, axis=1)
    regrets = sorted_costs[:, 1] - sorted_costs[:, 0]  # difference between second best and best

    # If at depot, prefer farthest to seed route
    if current_node == depot:
        dists_from_depot = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists_from_depot)]

    # Select customer with maximum regret
    best_idx = np.argmax(regrets)
    best_customer = unvisited_nodes[best_idx]

    # Early return if returning to depot is cheaper than going to best customer
    if distance_matrix[current_node][depot] < distance_matrix[current_node][best_customer]:
        return depot

    return best_customer
