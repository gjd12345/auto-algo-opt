"""
模块：定向变异算子（directed_mutate）
功能：借助大模型（LLM）对 InsertShips 问题的 Go 启发式函数做「有方向」的变异，
      用历史信息引导每次改动，而非随机扰动。
职责：
    - 组织变异提示词（父代代码 + 性能上下文 + 历史结果 + 失败约束 + 策略建议）。
    - 调用 LLM 生成变异后的 Go 代码，并从回复中抽取出完整的 InsertShips 函数。
    - 记录每一代的统计信息，供后续变异参考。
接口：
    - MUTATION_SYSTEM_PROMPT：约束 LLM 行为的系统提示词（要求只改一处、保持函数签名等）。
    - DirectedMutator(api_key, api_endpoint, model)：核心类，提供
      build_mutation_prompt(...) 构造提示、mutate(...) 生成单个变异、
      mutate_batch(...) 批量生成、record_generation(stats) 记录一代结果。
输入：
    - 父代 Go 代码字符串；当前最优分数 / 目标分数；失败约束与策略引导文本。
    - LLM 访问所需的 api_key / api_endpoint / model（可留空走默认）。
输出：
    - 变异后的 InsertShips 函数源码字符串（失败时返回 None 或空列表）。
示例：
    mutator = DirectedMutator(api_key="...", api_endpoint="...", model="...")
    child_code = mutator.mutate(parent_code=go_src, target_score=1000.0)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


# 发给 LLM 的系统提示词：设定角色（Go 与车辆路径优化专家），并明确变异规则——
# 必须保持函数可编译、只做一处有意义的改动、沿用给定的类型与方法、只返回完整的
# InsertShips 函数（放在 Go 代码块里，不要额外解释）。
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
    """调用 LLM 生成变异结果。

    把系统提示词与传入的用户 prompt 一起发给聊天补全接口，返回模型的文本回复。

    参数：
        prompt：用户侧提示（父代代码与各类上下文，由 build_mutation_prompt 拼装）。
        api_key / api_endpoint：访问凭证与地址，留空则由底层客户端按默认配置处理。
        model：模型名，留空时回退到 "deepseek-v4-flash"。
        timeout：单次请求的超时秒数。

    返回：模型回复字符串；请求出错时返回 None。
    """
    # 在函数内部导入，避免模块加载时就强依赖 LLM 客户端。
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
        # LLM 调用失败时不抛出，交由上层判断为「本次变异未产出」。
        return None


def _extract_code(response: str) -> str | None:
    """从 LLM 回复中抽取完整的 InsertShips 函数源码。

    先尝试取出 Go 代码块的内容；再从中定位 `func InsertShips(...) Dispatch {`
    起始位置，丢弃前面的多余文本，只保留函数本体。

    参数：
        response：LLM 的原始文本回复。

    返回：清洗后的函数源码字符串；若找不到 InsertShips 函数则返回 None。
    """
    # 优先匹配 ```go / ```golang 代码块；匹配不到则退化为使用整段回复。
    m = re.search(r"```(?:go|golang)?\s*\n(.*?)```", response, re.DOTALL)
    if m:
        code = m.group(1).strip()
    else:
        code = response.strip()

    # 定位函数签名，把签名之前的说明性文字截掉。
    func_match = re.search(
        r"func\s+InsertShips\s*\(.*?\)\s*Dispatch\s*\{",
        code, re.DOTALL
    )
    if func_match:
        code = code[func_match.start():]

    # 兜底校验：确实包含目标函数才算有效结果。
    if "func InsertShips" not in code:
        return None
    return code.strip()


class DirectedMutator:
    """定向变异器：用 LLM 结合历史信息，对启发式代码做有方向的改进。

    维护一份「代际历史」，据此提醒模型避开已试过的策略、聚焦到尚未尝试的方向，
    从而让每一代变异都带有明确意图。
    """

    def __init__(self, api_key: str = "", api_endpoint: str = "",
                 model: str = ""):
        """初始化变异器。

        参数：
            api_key / api_endpoint / model：LLM 访问配置，均可留空走默认。
        """
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.model = model
        # 逐代累积的统计信息，供 _summarize_history 汇总进提示词。
        self.generation_history: list[dict[str, Any]] = []

    def _summarize_history(self, max_entries: int = 3) -> str:
        """把最近若干代的结果汇总成一段文本，嵌入变异提示词。

        参数：
            max_entries：最多回顾多少代（默认最近 3 代）。

        返回：可读的历史摘要；若还没有任何一代则返回固定提示 "No previous generations."。
        """
        if not self.generation_history:
            return "No previous generations."

        lines = ["## Previous Generation Results\n"]
        # 只取最近 max_entries 代，逐条列出关键指标与策略。
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
        """记录一代的结果，供后续变异参考。

        参数：
            stats：本代的统计字典（如最优/平均适应度、失败率、最佳策略等）。
        """
        self.generation_history.append(stats)
        # 只保留最近 10 代，避免历史无限增长。
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
        """拼装带完整上下文的变异提示词。

        依次拼入：待变异的父代代码、当前/目标分数、历史摘要、失败约束，
        以及策略引导（外部指定则直接使用，否则自动挑选一个近期没试过的策略）。

        参数：
            parent_code：作为变异起点的 Go 源码。
            current_best_score：当前最优分数（可选）。
            target_score：期望超越的目标分数（可选）。
            failure_constraints：需要规避的失败约束文本（可选）。
            strategy_guidance：显式指定的策略引导（可选）。

        返回：完整的用户提示词字符串。
        """
        parts = []

        # 1) 待变异的父代代码。
        parts.append("## Parent Code (to mutate)\n")
        parts.append(f"```go\n{parent_code}\n```\n")

        # 2) 性能上下文：当前分数与目标分数。
        if current_best_score is not None:
            parts.append(f"Current best score: {current_best_score:.2f}")
        if target_score is not None:
            parts.append(f"Target score to beat: {target_score:.2f}")
        if current_best_score is not None or target_score is not None:
            parts.append("")

        # 3) 历史摘要：仅在确有历史时加入。
        history = self._summarize_history()
        if history != "No previous generations.":
            parts.append(history)

        # 4) 失败约束：提醒模型避开已知问题。
        if failure_constraints:
            parts.append(failure_constraints)

        # 5) 策略引导：外部给定则直接采用，否则自动推荐未试过的方向。
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
            # 从最近 5 代的最佳策略里提取关键词，过滤掉已经尝试过的方向。
            tried = {g.get("best_algorithm", "") for g in self.generation_history[-5:]}
            untried = [s for s in strategies if not any(
                keyword in t.lower()
                for t in tried
                for keyword in ["time-window", "regret", "load balanc", "sorting", "look-ahead"]
            )]
            if untried:
                # 有未试过的策略：最多推荐两条。
                parts.append("Consider trying one of these untried strategies:")
                for s in untried[:2]:
                    parts.append(f"- {s}")
            else:
                # 策略都试过了：让模型继续打磨近期最优方案。
                parts.append("Try to further refine the best strategy from recent generations.")
            parts.append("")

        # 6) 收尾要求：只做一处改进，返回完整函数。
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
        """生成单个定向变异结果。

        参数：与 build_mutation_prompt 一致，用于拼装提示词。

        返回：变异后的 InsertShips 函数源码；LLM 无回复或抽取失败时返回 None。
        """
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
        """批量生成多个定向变异结果。

        为每个候选轮流指派一个不同的策略引导，以增加变异方向的多样性。

        参数：
            parent_code：变异起点的 Go 源码。
            batch_size：期望生成的变异数量。
            current_best_score / target_score：性能上下文（可选）。
            failure_constraints：需规避的失败约束（可选）。

        返回：抽取成功的函数源码列表；失败的候选会被跳过，因此长度可能小于 batch_size。
        """
        results: list[str] = []
        strategies = [
            "Focus on time-window awareness in vehicle selection.",
            "Implement regret-based insertion (compare best vs second-best).",
            "Add load balancing to the scoring function.",
            "Optimize the vehicle sorting order with a composite score.",
        ]

        for i in range(batch_size):
            # 前若干个候选各分配一种预设策略；超出策略数量后不再附加引导。
            guidance = strategies[i % len(strategies)] if i < len(strategies) else ""
            code = self.mutate(
                parent_code=parent_code,
                current_best_score=current_best_score,
                target_score=target_score,
                failure_constraints=failure_constraints,
                strategy_guidance=guidance,
            )
            # 仅收集成功抽取到的代码。
            if code:
                results.append(code)

        return results
