# 跨问题策略迁移正式实验报告

结论：`inconclusive`。完整配对 9/15，win/tie/loss = 2/4/3。

| problem | complete pairs | median relative gain | raw p | Holm p |
|---|---:|---:|---:|---:|
| bp_online | 5 | 0.0000% | 1.0000 | 1.0000 |
| tsp_construct | 0 | N/A | N/A | N/A |
| cvrp_construct | 4 | -1.9962% | N/A | N/A |

Core suite 任一固定实例无有限 gap 时，该 problem + seed 配对不进入 Wilcoxon；禁止静默删除 timeout 或不可行实例。
已导出 4 份通过 AST、held-out 完整性与敏感信息检查的最佳代码。
