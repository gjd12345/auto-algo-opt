# Evaluator SPEC

> 位置：`eoh_rag/experiments/evaluator.py` + `eoh_rag/experiments/baselines.py`
> 目的：把"这次 run 表现如何、下一步该怎么办"这个决策收拢到一个纯函数里，避免每
> 个调用点各写一份 `if improvement > 0.05`。

## 1. 责任边界

| 做 | 不做 |
| --- | --- |
| 用 baseline 计算 improvement | 从磁盘读 run 结果 |
| 输出 decision ∈ {archive, continue, adjust, escalate} | 执行 archive / escalate 的副作用 |
| 处理 NaN / inf / 缺失 objective | 修复评估失败（属 evaluator 外层） |

## 2. baselines.py

```python
PROBLEM_BASELINES = {
    "bp_online":     0.0398,   # Online Bin Packing (Weibull, 1k items)
    "tsp_construct": 6.560,    # TSP construct heuristic (n=100)
    "cvrp_construct": 13.519,  # CVRP construct heuristic (n=200)
}
```

- 这些常量对齐冻结 evidence（`evidence/final_batch_20260630/`）。
- 修改前必须先修改 evidence README 并保留旧值痕迹。

## 3. evaluate_run 签名

```python
def evaluate_run(
    problem: str,
    objective: float,
    baseline: float | None = None,
    target_improvement: float = 0.05,
) -> dict
```

返回 dict：

```json
{
  "problem": "bp_online",
  "objective": 0.00674,
  "baseline": 0.0398,
  "improvement": 0.831,
  "target": 0.05,
  "passed": true,
  "decision": "archive",
  "reason": "improvement=0.831 >= target=0.050; eligible for archive/card"
}
```

## 4. Decision 语义

| decision | 触发条件 | 期望调用方行为 |
| --- | --- | --- |
| `archive` | `improvement >= target_improvement` | 写入精英代码池 / 合成 card / 计入报告 |
| `continue` | `0 <= improvement < target` | 继续进化，不额外副作用 |
| `adjust` | `improvement < 0` 或 objective NaN/inf | 换 seed / 换 operator，或减小步长 |
| `escalate` | 未知 problem baseline | 上报人（不要自动跑） |

`passed=True` 严格等价于 `decision=="archive"`。

## 5. improvement 定义

```
improvement = (baseline - objective) / |baseline|
```

- objective 越小越好。
- 用 `|baseline|` 避免负 baseline（虽然三个 problem 都是正数）。
- baseline == 0 情况暂不出现；若未来出现要单独处理（现设计会 ZeroDivisionError）。

## 6. 与其他模块的关系

- **PoolAPI**：`register_run` / `register_code` 本身不判断 improvement，调用方拿到
  `evaluate_run` 结果后决定是否入池。
- **card_synthesis**：应该只在 `decision == "archive"` 时被触发。当前 `_maybe_synthesize_card`
  的 5% 阈值 与本模块 default target 一致，由 hooks 统一入口触发。
- **RunTracker**：会把 evaluator 的输出落到 `run.json` 的 `eval` 字段。

## 7. 验收标准

- `test_evaluator.py` 全绿(≥ 12 用例覆盖 4 种 decision + edge cases)
- 三个 problem 的冻结 evidence 输入 → decision = archive
- 未知 problem → decision = escalate(拒绝隐式默认)
- objective=NaN / inf → decision = adjust(不 crash)

## 8. 与相关模块的联动

| 模块 | 关联点 |
| --- | --- |
| RunTracker | `save_eval(run_dir, eval_result)` 直接落 evaluator 输出 |
| Hooks | `on_run_finished(eval)` 触发 card 合成，取代 batch_runner 里内联的 `_maybe_synthesize_card` |
| BP 词表 | 词表更新会影响 card 合成，但不影响 evaluator 打分 |
