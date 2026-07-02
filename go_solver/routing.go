package main

import (
	"encoding/json"
	"math"
	"sort"
)

const MAXSTATIONS int = 16
const float64EqualityThreshold float64 = 1e-9

type Station struct {
	X         int `json:"x"`
	Y         int `json:"y"`
	TimeStart int `json:"timeStart"`
	TimeEnd   int `json:"timeEnd"`
	ReqCode   int `json:"reqCode"`
	Load      int `json:"load"`
}

// UnmarshalJSON keeps backward compatibility for both:
// 1) legacy datasets: timeReady/timeDue
// 2) current datasets: timeStart/timeEnd
func (st *Station) UnmarshalJSON(data []byte) error {
	type stationAlias struct {
		X         int `json:"x"`
		Y         int `json:"y"`
		TimeStart int `json:"timeStart"`
		TimeEnd   int `json:"timeEnd"`
		TimeReady int `json:"timeReady"`
		TimeDue   int `json:"timeDue"`
		ReqCode   int `json:"reqCode"`
		Load      int `json:"load"`
	}
	var aux stationAlias
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}
	st.X = aux.X
	st.Y = aux.Y
	st.ReqCode = aux.ReqCode
	st.Load = aux.Load
	if aux.TimeStart != 0 || aux.TimeEnd != 0 {
		st.TimeStart = aux.TimeStart
		st.TimeEnd = aux.TimeEnd
	} else {
		st.TimeStart = aux.TimeReady
		st.TimeEnd = aux.TimeDue
	}
	return nil
}

func Fequal(f1, f2 float64) bool {
	if math.Abs(f1-f2) <= float64EqualityThreshold {
		return true
	}
	return false
}

func (st *Station) Equal(st2 *Station) bool {
	if (st.X == st2.X) && (st.Y == st2.Y) && st.TimeStart == st2.TimeStart && st.TimeEnd == st2.TimeEnd {
		return true
	}
	return false
}

type RoutingTask struct {
	Stations       [MAXSTATIONS]Station `json:"stations"`
	StationsLen    int                  `json:"stationsLen"`
	Speed          float64              `json:"speed"`
	TimeCurrent    int                  `json:"timeCurrent"`
	StationCurrent Station              `json:"stationCurrent"`
	LoadCurrent    int                  `json:"loadCurrent"`
	LoadCap        int                  `json:"loadCap"`
}

type RoutingStackState struct {
	CurSta     int     `json:"curSta"`
	Travel     float64 `json:"travel"`
	CurTime    int     `json:"curTime"`
	CurLoad    int     `json:"curLoad"`
	CurSeqCode int     `json:"curSeqCode"`
}

type RoutingResult struct {
	Iteration int                            `json:"iter"`
	ConsEval  int                            `json:"consEval"`
	Cost      float64                        `json:"cost"`
	Route     [MAXSTATIONS]RoutingStackState `json:"route"`
	RouteLen  int                            `json:"routeLen"`
}

func cal_dis(st1, st2 Station) float64 {
	differ1 := float64(st1.X - st2.X)
	differ1 *= differ1
	differ2 := float64(st1.Y - st2.Y)
	differ2 *= differ2
	return math.Sqrt(differ1 + differ2)
}

func (stack *RoutingResult) Append(task *RoutingTask, index int) {
	var travel float64
	var seqcode, time, load int
	if stack.RouteLen == 0 {
		seqcode = 0
		load = task.LoadCurrent + task.Stations[index].Load
		travel = cal_dis(task.StationCurrent, task.Stations[index])
		time = task.TimeCurrent
		time += int(math.Ceil(travel / task.Speed))
	} else {
		load = stack.Route[stack.RouteLen-1].CurLoad + task.Stations[index].Load
		travel = cal_dis(task.Stations[stack.Route[stack.RouteLen-1].CurSta], task.Stations[index])
		time = stack.Route[stack.RouteLen-1].CurTime
		seqcode = stack.Route[stack.RouteLen-1].CurSeqCode
		time += int(math.Ceil(travel / task.Speed))
		travel += stack.Route[stack.RouteLen-1].Travel
	}
	if time < task.Stations[index].TimeStart {
		time = task.Stations[index].TimeStart
	}
	seqcode += 1 << index
	stack.Route[stack.RouteLen] = RoutingStackState{index, travel, time, load, seqcode}
	stack.RouteLen += 1
}

// ============ 优化1: 自适应候选站点评分 ============
func candidateScore(task *RoutingTask, curStation Station, idx int) float64 {
	st := task.Stations[idx]
	dist := cal_dis(curStation, st)

	// 时间窗口紧迫度
	timePenalty := 0.0
	if task.TimeCurrent > st.TimeEnd {
		timePenalty = 10000
	} else {
		slack := st.TimeEnd - task.TimeCurrent
		if slack < 10 {
			timePenalty = 500
		} else {
			timePenalty = float64(slack) / 50.0
		}
	}

	// 载重约束风险
	loadRisk := 0.0
	projectedLoad := task.LoadCurrent + st.Load
	if projectedLoad > task.LoadCap {
		loadRisk = 5000
	}

	return dist + timePenalty + loadRisk
}

func getSortedCandidates(task *RoutingTask, status int, curSta int, sts_len int) []int {
	unvisited := []int{}
	for i := 0; i < sts_len; i++ {
		if status>>i&1 == 0 {
			unvisited = append(unvisited, i)
		}
	}
	if len(unvisited) == 0 {
		return []int{}
	}

	var current Station
	if curSta < 0 {
		current = task.StationCurrent
	} else {
		current = task.Stations[curSta]
	}

	sort.Slice(unvisited, func(i, j int) bool {
		return candidateScore(task, current, unvisited[i]) < candidateScore(task, current, unvisited[j])
	})
	return unvisited
}

// ============ 优化2: MST下界估计 ============
func computeLowerBound(task *RoutingTask, stack *RoutingResult, status int, sts_len int) float64 {
	var currentTravel float64
	if stack.RouteLen > 0 {
		currentTravel = stack.Route[stack.RouteLen-1].Travel
	}

	type pair struct {
		idx  int
		dist float64
	}
	dists := []pair{}
	for i := 0; i < sts_len; i++ {
		if status>>i&1 == 0 {
			lastSta := -1
			if stack.RouteLen > 0 {
				lastSta = stack.Route[stack.RouteLen-1].CurSta
			}
			var cur Station
			if lastSta < 0 {
				cur = task.StationCurrent
			} else {
				cur = task.Stations[lastSta]
			}
			dists = append(dists, pair{i, cal_dis(cur, task.Stations[i])})
		}
	}

	if len(dists) == 0 {
		return currentTravel
	}

	sort.Slice(dists, func(i, j int) bool { return dists[i].dist < dists[j].dist })
	n := len(dists)
	min1 := dists[0].dist
	var min2 float64 = 1e9
	for i := 1; i < n; i++ {
		if dists[i].dist < min2 {
			min2 = dists[i].dist
		}
	}
	mstEstimate := min1 + float64(n-1)*(min1+min2)/2.0
	return currentTravel + mstEstimate*0.8
}

// ============ 优化3: 2-opt局部搜索 ============
func twoOptImprove(task *RoutingTask, stack *RoutingResult) {
	if stack.RouteLen < 3 {
		return
	}
	improved := true
	for improved && stack.Iteration < 1000000 {
		improved = false
		for i := 0; i < stack.RouteLen-1; i++ {
			for j := i + 2; j < stack.RouteLen; j++ {
				var nodeI, nodeI1, nodeJ, nodeJ1 int
				if i == 0 {
					nodeI = -1
					nodeI1 = stack.Route[i].CurSta
				} else {
					nodeI = stack.Route[i-1].CurSta
					nodeI1 = stack.Route[i].CurSta
				}
				nodeJ = stack.Route[j].CurSta
				if j+1 < stack.RouteLen {
					nodeJ1 = stack.Route[j+1].CurSta
				} else {
					nodeJ1 = -1
				}

				var oldDist float64
				if nodeI == -1 {
					oldDist += cal_dis(task.StationCurrent, task.Stations[nodeI1])
				} else {
					oldDist += cal_dis(task.Stations[nodeI], task.Stations[nodeI1])
				}
				if nodeJ1 != -1 {
					oldDist += cal_dis(task.Stations[nodeJ], task.Stations[nodeJ1])
				}

				var newDist float64
				if nodeI == -1 {
					newDist += cal_dis(task.StationCurrent, task.Stations[nodeJ])
				} else {
					newDist += cal_dis(task.Stations[nodeI], task.Stations[nodeJ])
				}
				if nodeJ1 == -1 {
					newDist += cal_dis(task.Stations[nodeI1], task.StationCurrent)
				} else {
					newDist += cal_dis(task.Stations[nodeI1], task.Stations[nodeJ1])
				}

				if newDist < oldDist {
					k := 0
					for k < (j-i)/2 {
						tmp := stack.Route[i+1+k]
						stack.Route[i+1+k] = stack.Route[j-k]
						stack.Route[j-k] = tmp
						k++
					}
					var travel float64
					if stack.RouteLen > 0 {
						travel = cal_dis(task.StationCurrent, task.Stations[stack.Route[0].CurSta])
						stack.Route[0].Travel = travel
					}
					for k = 1; k < stack.RouteLen; k++ {
						travel += cal_dis(task.Stations[stack.Route[k-1].CurSta], task.Stations[stack.Route[k].CurSta])
						stack.Route[k].Travel = travel
					}
					improved = true
				}
			}
		}
	}
}

const MAX_ITERATIONS = 500000

func RoutingTS(task *RoutingTask) RoutingResult {
	var stack RoutingResult
	var opt_stack RoutingResult
	opt_stack.Cost = -1
	var status int = 0
	var flag, subflag int = 0, 0
	sts_len := task.StationsLen

LOOP:
	for stack.Iteration < MAX_ITERATIONS {
		stack.Iteration++

		switch flag {
		case 2:
			subflag = 0
			lastSta := -1
			if stack.RouteLen > 0 {
				lastSta = stack.Route[stack.RouteLen-1].CurSta
			}
			candidates := getSortedCandidates(task, status, lastSta, sts_len)

			for _, idx := range candidates {
				if task.LoadCurrent+task.Stations[idx].Load > task.LoadCap {
					continue
				}
				stack.Append(task, idx)
				status += 1 << idx
				flag = 0
				subflag = 1
				break
			}
			if subflag == 0 {
				flag = -1
			}

		case 1:
			subflag = 0
			if stack.RouteLen == 0 {
				flag = -1
				break
			}
			lastIdx := stack.Route[stack.RouteLen-1].CurSta

			candidates := []int{}
			for i := 0; i < sts_len; i++ {
				if status>>i&1 == 0 {
					candidates = append(candidates, i)
				}
			}
			sort.Slice(candidates, func(i, j int) bool {
				return candidateScore(task, task.Stations[lastIdx], candidates[i]) < candidateScore(task, task.Stations[lastIdx], candidates[j])
			})

			for _, idx := range candidates {
				if task.LoadCurrent+task.Stations[idx].Load > task.LoadCap {
					continue
				}
				status &= ^(1 << lastIdx)
				stack.RouteLen--
				stack.Append(task, idx)
				status |= 1 << idx
				flag = 0
				subflag = 1
				break
			}
			if subflag == 0 {
				flag = -1
			}

		case 0:
			stack.ConsEval++
			if stack.RouteLen > 0 {
				if stack.Route[stack.RouteLen-1].CurTime > task.Stations[stack.Route[stack.RouteLen-1].CurSta].TimeEnd {
					flag = 1
					break
				}
				subflag = task.Stations[stack.Route[stack.RouteLen-1].CurSta].ReqCode
				if stack.Route[stack.RouteLen-1].CurSeqCode|subflag > stack.Route[stack.RouteLen-1].CurSeqCode {
					flag = 1
					break
				}
				if stack.Route[stack.RouteLen-1].CurLoad > task.LoadCap {
					flag = 1
					break
				}
				if opt_stack.Cost >= 0 {
					lb := computeLowerBound(task, &stack, status, sts_len)
					if lb >= opt_stack.Cost {
						flag = 1
						break
					}
				}
			}
			flag = 2
			if stack.RouteLen == sts_len {
				twoOptImprove(task, &stack)

				stack.Cost = 0
				if stack.RouteLen > 0 {
					travel := cal_dis(task.StationCurrent, task.Stations[stack.Route[0].CurSta])
					stack.Route[0].Travel = travel
					for i := 1; i < stack.RouteLen; i++ {
						travel += cal_dis(task.Stations[stack.Route[i-1].CurSta], task.Stations[stack.Route[i].CurSta])
						stack.Route[i].Travel = travel
					}
					stack.Cost = stack.Route[stack.RouteLen-1].Travel
				}

				if stack.Cost < opt_stack.Cost || opt_stack.Cost < 0 {
					opt_stack = stack
				}
				flag = -1
			}

		case -1:
			if stack.RouteLen == 0 {
				break LOOP
			}
			status &= ^(1 << stack.Route[stack.RouteLen-1].CurSta)
			stack.RouteLen--
			flag = 0
			if stack.RouteLen == 0 {
				break LOOP
			}
			flag = 1
		}
	}
	return opt_stack
}
