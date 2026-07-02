# PLAN.md

## Current Status
- Generated seeds from 'time window regret' query, but they contain undefined types (SortManager, sort.Sort).
- First evolution run shows high penalties (avg_fitness ~5e8) and best_fitness (219.81) worse than baseline (206.42).
- Need to create seeds that compile with exact structs from MEMORY.md.

## Immediate Actions
1. Create new seeds manually using add_new_seed with code that:
   - Uses only structs/functions from MEMORY.md (Dispatch, Assign, Station, cal_dis, etc.).
   - Implements time-window aware insertion with regret heuristics based on Solomon I1.
   - Passes run_code_review before adding.
2. Run evolution with these valid seeds.
3. If stagnation persists, run_deep_analysis.

## Updated Algorithm Design for InsertShips
- For each ship (pair of ori, des from oris, dess slices), evaluate feasible insertion positions in each existing assign's route (considering load capacity and time windows).
- Compute insertion cost for each feasible position using a combination of additional distance and time window push-forward:
  - c11 = additional distance = cal_dis(prev_station, ori) + cal_dis(ori, des) + cal_dis(des, next_station) - cal_dis(prev_station, next_station)
  - c12 = time window push-forward = max(0, new_arrival_time_at_next - original_arrival_time_at_next) where arrival times are computed considering travel times and waiting times.
  - c1 = α1*c11 + α2*c12 (with α1=0.5, α2=0.5 as initial weights).
  - c2 = λ*cal_dis(depot, ori) - c1 (with λ=1.0).
- For each ship, track the best insertion cost (min c2) and second-best insertion cost across all assigns.
- Compute regret = second_best_cost - best_cost.
- Select the ship with maximum regret and insert it at its best position.
- Repeat until all ships are inserted or no feasible insertions remain (then create new assigns if total_ship allows).
- Use Assign.AddShip and Assign.GenRoute methods to update routes and costs.
- Finally, call dispatch.RenewnTotalCost().

## Constraints
- NO undefined types (SortManager, sort.Sort).
- Must use Station fields: X, Y, TimeStart, TimeEnd, Load.
- Must use available methods: AddShip, RemoveShip, GenRoute, RenewnTotalCost.
- Must use utility functions: cal_dis, Abs.

## Target
Evolve InsertShips to beat baseline cost of 206.415358 across rc101–rc108.