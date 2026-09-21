# 研究闭环 v2 Router 预检

日期：2026-09-20  
范围：正式 EoH 路径的单请求训练侧预检；不属于 A/B/C 诊断预算，不读取 heldout。

## 冻结配置

- Endpoint：`https://model-router.edu-aliyun.com/v1/chat/completions`
- Model（首次失败尝试）：`qwen/deepseek-v4.1`
- Key lookup：`MODEL_ROUTER_API_KEY_ENV=MODEL_ROUTER_API_KEY`
- Provider request 上限：1，仅允许官方 EoH probe

## 首次结果

- Session：`run_fed2408c3dd843b5ac505561b114cef1`
- Run 状态：`COMPLETED`
- Provider requests：1
- Solver calls：1（训练侧 baseline；与后续诊断预算隔离）
- Probe receipt：`failed / provider_auth_invalid`
- 解释：Router 返回 HTTP 401 或 403。该结果只证明凭据未被 endpoint 接受；尚不能判断模型名是否可用。
- Controller token：`unavailable`，没有按零计入。

本地 compact evidence 位于忽略目录
`outputs/research-loop-v2-router-preflight-evidence/`，包含 16 个经
`SHA256SUMS.json` 重验的文件。凭据和原始私密思维不在 bundle 中。

## 门禁决定

## 新凭据复检

- Model：`qwen/deepseek-v4.1-flash`
- Session：`run_47388618ea01440696cd4a5d78ae7990`
- Run 状态：`COMPLETED`
- Provider requests：1
- Solver calls：1（训练侧 baseline；与诊断预算隔离）
- Probe receipt：`complete`，`finish_reason=stop`
- Usage：input 8 tokens，output 5 tokens
- 终止原因：`REQUEST_BUDGET_EXHAUSTED`，符合单请求预检上限，不是模型故障。

复检 evidence 位于忽略目录
`outputs/research-loop-v2-router-preflight-flash-evidence/`，共 16 个文件，
已通过 `SHA256SUMS.json` 重验。凭据不在 bundle 中。

## 门禁决定

Router、凭据和精确模型名已经在官方 EoH 路径上共同通过，允许启动三 seed × A/B/C 诊断。
