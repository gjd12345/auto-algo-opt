# Q3 v2 正式实验报告

结论：`directional_support`。10 个 seed 全部形成三臂完整配对。
answer 相对 pure 的 median gain 为 0.7275，win/tie/loss = 7/0/3。

| arm | runs | median 5k gap | valid candidate rate |
|---|---:|---:|---:|
| pure | 10 | 3.9825 | 100.0% |
| generic | 10 | 3.9530 | 100.0% |
| answer | 10 | 2.7965 | 100.0% |

判定严格使用计划锁定的方向性规则，不使用 p 值。generic 仅作机制诊断。
已导出 3 份通过 AST 与敏感信息检查的最佳代码。
