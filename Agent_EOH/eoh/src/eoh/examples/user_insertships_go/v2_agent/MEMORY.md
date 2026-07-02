# Agent Memory

## Facts
- Evaluation compiles a temporary Go binary from Archive_extracted/main.go + routing.go, replaces InsertShips, then runs rc101–rc108 and parses `final cost`.
- Baseline values match Archive_extracted/final_result.txt exactly.

## Constraints
- Candidate InsertShips code must be a single Go method definition:
  - `func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch { ... }`
- Must compile with the existing structs in Archive_extracted:

```go
const MAXASSIGNS = 32
const MAXSHIPS = 8
const MEMORYSIZE = 16
const MAXINSERTION = 64

type Station struct{
    X         int
    Y         int
    TimeStart int
    TimeEnd   int
    ReqCode   int
    Load      int
}

type Ship struct {
    Id  int
    Ori int
    Des int
    Load int
}

type RoutingStackState struct{
    CurSta     int     
    Travel     float64 
    CurTime    int     
    CurLoad    int     
    CurSeqCode int     
}

type RoutingResult struct{
    Iteration int                            
    ConsEval  int                            
    Cost      float64                        
    Route     [16]RoutingStackState 
    RouteLen  int                            
}

type RoutingTask struct{
    Stations       [16]Station 
    StationsLen    int                  
    Speed          float64              
    TimeCurrent    int                  
    StationCurrent Station              
    LoadCurrent    int                  
    LoadCap        int                  
}

type Assign struct {
    RoutingTask
    RoutingResult
    NextSta    int
    NextTime   int
    StaIndexes [MAXSHIPS]Ship
    StaIndexesLen int
    AccumulatedCost float64
}

// Available methods on Assign:
// func (assign *Assign) AddShip(id int, ori, des Station)
// func (assign *Assign) RemoveShip(id int)
// func (assign *Assign) GenRoute()

type Dispatch struct {
    Assigns    [MAXASSIGNS]Assign
    AssignsLen int
    TotalCost  float64
    AccumulatedCost float64
}

// Available method on Dispatch:
// func (dispatch *Dispatch) RenewnTotalCost()

// Available utility functions:
// func cal_dis(st1, st2 Station) float64
// func Abs(x int) int
```

## Working Heuristics
- The baseline logic uses distance to greedily sort and insert ships. It iterates over existing Assigns to find the first feasible one (Cost >= 0) and adds the ship.

## Latest Run
- The agent was previously confused about Go structs, assuming a `.Vehicles` or `.Demand` field existed. The actual struct definitions are provided above. Do NOT use `.Vehicles`, `.Demand`, or `.ReadyTime` - use the exact structs above.

## Open Questions
- How to implement regret insertion or time-window aware scoring using only the provided `Station` fields (`X`, `Y`, `TimeStart`, `TimeEnd`, `Load`) and `cal_dis`?