package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
)

type Order struct {
	ID           string  `json:"id"`
	Volume       float64 `json:"volume"`
	GoDistance   float64 `json:"go_distance"`
	BackDistance float64 `json:"back_distance"`
	MixTime      float64 `json:"mix_time"`
	UnloadTime   float64 `json:"unload_time"`
}

type Vehicle struct {
	Capacity float64 `json:"capacity"`
	Count    int     `json:"count"`
}

type SubOrder struct {
	OrderID         string  `json:"order_id"`
	Volume          float64 `json:"volume"`
	VehicleCapacity float64 `json:"vehicle_capacity"`
}

type Instance struct {
	WorkHours float64   `json:"work_hours"`
	Orders    []Order   `json:"orders"`
	Vehicles  []Vehicle `json:"vehicles"`
}

func SplitOrders(orders []Order, vehicles []Vehicle, workHours float64) []SubOrder {
	caps := make([]float64, 0)
	for _, vehicle := range vehicles {
		if vehicle.Capacity > 0 && vehicle.Count > 0 {
			caps = append(caps, vehicle.Capacity)
		}
	}
	for i := 0; i < len(caps); i++ {
		for j := i + 1; j < len(caps); j++ {
			if caps[j] > caps[i] {
				caps[i], caps[j] = caps[j], caps[i]
			}
		}
	}
	if len(caps) == 0 {
		return []SubOrder{}
	}

	result := make([]SubOrder, 0)
	largest := caps[0]
	for _, order := range orders {
		remaining := order.Volume
		for remaining > 1e-9 {
			chosen := largest
			for _, cap := range caps {
				if remaining <= cap+1e-9 {
					chosen = cap
				}
			}
			volume := math.Min(remaining, chosen)
			result = append(result, SubOrder{
				OrderID:         order.ID,
				Volume:          volume,
				VehicleCapacity: chosen,
			})
			remaining -= volume
		}
	}
	return result
}

func evaluate(inst Instance, suborders []SubOrder) (float64, bool, string) {
	if len(inst.Orders) > 0 && len(suborders) == 0 {
		return 1000000000, false, "empty result"
	}
	orders := make(map[string]Order)
	volumeByOrder := make(map[string]float64)
	for _, order := range inst.Orders {
		if order.ID == "" || order.Volume <= 0 {
			return 1000000000, false, "bad input order"
		}
		orders[order.ID] = order
	}

	totalWork := 0.0
	capacityAllowed := func(capacity float64) bool {
		for _, vehicle := range inst.Vehicles {
			if vehicle.Count > 0 && math.Abs(vehicle.Capacity-capacity) <= 1e-6 {
				return true
			}
		}
		return false
	}
	for _, sub := range suborders {
		order, ok := orders[sub.OrderID]
		if !ok {
			return 1000000000, false, "unknown order id"
		}
		if sub.Volume <= 0 {
			return 1000000000, false, "non-positive suborder volume"
		}
		if !capacityAllowed(sub.VehicleCapacity) {
			return 1000000000, false, "unknown vehicle capacity"
		}
		if sub.VehicleCapacity <= 0 || sub.Volume > sub.VehicleCapacity+1e-6 {
			return 1000000000, false, "capacity exceeded"
		}
		volumeByOrder[sub.OrderID] += sub.Volume
		timeCost := 0.5 + (order.GoDistance+order.BackDistance)/35.0
		totalWork += timeCost * sub.Volume / sub.VehicleCapacity
	}

	uncovered := 0.0
	for _, order := range inst.Orders {
		diff := math.Abs(volumeByOrder[order.ID] - order.Volume)
		if diff > 1e-6 {
			uncovered += diff
		}
	}
	if uncovered > 1e-6 {
		return uncovered * 1000000, false, "volume mismatch"
	}

	totalCapacityHours := 0.0
	for _, vehicle := range inst.Vehicles {
		if vehicle.Capacity > 0 && vehicle.Count > 0 {
			totalCapacityHours += vehicle.Capacity * float64(vehicle.Count) * inst.WorkHours
		}
	}
	extraVehicleUnits := 0.0
	if totalWork > totalCapacityHours && inst.WorkHours > 0 {
		extraVehicleUnits = math.Ceil((totalWork - totalCapacityHours) / inst.WorkHours)
	}
	cost := extraVehicleUnits*10000 + float64(len(suborders))*10 + totalWork
	return cost, true, "valid"
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: mixer_split_solver instance.json")
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "read instance: %v\n", err)
		os.Exit(1)
	}
	var inst Instance
	if err := json.Unmarshal(data, &inst); err != nil {
		fmt.Fprintf(os.Stderr, "parse instance: %v\n", err)
		os.Exit(1)
	}
	suborders := SplitOrders(inst.Orders, inst.Vehicles, inst.WorkHours)
	cost, feasible, reason := evaluate(inst, suborders)
	fmt.Printf("final cost %.6f\n", cost)
	fmt.Printf("suborders %d\n", len(suborders))
	fmt.Printf("feasible %v\n", feasible)
	fmt.Printf("reason %s\n", reason)
}
