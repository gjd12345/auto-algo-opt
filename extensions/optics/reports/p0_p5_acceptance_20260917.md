# 光学处方优化：P0–P5 实现与验收

## 后续修复验收（2026-09-17，优先于下方历史结论）

- durable assessment→SQLite窗口已修复：完整terminal及全部文件hash、输入处方、task/adapter/environment身份、逐profile账本必须一致，才事务收录；同时恢复baseline、candidate、incumbent和中断轮事实。不会重新执行模型或物理评测。
- COMPLETE assessment但candidate尚未提交的第二窗口也使用相同恢复路径。审计恢复只使用原冻结队列，不扩充队列。损坏证据将run置FAILED。
- 主进程已死不代表子进程已死：新增provider/physics所有权记录；仍存活的子进程阻止recover。
- 实际子进程os._exit(77)分别注入baseline、candidate、audit落盘后的崩溃，三项恢复及重复调用不重放通过；候选事实损坏拒绝通过。证据：`.local/recovery_final/receipt.json`。
- 停止/单profile超时回归及两轮Memory/反馈fixture通过：`.local/lifecycle_recovery`、`.local/session_recovery`。本轮无模型请求。
- 包内原始独立verifier已按SHA256SUMS导入，依赖严格按原requirements版本和wheel hash安装。已有t1_live_02最终处方由其重新执行四档物理，22/22断言通过，runner COMPLETED/PASS、reward=1、new_model_calls=0。证据：`.local/verifier_live02`，verification SHA256=e7dd5c977d4439a98362ac556ffdc78b9bc6c6e4ad96b132bba374e967112cd1。未修改旧run的封存summary。
- 这是Windows Python3.12.11 verifier结果，Linux3.12.14仍未通过环境门槛（再次检查WSL仍HCS_E_SERVICE_NOT_AVAILABLE，Docker命令不可用）。不宣称原环境复现。
- 准许下一步受控Windows adapted协议实验，不是无条件跨平台发布。外层实验明确交给GPT-5.6-Luna，修复验收由Astra完成。

500预算口径：总物理profile上限500；Runtime最多496（online476含baseline + audit5份×4），额外预留最终独立verifier4次。候选与模型请求最多475，单轮最多20，由Luna根据反馈选轮次及每轮额度；墙钟3600秒、audit预留120秒、Memory开启。配置在新run初始化冻结，禁止追加。

以下为首轮实现时的历史验收记录，其“恢复窗口未闭合/独立verifier未跑”已被本节更新；原始live成绩、token及历史hash保持不变。

日期：2026-09-17。基线：8a37fdda128e0f4032a2ac829ccf9f7ed56fb853。
实现位于独立分支 codex/optics-backend-v1、独立 extensions/optics 包。

## 结论

已实现 T1/T3 处方后端、独立 Session、光学 Skill 和有界真实搜索。
T1 真实运行获得 online 可行且本地四档 audit PASS 的处方。
这不等于独立 verifier 通过，也不等于 P0–P5 全部无条件签字。
P2 的评测落盘/数据库提交崩溃窗口及 P5 原环境验证仍需闭合。
目标是改善处方，不是发现可复用的光学优化算法。

| 阶段 | 已交付及证据 | 状态 |
|---|---|---|
| P0 | 修订 audit 准入、controller 身份、UNKNOWN、预算合同 | 已落地 |
| P1 | 严格 JSON/token span、资产身份、S1、原入口差分 | Windows 有限样本通过 |
| P2 | SQLite、幂等、请求/profile 网关、进程所有权、两轮反馈与 Memory、终态报告 | 主链通过；恢复窗口待闭合 |
| P3 | T1 两次有限真实运行，完整原始请求/响应和评测证据 | 完成；第二次得到局部改善 |
| P4 | T3 独立资产身份、online/四档 audit 原入口差分 | 离线通过；未做 T3 真实优化 |
| P5 | 独立 wheel、离开源码评测、旧身份保护、报告重建 | Windows 通过；Linux/独立 verifier 未验证 |

未提取旧 CO 公共组件、未修改旧 Skill，避免扩大兼容面。新 CLI 使用
`python -m artifact_session init --run <new-directory> --file <config.json>`；
TRD 中的数据表是逻辑实体，当前单 Session 数据库用 run/assessments/events 等表承载。
没有宣称已实现所有逻辑实体的一对一物理表。

## 真实处方优化

模型 qwen/deepseek-v4.1-flash；Model Router OpenAI-compatible endpoint。
外层 Plan/Evaluate 由宿主完成，生成模型身份独立冻结。
协议为 adapted_external_controller，不标 original_protocol。

首次 t1_live_01：两次响应均 finish_reason=length（各 6000 输出 token），
没有正式生成处方；正常结束、无 audit。历史输出保留，不改写成成功。
新建 t1_live_02 显式关闭 thinking 后，6 次响应均可解析；未追加该 Session 预算。

基线：online 不可行，S1=(0,-4.047660561176,-2.25,0.2640065476546554)。

| 轮次 | 宿主 Plan | 模型请求 Δ/累计 | online profiles | 候选 Q | incumbent Q | Memory |
|---|---|---|---|---|---|---|
| 1 | 校正焦面；对照曲率/厚度耦合 | 2/2 | 3（含基线） | 0.474370 可行；0.197257 不可行 | 0.474370，可行 | 关闭 |
| 2 | 保持可行性，检验耦合弯曲/孔径机制 | 2/4 | 2 | 0.178393 不可行；0.474370 重复父本 | 0.474370 | 关闭 |
| 3 | 固定焦面/曲率/厚度，仅变孔径 | 2/6 | 2 | 0.473917、0.473084，均可行 | 0.474370 | 关闭 |

S1 先比较可行性和约束违反，不能只按 Q 接受。
最佳变化为 sensor_z_mm 从 64.70806428379493 到 64.05806428379493。
第3轮预算封存，Agent Evaluate 明确为 EVALUATE_SKIPPED，不伪装完成。
冻结队列两个不同处方各做四档审计，均本地 PASS，最终仍选首个处方。
独立 verifier=NOT_RUN。后两轮无改善，不能声称连续进化成功或已达最优。

有效 pilot：6 请求、7 online profiles、8 audit profiles；输入 19871、输出 1694 tokens。
计入首次截断诊断：共8个外部请求，输入25580、输出13694 tokens。
外层宿主 token 和货币成本未知，不填0。总研究预算不设上限不改变单run冻结预算。
末次代码加固晚于 live 冻结身份；最终代码通过离线 fixture，未冒充同一 live 版本。

## 逐项核对 TRD

| 编号 | 复核结果/证据范围 |
|---|---|
| A01 | T1/T3 allowlist 导入、原始字节身份；P1 tamper 拒绝 |
| A02 | 6项合同测试覆盖严格 JSON、原文span、规范化、排序及身份；Plan变量范围由worker校验 |
| A03 | T1 baseline+有限扰动、T3 baseline 的原 CLI online/audit 差分通过；非全参数域证明 |
| A04 | S1/eligible 分离、稳定求和、排序重载通过；live 未接受更差处方 |
| A05 | 串行真实请求含 parent_online/recent_candidate_feedback；有效候选独立重评 |
| A06 | p2_fixture_final 两轮、精确反馈、Memory选读消费、幂等执行通过 |
| A07 | audit_fixture_01：两份PASS、空队列、未知候选后继续固定队列；最终PASS排序有确定性tie规则 |
| A08 | fixture封存后Plan拒绝；审计只在finalizer，不注入生成prompt |
| A09 | lifecycle_02实际profile超时和进程树停止；audit_fixture_01未知不重放；请求账本先预留 |
| A10 | 操作幂等、PID复用拒绝通过；落盘后DB提交前崩溃只保留证据，不自动恢复候选，未完全闭合 |
| A11 | 全无效fixture输出baseline_fallback；未跑verifier不标PASS |
| A12 | 两轮fixture正文消费通过；可选Memory失败降级代码已实现，未穷举存储故障 |
| A13 | 旧包/入口无git修改，55个实际Runtime/Skill身份输入字节一致；未重跑完整旧EoH回归 |
| A14 | 最终wheel在独立venv、源码目录外运行原基线一致；Linux3.12.14未验证 |
| A15 | live02重载89条event hash chain、9份完整assessment；报告两次重建一致，0请求/0物理调用 |
| A16 | controller/provider/runtime/skill分开冻结，original_protocol无依据被拒绝；未知身份不补猜 |

最终11项定向单元测试、compileall、两轮fixture通过。
离线评测 wheel SHA256：7bff6e20747cbef5e6aeb4a3bca383f1534c9626951407cb851ca0e0204665e1。
随后仅修正 optics_backend.__version__ 与模块说明/尾部空行，最终 wheel SHA256：
3e1c7d3cf601ad87b5a9e10186a1ab0a46b00d82a11d764bd4b0f33789cacb77；重新安装后 import 与 Skill 资源检查通过，未重复物理评测。
Skill validator 已通过。最终 wheel 无 eoh/agent_skill_loop runtime 依赖。

## 证据与发布边界

原始证据留在 extensions/optics/.local，不纳入 Git（含项目方原始资产及生成处方）。
主要目录：p1_20260917_acceptance、p2_fixture_final、lifecycle_02、audit_fixture_01、
t3_differential_01、t1_live_01、t1_live_02、wheel_online_final。
live02 config hash：3c673f43d5f5b48e255fe56a0e98bd44167a6cc0d7676b9607a772de9e94cf5e。
最终summary hash：169af3c61dd158e536994c7a70159b63844ae56ece97a3ca689cab5e7db2b7da。

复核命令：`python tools/verify_evidence.py --run .local/t1_live_02`（在扩展目录执行，已安装wheel或设置PYTHONPATH）。
校验只证明可信宿主内证据一致性，不提供数字签名安全性。

## 下一步门槛

1. 闭合 durable assessment→SQLite 的恢复窗口，增加一个精确崩溃注入用例。
2. 在原声明 Linux Python3.12.14 环境重跑有限差分及安装检查；本机WSL启动失败 HCS_E_SERVICE_NOT_AVAILABLE。
3. 独立 verifier 可用后验证最终处方；未通过前只写 local audit PASS。
4. 再开独立冻结run优化T1/T3；上一run audit不能回灌同run。是否跨run使用审计指导必须另立实验协议。

当前推送是可审查实现与证据摘要，不是无条件发布认证。
