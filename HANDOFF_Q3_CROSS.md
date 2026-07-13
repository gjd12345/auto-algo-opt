# Q3 v2 与跨问题迁移实验交接

## 状态

计划内 Proxy 6/6、Q3 30/30、Cross 30/30 均已完成。Q3 与 Cross 的 60 个正式 run 状态均为 `ok`。随后按自动决策门禁执行 20 个 Q3 胜出卡组件归因坐标，其中 12 个有效、8 个在预设重试后失败；失败坐标原样保留。原始运行目录保持 Git ignored；可提交证据只包含 manifest 锁、环境白名单、数据哈希、紧凑索引、显式配对结果、判定和安全检查后的最佳代码。

## 结论

- Q3：`directional_support`。10 个 seed 完整配对，answer 相对 pure 的 median gain 为 0.7275，win/tie/loss 为 7/0/3。
- Cross：`inconclusive`。BP 5/5、TSP 0/5、CVRP 4/5 完整配对；全局检验不执行。TSP timeout 与 CVRP 不可行结果均被保留，未删样本换取显著性。
- 组件归因：`supports_pair_complementarity`。harmonic-only 9/10 有效，residual-poly-only 3/10 有效；answer 相对两者分别为 7/1/1 和 3/0/0。单卡实验同时改变上下文长度和候选选择空间，因此只支持“互补或上下文交互”，不宣称严格加性协同。
- 对抗候选：605-run 冻结快照缺少 `failures_<problem>.jsonl`，因此明确记录为 `needs_human_review`，没有从成功代码或日志臆造失败模式。

## 证据入口

- 协议：[`docs/experiments/gated_strategy_card_experiments.md`](docs/experiments/gated_strategy_card_experiments.md)
- Q3：[`reports/strategy_experiments/q3_v2/q3_report.md`](reports/strategy_experiments/q3_v2/q3_report.md)
- Cross：[`reports/strategy_experiments/cross_problem_transfer/cross_report.md`](reports/strategy_experiments/cross_problem_transfer/cross_report.md)
- 组件归因：[`reports/strategy_experiments/q3_card_components/component_report.md`](reports/strategy_experiments/q3_card_components/component_report.md)
- 汇总索引：[`reports/strategy_experiments/README.md`](reports/strategy_experiments/README.md)
- Kami 报告：[`reports/kami/q3-v2-cross-transfer-execution-report.pdf`](reports/kami/q3-v2-cross-transfer-execution-report.pdf)

## 复核命令

```powershell
python scripts/export_strategy_experiment_evidence.py --repository-root .
python -m pytest tests/test_strategy_evidence_export.py -q
python -m pytest -q
python -m compileall -q eoh_rag official_eoh scripts
git diff --check
```

## 结论边界与下一步

Q3 主问题已经得到方向性支持，组件实验进一步把收益定位到双卡组合，而不是任一单卡。Cross 当前不能宣称存在迁移增益；若继续研究，应先将 TSP 大规模 Core 的评测合同拆成独立、有预算上限的稳定基准，再按新协议重新跑完整 15 对，不得复用本轮不完整配对补齐显著性。若要严格区分“策略互补”与“上下文长度/候选空间效应”，应另行预注册等长度、等候选数对照，而不是对本轮 8 个失败坐标继续补抽。对抗候选只有在补齐 failure JSONL 并经人工评审后，才能进入下一版 Core。
