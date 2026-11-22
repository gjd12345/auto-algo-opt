def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 0:
        return depot

    # Compute savings: distance(current_node, depot) + distance(depot, candidate) - distance(current_node, candidate)
    from_depot = distance_matrix[depot][unvisited_nodes]
    from_current = distance_matrix[current_node][unvisited_nodes]
    depot_to_current = distance_matrix[depot][current_node] if current_node != depot else 0.0
    savings = depot_to_current + from_depot - from_current

    # Capacity pressure: prefer customers that fit well into remaining capacity
    # Higher pressure when rest_capacity is small relative to demand
    capacity_pressure = 1.0 - (demands[unvisited_nodes] / rest_capacity)
    capacity_pressure = np.clip(capacity_pressure, 0.0, 1.0)

    # Combine: prioritize high savings and low capacity pressure, with balance weight
    weight_savings = 0.7
    weight_capacity = 0.3
    scores = weight_savings * savings + weight_capacity * capacity_pressure

    # Select the candidate with the highest score
    best_idx = unvisited_nodes[np.argmax(scores)]
    return best_idx
