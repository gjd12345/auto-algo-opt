# 实验合同修订与真实接线记录（2026-09-15）

## 结论

Runtime 功能合同冻结于 `81e6156`。已进入真实 provider 实验阶段，但本次首个 DeepSeek probe 返回 HTTP 401 / `provider_auth_invalid`，未完成真实两轮热启动。下一次实验需要有效凭据和新的 Session；本次不追加请求或重跑。

## 代码修订

- `ExperimentManifest.extra` 保存完整 `generation_contract`、`resource_contract` 及 search defaults/limits，全文进入实验 hash。初始化检查声明值与实际配置一致；历史缺合同 manifest 仍可只读复评，但不能作为新 Session 的完整实验身份。
- Bridge 与 Manifest 从同一个函数生成参数。普通生成 temperature=1.0、max_tokens=16384；修复为 0.2 / 8192。thinking 的默认/显式模式、OpenCode 附加项、请求超时、单并发、provider_seed=null、response policy 均有身份记录。
- compact evidence 新增 `generation_diagnostics.json`，按 request_id、sequence、purpose、响应 hash 和 finish_reason 核验来源，派生长度、截断、空正文、修复及未知请求统计。
- CI 新增两平台 `closure_invariants.json` 比较，比较原始种群顺序、seed 顺序、选择成员及 heldout 向量。跨运行原始 selection hash 含局部 ID，另外使用明确命名的 semantic_selection_sha256。ZIP digest 不作为语义一致性依据。
- Runtime/Skill 被 hash 的文本固定 LF。Knowledge 指针支持 Git 将 current symlink 检出为普通文本；CI 新增实际 store/current 两入口检查。
- 导出器统一 LF 后再计算证据清单 hash，避免 Windows report inputs 的 CRLF 在 Git checkout 后破坏包内校验。

## 验证边界

- 62 项定向回归通过，覆盖 benchmark、request bridge、release mechanics、compact evidence 和新增实际参数/预算错配拒绝。
- 最后将 search defaults/limits 纳入合同后，相关 2 项复检通过；Python compileall 通过。
- 官方 EoH 两轮 localhost fixture 通过，产物 `outputs/closure_contracts_20260915/`；第二轮成功重评两份 seed 并生成新候选，三类 heldout 报告可重建。此 fixture 在最终加入 search-policy 身份字段前执行，不能描述为最终提交全部路径再跑通过。
- fixture compact bundle 22 项文件 hash 通过；诊断覆盖 16 次生成响应，无缺失、截断或 unknown。另有 2 次 probe。
- 本机真实 checkout 的 Knowledge store/current 两入口通过。
- Linux/Windows semantic comparator 已实现，远程 CI 尚未验证本轮提交，因此 G6 仍待远程结果。
- 上游未记录 parse/retry lineage：`parse_failed` / `recovered` 为 null，不能宣称完整恢复诊断已交付。

## 真实试跑冻结输入

| 项目 | 值 |
| --- | --- |
| run | run_175b62a006434cccb0881a2869dd60a8 |
| 源码 | 81e6156 |
| Runtime hash | f5437c7719415c86f9755739ba4cd65c041c5d3e00a834d5b4d563f249e031ac |
| Skill hash | 06ed229843d0037f231c2918aa75a0e56ae99dc0f2ef753d3615022a0098b6a1 |
| experiment manifest | 04f3cd7e9916f512976a7aac0945ba1f7b4d1a02cd16d7a8dd42cede21079667 |
| benchmark | eohs_v1 / obp_evolution_mini |
| model / endpoint | deepseek-flash / https://api.deepseek.com/v1/chat/completions |
| thinking / temperature / max tokens | disabled / 1.0 / 16384 |
| timeout / concurrency | 180 秒 / 1 |
| population / rounds | 2 / 2 |
| training evaluations | 全局 20，每轮 10，不结转 |
| provider requests | 全局 24，每轮上限 24，共享账本约束 |
| wall budget | 全局 600 秒，每轮 300 秒 |
| EoH search policy | pop_size=2, n_pop=2, max_sample_nums=20，范围固定 |
| seed | 20260908 |
| Memory / KB / repair | OFF / OFF / OFF |

当前 Coding Agent 按 Skill 提交 Plan/Evaluate；没有独立外层模型请求。凭据从 Windows 用户环境读取，值未写入输出或证据。

## 实际输出

首次 probe 请求失败：HTTP 401，error_code=`provider_auth_invalid`，耗时约 0.578 秒。账本只有 1 次 provider 请求，input/output tokens 均为 null。官方任务终态为 `PROVIDER_TERMINAL`。

只完成 1 次 baseline 评测，逐实例 gap=[0,0,0,0]；generated=0、seed reevaluations=0、repair=0。baseline 被保留为 incumbent，不能解释为生成技能或进化成功。没有第二轮，也没有生成候选 selection 或 heldout 搜索结果。

本地 Evaluate 接受上述事实并关闭 Memory，随后以 finish-round complete 结束会话。Runtime 的 `run_state=COMPLETED` 表示人工收口；任务终止原因仍是 `PROVIDER_TERMINAL`，本次实验验收状态为 **blocked_provider_auth**，不是两轮成功。

完整 Session：`outputs/real_wiring_contracts_20260915/session/`。
可分享证据：`reports/evidence/real_wiring_contracts_20260915/`，9 项文件通过 SHA256 清单校验，包括 Plan、Evaluate、训练事实、请求/solver 账本、诊断和冻结 Manifest；不包含密钥或原始 provider transcripts。

## 下一步

1. 更新有效 DeepSeek 用户环境凭据，保持本次源码和配置，创建新 Session 再做一次有界真实两轮接线。保留此失败 replicate。
2. 等待远程 cross-platform comparator；若发现差异，先诊断并发布新冻结版本，再建新实验，不修改在途 Session。
3. 真实热启动成功后再执行 fixture A/B/C/D 和单次真实 A/B/C/D。效果数据在生成 profile 前冻结 admission_spec 的数值阈值、seed 和 split；当前阈值尚未注册，不能启动效果数据筛选。
4. 三组 replicate 定义为配对实验配置，保留 API 随机性；2000 / 4×500、Memory、KB 和不同 controller 实验后置。
