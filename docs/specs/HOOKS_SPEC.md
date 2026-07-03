# Hooks SPEC

> 位置：`eoh_rag/experiments/hooks.py`
> 目的：把 pool 注册、card 合成、outcome 追加等副作用逻辑收拢到两个事件函数
> `on_run_success` / `on_run_failure`，供主循环或测试独立调用。

## 1. 责任边界

| 做 | 不做 |
| --- | --- |
| 组合调用 PoolAPI + evaluator + card_synthesis | 调度 run（属 batch_runner） |
| 决定是否触发 card 合成（evaluator passed） | 实际的 JSONL 读写（属 PoolAPI） |
| 追加 online outcome 记录 | 管理 outcome 文件生命周期 |

## 2. 接口

```python
def on_run_success(
    pool: PoolAPI,
    problem: str,
    run_dir: str,
    summary: dict,       # EoH run summary（含 run_summary + rag_trace）
    manifest: dict,      # 实验 manifest（取 operators 字段）
    outcome_file: str = "",
) -> dict               # evaluator 结果

def on_run_failure(
    pool: PoolAPI,
    problem: str,
    summary: dict,
) -> None
```

## 3. on_run_success 执行顺序

1. 从 summary 提取 `best_objective` 和 `best_code`
2. 调用 `evaluate_run(problem, objective)` 得到 eval_result
3. 读取当前 pool 最佳（用于 operator delta 计算）
4. `pool.register_run(...)` + `pool.register_code(...)`
5. 若 `eval_result["passed"]` → `_maybe_synthesize_card(...)`
6. 若有 prev_best → `pool.register_operator_stat(...)`
7. 若 outcome_file 非空 → `_append_online_outcome(...)`
8. 返回 eval_result

## 4. on_run_failure 执行顺序

1. 从 summary 提取 failure_reason + best_code
2. 若两者都有 → `pool.register_failure(problem, code, fail_reason)`

## 5. 验收标准

- `tests/test_hooks.py` 全绿（≥ 9 用例）
- on_run_success 正确注册 run/code/operator
- card 合成只在 passed=True 时触发
- on_run_failure 在缺 code 或 reason 时静默跳过
- 中文模块头前 30 行可回答"这是什么"

## 6. 与 batch_runner 的关系

batch_runner 主循环目前以等价的内联逻辑实现同一套副作用（pool 注册、card 合成、outcome 追加）。
hooks 把这套逻辑抽取为两个事件函数并配单元测试，作为可复用入口；调用方可按如下方式使用：

```python
# 在主循环中调用
if run_ok:
    eval_r = on_run_success(pool, problem, run_out, sm, manifest, outcome_file)
else:
    on_run_failure(pool, problem, sm)
```
