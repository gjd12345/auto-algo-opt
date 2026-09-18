# CO Iteration A：离线证据闭环验收

日期：2026-09-18。基线分支 `agent-skill-loop-0908`，起点 HEAD `b3a5fea`；工作区的光学源码、benchmark 工具和既有未跟踪实验产物均不属于本次变更。本次未提交、未 push、未使用付费模型。

## 实现与证据

|合同|交付|离线结论|
|---|---|---|
|A0 冻结身份|Runtime/Skill/ProblemSpec/evaluator/EoH hash、实际模块路径和 Python 解释器；安装方式与未知 wheel hash 分开表示|新 Session 冻结，不回写旧 Session|
|A1 LoadedIdentity/v1|启动前子进程加载身份及隔离 eval worker 握手，身份不符停止在外发前；预检落盘|源码两轮 fixture 和脱离源码 wheel 均通过；宿主模型身份只能标 reported/unknown|
|A2 BehaviorEvidence/v1|OBP 同次评测记录物理 bin 选择、事件数、完整流式摘要及有界样本；部分失败不可判等|两段不同源码的相同行为、不同选择行为及 partial 无签名均通过；无额外诊断评测|
|A3 ExecutionDelta/v1|最终 `_generate` 调用的实际父本；候选精确源码、行为与逐实例效果分开比较；事实通过 `evaluation_facts` hash 引用并进入下轮有界反馈|i1 无父本；e/m 操作在 fixture 中观察到已验证父本；重复重试不误绑定首次父本|
|A4 MemoryConsumption/v1|持久化搜索与失败选读，分别列出 selected、compiled、omitted、最终 gateway request、publication；Round receipt 带 SHA256|第二轮完整读取后确实在生成请求中出现编译后的完整上下文；不声称模型理解或效果增益|
|A5 两轮 OBP|官方 EoH、冻结 OBP 训练套件，首轮冷启动、次轮 population seeds 全量重评，SQLite 成本与 sidecar 报告可重建|零 provider 付费请求（仅 localhost fixture），两轮均结束且能从磁盘重建报告|

最小验证：`py -3.11 -m compileall -q agent_skill_loop eoh_frozen`；定向 `tests/eoh_frozen/test_iteration_a_evidence.py`、原两轮 Memory 集成与分页测试；`tools/validate_skill.py skills/algorithm-optimization`；`tools/verify_release_install.py` 从构建 wheel 的新环境检查 Skill hash 和子进程预检。原始断言与离线复跑步骤保留在上述测试和工具中，临时 pytest Session 不作为仓库长期性能数据。

## 边界和未完成项

- 此处的同 Session 两轮仍是两次官方 EoH task，第二轮 seed 完整重评；不是 RNG/checkpoint 精确恢复，也不是 Agent 模型已经学会搜索。
- fixture 的第二轮 EoH 最终请求包含 Memory 摘录；这是 gateway 尝试和 prompt 字节证据，不证明 provider 收到、理解或使用。Memory 写入是 Agent 决策，不强制每轮发布。
- 行为签名只在同合同、同套件、完整有序实例轨迹范围内比较。运行时间和结果边界可能受观察开销影响；还没有量化真实大实例的开销。
- 未运行真实 API、heldout、正式受控实验，也未实现 Iteration B 的 SearchProgress 和探索/利用子预算。不能从此验收宣称算法效果提升。
- 不升级正在运行或历史 Session 的 Runtime/Skill 身份；升级后创建新 Session。光学路径未修改，仍作为以后独立的兼容性验证。
