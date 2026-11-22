import numpy as np

def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if current_node == depot or len(unvisited_nodes) == 0:
        if len(unvisited_nodes) == 0:
            return depot
        dists = distance_matrix[depot][unvisited_nodes]
        return unvisited_nodes[np.argmax(dists)]

    best_node = None
    best_regret = -1.0

    for u in unvisited_nodes:
        insertion_costs = []
        # Candidate insertion positions: before current_node or after current_node
        # (since route is just current_node -> next, we consider cost of inserting u)
        # Insertion cost = distance(current_node, u) + distance(u, depot) - distance(current_node, depot)
        cost_direct = distance_matrix[current_node][u] + distance_matrix[u][depot] - distance_matrix[current_node][depot]
        insertion_costs.append(cost_direct)
        # Also consider inserting after u and returning to depot (if u becomes new current)
        # But for regret we use nearest and second nearest among all possible insertion points
        # Simplified: use cost_direct as main, also consider if there are other unvisited
        # Build list of insertion costs for this u relative to current_node and other unvisited
        # Actually compute insertion cost into the current partial route segment (current_node -> depot)
        base_cost = distance_matrix[current_node][depot]
        insert_cost_after = distance_matrix[current_node][u] + distance_matrix[u][depot] - base_cost
        # For regret, also consider inserting u into a hypothetical future route from depot
        future_cost = distance_matrix[depot][u] + distance_matrix[u][depot]  # round trip
        # Regret = difference between best insertion in current route vs best alternative
        best_in_current = insert_cost_after
        best_alternative = future_cost  # alternative: serve u in a separate route
        regret = best_alternative - best_in_current

        if regret > best_regret:
            best_regret = regret
            best_node = u

    if best_node is None:
        return unvisited_nodes[0]
    return best_node
