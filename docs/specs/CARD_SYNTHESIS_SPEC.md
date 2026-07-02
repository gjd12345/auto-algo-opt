# Card Synthesis SPEC

> 位置：`eoh_rag/rag/card_synthesis.py` + `eoh_rag/rag/problem_vocab.py`
> 目的：把进化产出的 best code 转成可检索的 Skill Card，并保证 card 用词严格
> 隔离在本 problem 词表内（BP card 绝不出现 TSP/CVRP 术语，反之亦然）。

## 1. 责任边界

| 做 | 不做 |
| --- | --- |
| 从 best code 抽取 strategy features | 决定哪段 code 值得合成（属 evaluator/hooks） |
| 用 problem 专属词表生成 title/summary/content | 判断 objective 是否达标（属 evaluator） |
| 把 card append 到 RAG corpus（去重） | 检索/重排 card（属 rag.retriever/reranker） |
| 保证跨 problem 词表零泄漏 | 语义化理解代码（未来可交小模型） |

## 2. 组件

### 2.1 problem_vocab.py

```python
BP_FEATURE_DO / BP_FEATURE_WHEN     # bin packing 术语（residual/tight_fit/utilization/...）
TSP_FEATURE_DO                       # TSP 术语（destination/regret/two_opt/...）
CVRP_FEATURE_DO                      # CVRP 术语（depot_distance/savings/sweep/...）

def get_feature_vocab(problem) -> tuple[dict, dict]   # (feature_do, feature_when)
```

- `get_feature_vocab` 是 card_synthesis 取词的唯一入口。
- 未知 problem 返回 `({}, {})` —— 调用方须能容忍空词表（退化为通用描述）。
- BP 词表包含 5 个与 evidence 中"same-size reservation"策略对齐的特征：
  `same_size_reservation`、`item_scaled_residual`、`reusable_slack`、
  `dead_gap_avoidance`、`awkward_gap_penalty`。DO 与 WHEN 两张表必须成对出现。

### 2.2 card_synthesis.py 主要接口

```python
def synthesize_card(problem, code, objective, ...) -> CorpusItem | None
def append_card_to_corpus(card: CorpusItem, corpus_dir) -> bool   # 去重后 append
def extract_strategy_features(code) -> set[str]                    # canonical 特征抽取
def _build_content(problem, features, code=None) -> str           # 用 get_feature_vocab 渲染
```

- `_build_content` 内部调用 `get_feature_vocab(problem)`，只渲染命中词表的 feature。
- `synthesize_card` 产出 `CorpusItem`，`item_id` 形如 `history_<problem>_<feature_hash>`。
- `append_card_to_corpus` 以 `item_id` / 内容 hash 去重，重复返回 `False` 不写入。

## 3. 词表隔离契约（核心验收点）

1. **BP card 不得出现** `destination / depot / tour / nearest_node / farthest`
   （TSP 术语）与 `depot_distance / savings / sweep / capacity`（CVRP 术语）。
2. **TSP 词表不得出现** `residual / tight_fit / utilization / fragmentation / bin / gap_penalty`（BP 术语）。
3. 修改任何一张词表后，`tests/test_bp_card_synthesis.py` 必须仍然全绿。

## 4. 与其他模块关系

- **evaluator**：card 合成只应在 `decision == "archive"` 时触发。
  batch_runner 的 `_maybe_synthesize_card` 用 5% 阈值，与 evaluator default 一致。
- **hooks**：`on_run_success` 里的 `maybe_synthesize_history_card(...)`
  是合成 card 的唯一生产入口；batch_runner 主体不直接调 card_synthesis。
- **retriever/reranker**：只消费 corpus 里的 card，不参与合成。

## 5. 验收标准

- `tests/test_bp_card_synthesis.py` 全绿，覆盖：
  - BP 5 个特征在 DO 与 WHEN 中成对存在
  - BP 词表与 TSP/CVRP 术语零交集
  - `_build_content("bp_online", ...)` 输出不含 destination/depot/tour
  - `get_feature_vocab` 已知/未知 problem 行为
- 人工抽查：拿一段 BP best code 跑 `synthesize_card`，card 描述读起来是装箱语言。

## 6. 后续演进

| 方向 | 说明 |
| --- | --- |
| 小模型改写 | 未来用小模型替换模板 `_build_content`，但仍受词表隔离约束 |
| 词表扩充 | 新策略先加进 `problem_vocab`，再在 test 里补断言，最后才改合成逻辑 |
| 多 problem | 新增 problem 时补 `<PROBLEM>_FEATURE_DO` 并在 `get_feature_vocab` 注册 |
