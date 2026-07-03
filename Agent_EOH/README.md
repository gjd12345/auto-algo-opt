# Agent_EOH — vendored EoH 引擎（Go 问题轨道）

Go 评测轨道（InsertShips 派船调度家族）的进化引擎,内置自上游
**Evolution of Heuristics (EoH)**,让本仓自包含地驱动 Go 侧候选的生成与评测,
无需依赖任何外部 EoH 安装。

- **上游**:https://github.com/FeiLiu36/EoH （MIT License,见 `LICENSE`）
- **引用**:Fei Liu, Xialiang Tong, Mingxuan Yuan, Xi Lin, Fu Luo, Zhenkun Wang,
  Zhichao Lu, Qingfu Zhang. *Evolution of Heuristics: Towards Efficient Automatic
  Algorithm Design Using Large Language Model.* ICML 2024.

## 内容

- `eoh/src/eoh/` —— EoH 引擎:`methods/`（ael / eoh / localsearch / management / selection）、
  `llm/`（大模型客户端与接口）、`problems/`、`utils/`。
- `eoh/src/eoh/examples/user_*_go/` —— Go 轨道各问题的定义:
  `bin_packing_go` / `insertships_go` / `knapsack_go` / `mixer_split_go`,
  每个含 `prob_*_go.py`（评测器）、`prompts_*_go.py`（提示词）与 `seeds_*.json`（种子代码）。

## 与 `official_eoh/` 的分工

- `official_eoh/` —— 主线 Python 三题（`bp_online` / `tsp_construct` / `cvrp_construct`）的评测引擎。
- `Agent_EOH/` —— Go 轨道（InsertShips 家族）的评测引擎;候选是 Go 代码,编译成求解器后跑基准。

## 本地适配

`eoh/src/eoh/llm/api_general.py` 在上游基础上加入了配额/限流处理:
`EOH_API_QUOTA_MAX_PAUSES` 默认最多暂停重试 3 次(fail-closed),
配额长期不恢复时放弃返回而非无限等待;显式设为 0 可恢复为不限次数。
