# Regret-2 Insertion Heuristic

**Source:** Potvin, J.-Y. & Rousseau, J.-M. (1993). "A Parallel Route Building Algorithm for the Vehicle Routing and Scheduling Problem with Time Windows." *European Journal of Operational Research*, 66(3), 331-340.

Also formalized in: Ropke, S. & Pisinger, D. (2006). "An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows." *Transportation Science*, 40(4), 455-472.

**Best for:** Medium-density instances with competing insertion options. Avoids the "greedy trap" of nearest/farthest insertion by considering the cost of *not* inserting an order now.

## Core Concept

```
For each unrouted order u:
    cost_1st(u) = cost of best insertion position for u
    cost_2nd(u) = cost of second-best insertion position for u
    regret(u)   = cost_2nd(u) - cost_1st(u)

Select the order with MAXIMUM regret.
Rationale: orders with high regret will be much more expensive to insert later
if not handled now, because their second-best option is already poor.
```

Regret-k generalizes to top-k best positions.

## Pseudocode (Regret-2, Adapted for InsertShips)

```
Algorithm: Regret-2 Insertion for InsertShips
================================================

Input:  dispatch Dispatch, oris []Station, dess []Station, total_ship int
Output: Dispatch

unserved = {0, 1, ..., len(oris)-1}

WHILE unserved is not empty:
    best_regret_order = -1
    best_regret_value = -1
    best_regret_action = NULL   // (k, a) for the best insertion

    FOR EACH k in unserved:
        costs = []   // list of (assign_index, cost_delta) pairs

        FOR EACH a from 0 to dispatch.AssignsLen-1:
            Save state
            ok = dispatch.Assigns[a].AddShip(total_ship + k, oris[k], dess[k])
            IF ok:
                dispatch.Assigns[a].GenRoute()
                delta = dispatch.Assigns[a].Cost - saved_cost
                costs.append((a, delta))
                // Undo
                dispatch.Assigns[a].RemoveShip(total_ship + k)
                dispatch.Assigns[a].GenRoute()
            END IF
        END FOR

        IF len(costs) == 0:
            CONTINUE   // No feasible insertion for this order — will fallback
        ELSE IF len(costs) == 1:
            regret = INF   // Only one option — must insert now
        ELSE:
            Sort costs by delta ascending
            regret = costs[1].delta - costs[0].delta   // regret-2
        END IF

        IF regret > best_regret_value:
            best_regret_value = regret
            best_regret_order = k
            best_regret_action = costs[0]   // (a, delta) of best insertion
        END IF
    END FOR

    // Execute best regret order insertion
    IF best_regret_order >= 0:
        (a_best, _) = best_regret_action
        dispatch.Assigns[a_best].AddShip(total_ship + best_regret_order, oris[best_regret_order], dess[best_regret_order])
        dispatch.Assigns[a_best].GenRoute()
        Remove best_regret_order from unserved
    ELSE:
        // Fallback: force any order into any feasible position
        Pick any k from unserved
        inserted = false
        FOR a from 0 to min(dispatch.AssignsLen, MAXASSIGNS-1):
            IF dispatch.Assigns[a].AddShip(total_ship + k, oris[k], dess[k]):
                dispatch.Assigns[a].GenRoute()
                IF a >= dispatch.AssignsLen: dispatch.AssignsLen += 1
                inserted = true; BREAK
            END IF
        END FOR
        Remove k from unserved
    END IF
END WHILE

dispatch.RenewnTotalCost()
RETURN dispatch
```

## InsertShips Mapping

- Regret = "if I don't insert this order now, how much worse will my second-best option be?"
- Each `Assign` represents a route; the insertion positions within an Assign are the route positions
- Key advantage over greedy: avoids leaving "hard" orders until last, when routes are full and options are fewer
- INF for single-option orders = insert immediately (no backup plan)
