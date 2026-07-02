"""
Directed mutation: replace random m1/m2 EOH mutation operators with
LLM-driven targeted improvements informed by:
1. Analysis of what worked/failed in previous generations
2. Known failure patterns from FailureMemory
3. Specific optimization targets

The LLM receives:
- The parent code (best candidate from previous generation)
- Performance context (current score, target score)
- What worked in other successful candidates
- What failed patterns to avoid
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


MUTATION_SYSTEM_PROMPT = """You are an expert in Go programming and vehicle routing optimization.

Your task is to mutate a Go InsertShips function to improve its performance on dynamic vehicle routing with pickup and delivery.

## Mutation Guidelines

1. **Preserve correctness**: The function must compile and produce valid routes.
2. **Target improvement areas**: Better vehicle selection strategy, smarter insertion ordering, time-window awareness, regret-based decisions, load balancing.
3. **Keep the structure**: Maintain the same function signature. Use only provided types and methods.
4. **One meaningful change per mutation**: Don't throw everything at once. Make ONE strategic improvement.

## Available types and methods

```go
const MAXASSIGNS = 64
const MAXSHIPS = 8

type Station struct { X, Y, TimeStart, TimeEnd, ReqCode, Load int }
type Ship struct { Id, Ori, Des, Load int }

type Assign struct {
    // Embedded: RoutingTask (Stations, StationsLen, Speed, TimeCurrent, StationCurrent, LoadCurrent, LoadCap)
    // Embedded: RoutingResult (Cost, Route, RouteLen)
    NextSta, NextTime int
    StaIndexes [MAXSHIPS]Ship
    StaIndexesLen int
    AccumulatedCost float64
}
// Methods: AddShip(id int, ori, des Station) bool
//          RemoveShip(id int)
//          GenRoute()

type Dispatch struct {
    Assigns [MAXASSIGNS]Assign
    AssignsLen int
    TotalCost float64
}
// Methods: RenewnTotalCost()

// Utility: func cal_dis(st1, st2 Station) float64
//          func Abs(x int) int
```

## Output format

Return ONLY the complete InsertShips function, enclosed in a markdown code block. No explanation.
```go
func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
    // your mutated code here
}
```
"""


def _call_llm(prompt: str, api_key: str = "", api_endpoint: str = "",
              model: str = "", timeout: int = 120) -> str | None:
    from eoh_rag.llm.client import chat_completion

    try:
        return chat_completion(
            messages=[
                {"role": "system", "content": MUTATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            api_key=api_key,
            endpoint=api_endpoint,
            model=model or "deepseek-v4-flash",
            temperature=0.6,
            timeout_s=timeout,
            max_retries=3,
        )
    except RuntimeError:
        return None


def _extract_code(response: str) -> str | None:
    m = re.search(r"```(?:go|golang)?\s*\n(.*?)```", response, re.DOTALL)
    if m:
        code = m.group(1).strip()
    else:
        code = response.strip()

    func_match = re.search(
        r"func\s+InsertShips\s*\(.*?\)\s*Dispatch\s*\{",
        code, re.DOTALL
    )
    if func_match:
        code = code[func_match.start():]

    if "func InsertShips" not in code:
        return None
    return code.strip()


class DirectedMutator:
    """Generates targeted mutations using LLM informed by generation history."""

    def __init__(self, api_key: str = "", api_endpoint: str = "",
                 model: str = ""):
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.model = model
        self.generation_history: list[dict[str, Any]] = []

    def _summarize_history(self, max_entries: int = 3) -> str:
        if not self.generation_history:
            return "No previous generations."

        lines = ["## Previous Generation Results\n"]
        for gen in self.generation_history[-max_entries:]:
            lines.append(f"### Generation {gen.get('gen', '?')}")
            lines.append(f"- Best fitness: {gen.get('best_fitness', 'N/A')}")
            lines.append(f"- Average fitness: {gen.get('avg_fitness', 'N/A')}")
            lines.append(f"- Failure rate: {gen.get('none_rate', 'N/A')}")
            if gen.get("best_algorithm"):
                lines.append(f"- Best strategy: {gen['best_algorithm']}")
            if gen.get("surviving_strategies"):
                lines.append(f"- Surviving strategies: {', '.join(gen['surviving_strategies'])}")
            lines.append("")
        return "\n".join(lines)

    def record_generation(self, stats: dict[str, Any]) -> None:
        """Record the results of a completed generation for future mutations."""
        self.generation_history.append(stats)
        # Keep only last 10 generations
        if len(self.generation_history) > 10:
            self.generation_history = self.generation_history[-10:]

    def build_mutation_prompt(
        self,
        parent_code: str,
        current_best_score: float | None = None,
        target_score: float | None = None,
        failure_constraints: str = "",
        strategy_guidance: str = "",
    ) -> str:
        """Build a mutation prompt with full context."""
        parts = []

        parts.append("## Parent Code (to mutate)\n")
        parts.append(f"```go\n{parent_code}\n```\n")

        if current_best_score is not None:
            parts.append(f"Current best score: {current_best_score:.2f}")
        if target_score is not None:
            parts.append(f"Target score to beat: {target_score:.2f}")
        if current_best_score is not None or target_score is not None:
            parts.append("")

        history = self._summarize_history()
        if history != "No previous generations.":
            parts.append(history)

        if failure_constraints:
            parts.append(failure_constraints)

        if strategy_guidance:
            parts.append("## Mutation Strategy Guidance\n")
            parts.append(strategy_guidance)
        else:
            parts.append("## Mutation Strategy Guidance\n")
            strategies = [
                "Add time-window awareness: prefer vehicles that are closer to the pickup time window.",
                "Implement regret-k insertion: compute best and second-best insertion costs, pick the ship with highest regret.",
                "Add load balancing: penalize vehicles that are already heavily loaded.",
                "Improve sorting: score vehicles by a weighted combination of distance + urgency + load.",
                "Add look-ahead: estimate how current insertion affects future insertions.",
            ]
            # Pick a strategy we haven't tried recently
            tried = {g.get("best_algorithm", "") for g in self.generation_history[-5:]}
            untried = [s for s in strategies if not any(
                keyword in t.lower()
                for t in tried
                for keyword in ["time-window", "regret", "load balanc", "sorting", "look-ahead"]
            )]
            if untried:
                parts.append("Consider trying one of these untried strategies:")
                for s in untried[:2]:
                    parts.append(f"- {s}")
            else:
                parts.append("Try to further refine the best strategy from recent generations.")
            parts.append("")

        parts.append("Make ONE strategic improvement. Return the complete mutated function.")

        return "\n".join(parts)

    def mutate(
        self,
        parent_code: str,
        current_best_score: float | None = None,
        target_score: float | None = None,
        failure_constraints: str = "",
        strategy_guidance: str = "",
    ) -> str | None:
        """Generate a single directed mutation. Returns mutated code or None."""
        prompt = self.build_mutation_prompt(
            parent_code=parent_code,
            current_best_score=current_best_score,
            target_score=target_score,
            failure_constraints=failure_constraints,
            strategy_guidance=strategy_guidance,
        )

        response = _call_llm(prompt, self.api_key, self.api_endpoint, self.model)
        if not response:
            return None

        return _extract_code(response)

    def mutate_batch(
        self,
        parent_code: str,
        batch_size: int = 4,
        current_best_score: float | None = None,
        target_score: float | None = None,
        failure_constraints: str = "",
    ) -> list[str]:
        """Generate multiple directed mutations. Returns list of code strings."""
        results: list[str] = []
        strategies = [
            "Focus on time-window awareness in vehicle selection.",
            "Implement regret-based insertion (compare best vs second-best).",
            "Add load balancing to the scoring function.",
            "Optimize the vehicle sorting order with a composite score.",
        ]

        for i in range(batch_size):
            guidance = strategies[i % len(strategies)] if i < len(strategies) else ""
            code = self.mutate(
                parent_code=parent_code,
                current_best_score=current_best_score,
                target_score=target_score,
                failure_constraints=failure_constraints,
                strategy_guidance=guidance,
            )
            if code:
                results.append(code)

        return results
