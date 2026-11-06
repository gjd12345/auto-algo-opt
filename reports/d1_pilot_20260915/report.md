# D1 真实反馈链路试跑（2026-09-15）

## 结论

本次 D1 验证了 Coding Agent 真正进入第二轮决策链：第一轮可信 `EvaluationFacts` 被读取，Agent 选择了不同的 size-conditioned nonlinear mechanism，提交了带精确 `feedback_basis` 的第二轮 Plan，Runtime 生成并保存 `feedback_summary`，随后执行了 `population_seeds` 门禁。

结果没有形成可比较的两轮效果数据：第一轮只完成 baseline 和 1 个有效生成候选，均为 `0.0` gap；因 `DEADLINE_EXCEEDED` 未产生完整 final population snapshot，第二轮被正确终止为 `POPULATION_SNAPSHOT_MISSING`，没有冷启动替代，也没有虚构第二轮结果。

固定身份：`qwen/deepseek-v4.1-flash`；model-router endpoint；API key env `MODEL_ROUTER_API_KEY`；profile `eohs_v1/obp_evolution_mini`；Memory / KB / repair 为 OFF；私有 chain-of-thought 未收集。

公开证据：

- compact bundle：`reports/evidence/d1_router_v41_20260915/`
- full Session：`outputs/obp_d1_router_v41_20260915/session/`
- round summary：`outputs/obp_d1_router_v41_20260915/session/round_progress.md`
- controller/environment identity：Session `config_frozen.json` 与 manifest

这是 controller wiring 和安全门禁结果，不是性能结论，也不能与历史 D0 做因果比较。后续 D1 需要更宽裕的 round wall-clock 或更低延迟的 provider 配置，以便形成完整 final population 后再测试 population-seed inheritance。
