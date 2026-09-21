# 研究闭环 v2：三 seed A/B/C 诊断结果

日期：2026-09-21  
范围：`obp_online / obp_evolution_mini` 的 `dev_train`；未读取 heldout。  
模型：`qwen/deepseek-v4.1-flash`。  
设计：3 个确定性配对 seed × A/B/C × 4 轮 × 25 次 solver 调用，共 9 个运行、900 次 solver 调用。

## 结论

研究闭环已经达到可审计状态：九个运行全部完成、预算账本完整、证据包哈希通过，
B 的每轮 Plan 从第二轮起精确引用上一轮研究笔记，C 在三个 seed 中都完成了
“第一轮发布 → 后续轮检索 → 完整读取 → Plan 采用 → 实际 EoH 请求携带”的运行内
Memory 链。外层 Controller token 无法由宿主精确提供，全部标为 `unavailable`，没有按
零计入总成本。

本次诊断无法回答 Reflection 或 Memory 是否提高目标质量。冻结训练集的 baseline 从
第一次 solver 调用起就是 0.0，且该指标的下界也是 0.0；因此九条 best-so-far 曲线、
终点 objective 和曲线面积完全相同。B−A 与 C−B 在所有配对 seed、所有第二至第四轮的
objective 差值均为 0.0。这是实验问题域缺乏改进余量，不是三种处理等效的证据。

搜索诊断没有出现跨 seed 一致的处理效应。B 的有效候选率相对 A 在两个 seed 上更高、
一个 seed 上更低；C 相对 B 在一个 seed 上更高、两个 seed 上更低。行为重复率也存在
同样的符号反转。三 seed 只足以验证流程和暴露信号，不能支持显著性或普适性声明。

## 汇总结果

| 组 | 处理 | 平均有效候选率 | 平均行为重复率 | 平均 EoH token | 平均 engine wall time |
|---|---|---:|---:|---:|---:|
| A | facts → Plan | 87.72% | 83.00% | 276,752 | 465.69 s |
| B | facts → 显式研究笔记 → Plan | 92.18% | 82.59% | 274,575 | 446.71 s |
| C | B + 运行内在线 Memory | 91.34% | 81.93% | 295,138 | 491.42 s |

C 的平均 EoH token 比 B 高 7.49%，平均 engine wall time 高 10.01%。这是值得后续继续
观察的成本信号，但样本很小，而且外层 Controller token 不可用，所以不能宣称总 token
效率或总成本优势。B 相对 A 的 EoH token 平均低 0.79%，wall time 低 4.08%，同样只作
描述性记录。

| seed | A 有效率 / 重复率 | B 有效率 / 重复率 | C 有效率 / 重复率 | C Memory 实际复用 |
|---:|---:|---:|---:|---|
| 1436574329 | 84.52% / 81.69% | 91.67% / 76.62% | 96.43% / 72.84% | 是 |
| 2082454166 | 94.12% / 80.00% | 89.53% / 87.01% | 86.90% / 78.08% | 是 |
| 3603139526 | 84.52% / 87.32% | 95.35% / 84.15% | 90.70% / 94.87% | 是 |

九个运行合计记录 2,539,394 个 EoH 模型 token 和 4,211.45 秒 engine wall time。每个
运行恰有 100 次 solver 调用。A/B/C 的外层 Controller 事件分别为每运行 4、8、14 条，
但 token 数均不可用。

## 运行中发现并冻结的两个合同修复

第一次门禁失败来自反馈上下文：完整的 25 条 attempt trace 被复制到下一轮提示，超过
12,000 字符上限。现在提示只接收固定字段的 window/cumulative 标量摘要；完整轨迹仍
保存在 `evaluation_facts.json` 和证据包中。真实首轮事实下，上下文缩至 7,448 字符。

第二次门禁失败来自种群继承：官方最终种群可能收缩为 2 个有效成员，而旧 Runtime 把
`pop_size=4` 误当作“必须继承 4 个种子”。现在继承所有可验证且源码唯一的最终成员，
最多 4 个；只有 0 个可执行成员才失败。实际继承数继续进入 `seed_selection.json`。
两批门禁失败会话已隔离保存，不与最终九个运行合并。

报告器还修复了两个离线接口漂移：支持导出器当前的 `{sha256, document}` Manifest
包装并重验文档哈希；把 Memory 读取的正式状态 `complete` 识别为成功。它们不改变
任何运行结果，只修正离线汇总。

## 下一步

当前 OBP mini profile 适合验证闭环，不适合估计目标质量增益。下一阶段应先冻结一个
仍有 headroom 的训练 profile，继续保持 heldout 锁定；用同样的 A/B/C 合同做小规模
方差估计，再决定正式样本量。若仍使用 OBP，应通过更难实例或更弱但合法的共同 baseline
制造可测改进空间，同时保持 MetricSpec、solver 预算和三组输入合同不变。

在新的 profile 上，预注册的主要问题应是：B 是否相对 A 改善固定 solver 预算下的质量
曲线，以及 C 是否相对 B 在第二至第四轮产生增量。有效率、行为重复率和 Memory 引用链
继续作为机制诊断；总模型 token 只有在外层宿主能提供精确 token 后才能成为完整成本指标。

机器可读报告与九个 compact evidence bundle 位于忽略目录
`outputs/research-loop-v2-diagnostic/`。报告中的所有运行均通过 bundle inventory 与
`SHA256SUMS.json` 校验。
