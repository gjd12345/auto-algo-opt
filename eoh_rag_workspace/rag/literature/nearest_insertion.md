# Nearest Insertion Heuristic

**Source:** Rosenkrantz, D.J., Stearns, R.E., & Lewis, P.M. (1977). "An Analysis of Several Heuristics for the Traveling Salesman Problem." *SIAM Journal on Computing*, 6(3), 563-581.

**Best for:** Low-density instances where the nearest feasible insertion is likely close to optimal. Fast and deterministic.

## Pseudocode

```
Algorithm: Nearest Insertion for InsertShips
==============================================

Input:  dispatch Dispatch, oris []Station, dess []Station, total_ship int
Output: Dispatch (with all orders inserted)

FOR each order index k from 0 to len(oris)-1:
    ori = oris[k]
    des = dess[k]
    best_assign = -1
    best_cost_delta = +Inf

    // Phase 1: Try insertion into each existing assignment
    FOR each assign index a from 0 to dispatch.AssignsLen-1:
        Save current state of dispatch.Assigns[a]
        ok = dispatch.Assigns[a].AddShip(total_ship + k, ori, des)
        IF ok:
            dispatch.Assigns[a].GenRoute()
            delta = dispatch.Assigns[a].Cost - saved_cost_of_a
            IF delta < best_cost_delta:
                best_cost_delta = delta
                best_assign = a
            // Undo: restore previous state
            dispatch.Assigns[a].RemoveShip(total_ship + k)
            dispatch.Assigns[a].GenRoute()
        END IF
    END FOR

    // Phase 2: Apply best insertion or fallback
    IF best_assign >= 0:
        dispatch.Assigns[best_assign].AddShip(total_ship + k, ori, des)
        dispatch.Assigns[best_assign].GenRoute()
    ELSE IF dispatch.AssignsLen < MAXASSIGNS:
        // Fallback: use a new assignment
        dispatch.Assigns[dispatch.AssignsLen].AddShip(total_ship + k, ori, des)
        dispatch.Assigns[dispatch.AssignsLen].GenRoute()
        dispatch.AssignsLen += 1
    ELSE:
        // Safety: try any assignment, forcing AddShip
        FOR a from 0 to dispatch.AssignsLen-1:
            IF dispatch.Assigns[a].AddShip(total_ship + k, ori, des):
                dispatch.Assigns[a].GenRoute()
                BREAK
            END IF
        END FOR
    END IF
END FOR

dispatch.RenewnTotalCost()
RETURN dispatch
```

## InsertShips Mapping

- `oris[k]`, `dess[k]` = the dynamic order pair to insert
- `Assign.AddShip()` = attempt insertion; returns false if infeasible
- `Assign.GenRoute()` = regenerate route after successful insertion
- Cost delta = new `Assign.Cost` - saved cost before insertion (approximate via `cal_dis`)
- Fallback: never skip an order; if no existing Assign accepts it, create or force-insert
- `RenewnTotalCost()` must be called exactly once before return
