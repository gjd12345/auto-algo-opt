# Farthest Insertion Heuristic

**Source:** Rosenkrantz, D.J., Stearns, R.E., & Lewis, P.M. (1977). "An Analysis of Several Heuristics for the Traveling Salesman Problem." *SIAM Journal on Computing*, 6(3), 563-581.

**Best for:** Dispersed order distributions where the nearest-first strategy would leave distant orders poorly served. Complementary to Nearest Insertion.

## Pseudocode

```
Algorithm: Farthest Insertion for InsertShips
===============================================

Input:  dispatch Dispatch, oris []Station, dess []Station, total_ship int
Output: Dispatch (with all orders inserted)

// Precompute "distance from current route" for each uninserted order
unserved = list of all order indices (0 to len(oris)-1)

WHILE unserved is not empty:
    // Find the order farthest from any existing assignment
    farthest_order = -1
    farthest_dist = -1

    FOR each k in unserved:
        min_dist_to_route = +Inf
        FOR each assign a from 0 to dispatch.AssignsLen-1:
            dist = cal_dis(dispatch.Assigns[a].StationCurrent, oris[k])
            IF dist < min_dist_to_route:
                min_dist_to_route = dist
            END IF
        END FOR
        IF min_dist_to_route > farthest_dist:
            farthest_dist = min_dist_to_route
            farthest_order = k
        END IF
    END FOR

    // Insert the farthest order using best-cost position
    best_assign = -1
    best_cost = +Inf
    FOR a from 0 to dispatch.AssignsLen-1:
        Save state of dispatch.Assigns[a]
        ok = dispatch.Assigns[a].AddShip(total_ship + farthest_order, oris[farthest_order], dess[farthest_order])
        IF ok:
            dispatch.Assigns[a].GenRoute()
            delta = dispatch.Assigns[a].Cost - saved_cost
            IF delta < best_cost:
                best_cost = delta
                best_assign = a
            END IF
            dispatch.Assigns[a].RemoveShip(total_ship + farthest_order)
            dispatch.Assigns[a].GenRoute()
        END IF
    END FOR

    // Apply or fallback
    IF best_assign >= 0:
        dispatch.Assigns[best_assign].AddShip(total_ship + farthest_order, oris[farthest_order], dess[farthest_order])
        dispatch.Assigns[best_assign].GenRoute()
    ELSE:
        // Fallback: force-insert into existing or new assignment
        inserted = false
        FOR a from 0 to min(dispatch.AssignsLen, MAXASSIGNS-1):
            IF dispatch.Assigns[a].AddShip(total_ship + farthest_order, oris[farthest_order], dess[farthest_order]):
                dispatch.Assigns[a].GenRoute()
                IF a >= dispatch.AssignsLen: dispatch.AssignsLen += 1
                inserted = true
                BREAK
            END IF
        END FOR
        // Safety: if still not inserted, log warning and continue
    END IF

    Remove farthest_order from unserved
END WHILE

dispatch.RenewnTotalCost()
RETURN dispatch
```

## InsertShips Mapping

- Selection criterion ≠ insertion criterion: first pick *which* order (farthest), then pick *where* (best-cost)
- `cal_dis(StationCurrent, oris[k])` measures distance from route to order
- Cost delta from GenRoute() approximates insertion cost
- Farthest-first = prioritize hard-to-serve orders early, leaving easy ones for later when routes are fuller
