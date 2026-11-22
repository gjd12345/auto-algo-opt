def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    candidates = unvisited_nodes
    n = len(candidates)
    if n == 1:
        return candidates[0]

    best_score = float('inf')
    best_idx = 0

    for i, candidate in enumerate(candidates):
        direct_cost = distance_matrix[current_node][candidate]
        # Simulate: from candidate, do a greedy nearest-neighbor tour through remaining unvisited
        remaining = np.delete(candidates, i)
        if len(remaining) == 0:
            round_trip = direct_cost + distance_matrix[candidate][destination_node]
        else:
            tour_cost = 0
            curr = candidate
            rem_set = set(remaining)
            while rem_set:
                rem_arr = np.array(list(rem_set))
                next_idx = np.argmin(distance_matrix[curr][rem_arr])
                next_node = rem_arr[next_idx]
                tour_cost += distance_matrix[curr][next_node]
                curr = next_node
                rem_set.remove(next_node)
            tour_cost += distance_matrix[curr][destination_node]
            round_trip = direct_cost + tour_cost

        score = round_trip
        if score < best_score:
            best_score = score
            best_idx = i

    return candidates[best_idx]
