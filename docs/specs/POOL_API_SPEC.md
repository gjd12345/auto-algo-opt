# PoolAPI SPEC

> 位置：`eoh_rag/experiments/pool_api.py`
> 目的：统一 shared-pool 的读写入口。`PoolAPI` 类封装 pool_dir 下 4 类 JSONL 的
> append/read，供 batch_runner、hooks、retriever 调用。

## 1. 责任边界

| 做 | 不做 |
| --- | --- |
| pool_dir 下 4 类 JSONL 的 append/read | 决定谁应该 register（属 batch_runner / hooks） |
| 跨平台 advisory lock 保证多进程安全 | card synthesis / 语料库写入（属 `rag.card_synthesis`） |
| 目标值最小化（minimize）语义的排序去重 | baseline 阈值（属 `experiments.baselines`） |
| 失败模式短提示的静态推断 | 语义化理解失败原因（可交给小模型） |

## 2. 磁盘布局

```
<pool_dir>/
├── pool_index.jsonl                  # 每次完成 run 的索引
├── best_codes_<problem>.jsonl        # 每个 problem 的精英代码池
├── operator_stats_<problem>.jsonl    # e1/e2/m1/m2 的成功率统计
└── failures_<problem>.jsonl          # 失败代码短提示
```

所有文件是 **JSONL**（一行一条 dict），且 append-only。**永远不 truncate**——
数据演进时新建 pool_dir，不 rewrite 已有文件。

## 3. 接口

```python
class PoolAPI:
    def __init__(self, pool_dir: str | Path)

    # run 索引
    def register_run(problem, run_dir, objective, **meta) -> None
    def best_run(problem) -> str
    def list_runs(problem=None) -> list[dict]

    # 精英代码
    def register_code(problem, code, objective, **meta) -> None
    def best_codes(problem, top_k=3) -> list[dict]

    # 算子成功率
    def register_operator_stat(problem, operator, improved, delta) -> None
    def operator_weights(problem) -> dict[str, float]

    # 失败模式
    def register_failure(problem, code, failure_type, pattern_hint="") -> None
    def failure_hints(problem, top_k=5) -> list[str]
```

### 3.1 语义要点

- **objective 越小越好**（minimize）。`best_run` / `best_codes` 均按升序取。
- `best_codes` 会按 `objective` 去重，避免多次注入同一份 code。
- `operator_weights` 在 `total < 3` 时返回默认 `1.0`，避免早期偶然导致过拟合。
- `register_failure` 允许调用方传 `pattern_hint` 覆盖静态推断（hooks 可以让小模型
  来生成 hint）。
- `list_runs(problem=None)` 用于诊断脚本；生产代码请传具体 problem。

### 3.2 线程/进程安全

- 所有 append 走 `_append_jsonl`，用 `eoh_rag.utils.file_lock.exclusive_lock` 独占写。
- 读取无锁（append-only + JSONL 行独立 → 最坏情况读到少一行，不会读到损坏行）。

## 4. 调用约定

外部调用统一走 `PoolAPI` 实例方法，例如：

```python
# 例：batch_runner.py
PoolAPI(pool_dir).register_run(problem, run_dir, objective)
```

调用方只需构造一个 `PoolAPI(pool_dir)`，无需感知底层 JSONL 布局与文件锁细节。

## 5. 验收标准

- 单元测试 `tests/test_pool_api.py` 覆盖：
  - `register_run` + `best_run` 单/多 problem
  - `best_codes` 去重与 top_k
  - `operator_weights` 阈值行为（<3 → 1.0；≥3 → 0.5+rate）
  - `failure_hints` 按频次排序
  - 空 pool_dir 时读接口返回空
- 手工验证：拿现有 evidence 中 pool 目录（如果存在）跑 `PoolAPI.best_run`，
  结果符合 minimize 语义（取 objective 最小的 run）。
- 中文模块头：读前 30 行即可回答"这个模块解决什么"。

## 6. 演进边界

| 相关模块 | 会不会改 PoolAPI | 改动方向 |
| --- | --- | --- |
| batch_runner | ✗ | 内联函数统一调用 PoolAPI |
| baselines/evaluator | ✗ | 独立模块，不入池 |
| RunTracker | ✓ 可能新增 `register_run_manifest` | 追加 run 目录里的 manifest 摘要 |
| hooks | ✓ 可能新增 `register_hook_event` | 需要一个通用事件流 |
| card_synthesis | ✗ | 只影响阈值/词表 |
| 诊断脚本 | ✗ | 调用 PoolAPI 读写，不改接口 |

任何新增方法都要先更新本 SPEC，再改代码。
