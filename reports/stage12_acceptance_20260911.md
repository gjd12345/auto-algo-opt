# 阶段 1、2 修复、自检与真实 API 报告

日期：2026-09-11。范围：修复原审查的 13 项问题，清理生产旧搜索路径，校正官方 EoH 的治理及资产边界。3+1 角色和 Memory 不在本次实现范围。

## 二次复核与修复（当前工作区）

本节替代下文原结论。下文测试、wheel、真实 API 和源码 hash 均为**修复前历史证据**，不代表修复后已通过测试。本轮未提交、推送或调用真实 API。

### 修复内容

1. 导出异常统一使最终状态成为 `export_failed`、`loop_completed=false`、CLI 返回 2；原状态与停止原因保留为 `prior_status` / `prior_stop_reason`。配置收尾写入也纳入异常处理。
2. 评测前将代码、身份、请求关联原子保存至 `results/evaluation_starts/<evaluation_id>.json`，完成记录携带同一 ID。引擎停止后对账，未完成项写入 `evaluation_interruptions.json`，标明 cancelled/interrupted 与停止原因，不伪造分数。`solver_calls` 改为已登记启动数；新增 `solver_calls_started/completed/interrupted`。started 指进入适配器评测流程，不保证子进程已成功创建。
3. `save_skill(..., evidence=...)` 将证据与代码、元数据写入同一临时目录，全部成功才发布目录。证据写入失败不会留下半成品 skill；ref 仍原子替换。
4. 旧 transport/usage 类移入 `tests/fixtures/client.py`；旧 interface_boundary、repair_hint、stagnation_hint 从 ProblemSpec/评测器移入 fixture generator。生产仅保留共享 HTTP 能力，不反向导入 fixtures。旧资产字段保留作兼容数据。

### 13 项修复后对照

源码完成不等于本轮测试已通过；定向回归正在等待用户确认范围。

| 编号 | 当前结论 | 二次复核依据 |
|---|---|---|
| 1 | 源码完成 | 两个 CLI 共用官方监督入口；旧 loop 不在生产包 |
| 2 | 源码完成 | 官方父本与算子未替换；旧策略及提示专用字段仅留 fixtures |
| 3 | 源码完成 | 三个 spec 共用官方链路；父本先重评再进入 seed |
| 4 | 源码完成 | generated 标记 official_eoh + commit，其他来源分开 |
| 5 | 源码完成 | 当前合同更新；旧传输和提示移出生产，兼容测试依赖 fixtures |
| 6 | 本轮补修完成，回归待执行 | 导出失败影响退出码；开始和中断评测独立记账 |
| 7 | 源码完成 | bridge 终止闸门、串行转发、请求预算保留 |
| 8 | 源码完成 | 问题/接口/suite/evaluator 身份绑定当前 spec |
| 9 | 源码完成 | 多来源 checkpoint 比较与本地证据选优保留 |
| 10 | 本轮补修完成，回归待执行 | 开始/中断证据齐备；skill 与 evidence 原子发布 |
| 11 | 源码完成 | v2 身份核验、v1 兼容、无效父本入库前拒绝保留 |
| 12 | 源码完成 | AST 防护未改动；不宣称 OS 沙箱 |
| 13 | 配置完成，当前回归及远端 CI 待验 | 双平台 CI 保留；旧通过数不冒充新结果 |

### 本轮验证与待验范围

- Python 3.11 语法解析及生产入口、适配器、资产、迁移后 fixture 模块 import 通过。
- 源码扫描：生产无 FixedSearchPolicy、旧 repair/stagnation 提示字段或旧 transport 类定义。
- 增补回归：预算停止叠加导出失败、未完成评测对账、证据失败不发布半成品；强化墙钟和生产隔离断言。
- **尚未运行本轮 pytest、重建 wheel 或调用真实 API。** 已询问定向测试范围，等待确认，不自动扩大测试。
- 获准后仅运行官方链路、skill 保存、import 隔离及本次迁移影响的兼容测试。预期导出失败退出 2；started = completed + interrupted；取消无分数；证据失败无最终资产；生产不导入 fixtures。
- 当前源码 hash 已改变，下文历史产物不改写、不代表本轮已验收。

## 首轮结论（历史记录，非本轮验证结果）

13 项对应的代码修复已完成，并完成逐项源码/调用链检查。本机 Python 3.11、Windows 全量测试为 **154 passed、1 skipped**，跳过项是 POSIX 专用进程组测试。官方 EoH 真实控制流的 16 项 localhost 端到端测试通过；它们没有替换 EoH 类、父本选择或算子。

真实 API 已执行，但服务返回 **HTTP 401 / provider_auth_invalid**，因此只能验收认证失败终态、预算及资产保存，不能宣称真实模型多轮生成闭环成功。后续真实成功验收需要有效的 DEEPSEEK_API_KEY。未因失败更换账户、模型或绕过认证。

Ubuntu/Windows 官方 EoH CI matrix 已配置；本报告不宣称远端 CI 已触发或通过。本次没有提交、推送或修改 git 历史。

## 13 项逐项对照

编号沿用最初 13 项问题，未把后续讨论重新编号为另一张问题表。

| 编号 | 原问题 | 本次修正与检查证据 | 自检 |
|---|---|---|---|
| 1 | 生产 run 绕过官方 EoH，仍使用固定策略 | 两个 CLI 共用参数与监督入口；旧 loop 移出生产包；独立进程 import 检查和 wheel 清单均证明旧入口不可导入 | 通过 |
| 2 | 自写 e1 单父改进、m1 失败修复冒充官方语义 | 旧 generator/policy 仅留 tests/fixtures；实际官方引擎分别跑 e1/e2/m1/m2，捕获真实 prompt 验证多父本及变异语义 | 通过 |
| 3 | 多问题及 parent 只接旧入口 | 三个注册问题均经官方引擎、隔离评测、导出及重载重评；显式父本走当前校验和官方 seed | 通过 |
| 4 | 官方输出仍被标记 fixed/v1 | generated 显式记录 official_eoh + commit；基线、导入和父本按来源标记；未指定来源不默认冒充官方；prepare 写官方身份 | 通过 |
| 5 | README、计划、测试固化旧架构 | 新建当前运行合同；旧计划归档并设置入口说明；生产 smoke 改走真实官方 EoH；测试辅助代码不打包 | 通过 |
| 6 | 请求/墙钟到限后的终态、摘要不完整 | 外层监督官方子进程，关闭引擎及子树；评测共享 deadline；停止后仅保存已有证据；分别测试请求上限、候选中途墙钟、零墙钟及导出失败 | 通过 |
| 7 | 上游重试导致认证/未知结果重复付费请求 | bridge 串行转发和终止闸门；协议结构校验；仅明确可重试 429/5xx 可重试；401、畸形 JSON、未知结果测试及真实 401 均只预留/外发一次 | 通过 |
| 8 | 问题适配和导出身份硬编码 CVRP | FrozenProblem 绑定注册 spec，校验 suite.problem；导出按当前 spec，核对 entrypoint、suite/evaluator/code hash | 通过 |
| 9 | 空 pops_best 不回退、旧 checkpoint 掩盖更新结果 | 统一比较 pops_best、samples、pops，过滤缺码、布尔/非有限目标；测试空目录、seed checkpoint、更新 sample 和 -inf；生产以完整本地评测证据保存资产 | 通过 |
| 10 | 只有 scalar，候选证据和实现身份不足 | 保留完整代码/逐实例评测、实际 prompt/响应及 hash、请求索引；核验官方 commit/RECORD，记录适配源码 hash；每份 skill 附 evidence.json | 通过，谱系边界见下文 |
| 11 | ref 身份未核验，无效父本先入库 | v2 强校验全部身份；原 v1 兼容缺少的 problem/entrypoint，已声明字段仍校验；循环引用拒绝；无效父本测试确认未创建 seed 或可复用父资产 | 通过 |
| 12 | np/math 容器别名绕过 AST 白名单 | 未知属性默认拒绝，覆盖容器、解包、参数及直接下标接收者；限制模块重绑定；保留合法数值/容器方法测试 | 通过，不宣称完整 OS 沙箱 |
| 13 | CI 无真实官方 EoH E2E、无 Windows 覆盖 | Ubuntu/Windows matrix 安装 pinned extra；测试真实 EoH.run、localhost HTTP、嵌套评测、导出重载和停止；本地 Windows 全量验证通过 | 本地通过，远端 CI 待运行 |

## 本次额外关闭的迁移问题

- 删除旧 candidate-attempts/max-llm-requests 隐式映射，两个入口共用官方参数定义。初始化样本、进化尝试、探活/重试 HTTP 请求分别记账；允许明确的小预算提前停止。
- 仅种子运行不再填写 best_generated_path。新增测试：0 个进化样本、仅一次官方探活，生成数为 0，显式父资产保留来源版本。
- 所有有效生成候选均保存为不可变 skill；整体 incumbent 与最好生成版分开。即使模型服务失败，合法基线仍可保存，但 origin=baseline，不归因于生成。
- 正常收尾和限额停止均使用已完成的评测证据，不在墙钟到期后启动导出重评。
- 独立 checkpoint 导出仍重新评测，并分别保存官方舍入目标值和本地精确目标值。
- 导出错误与 provider 错误分开。发布 ref 使用原子文件替换，旧资产不会因新发布失败而先被删除。

## 实际验证

最终命令：

```powershell
py -3.11 -m pytest -q -rs --tb=short --junitxml=outputs/stage12_selfcheck_20260911.xml
```

结果：154 passed、1 skipped，94.16 秒。[JUnit 记录](../outputs/stage12_selfcheck_20260911.xml)。此前用于定位问题的中间失败不作为最终通过证据。

官方链路测试文件：[test_supervised_chain.py](../tests/eoh_frozen/test_supervised_chain.py)。涵盖三个问题、四算子、请求上限、候选中途墙钟、未知请求结果、协议错误、seed-only、无效父本、零墙钟、导出故障。有效代码在新隔离进程重载重评，分数一致。

另一次可直接检查的离线运行：[summary.json](../outputs/acceptance_stage12_smoke_02/summary.json)：4 次初始化 + 2 次进化，6 个有效候选，7 次 localhost HTTP（含探活）。它是中间版本的链路演示；最终版本以全量 JUnit 与最终真实请求配置记录为准。

安装包验证：正常隔离构建成功，wheel 共 28 项文件，不包含 tests、旧 loop/policy/generator/report 或 legacy 目录。[wheel](../outputs/stage12_wheel/agent_skill_loop-0.1.0-py3-none-any.whl)。本机关闭构建隔离时缺少 bdist_wheel，正常隔离构建补齐构建依赖后成功，未改动全局 Python 环境。

官方安装核验：14 个 Python 文件全部匹配安装 RECORD，来源 commit 为 472545785c936dcfc863d2bc0d6109cf23c7ce62。

## 真实 API 测试

最终代码运行命令：

```powershell
py -3.11 -m agent_skill_loop run --problem cvrp_construct --model deepseek-chat --endpoint api.deepseek.com --api-key-env DEEPSEEK_API_KEY --pop-size 2 --n-pop 1 --max-sample-nums 2 --max-requests 7 --count 1 --size 6 --solver-timeout 10 --request-timeout 45 --wall-seconds 180 --output outputs/stage12_real_api_20260911_final
```

| 项目 | 实测结果 |
|---|---|
| 服务请求 | 官方初始化探活，eoh_probe |
| HTTP | 401 |
| 错误分类 | provider_auth_invalid |
| 状态 | provider_failed / provider_error，loop_completed=false |
| 外发请求数 | 1，无自动认证重试 |
| 生成/有效生成数 | 0 / 0 |
| best_generated_path | null |
| 保留资产 | baseline，目标值 3.0620577466115493 |
| 墙钟 | 约 1.141 秒 |

证据：[summary](../outputs/stage12_real_api_20260911_final/summary.json)、[请求账本](../outputs/stage12_real_api_20260911_final/results/requests.jsonl)、[冻结配置](../outputs/stage12_real_api_20260911_final/config_frozen.json)。未在报告、配置或请求日志中写入密钥。

该运行适配层源码 SHA-256：`3c7a10bffccf2b2ca7cb83aa9e81c90313b6dea5f2514bf4fcbc6a8ed7398601`。

本次先进行了一次真实请求测试，在完成剩余源码/身份整理后又对最终版本执行一次。两次分别各 1 次 HTTP，均为 401，总计 2 次真实外发；第二次是显式版本验收，不是引擎隐藏重试。首轮记录在 outputs/stage12_real_api_20260911_01。

## 边界与剩余条件

真实模型多轮生成、真实反馈后的再生成仍未验证，需要有效服务凭据。当前不能报告“真实 API 端到端成功”。

上游丢弃选择后的父本 ID，本次保留实际 prompt/响应、请求索引及评测行，明确记录 upstream_parent_ids_not_exposed，不伪造单父谱系。3+1 的计划对象与多父引用仍属于后续设计。

旧搜索实现和旧报告模板仅在 tests/fixtures 保留作隔离测试辅助；旧计划归档，生产不再打包或导入。历史运行、研究材料和 git 分支未删除。本报告是阶段 1、2 的历史验收证据；当前实现与边界见 [audit_20260912/acceptance.md](audit_20260912/acceptance.md)。

自动审批拒绝了删除本次构建生成的 build/ 临时目录。目录保留并列入 .gitignore，不进入 wheel，不作为历史搜索源码；没有通过其他删除方式绕过该拒绝。
