# A/B/C 人读案例（design_example）

本页用于说明协议中的可审查链条。所有标识、objective 和行为签名都是
`design_example`，不是历史运行结果，不得用于效果结论。

## 共同事实包

三组都收到同一结构和同一选择规则生成的 packet。示例中：

- 谱系槽：`eval-child-17` 精确引用父代 `eval-parent-04`；objective 从 12.4 降到 10.9；
- 行为重复槽：`eval-child-19` 源码不同，但与更早的 `eval-child-11` 具有相同完整行为签名；
- 效果差异槽：`eval-child-17` 和 `eval-child-21` aggregate 都接近 10.9，
  但前者改善大实例、后者改善小实例；
- 一条 timeout 只出现在状态摘要，不参与“行为相同”判断；
- 当前 25 次 attempts 的有效率为 0.84，行为重复率为 0.29，搜索状态为 `stagnated`。

Plan 的声明方向是“减少高负载下的延迟惩罚”，声明机制是“提高余量不足任务的选择权重”。
packet 把声明与实际改动并排给出，不预先裁定是否一致。

## A：事实直接形成 Plan

A 阅读 packet 后直接提交下一轮 Plan：

```json
{
  "search_intent": {
    "direction": "区分负载分段策略和统一权重策略",
    "mechanism": "只改变高负载实例的余量权重，并保留低负载控制支路"
  },
  "reflection_basis": null
}
```

链条是 `comparison packet → Plan`。A 不生成结构化研究笔记。

## B：相同事实先形成研究笔记

B 先在 `evaluation.submitted.json` 提交：

```json
{
  "observations": [
    {
      "claim": "总分接近的两个候选在大小实例上的收益方向相反",
      "evidence_refs": ["rounds/round_0001/comparison_packet.json"]
    }
  ],
  "hypotheses": [
    {
      "claim": "统一提高余量权重可能把大实例收益换成小实例损失",
      "confidence": "medium",
      "evidence_refs": ["rounds/round_0001/comparison_packet.json"]
    }
  ],
  "next_search_advice": {
    "direction": "用分段权重和统一权重的成对候选区分规模条件效应"
  }
}
```

下一轮 Plan 必须精确引用该笔记：

```json
{
  "search_intent": {
    "direction": "检验规模条件效应",
    "mechanism": "仅在高负载分段提高余量权重"
  },
  "reflection_basis": {
    "round_id": 1,
    "evaluation_ref": "rounds/round_0001/evaluation.submitted.json",
    "evaluation_sha256": "<accepted-note-sha256>"
  }
}
```

链条是 `comparison packet → evidence-bound note → reflection_basis → Plan`。

## C：笔记发布为 run 内经验并在后轮引用

C 第一轮与 B 一样提交笔记，随后可发布 insight：

```markdown
---
evidence_ref: rounds/round_0001/comparison_packet.json
source_run_id: run-design-c
round_id: 1
---
**Applicability:** OBP 在线分配中，aggregate 接近但实例向量分化的候选。

**Limitations:** 目前只有训练侧一轮证据；行为签名相同也不证明所有输入等价。
```

第二轮检索只能返回 `source_run_id=run-design-c` 且 `round_id=1` 的记录。Agent 实际读取后，
在公开 Memory consumption 记录中留下引用，并提交与 B 相同格式的
`reflection_basis`。Plan 可以采用该经验，也可以说明为何本轮条件不适用。

链条是
`comparison packet → note → run-internal Memory → later search/read → reflection_basis → Plan`。
第一轮 C 没有早先经验，因此不能把第一轮的 C−B 差异解释为 Memory 效应。

