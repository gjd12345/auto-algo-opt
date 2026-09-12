# auto-algo-opt
生产搜索使用锁定提交的官方 FeiLiu36/EoH。当前实现与 3+1 修复边界见 [审计验收报告](reports/audit_20260912/acceptance.md)，阶段 1、2 的运行证据见 [历史验收报告](reports/stage12_acceptance_20260911.md)。

支持 `cvrp_construct`、`tsp_construct`、`tsp_2opt`。官方引擎负责种群、父本选择及 e1/e2/m1/m2；适配层负责隔离评测、预算、进程停止、证据和 skill 发布。

```powershell
py -3.11 -m pip install -e ".[dev,eoh]"
py -3.11 -m pytest -q
py -3.11 -m agent_skill_loop smoke --problem cvrp_construct --output outputs/offline_smoke
```

smoke 使用 localhost 模型响应，完整执行官方引擎，无外部模型调用。旧 AgentLoop、固定策略和 fixture harness 已从当前测试入口移除，生产中没有旧循环兼容入口。

用户授权的真实运行示例（DeepSeek 官方 OpenAI 兼容 API）：

```powershell
py -3.11 -m agent_skill_loop run --problem cvrp_construct --model deepseek-flash --endpoint https://api.deepseek.com --api-key-env DEEPSEEK_API_KEY --pop-size 2 --n-pop 1 --max-sample-nums 2 --max-requests 7 --wall-seconds 180 --output outputs/live
```

`python -m eoh_frozen run` 与上述 run 共用参数和实现。`max-sample-nums` 仅限制初始化后的进化尝试；冷启动另有 `2 * pop_size` 个初始化尝试。探活、解析/去重重试也消耗真实 HTTP 请求预算，较小预算允许提前停止。

```powershell
py -3.11 -m agent_skill_loop prepare --problem tsp_construct --output outputs/prepared
py -3.11 -m agent_skill_loop evaluate-skill --skill outputs/live/exported_skill --suite outputs/live/dev_suite.json
```

`--parent-skill PATH` 显式导入父本，当前套件检查通过后经官方 seed 路径使用。历史分数不继承。基线、显式父本、本次生成资产分别记录；`best_generated_path` 仅指向本次已评测的有效生成候选。

3+1 workflow 入口会按 Plan → 官方 EoH Execute → Evaluate 运行，并可通过 `--memory-store` 启用版本化轻量 Memory：

```powershell
py -3.11 -m agent_skill_loop workflow --problem cvrp_construct --model deepseek-flash --endpoint https://api.deepseek.com --api-key-env DEEPSEEK_API_KEY --output outputs/workflow --rounds 1 --max-requests 12 --memory-store outputs/memory_store
```

历史研究材料保留为追溯证据，不作为当前执行指引。

Phase 1 已提供不触发外部效果的 SQLite session control plane：

```powershell
py -3.11 -m agent_skill_loop session init --output outputs/session-001 --operation-id init-001 --eoh-model deepseek-flash
py -3.11 -m agent_skill_loop session state --run outputs/session-001
py -3.11 -m agent_skill_loop session stop --run outputs/session-001 --operation-id stop-001 --expected-state-version 1
```

`session init` 只冻结问题、套件、评测器、EoH 和预算身份，不读取 API key、不调用模型或 solver；`state` 是纯读取，`stop` 使用全局 `state_version` 和 `operation_id` 保证幂等。
