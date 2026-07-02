# Literature-RAG 伪代码库

## 来源

每条伪代码都来自 VRP/VRPTW 领域的标准文献，统一改写为 InsertShips 可用的算法描述格式。

## 条目清单

| # | id | 算法 | 出处 | 适用密度 |
|---|---|---|---|---|
| 0 | `sa_seed_1` | SA baseline（Greedy Least-Cost） | 项目现有 main.go | 全部 |
| 1 | `nearest_insertion` | Nearest Insertion | Rosenkrantz et al. 1977 | d25（低密度） |
| 2 | `farthest_insertion` | Farthest Insertion | Rosenkrantz et al. 1977 | d25-d50（分散分布） |
| 3 | `solomon_i1` | Solomon I1 顺序插入 | Solomon 1987, Op. Res. | d50-d75（中高密度） |
| 4 | `regret2_insertion` | Regret-2 Insertion | Potvin & Rousseau 1993, EJOR | d50-d75（竞争插入场景） |
| 5 | `cw_savings` | Clarke-Wright Savings | Clarke & Wright 1964, Op. Res. | d50-d75（路线合并） |

## 格式说明

每条 CorpusItem 包含 4 部分：

1. **算法名 + 出处**：完整文献引用
2. **核心公式/准则**：选择订单或插入位置的数学标准
3. **标准伪代码**（10-30 行）：针对 InsertShips 场景改写
4. **InsertShips 映射说明**：Go 参数对应、安全约束、适用密度

安全约束（所有条目共享）：
- 不能漏单，任何订单必须有兜底插入路径
- 尝试插入前保存状态，失败后完整 rollback
- `RenewnTotalCost()` 必须在返回前恰好调用一次
- 不使用包/导入/外部调用、不打印日志

## 使用方法

corpus 已写入 `../corpus/algorithm_cards.jsonl`（与 code_examples、api_constraints、failure_cases 并列）。
运行时 `load_all_corpora()` 自动加载全部 6 条 algorithm_cards。

测试单实例：
```bash
python -m eoh_rag.experiments.eoh_arrival_grid \
  --problem rc102 --density d50 --arrival-scale 1.0 \
  --generations 1 --pop-size 4 \
  --ablation-pair --llm-model deepseek-v4-flash \
  --output-dir eoh_rag_workspace/reports/tables/rag_literature_rc102d50
```
