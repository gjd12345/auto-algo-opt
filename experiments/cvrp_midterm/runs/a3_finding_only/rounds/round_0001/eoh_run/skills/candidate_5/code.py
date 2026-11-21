def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """Select the next node to visit in a CVRP greedy construction."""
    if len(unvisited_nodes) == 0:
        return 0
    
    cur_dist = distance_matrix[current_node][unvisited_nodes]
    depot_dist = distance_matrix[depot][unvisited_nodes]
    node_demands = demands[unvisited_nodes]
    
    # Span-proportional normalization (scale invariant)
    dmax = np.max(cur_dist) if np.max(cur_dist) > 0 else 1.0
    ddmax = np.max(depot_dist) if np.max(depot_dist) > 0 else 1.0
    dtotal = dmax + ddmax if (dmax + ddmax) > 0 else 1.0
    
    # Weighted combination: closer to current + not too far from depot
    score = (cur_dist / dtotal) + 0.5 * (depot_dist / dtotal)
    
    # Load regulation: prefer larger demands when capacity is tight (fill vehicle well)
    # Only active when remaining capacity is close to serving remaining options
    if rest_capacity > 0:
        # Scale-invariant load factor: fraction of remaining capacity used
        cap = rest_capacity if rest_capacity > 0 else 1.0
        load_frac = node_demands / cap
        # Slight bonus to higher-demand customers to reduce vehicle count
        score = score - 0.1 * load_frac
    
    return int(unvisited_nodes[np.argmin(score)])