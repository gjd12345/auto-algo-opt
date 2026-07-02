package main

import (
	"encoding/json"
	"fmt"
	"os"
)

type Item struct {
	Weight int `json:"weight"`
	Value  int `json:"value"`
}

type Instance struct {
	Capacity int    `json:"capacity"`
	Items    []Item `json:"items"`
}

func SelectItems(items []Item, capacity int) []bool {
	selected := make([]bool, len(items))
	remaining := capacity
	for i, item := range items {
		if item.Weight <= remaining {
			selected[i] = true
			remaining -= item.Weight
		}
	}
	return selected
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: knapsack_solver instance.json")
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
	selected := SelectItems(inst.Items, inst.Capacity)
	if len(selected) != len(inst.Items) {
		fmt.Printf("final cost 1000000000\n")
		fmt.Printf("value 0\n")
		fmt.Printf("weight 0\n")
		fmt.Printf("feasible false\n")
		return
	}
	value := 0
	weight := 0
	for i, ok := range selected {
		if !ok {
			continue
		}
		weight += inst.Items[i].Weight
		value += inst.Items[i].Value
	}
	if weight > inst.Capacity {
		fmt.Printf("final cost 1000000000\n")
		fmt.Printf("value %d\n", value)
		fmt.Printf("weight %d\n", weight)
		fmt.Printf("feasible false\n")
		return
	}
	fmt.Printf("final cost %d\n", -value)
	fmt.Printf("value %d\n", value)
	fmt.Printf("weight %d\n", weight)
	fmt.Printf("feasible true\n")
}
