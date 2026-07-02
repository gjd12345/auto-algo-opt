# Solomon I1 Sequential Insertion Heuristic

**Source:** Solomon, M.M. (1987). "Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints." *Operations Research*, 35(2), 254-265.

**Best for:** Medium-to-high density. Balances distance cost vs. time/delay cost with weighted criteria. The standard constructive heuristic for VRPTW.

## Core Insertion Criterion

For inserting unrouted customer `u` between adjacent positions `i` and `j` in the current route:

```
score(i,u,j) = w1 * d(0,u) - w2 * c11(i,u,j) - w3 * c12(i,u,j)

where:
  d(0,u)  = distance from depot to u (reward for serving far-away orders)
  c11     = d(i,u) + d(u,j) - μ * d(i,j)   (added travel distance)
  c12     = bj_new - bj                      (time push-forward at j)

  w1 = α1, w2 = α2, w3 = λ * (1 - α1 - α2)
  Recommended: μ=1, λ=1, α1=1, α2=0  →  w1=1, w2=0, w3=0
  (Simplest form: maximize d(0,u), minimize insertion distance)
```

## Pseudocode (Adapted for InsertShips)

```
Algorithm: Solomon I1 Sequential Insertion for InsertShips
============================================================

Input:  dispatch Dispatch, oris []Station, dess []Station, total_ship int
Output: Dispatch
Params: μ=1, α1=1, α2=0, λ=1 (simplest: w1=1, w2=0, w3=0)

unserved = {0, 1, ..., len(oris)-1}

WHILE unserved is not empty:
    best_score = -Inf
    best_action = NULL

    FOR EACH k in unserved:
        ori_k, des_k = oris[k], dess[k]
        d_0u = cal_dis(Station{X:0,Y:0}, ori_k)   // depot distance approx

        FOR EACH a from 0 to dispatch.AssignsLen-1:
            // Try insertion at position j (end of route) and position i (before j)
            Save state
            ok = dispatch.Assigns[a].AddShip(total_ship + k, ori_k, des_k)
            IF NOT ok: CONTINUE

            dispatch.Assigns[a].GenRoute()
            c11 = dispatch.Assigns[a].Cost - saved_cost   // delta cost = insertion distance proxy

            score = α1 * d_0u - α2 * c11 - λ * (1 - α1 - α2) * 0
            // Note: c12 (time push) ≈ 0 for this problem since no hard time windows

            IF score > best_score:
                best_score = score
                best_action = (k, a)
            END IF

            // Undo
            dispatch.Assigns[a].RemoveShip(total_ship + k)
            dispatch.Assigns[a].GenRoute()
        END FOR
    END FOR

    // Execute best insertion
    IF best_action is not NULL:
        (k_best, a_best) = best_action
        dispatch.Assigns[a_best].AddShip(total_ship + k_best, oris[k_best], dess[k_best])
        dispatch.Assigns[a_best].GenRoute()
        Remove k_best from unserved
    ELSE:
        // No feasible insertion found — fallback to seed-style
        k_any = any element from unserved
        FOR a from 0 to min(dispatch.AssignsLen, MAXASSIGNS-1):
            IF dispatch.Assigns[a].AddShip(total_ship + k_any, oris[k_any], dess[k_any]):
                dispatch.Assigns[a].GenRoute()
                IF a >= dispatch.AssignsLen: dispatch.AssignsLen += 1
                BREAK
            END IF
        END FOR
        Remove k_any from unserved
    END IF
END WHILE

dispatch.RenewnTotalCost()
RETURN dispatch
```

## InsertShips Mapping

- Solomon's `c12` (time push-forward) is mostly zero for InsertShips since there are no strict time window constraints. Simplified weight: w1=1, w2=0, w3=0 rewards far-from-depot orders.
- The key difference from greedy insertion: Solomon I1 *selects which order next* based on a global score, not just iterating in order.
- For density-aware variant: set α2>0 when density is high (penalize distance cost more).
