# 研究闭环 v2 上下文门禁记录

日期：2026-09-21  
范围：首个配对 seed 的第一轮诊断；不读取 heldout。

首轮 A/B/C 均完成 25 次 solver 调用。进入第二轮提交 Plan 时，Runtime 拒绝了
上下文并报告 `plan_context_too_large`，未产生新的 provider 请求。原因是
`evaluation_facts.json` 中固定窗口的完整 25 条 attempt trace 被原样复制进下一轮
EoH 提示；提示长度随 solver 预算增长，违反有界上下文合同。

处置如下：

- 停止并保留全部九个已初始化 Session，不把它们计入正式诊断；
- 完整 attempt trace 与父代频次继续保存在事实文件和 evidence bundle；
- 下一轮提示仅接收固定字段集合的 window/cumulative 标量摘要、冻结 policy 与
  stagnation 判定；
- 使用首轮真实事实复核，修复后的上下文为 7,448 字符，低于 12,000 字符上限；
- 重新生成预注册清单和 Session，使冻结的 runtime identity 与修复后代码一致。

旧 Session 及其证据保存在忽略目录
`outputs/research-loop-v2-diagnostic-pre-context-fix/`，仅作为门禁失败记录，不能与重启后的
A/B/C 结果合并。
