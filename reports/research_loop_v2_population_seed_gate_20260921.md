# 研究闭环 v2 种群继承门禁记录

日期：2026-09-21  
范围：上下文修复后首个配对 seed 的第二轮启动；不读取 heldout。

A、B 第一轮分别产生 22/24 与 24/24 个有效候选，但官方 EoH 最终种群均收缩为
2 个可验证且源码唯一的成员。旧 Runtime 把 `pop_size=4` 同时解释为“继承必须有
4 个种子”，因此在第二轮 provider 请求前以 `insufficient_valid_seeds` 终止。
C 的最终种群恰有 4 个成员，能够继续。这会把随机的最终种群大小混入组间处理效应。

上游 EoH 的父代选择允许从非空种群有放回采样，且后续 population management 会把
新候选并入种群容量。因此冻结以下继承规则：

- 继承上一轮官方最终种群中所有可验证、源码唯一的成员，最多 `pop_size` 个；
- `pop_size` 是容量上限，不再是启动下一轮所需的种子数；
- 至少需要 1 个可执行成员，0 个仍以 `insufficient_valid_seeds` 明确失败；
- 实际种子数、目标容量和成员精确身份继续写入 `seed_selection.json`；
- A/B/C 使用同一规则，最终种群收缩本身仍作为搜索结果保留。

受影响批次已停止并保存在忽略目录
`outputs/research-loop-v2-diagnostic-pre-seed-selection-fix/`。其中 C 完成了两轮并证明
Memory 发布、检索、完整读取和请求引用链可工作，但该批次不与修复后正式诊断合并。
