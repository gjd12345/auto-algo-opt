def select_next_node(current_node: int, destination_node: int, unvisited_nodes: np.ndarray, distance_matrix: np.ndarray) -> int:
    n_remaining = len(unvisited_nodes)
    if n_remaining <= 3:
        return unvisited_nodes[np.argmin(distance_matrix[current_node][unvisited_nodes])]

    dist_current = distance_matrix[current_node][unvisited_nodes] + 1e-10
    rec_dist = 1.0 / dist_current

    # Compute direction vectors from current_node to each unvisited node
    # Use distances from distance matrix as proxies for directions (assumes nodes have coordinates accessible via some index mapping)
    # We'll approximate angular dispersion by computing pairwise cosine similarities between candidate vectors
    # Since we don't have coordinates, use distance correlations: for each candidate, compute mean cosine similarity with all others
    n_nodes = distance_matrix.shape[0]
    all_nodes = np.arange(n_nodes)
    # Get distances from current_node to all nodes
    d_from_current = distance_matrix[current_node]
    # For each candidate, approximate vector: use distances from candidate to others as feature
    vectors = np.array([distance_matrix[u] - d_from_current for u in unvisited_nodes])
    # Normalize
    norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10
    vectors = vectors / norms
    # Compute mean cosine similarity of each vector with all others
    sim_matrix = vectors @ vectors.T
    np.fill_diagonal(sim_matrix, 0)
    mean_sim = np.sum(sim_matrix, axis=1) / (n_remaining - 1)
    # Angular dispersion: low similarity -> high dispersion
    dispersion = 1.0 - mean_sim
    dispersion = np.maximum(dispersion, 1e-10)

    scores = rec_dist * dispersion
    return unvisited_nodes[np.argmax(scores)]
