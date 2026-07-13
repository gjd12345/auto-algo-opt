# 正式策略实验证据

- [实验协议](../../docs/experiments/gated_strategy_card_experiments.md)
- [Q3 v2 正式报告](q3_v2/q3_report.md)
- [跨问题迁移正式报告](cross_problem_transfer/cross_report.md)
- [Q3 胜出卡组件归因](q3_card_components/component_report.md)
- [对抗候选数据缺口](adversarial_candidates.json)

## 综合结论

- Q3：`directional_support`，answer 对 pure 为 7 胜 3 负，中位改善 0.7275。
- 跨问题迁移：`inconclusive`；TSP Core-12 没有完整配对，不能确认迁移收益。
- 组件归因：`supports_pair_complementarity`；任一单卡都不足以解释双卡 answer 的优势。

原始运行目录受 `.gitignore` 保护；本目录仅保存 manifest 锁、环境白名单、紧凑索引、配对结果、判定与通过安全检查的最佳代码。
