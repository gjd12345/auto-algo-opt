# 研究闭环 v2 Router 预检

日期：2026-09-20  
范围：正式 EoH 路径的单请求训练侧预检；不属于 A/B/C 诊断预算，不读取 heldout。

## 冻结配置

- Endpoint：`https://model-router.edu-aliyun.com/v1/chat/completions`
- Model：`qwen/deepseek-v4.1`
- Key lookup：`MODEL_ROUTER_API_KEY_ENV=MODEL_ROUTER_API_KEY`
- Provider request 上限：1，仅允许官方 EoH probe

## 结果

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

在使用新凭据重复同一单请求 probe 并得到成功 receipt 前，不启动三 seed × A/B/C 的九次运行。
这样认证故障不会污染 solver-budget 主分析，也不会制造九组系统性失败记录。

