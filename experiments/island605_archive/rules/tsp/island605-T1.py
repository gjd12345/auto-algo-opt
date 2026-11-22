def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    if len(unvisited_nodes) == 1:
        return unvisited_nodes[0]
    
    dists = distance_matrix[current_node][unvisited_nodes]
    best_idx = np.argmin(dists)
    n_remaining = len(unvisited_nodes)
    
    if n_remaining == 2:
        return unvisited_nodes[best_idx]
    
    scores = np.zeros(n_remaining)
    for i, u in enumerate(unvisited_nodes):
        direct_cost = dists[i]
        
        # Regret: difference between worst and best insertion into remaining route
        remaining = unvisited_nodes[unvisited_nodes != u]
        if len(remaining) >= 3:
            # Simulate nearest neighbor tour from u back to destination
            sim_current = u
            tour_cost = 0.0
            rem_sim = remaining.copy()
            while len(rem_sim) > 0:
                sim_dists = distance_matrix[sim_current][rem_sim]
                nidx = np.argmin(sim_dists)
                tour_cost += sim_dists[nidx]
                sim_current = rem_sim[nidx]
                rem_sim = np.delete(rem_sim, nidx)
            tour_cost += distance_matrix[sim_current][destination_node]
            
            # Compute best and worst local connections from current_node to remaining
            local_dists = distance_matrix[current_node][remaining]
            sorted_local = np.sort(local_dists)
            best_local = sorted_local[0]
            worst_local = sorted_local[-1]
            regret = worst_local - best_local
        else:
            tour_cost = distance_matrix[u][destination_node]
            regret = 0.0
        
        # 2-opt awareness: penalize edges that are much longer than median neighbor distance
        neighbors = distance_matrix[current_node]
        positive = neighbors[neighbors > 0]
        median_neighbor = np.median(positive) if len(positive) > 0 else 1.0
        penalty = max(0, direct_cost - 1.5 * median_neighbor) / (median_neighbor + 1e-9)
        
        # Dynamic weights: as fewer nodes remain, weight direct cost more
        w_direct = 1.0 + 0.5 * (1.0 - n_remaining / len(distance_matrix))
        w_tour = 0.6 * (n_remaining / len(distance_matrix))
        w_regret = 0.4 * (n_remaining / len(distance_matrix))
        w_penalty = 0.2
        
        scores[i] = w_direct * direct_cost + w_tour * tour_cost - w_regret * regret + w_penalty * penalty
    
    if np.max(scores) - np.min(scores) < 1e-9:
        return unvisited_nodes[best_idx]
    return unvisited_nodes[np.argmin(scores)]