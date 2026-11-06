# auto-algo-opt 独立评测：以远程 74a1fb8b 为准

评测日期：2026-10-04（Asia/Hong_Kong）。主线：CO；光学仅审查兼容性。本文区分代码事实、现有运行证据、推断和建议。没有启动模型请求、solver 搜索或新的 heldout 评测，没有修改实现或历史 Session。

## Executive conclusion

**架构值得继续，但当前不宜发布，也不宜直接开展正式效果实验。** 官方 EoH 仍掌握父本、算子和种群搜索；Runtime 的预算预留、保守恢复、源码身份、种群继承、训练事实与 Memory 传输已经有实质实现，且官方 EoH 的 Linux/Windows 测试及两轮零外部 provider closure 在当前远程提交通过。不能再把该系统描述成“Memory 未接入、没有行为证据、只围绕 incumbent 的空壳”。

另一方面，本次找到了一个真实的 **heldout 行为诊断边界缺口**：观察器对 heldout 也生成轨迹，且 CI 导出的 test_result 实际携带这些轨迹。当前 kernel CI 双平台均失败。新增 SearchProgress 还存在新颖性、未知谱系、成本及停滞窗口的口径问题；这些问题直接削弱对“为什么搜得不好”的解释。

Reflection 的情况要分层看：Skill 已要求“事实→解释→可检验决策”，比简单结果好坏反馈更好；Runtime 只约束格式和证据引用，未要求完整的问题分析；最新真实 pilot 的可见控制器是固定脚本，假设数组为空、继续决策按轮数固定。**它不是 Coding Agent Reflection 效果实验。** Memory 有传输闭环的工程证据，Memory 改善搜索仍是 UNKNOWN。

| 使用场景 | 建议 | 条件和范围 |
|---|---|---|
| engineering fixture | GO（限定训练侧、零外部 provider） | 可继续工程开发；当前含 heldout 的整套 closure 不能宣称边界验收合格，先修 R01 |
| small real pilot | CONDITIONAL GO | 先修 heldout 隔离和关键观测口径、恢复相关 CI；冻结实际运行版本及 controller；明确只做流程/假设 pilot |
| formal effectiveness experiment | NO-GO（当前） | 尚缺可信处理组、修正后的计量、可复核原始证据与预先制定的重复实验方案 |
| release | NO-GO | R01 与当前红 CI 是 release gate；不把所有 CI 失败解释为 fitness 错误 |

## 版本、工作区与证据基线

| 层次 | 本次观察 |
|---|---|
| 当前远程 HEAD、重点分支 | git ls-remote 确认 HEAD 与 refs/heads/agent-skill-loop-0908 都是 74a1fb8b3b747a2113426e90315dc170039a0f60 |
| 当前本地 checkout | agent-skill-loop-0908，3a15c2ad2f5c382a21e40ca547a5c7c810db736a；落后远程两次提交 |
| 新增远程提交 | e310ff42：Iteration B SearchProgress；74a1fb8b：Iteration B real pilot |
| 主审源码 | 从上述远程 commit 导出独立快照；没有切换、重置或覆盖原工作区 |
| 已跟踪未提交改动 | optics runner、optics worker、tools/export_benchmark_evidence.py；合计 109 增、8 删 |
| 其他未跟踪内容 | 多份历史报告/证据目录、pilot/进度脚本、test_pilot_corrections.py 等；见工作区清单，不计入远程实现 |
| 历史真实实验 | 远程报告提到 experiments/co_iteration_b_20260919_search；当前工作区及提交快照未取得该原始 Session，报告中的 500 attempts、483 requests 及效果数字未独立重建 |
| 可访问运行证据 | 当前 GitHub Actions 元数据、失败日志、Ubuntu closure artifact；compact bundle 的 22 个文件 hash 全部匹配 |

本地 optics 改动主要涉及提示上下文压缩及评测调整，exporter 改动涉及 controller 等附加证据输出。这些不属于 74a1fb8b，也不受该 commit 的 CI 背书。本次没有把这些改动合并为“当前远程能力”。

复核资料均放在本目录：[CI 状态](ci-status.json)、[失败日志](ci-failed.log)、[原有工作区差异](preexisting-working-tree.patch)、[工作区清单](working-tree-status.txt)、[只读核验摘要](read-only-verification.json)。源码引用均锁定 74a1fb8b，避免与本地旧 checkout 混淆。

## Findings

### R01

- **ID:** R01
- **Severity:** P0
- **Area:** heldout / behavior evidence
- **Claim:** OBP 行为观察器没有按 split 限制；heldout 评测生成并导出了行为诊断，且标识为训练范围。
- **Evidence:** [evaluator.py:678](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/evaluator.py#L678) 只检查 ProblemSpec 是否提供 evaluate_with_behavior，不检查 split；[obp.py:119](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/problems/obp.py#L119) 将 scope 固定为 frozen-training-suite。[harness.py:403](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/benchmark/harness.py#L403) 对 selection 使用 collect_partial=True，:448 原样复制 partial rows 的 metrics。当前 CI artifact 的 incumbent_top1.inputs.json 中，test_result/member_results/0/instance_results/0 和 /1 的 metrics/behavior_evidence 均为 complete，声明 scope=frozen-training-suite；见只读核验摘要。本次只核查字段存在和范围标识，没有用 heldout 轨迹分析算法。
- **Why it matters:** “锁定 selection 后才测 heldout”做到了，但这不足以满足“heldout 不进入行为诊断”的更强边界。
- **Engineering impact:** heldout 输出包含不必要的诊断侧信道和错误范围标识；现有 closure 通过不能证明该边界。
- **Research-validity impact:** 存在后续研究者读到 heldout 行为后调整机制的通道。**没有证据表明本次历史 pilot 已实际回流训练**，不能倒推它的全部分数无效。
- **Recommended minimal fix:** 在可信 evaluator 请求/ProblemSpec 调度处根据已验证 split 禁止 heldout 行为记录；harness 再做输出白名单过滤。继续保留锁定评测所需目标值、有效性和逐实例效果。
- **How to verify fix:** 一个训练/heldout 配对的确定性验证：训练有轨迹，heldout 任意嵌套层级均无 behavior/signature/sample；训练 Session 不变，目标值不变。随后检查修复后的 closure 导出。此项为修复后的最小验证建议，本次未运行。

### R02

- **ID:** R02
- **Severity:** P0（release gate）
- **Area:** CI / Memory acceptance / contract drift
- **Claim:** 当前远程 CI 确实失败；其中 Memory publication 格式校验发生在 Evaluate 接受前，不能把全部失败都归为无害快照过时。
- **Evidence:** [当前 CI run](https://github.com/gjd12345/auto-algo-opt/actions/runs/35497862659)。Linux 和 Windows kernel 都是 3 failed、190 passed、1 skipped：schema 文档不匹配；solution-rejected 测试在 solution_execution_section_missing 提前抛出；Memory-off state 精确字典断言多了三个字段。[session_actions.py:764](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_actions.py#L764) 在记录 accepted Evaluate / READY_TO_FINISH 前调用 validate_memory_publication；其调用 MemoryEntry 内容格式校验。
- **Why it matters:** 文档/schema、投影 API 和拒绝阶段都发生了变化。对于格式错误的 Memory，当前行为是整份 Evaluate 不被接受；不是接受 Evaluate 后记录 Memory=rejected。
- **Engineering impact:** kernel wheel 验证步骤被跳过；格式错误的 Memory 需要重新提交 Evaluate，不能直接从 READY_TO_FINISH 调用 memory-revise。已 collect 的 deterministic facts 不会因此被删除。
- **Research-validity impact:** 不证明 evaluator 分数错误，但影响闭环恢复叙述和发布可信度。
- **Recommended minimal fix:** 明确格式校验属于提交拒绝还是 publication 拒绝。若坚持两者独立，把可恢复 publication 内容错误转为 Memory rejection；若保留提前拒绝，修订合同、Skill 和测试预期。同步 schema 文档及 Memory-off 投影断言，不能仅删除失败测试。
- **How to verify fix:** 只复核这三个现有失败用例及失败场景的 state/facts 保留；确认当前提交的 kernel job 和外部 checkout wheel gate 通过。无需因此扩大本地全仓测试。

### R03

- **ID:** R03
- **Severity:** P1
- **Area:** Reflection / treatment validity / controller identity
- **Claim:** 最新 real-pilot runner 只能代表脚本化外层策略，不能代表实施了问题分析的 Coding Agent；Runtime 也没有强制 Reflection v2 的关键结构。
- **Evidence:** [run_co_iteration_b.py:68](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/tools/run_co_iteration_b.py#L68) 根据组别、轮号和 duplicate_rate>=0.5 选择固定 Plan；[:167](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/tools/run_co_iteration_b.py#L167) 的 Evaluate 只报告有效候选数量，hypotheses=[]、plan_alignment=unknown；[:280](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/tools/run_co_iteration_b.py#L280) 按轮数决定 continue。[parse_evaluation:685](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_actions.py#L685) 允许 observations/hypotheses 缺省为空；已有 observation 才要求引用存在。Plan hypothesis 是必填非空文本，没有 question ID、预期区分结果或证据不足理由合同。[Runtime hash:184](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_runtime.py#L184) 只覆盖 agent_skill_loop 和 eoh_frozen，未覆盖该 tools controller；[preflight:190](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_supervisor.py#L190) 的 controller.model 实际填入 eoh_model。
- **Why it matters:** 证据引用存在不等于 claim 被证据支持；机制词出现不等于实际执行了机制。固定脚本和 Coding Agent 是不同处理。
- **Engineering impact:** 系统可承载 B 型分析，但不能机械保证每轮发生 B；当前 pilot 实际更接近带重复率分支的 A。
- **Research-validity impact:** 不能据此归因“Agent/Reflection 提高或拖累搜索”。G1 同时加入指导与反馈，G2 同时改变外层分支和 EoH 上下文；G4 phase intent 也进入 prompt，不能把差异单独归于预算政策。
- **Recommended minimal fix:** 保留薄 Runtime；给研究运行增加简短结构：question、未解释观察及引用、备择解释/证据不足、预期区分的行为或效果、下一轮对此问题的更新。绑定 controller 类型、源码 hash、版本与公开决策产物；外层模型未知就写 unknown，和生成模型分开。把现有 pilot 明确标成 scripted-controller wiring pilot。
- **How to verify fix:** 静态审查两轮公开 Plan/Evaluate 是否串起同一可证伪问题，实际请求是否包含应有上下文，controller 身份是否与所跑脚本一致。先验证处理实施，再做效果比较。

### R04

- **ID:** R04
- **Severity:** P1
- **Area:** SearchProgress stagnation / continuation
- **Claim:** 停滞判定不是严格固定 attempts 窗口，零阈值存在旁路，缺少起点会误标 stagnated；结果目前也不驱动 pilot 的继续决策。
- **Evidence:** [search_progress.py:363](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/evidence/search_progress.py#L363) 向后累加整轮，达到窗口即停止，无法截取轮内精确边界。:391 用绝对门和相对门 OR；只设 absolute=0.5、relative 默认 0 时，10→9.999 的极小增益也通过相对门。首轮 incumbent_before=None（已下载 fixture facts 也是如此），窗口满足时 gain=None 导致 stagnated，而不是证据不足。[finish_round:782](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_actions.py#L782) 检查预算和终态，不检查停滞结果；pilot :280 固定继续。
- **Why it matters:** “有停滞指标”不能直接等同“避免收益递减”。当前默认 policy 本来就是 disabled，启用后仍需明确的外层决策合同。
- **Engineering impact:** 阈值配置容易产生反直觉结果；不同轮预算使同名 window 不同长；首轮无法区分无进展和无比较起点。
- **Research-validity impact:** 会影响进展率与政策组解释。没有证据证明目前长期无限搜索；max rounds、requests、solver、wall 上限仍有效。
- **Recommended minimal fix:** 明确 OR/AND 与“未启用阈值”语义，避免 0 阈值旁路；采用按 solver ledger 截取的精确窗口，或改名并报告实际覆盖 attempts；缺起点返回 insufficient_evidence。让 Agent/脚本记录对 stagnation 的决策理由，不要求 Runtime 代替 Agent 选机制。
- **How to verify fix:** 最小静态/确定性案例覆盖仅绝对阈值、首轮无起点、窗口跨越半轮；确认 policy 输出与继续理由能对应。避免顺带改写 EoH 搜索策略。

### R05

- **ID:** R05
- **Severity:** P1
- **Area:** search efficiency / cost accounting
- **Claim:** SearchProgress 中 wall time 是 provider 请求耗时之和；部分未知 token 被静默丢掉后汇总为看似完整的总数。
- **Evidence:** [session_supervisor.py:587](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_supervisor.py#L587) 的 total(name) 过滤 None 后求和，elapsed_seconds 将未知值按 0 计；[search_progress.py:278](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/evidence/search_progress.py#L278) 把该 elapsed_seconds 命名为 round_wall_seconds。实际 task engine_elapsed_seconds 和 solver_cost_summary 已在其他位置维护。
- **Why it matters:** solver、EoH、本地进程初始化和等待时间没有包含在 provider latency 中；一部分请求 token 未知时，已知部分的和不是 total。
- **Engineering impact:** 不会因此绕过硬预算，但报表会低报或错名成本。
- **Research-validity impact:** 每秒/每 token 的搜索效率、不同处理组成本比较可能失真；总 reservation 数仍可审计。
- **Recommended minimal fix:** 分开 task elapsed、provider elapsed、solver elapsed；保留 known_token_sum、known_request_count、unknown_request_count，只有全部已知才提供 total。明确 wall 是否包含外层 Agent 时间；目前该时间也不在 EoH task 成本内。
- **How to verify fix:** 用已有账本做只读重建；含一条未知 usage 时 total 为 null 且 coverage 可见，wall 与 task 时长对应。无需调用 provider。

### R06

- **ID:** R06
- **Severity:** P2
- **Area:** novelty / lineage metrics
- **Claim:** 新颖性基准不一致；已知无父本的 i1 被计成未知谱系。
- **Evidence:** [source:141、behavior:165](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/evidence/search_progress.py#L141) 的 seen 包含所有 prior-round candidates，但当前轮只遍历 generated，忽略同轮先评测的 baseline/seeds/repair。[:243](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/evidence/search_progress.py#L243) 将所有非 verified 计为 unknown，含 no_parent。实际 CI fixture 首轮：9 个 generated、4 个 no_parent、5 个 verified，却报告 lineage_unknown_rate=4/9；行为“新颖数”报告 2，若纳入已评测 baseline 则只有 1。见只读核验摘要。
- **Why it matters:** 新颖性必须说明相对于谁；合法的 i1 无父本不是采集失败。execution_delta 的源码新颖性逐行纳入非 generated，和这里也不同。
- **Engineering impact:** 同一 Session 不同投影对 novel 的回答不同，谱系覆盖看起来比实际差。
- **Research-validity impact:** 会扭曲 novel-behavior 成本和谱系可观测性。这里的 fixture 比例只是口径反例，不是实际算法效率估计。
- **Recommended minimal fix:** 按真实评测顺序更新 seen，并明确基准为 prior-evaluated 或 generated-only，跨轮保持一致；拆分 verified-parent、known-no-parent、unknown。repair 的独立重复率也应覆盖同轮原始版本与之前 repair。
- **How to verify fix:** 对现有 artifact 只读重建：4 个 i1 归 known-no-parent；baseline 已见行为不再算 session-novel；window 与 cumulative 的定义一致。

### R07

- **ID:** R07
- **Severity:** P2
- **Area:** Memory knowledge contract
- **Claim:** Memory 传输可审计，但“none 必须说明理由”和“memory-revise 仅纠正原 proposal”没有被 Runtime 严格执行。
- **Evidence:** [MemoryAction:276](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_contracts.py#L276) 对 none 的 reason 可省略，而 Skill 要求 reason。[memory_revise:721](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_actions.py#L721) 接受任意新 insight/solution；[session_memory.py:46](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_memory.py#L46) 对 revision 用新正文自身建立 expected，仅校验新 proposal hash、场景与相应门槛，没有旧新内容关系限制。insight 的 evidence_ref 可省略。原记录仍保留，并非静默篡改已发布正文。
- **Why it matters:** 完整读取/注入证明 transport，不证明知识可复用；任意改写可以脱离原 Evaluate 的观察。
- **Engineering impact:** 原 proposal 和最终 published content 的语义关系需要人工判断。
- **Research-validity impact:** 容易把流水账、重复事实或新加结论统计成“有效经验”，publication 次数不能作为 Memory 价值指标。
- **Recommended minimal fix:** 对新提交 none 强制非空 reason；revision 记录 supersedes、修改理由和证据引用，明确允许“替换知识”还是只修格式。不要用自动相似度假装能证明语义一致；重大替换作为独立 Agent 决策记录。
- **How to verify fix:** 无 reason 的新 none 被拒绝；修订链能显示原/新 proposal、理由及 facts 身份；已发布条目不可经该命令改写；恢复不增加 EoH 请求。

### R08

- **ID:** R08
- **Severity:** P2
- **Area:** portable evidence / reviewability
- **Claim:** 当前 compact export 的 hash 校验成功不代表行为、Memory 与实际请求证据闭包完整。
- **Evidence:** [export_benchmark_evidence.py:62](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/tools/export_benchmark_evidence.py#L62) 只复制 facts/population/seeds/Plan/Evaluate/context，未复制 execution_delta、memory_consumption、context_manifest、request_inputs；verify_bundle 只核对文件清单/hash。已下载的 22 文件 bundle 完整性通过，但两轮 facts 引用的 execution_delta 都不在包内。
- **Why it matters:** 该工具本来就声明是 compact、非 resumable bundle；问题不是它承诺保存一切，而是新增证据链已超出旧导出合同，外部审查无法仅凭此包验证全部新能力。
- **Engineering impact:** 离开原 Session 后，实际请求注入和详细父本比较需要额外证据包。
- **Research-validity impact:** 历史报告中的 Memory consumed / Plan executed 声明不能仅靠 compact hash 验证。
- **Recommended minimal fix:** 增加版本化 evidence bundle profile，复制非敏感 sidecars 及 request-input 证据，或逐类标明 omitted/unverifiable；无需公开 provider 凭据和私人推理。脱敏后内容应记录新的 hash 与映射，不能沿用原请求内容 hash。
- **How to verify fix:** 在只有 bundle 的空目录做只读引用闭包检查；缺省省略的证据必须明确降级，不能宣称“全部已验证”。

### R09

- **ID:** R09
- **Severity:** P2
- **Area:** phase budget / pre-effect boundary
- **Claim:** phase solver 配额在 solver reserve 时才检查；provider reserve 不检查 phase，因此 phase 已满但 round/total 尚未满时仍可能产生无法评测的新请求。
- **Evidence:** [SessionRequestBudget.reserve:71](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_ledger.py#L71) 检查 request、round/total solver、repair 和状态；没有 phase 检查。相同文件 [:156](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_ledger.py#L156) 只在 solver_event 中检查 phase_used。EoH 下一候选先生成，再到 solver reserve。
- **Why it matters:** phase policy 的目的包括预算约束；晚拒绝会浪费请求，而且将 generation 成本和对应 evaluator attempt 分离。
- **Engineering impact:** provider 请求仍被计入总 request budget，solver 不会越过 phase 上限；这是提前阻断遗漏，**不是已证明超出总预算或重复付费**。当前 50/50 pilot 中 phase 和 round 上限重合，不能据此声称它已发生。
- **Research-validity impact:** 在 phase 小于 round 的配置下，单位有效探索成本与 policy 对比会受影响。
- **Recommended minimal fix:** gateway reserve 复用 phase 剩余容量检查；在已知不能再评测时停止新 generation/repair，保留 terminal receipt。
- **How to verify fix:** 使用零 provider 的账本/fixture，phase exhausted 且 total/round 尚有余额，后续 request reservation 应为零；原 ledger 不退款、不重放。

## 实际系统链路及问题 A–H

### A：源码、行为、效果已被区分，但覆盖有范围

code_sha256 仍按精确 UTF-8 源码计算；没有用归一化代码、fitness 或行为 hash 替代资产身份。OBP 行为来自可信 evaluator 在原求解循环中记录 item_index、selected_bin_id、opened_new_bin、bins_used；不依赖候选自报，也没有为行为观察新增一次 solver 求解。

BehaviorTraceRecorder 只有完整实例和 complete 状态才产 signature；partial 无可比较 signature，timeout 返回无完整行为结果。execution_delta 比较前要求 contract、suite、实例顺序和完整性匹配。两段源码不同但同轨迹、轨迹不同但同 aggregate fitness 都能表示。支持的是**该 suite 上观察到的决策轨迹关系**，不等同算法语义等价，也不观察所有内部计算差异。

当前注册的 behavior observer 只接入 OBP；CVRP、TSP、TSP-2opt 的行为关系应是 unsupported/unknown，不能用 fitness 相同替代。该覆盖限制本身不是算法失败。R01 是 split 边界问题，R06 是派生统计口径问题，二者不否定原训练轨迹机制的实现。

### B：Reflection 更接近哪一类

- Skill：偏 B。明确要求观察、解释、可证伪假设、证据不足和下一实验，禁止把 Plan 声明视为执行事实。
- Runtime：支持 B、允许 A。observation 非空时必须引用本轮合法 evidence；hypothesis 是自由文本加 confidence；不检查引用能否支持 claim，数组可空。
- 最新可见 pilot controller：偏 A。重复率触发固定换机制；没有逐实例异常分析、竞争解释或假设更新，继续也不由结果决定。
- next Plan：强制绑定上一轮 feedback 身份（对启用反馈的组），并不强制来自上一轮某个明确研究问题。
- actual parent/incumbent/reference skill：execution_delta 有独立角色；缺父本不拿 incumbent 冒充。reference skill 可标记未加载比较。plan_alignment 为 Agent 解释，不是 Runtime 对机制实施的认证。

因此不能认定“Reflection 是搜索不佳的根因”；目前首先缺的是有效 Reflection treatment 及可信计量，因果结论尚不存在。

### C：Memory 各阶段是否有 durable evidence

| 阶段 | 实现与证据 | 边界 |
|---|---|---|
| searched / hit | memory_searches 保存 query hash、filters、版本引用/hash、hit/no_hits/degraded/disabled | query 原文不在 receipt；历史 identity 不匹配时返回 search_receipt_recorded=false |
| full read | memory_reads 记录分页偏移/长度/总长/hash，complete_reads 按同一 ref+hash 合并覆盖；Plan 前重读校验正文 hash | 证明 API 返回完整正文，不证明人/Agent 理解 |
| selected/adopted | Plan.memory_basis 最多两个已完整读取的版本 | 属于 Agent 选择；不是 Runtime 判断有用 |
| compiled | context_manifest 与正文/注入 hash、omitted_refs | 超长时整条省略，不偷偷截断适用条件 |
| actual request | bridge 在 HTTP 前保存最终 request_inputs；memory projection 检查 exact context 恰出现一次 | durable “gateway attempt”；不保证远端接收、注意或有效利用 |
| probe/generation/repair | 独立 purpose；Memory consumption 只投影 generation/repair | 不把 probe 算成 Memory generation 消费 |
| publication | proposed→accepted→published/rejected/failed；operation_key 幂等 | 格式拒绝发生得更早，见 R02 |
| next-round availability | versioned store 可再次搜索/读取 | 端到端 fixture 有两轮证据；真实 pilot 原始 Session 本次未取得 |

Memory-off 在 schema、read、plan refs、memory_action 上有关闭分支；CI 的 Memory-off 失败是多出状态字段，不是发现 Memory 被偷偷打开。不能证明外部 controller 从未自行粘贴历史知识；控制实验还必须约束 controller 可见上下文和 store。本次没有发现官方 runtime 自动把关闭的 Memory 加回 prompt。

恢复 publication 只处理存储写入，不调用 EoH。R07 的语义不足仍需独立处理。

### D：声明搜索与实际搜索

[provenance.py:35](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/eoh_frozen/provenance.py#L35) 包装 pinned EoH 的 generation 调用，观察实际 _generate 返回的 parents；特别处理 duplicate retry 最终 code 的父本关系。i1 可为 no_parent，拿不到就 unknown。单 sampler 是该 wrapper 的明确前提。bounded repair 保留原 candidate/revision 与原 generation request，不把 repair 当作一次新 EoH 父本选择。

[population snapshot:18](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_supervisor.py#L18) 从官方 population_generation 文件选择最后一代，按 code 与可信 evaluation 对照（允许官方五位小数的匹配容差），不从 checkpoint 字段直接创造可信 fitness。[seed selection:99](https://github.com/gjd12345/auto-algo-opt/blob/74a1fb8b3b747a2113426e90315dc170039a0f60/agent_skill_loop/session_actions.py#L99) 校验上一轮 snapshot 的 hash/身份；不足则终止，不冷启动替代。

每轮确实重建一个 EoH engine，重新评测 baseline/seeds，并使用跨轮 seed；不是原地恢复全部 EoH RNG/进程/checkpoint。Skill 对此有明确说明，未发现最新 Skill 把它夸大成 exact resume。

可以机械回答“声明了什么、已评测候选用了哪些可验证父本、源码怎么变、该 suite 的行为/效果怎么变”。不能机械判定自然语言机制完全实施。实际 operator 在原始评测/provenance/repair 证据中可追踪，但 compact candidate/delta 投影未完整暴露所有 operator 字段；被官方丢弃、未进入 evaluator 的生成不能靠 evaluation_facts 单独统计。

### E：搜索效率能与不能判断什么

| 指标 | 当前可用程度 |
|---|---|
| exact-source duplicate | 对进入 evaluator 的 generated 可算；R06 的基准须明确；不是所有 provider 回复重复率 |
| valid generated yield | 是已评测原始 generated 的 valid 比例；不是每次 provider 请求产出有效候选的概率 |
| behavior duplicate/coverage | OBP 完整轨迹可算；其他问题不支持；修正 R06 后使用 |
| lineage concentration | 对 verified 父本链接可算；no_parent 应单列；不是整个种群熵 |
| per-instance diversity | 有有效向量数、唯一向量数、成对 L1；不等同结构/机制多样性 |
| fitness gain / solver attempts | facts 与账本可重建；首轮起点、窗口、baseline/seed/repair 成本要明确 |
| requests / solver / wall / token | request 与 solver reservation 已持久化；wall/token 聚合须修 R05 |
| repair、seed、baseline 成本 | origin、revision 和 solver_costs 有拆分；不得隐藏初始化成本 |
| Memory 消费 | transport 可观测；语义收益不可直接测 |
| repeated mechanism | 没有可信机制分类器/强制研究问题跟踪；自然语言不同不证明机制不同 |

当前 CI fixture 首轮 source duplicate=0、behavior duplicate=7/9，次轮 source duplicate=0、behavior duplicate=7/7，说明**系统能表示“源码一直不同而行为重复”**。fixture responder 本就设计重复行为；这些数字不支持现实搜索效率差的结论。真实 pilot 报告的 53%–83% 左右行为重复率本次没有原始 Session 可重建，不能当本次独立发现。

值得追查的搜索质量因素是：固定脚本的研究问题表达不足、Plan 建议不保证执行、新颖性/成本定义不稳、mini suite 很快饱和。它们是代码支持的风险或待验证假设，不是已经建立的性能根因。没有证据支持“一直只围绕 incumbent 搜索”；当前种群 seeds 与实际多父本链明确反驳这种一概判断。

### F：身份、来源与可复现性

- Runtime hash 覆盖两个核心 Python package；Skill hash 覆盖实际发布的 md/yaml；evaluator hash 纳入相关问题和行为代码；ProblemSpec、suite/data/metric/benchmark 都有独立身份。
- 官方 EoH pin 为 472545785c936dcfc863d2bc0d6109cf23c7ce62；verify_upstream 校验 distribution direct_url commit 与已安装 Python 文件的 RECORD hash。
- startup_preflight 是独立子进程的实际加载探针，比较 Session 冻结 hash，并额外探测 eval_worker 路径/hash。EoH/evaluator 实际子进程使用当前 package root 的 PYTHONPATH；这比仅记录 Git SHA 明显更强。
- **边界：** preflight 不是每个实际 worker 的运行时签名/认证；实际 solver 结果没有逐次返回完整 loaded-identity 回执。verify_upstream 验证的是 distribution 文件集合，未显式把每个已导入 EoH 模块路径逐一和 RECORD 绑定。未发现当前发生错载，但不能称强 attestation。
- wheel_sha256 明确为 null 并说明原因；安装模式/模块路径有记录。依赖版本、OS/数值环境、provider 实际模型后端不构成完整可复现封装。
- controller 身份不足见 R03；Git dirty patch、tools controller 不都在核心 runtime hash 内。hash 证明内容一致性，不证明发布者身份或安全来源。
- 本机 Python 3.11 静态模块定位显示 EoH 位于 Python311/site-packages；本次源码来自独立远程快照，不能把该安装路径当历史 Session 实际执行环境。未为它安装或升级依赖，也未声称新 wheel 已验证。

### G：预算、恢复与副作用

request reserve 先在 SQLite transaction 写入，再记录 request input 并发送 HTTP；solver_event 在求解前写入 started 记录。硬限额按 reservation/attempt 计算，unknown 不退款。gateway 遇 authentication、unknown/protocol 类失败转 terminal，官方重试不能继续转发；明确 retryable 429/5xx 若重试会再占新 slot。

supervisor 有独立 deadline、进程树终止和父进程 watchdog；dead-task recovery 把不确定请求标 unknown、solver 标 interrupted，不重做 provider/solver。操作 operation_id 与 state_version 用于幂等重放；已有 effectful task 阻止再执行同轮。

这是可信的**保守计费与恢复设计**。不承诺外部 provider 在本地 kill 后绝不继续计算；reserve→发送之间也不是跨本机/远端原子事务。stop 返回与远端已经开始的请求不能混同“已取消收费”。没有证据证明当前会自动重放 unknown 或自动退款。

R09 是 phase 检查的具体缺口。总 engine wall 主要度量执行任务，不包含所有外层思考/等待时间；如研究要求固定端到端计算预算，必须另记 controller 成本。新 Session 有新 ID，但目前没有跨 Session 的全局研究尝试注册表；换 Session 可隐藏失败的风险需要实验登记与报告全部失败尝试来约束，不能靠单 Session ledger 自动解决。

### H：optics 兼容性

extensions/optics 有独立 pyproject、artifact_session、optics_backend、optical-design Skill；CO package 未导入 optics backend，光学也不经过 official EoH。其源数据/私有审计任务包不在公共仓库，当前 CI 只验证公开合同与安装，不能证明 T1/T3 物理优化普遍稳定。

公共思想相同：hash 身份、artifact 而非 Python code 的资产、reserve/start/finish ledger、UNKNOWN 恢复、Memory 与执行解耦、online/audit 分区。实现是两套 runtime，并非一个已证明完全一致的共享内核。本次未发现 optics-specific 搜索逻辑泄漏到 CO。

可考虑回流 CO 的工程模式是 optics 的 reserve 与 start_effect 再检查状态/deadline、online/audit 分区及 artifact 身份；不应把连续参数调优当成 CO 搜索策略，也无需为了统一概念重写 official EoH。

## 当前 CI 与本地验证

CI 对应 74a1fb8b，运行日期 2026-09-20，2026-10-04 查询；并非引用历史验收报告。

| Job | 当前结果 | 解释 |
|---|---|---|
| optics / ubuntu | PASS | 公开 tests、compile、wheel；不含私有真实物理验收 |
| optics / windows | PASS | 同上 |
| knowledge / ubuntu | PASS | 知识测试、release 校验、current pointer |
| knowledge / windows | PASS | 同上 |
| kernel / ubuntu | FAIL | 3 fail / 190 pass / 1 skip；外部 checkout wheel 步骤 SKIPPED |
| windows-kernel | FAIL | 同样三个失败 |
| eoh / ubuntu | PASS | 45 tests；两轮 fixture closure；evidence export |
| eoh / windows | PASS | adapter tests、closure、export |
| closure-parity | PASS | 两平台现有 closure invariants 一致；不代表 invariant 覆盖了 R01 |

三个 kernel 失败与本次 Memory/schema 演进直接有关；不是“GitHub 网络失败”。schema/Memory-off 两项主要是合同投影同步问题，solution rejection 一项存在接受阶段差异，详见 R02。

本地只执行：
1. 远程源码快照的 Python 3.11 compileall（CO、EoH、tools、Skill Python）通过；
2. Python 3.12 optics src compileall 通过；
3. 已存在 CI compact bundle 的只读文件/hash 核验，22/22 通过；
4. 已有 JSON 的只读字段/引用/统计检查，记录于 read-only-verification.json。

未跑本地 pytest、未发 provider 请求、未调用 solver、未新增效果实验、未修改历史 Session。编译不是功能验证；功能运行证据来自明确列出的远程 CI。后续验证步骤仅为修复验收建议，未自行扩展执行。

## 文档声明抽样分级

“VERIFIED”仅对本表写明的范围有效，不能泛化成真实研究收益。

| 声明 | 分类 | 依据与边界 |
|---|---|---|
| OBP behavior evidence 可区分源码与观察行为 | IMPLEMENTED_AND_VERIFIED | 代码、当前通过的 behavior fixture；其他问题不支持 |
| 行为证据仅限训练范围 | CONTRADICTED_BY_CODE | R01；现有 heldout artifact 直接反例 |
| Memory 搜索→读→选→上下文→请求→发布→下一轮 | IMPLEMENTED_AND_VERIFIED（fixture 范围） | 当前 EoH 两轮测试与源码；真实 pilot 明细本次 UNKNOWN |
| actual request injection | IMPLEMENTED_AND_VERIFIED（gateway-attempt 范围） | 最终 payload 持久化和匹配；“provider 必然收到/利用”仍 UNKNOWN |
| 实际父本 provenance | IMPLEMENTED_AND_VERIFIED（pinned EoH、单 sampler） | wrapper、当前 EoH tests；未知保留未知 |
| worker loaded identity | PARTIAL | 子进程预检和路径/hash 有验证；不是每次实际执行身份签名，controller 另有缺口 |
| SearchProgress | PARTIAL | 指标和 ledger 接入真实存在；R04–R06 修正前不能笼统称精确效率/停滞指标 |
| Reflection v2 完整分析闭环 | PARTIAL | Skill 指令已写；合同不强制、pilot 不是该处理 |
| 跨轮 population inheritance | IMPLEMENTED_AND_VERIFIED | 当前两平台两轮 closure；不是 exact EoH checkpoint resume |
| optics isolation | IMPLEMENTED_AND_VERIFIED（公开工程范围） | 独立包/Skill、当前公开 CI；真实物理稳定性不在此结论内 |
| Memory publication 与 Evaluate 完全独立 | PARTIAL | 后端失败可恢复；格式错误在 Evaluate 接受前拒绝 |
| none 一定包含 reason | CONTRADICTED_BY_CODE（若理解为 Runtime 强制） | Skill 要求，MemoryAction 接受省略 |
| Memory/Reflection/SearchProgress 提升泛化搜索 | UNKNOWN | 无本次可复核的受控重复效果证据 |
| 最新 real pilot 的具体性能数字 | UNKNOWN（本次独立核验） | 有提交的报告，未取得其原始 Session；未用 fixture 替代 |

本次未把重要能力仅凭“implemented/verified”文案归为实现，也没有为了用满所有标签而虚构 DOCUMENTED_ONLY 项。某项只有操作建议的部分（例如 Reflection 的完整分析顺序）仍属于说明性协议，不是自动执行保证。

## 最终决策与最小实施顺序

**1. 当前架构是否值得继续：值得。** 保留官方 EoH 搜索权、Runtime 事实权、Agent 解释权。优先修边界和证据合同，不建议另写一个外层算法搜索器替代 EoH。

**2. 新的真实 CO 实验前必须处理：**
- R01：禁止 heldout 行为诊断；校准后的输出不能暴露轨迹。
- R02：消除当前 CI gate 失败，尤其把 Memory 提交/拒绝/恢复阶段说清。
- 冻结远程实现、实际解释器/依赖与 controller；不要混跑当前旧 checkout、未提交补丁和新远程代码。
- 若实验使用 SearchProgress/停滞/phase 因子，先修 R04–R06、R09；否则显式关闭这些因子，不以其有问题的指标做决策或主结果。
- 为每个真实运行保存可审查 evidence bundle 和失败尝试登记；没有原始数据就保留 UNKNOWN。

**3. 可以延后：** CVRP/TSP 全量行为观察器、更丰富的种群熵/机制分类、跨领域 Memory 检索优化、统一 optics/CO 实现、完整 wheel 二进制指纹和更强运行时身份封装。Memory-off pilot 可把 R07 的知识修订增强延后；Memory 效果实验不能忽略它。

**4. 当前可以支持的科学/工程声明：** 官方 EoH 能在冻结 evaluator 下生成和评测候选；OBP 可以产生 suite-scoped 行为证据；源码/轨迹/效果可以分别记录；工程 fixture 能跨轮继承种群并传递 Memory；现有 ledger 可以审计已计费尝试与保守恢复。它们主要是系统实现和流程可行性声明。

**5. 当前不能支持的声明：** Agent、Reflection 或 Memory 提升搜索效率/泛化；行为 signature 不同就是新算法；相同 signature 就语义等价；少量 mini suite 分数代表完整 EoH-S/SOTA；当前 stop/deadline 能撤销远端已开始费用；hash 是签名或安全认证；当前所有工程验收通过。

**6. 最小实施顺序：**
1. 固定版本与证据基线，修 R01 和 R02。
2. 修计量：真实 wall/unknown usage、novelty 基准、no_parent 分类。
3. 修停滞窗口/阈值/无起点语义及 phase 请求提前阻断；只读重建已有证据。
4. 完整导出证据，并给 controller 增加明确身份与可检验问题记录。
5. 先做不承诺效果的小型真实接线/假设 pilot，再预先制定正式比较的任务集、独立重复、预算、统计口径、Memory 初始条件和 heldout 使用次数。不要把任意“至少三个 seed”写成足以证明效果的通用门槛。

**7. 建议汇总：** 训练侧 engineering fixture GO；small real pilot CONDITIONAL GO；formal effectiveness experiment 与 release 当前 NO-GO。最小而有价值的下一步是修正隔离和计量，让一轮真实搜索能回答“检验什么、实际做了什么、还不知道什么”，再讨论增加搜索预算。

