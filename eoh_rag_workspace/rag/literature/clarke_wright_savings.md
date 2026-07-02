# Clarke-Wright Savings Algorithm

**Source:** Clarke, G. & Wright, J.W. (1964). "Scheduling of Vehicles from a Central Depot to a Number of Delivery Points." *Operations Research*, 12(4), 568-581.

**Best for:** Multi-route VRP where route merging significantly reduces total distance. Useful for InsertShips when deciding whether to create a new Assign or reuse an existing one.

## Core Savings Formula

```
For two orders i and j:
    s(i,j) = d(depot,i) + d(depot,j) - d(i,j)

s(i,j) > 0: serving i and j on the same route saves distance
s(i,j) ≤ 0: serve them on separate routes
```

## Pseudocode (Adapted for InsertShips)

```
Algorithm: Savings-Based InsertShips
=======================================

Input:  dispatch Dispatch, oris []Station, dess []Station, total_ship int
Output: Dispatch

// Compute savings matrix for all order pairs
savings = empty list
FOR i from 0 to len(oris)-1:
    FOR j from i+1 to len(oris)-1:
        d_depot_i = cal_dis(Station{X:0,Y:0}, oris[i])
        d_depot_j = cal_dis(Station{X:0,Y:0}, oris[j])
        d_i_j     = cal_dis(oris[i], oris[j])
        s = d_depot_i + d_depot_j - d_i_j
        IF s > 0:
            savings.append((s, i, j))
        END IF
    END FOR
END FOR

// Sort savings descending (merge most profitable pairs first)
Sort savings by s descending

// Track which orders are already served
served = set()

// Process savings list
FOR each (s, i, j) in savings:
    IF i in served AND j in served: CONTINUE   // both already handled
    IF i not in served AND j not in served:
        // Both new: create a new route with these two orders
        // Try inserting both into the same Assign
        Find or create an Assign a
        Insert order i into a (best-cost position or add as first)
        Insert order j into a (best-cost position)
        served.add(i); served.add(j)
    ELSE IF i in served AND j not in served:
        // Add j to i's route
        Find the Assign containing order i
        Insert order j at best-cost position in that Assign
        served.add(j)
    ELSE IF i not in served AND j in served:
        // Add i to j's route
        Find the Assign containing order j
        Insert order i at best-cost position in that Assign
        served.add(i)
    END IF
END FOR

// Handle remaining unserved orders with greedy insertion
FOR EACH k not in served:
    best_assign = -1
    best_delta = +Inf
    FOR EACH a from 0 to dispatch.AssignsLen-1:
        Save state; try AddShip; if ok: GenRoute; record delta; undo
    END FOR
    IF best_assign >= 0:
        Apply insertion
    ELSE:
        Force-insert into new or existing Assign (fallback)
    END IF
END FOR

dispatch.RenewnTotalCost()
RETURN dispatch
```

## InsertShips Mapping

- Savings formula uses `cal_dis()` for distance approximation
- "Route merging" = deciding whether to add an order to an existing Assign or create a new one
- The savings list guides which pairs to prioritize — orders with high savings should share an Assign
- In dynamic context (arrival_scale < 1.0), savings can be recomputed per batch
- Fallback: any unserved order after savings processing gets greedy insertion
