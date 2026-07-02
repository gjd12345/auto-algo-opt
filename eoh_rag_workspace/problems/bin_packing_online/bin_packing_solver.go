package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
)

var _ = math.Sqrt
var _ = math.Exp

type Instance struct {
	Name     string `json:"name"`
	Capacity int    `json:"capacity"`
	Items    []int  `json:"items"`
}

type Dataset struct {
	Instances []Instance `json:"instances"`
}

type InstanceResult struct {
	Name       string  `json:"name"`
	UsedBins   int     `json:"used_bins"`
	LowerBound int     `json:"lower_bound"`
	GapToLB    float64 `json:"gap_to_lb"`
}

type Result struct {
	Objective     float64          `json:"objective"`
	AvgGapToLB    float64          `json:"avg_gap_to_lb"`
	AvgUsedBins   float64          `json:"avg_used_bins"`
	AvgLowerBound float64          `json:"avg_lower_bound"`
	Instances     []InstanceResult `json:"instances"`
}

func ScoreBin(item int, remaining []int, capacity int) []float64 {
	scores := make([]float64, len(remaining))
	for i, rem := range remaining {
		scores[i] = float64(capacity - (rem - item))
	}
	return scores
}

func lowerBound(items []int, capacity int) int {
	total := 0
	for _, item := range items {
		total += item
	}
	lb := total / capacity
	if total%capacity != 0 {
		lb++
	}
	if lb < 1 {
		return 1
	}
	return lb
}

func firstFit(items []int, capacity int) int {
	remaining := make([]int, 0)
	for _, item := range items {
		placed := false
		for i := range remaining {
			if remaining[i] >= item {
				remaining[i] -= item
				placed = true
				break
			}
		}
		if !placed {
			remaining = append(remaining, capacity-item)
		}
	}
	return len(remaining)
}

func bestFit(items []int, capacity int) int {
	remaining := make([]int, 0)
	for _, item := range items {
		best := -1
		bestAfter := capacity + 1
		for i, rem := range remaining {
			if rem >= item && rem-item < bestAfter {
				best = i
				bestAfter = rem - item
			}
		}
		if best >= 0 {
			remaining[best] -= item
		} else {
			remaining = append(remaining, capacity-item)
		}
	}
	return len(remaining)
}

func packWithScore(items []int, capacity int) (int, error) {
	remaining := make([]int, 0, len(items))
	for _, item := range items {
		if item <= 0 || item > capacity {
			return 0, fmt.Errorf("invalid item size %d", item)
		}
		feasibleIdx := make([]int, 0, len(remaining))
		feasibleRemaining := make([]int, 0, len(remaining))
		for i, rem := range remaining {
			if rem >= item {
				feasibleIdx = append(feasibleIdx, i)
				feasibleRemaining = append(feasibleRemaining, rem)
			}
		}
		if len(feasibleRemaining) == 0 {
			remaining = append(remaining, capacity-item)
			continue
		}
		scores := ScoreBin(item, feasibleRemaining, capacity)
		if len(scores) != len(feasibleRemaining) {
			return 0, fmt.Errorf("score length mismatch: got %d want %d", len(scores), len(feasibleRemaining))
		}
		bestLocal := -1
		bestScore := math.Inf(-1)
		for i, score := range scores {
			if math.IsNaN(score) || math.IsInf(score, 0) {
				return 0, fmt.Errorf("invalid score")
			}
			if bestLocal < 0 || score > bestScore {
				bestLocal = i
				bestScore = score
			}
		}
		remaining[feasibleIdx[bestLocal]] -= item
	}
	return len(remaining), nil
}

func evaluate(dataset Dataset) (Result, error) {
	result := Result{Instances: make([]InstanceResult, 0, len(dataset.Instances))}
	for _, instance := range dataset.Instances {
		used, err := packWithScore(instance.Items, instance.Capacity)
		if err != nil {
			return result, err
		}
		lb := lowerBound(instance.Items, instance.Capacity)
		gap := float64(used-lb) / float64(lb)
		result.Instances = append(result.Instances, InstanceResult{
			Name:       instance.Name,
			UsedBins:   used,
			LowerBound: lb,
			GapToLB:    gap,
		})
		result.AvgGapToLB += gap
		result.AvgUsedBins += float64(used)
		result.AvgLowerBound += float64(lb)
	}
	n := float64(len(dataset.Instances))
	if n == 0 {
		return result, fmt.Errorf("empty dataset")
	}
	result.AvgGapToLB /= n
	result.AvgUsedBins /= n
	result.AvgLowerBound /= n
	result.Objective = result.AvgGapToLB
	return result, nil
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: bin_packing_solver <dataset.json>")
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "read dataset: %v\n", err)
		os.Exit(1)
	}
	var dataset Dataset
	if err := json.Unmarshal(data, &dataset); err != nil {
		fmt.Fprintf(os.Stderr, "parse dataset: %v\n", err)
		os.Exit(1)
	}
	result, err := evaluate(dataset)
	if err != nil {
		fmt.Fprintf(os.Stderr, "evaluate: %v\n", err)
		os.Exit(1)
	}
	payload, _ := json.Marshal(result)
	fmt.Println(string(payload))
	fmt.Printf("first fit bins %.0f\n", avgBaseline(dataset, firstFit))
	fmt.Printf("best fit bins %.0f\n", avgBaseline(dataset, bestFit))
	fmt.Printf("final cost %.8f\n", result.Objective)
}

func avgBaseline(dataset Dataset, fn func([]int, int) int) float64 {
	if len(dataset.Instances) == 0 {
		return 0
	}
	total := 0.0
	for _, instance := range dataset.Instances {
		total += float64(fn(instance.Items, instance.Capacity))
	}
	return total / float64(len(dataset.Instances))
}
