# EoH adapter: TSP 2-opt — select_2opt_move

Registered problem_id: `tsp_2opt`.

Only improving 2-opt candidates are offered. Not Lin-Kernighan.

Plan JSON cannot contain a `code` field. Put the mechanism in `operations[].mechanism`. If a later seed is required, use `explicit_seeds` and label it as an adapter, not the original paper algorithm.

```python
def select_2opt_move(tour: np.ndarray, distance_matrix: np.ndarray,
                     move_start: np.ndarray, move_end: np.ndarray,
                     move_delta: np.ndarray, remaining_moves: int) -> int:
    """TSP 2-opt move selector. Candidates are already improving 2-opt moves.

    Return an index into move_start/move_end/move_delta. This is not Lin-Kernighan
    variable-depth search and not Or-opt/3-opt unless those moves are in the list.
    """
    # mechanism: pick among improving 2-opt deltas
    return int(np.argmin(move_delta))
```
