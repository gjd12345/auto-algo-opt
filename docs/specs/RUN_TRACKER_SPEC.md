# RunTracker SPEC

> 位置：`eoh_rag/experiments/run_tracker.py`
> 目的：为每次 run 生成标准化元数据目录，用于事后分析、论文表格、结果 replay。
> 不改变 EoH 原始输出结构，只旁路落盘。

## 1. 责任边界

| 做 | 不做 |
| --- | --- |
| 创建 tracker 目录 + 标准化 JSON 文件 | 调度 run（属 batch_runner） |
| 落盘 eval_result / rag_trace / command 副本 | 评估 objective（属 evaluator） |
| finalize 时写 outcome + best_code.py | 读取 EoH 输出文件（调用方负责解析） |

## 2. 目录布局

```
<base_dir>/<suite>/<run_tag>/
├── run.json                      # 入口元数据（started_at, problem, arm, gen, rep）
├── command.json                  # 执行命令副本
├── official_eoh_run_summary.json # EoH 原始结果副本
├── eval_result.json              # evaluator 输出
├── rag_trace.json                # RAG 上下文追踪
├── outcome.json                  # 最终状态（status, objective）
└── best_code.py                  # 最优代码（仅 status=ok 时）
```

`run_tag` = `{problem}_{arm}_g{gen}_r{rep}`

## 3. 接口

```python
class RunTracker:
    def __init__(self, base_dir: str | Path)

    def start_run(suite, problem, arm, gen, rep, run_dir) -> Path
    def save_summary(tracker_dir, summary: dict) -> None
    def save_eval(tracker_dir, eval_result: dict) -> None
    def save_rag_trace(tracker_dir, rag_trace: dict) -> None
    def save_command(tracker_dir, cmd: list[str]) -> None
    def finalize(tracker_dir, status, best_code="", objective=None) -> None
```

## 4. 设计决策

- **旁路不侵入**：RunTracker 落盘与 EoH 的实际 run_dir 独立，不修改 EoH 的文件结构。
- **幂等**：重复调用 start_run 不崩，覆盖 run.json。
- **finalize 更新 run.json**：status 字段从 "running" → 实际状态。
- **best_code.py 只在有代码时写**：方便 grep/find 快速定位精英代码。

## 5. 验收标准

- `tests/test_run_tracker.py` 全绿（≥ 10 用例）
- start_run 创建目录 + run.json
- finalize 写 outcome.json 且更新 run.json status
- 即使 run.json 缺失也不崩（容错）
- 中文模块头前 30 行可回答"这是什么"

## 6. 联动组件

| 组件 | 关联 |
| --- | --- |
| Hooks | hooks.on_run_success 调用 tracker.save_eval / finalize |
| Replay 脚本 | 为历史 run 补写 tracker 目录 |
