# OBP v1.1 A/B/C/D 真实 API Pilot 比较报告

> 本报告由四个独立 Session 的持久化证据重建。每组训练评测预算为 100；heldout 只在 selection 锁定后离线执行，未产生模型请求。

## 运行摘要

| 组 | 轮数 | 总评测 | 生成候选（有效率） | seed 重评 | Provider 请求 | 最好生成训练 fitness | incumbent 训练 fitness | heldout Top1 | heldout archive Top10 | heldout final population |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 1 | 100 | 85/99 (85.9%) | 0 | 100 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| B | 2 | 100 | 90/96 (93.8%) | 2 | 99 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| C | 2 | 100 | 89/96 (92.7%) | 2 | 98 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| D | 2 | 100 | 92/96 (95.8%) | 2 | 98 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## 预算与链路核对

| 组 | novel candidate | seed reevaluation | baseline | repair | archive 条目 | 终止原因 | token（输入/输出） |
|---|---:|---:|---:|---:|---:|---|---:|
| A | 98 | 0 | 1 | 0 | 84 | `ROUND_BUDGET_EXHAUSTED` | 123080/21507 |
| B | 88 | 2 | 2 | 0 | 82 | `ROUND_BUDGET_EXHAUSTED` | 177391/16526 |
| C | 95 | 2 | 2 | 0 | 88 | `ROUND_BUDGET_EXHAUSTED` | 183709/21702 |
| D | 96 | 2 | 2 | 0 | 92 | `ROUND_BUDGET_EXHAUSTED` | 180618/17459 |

## 逐组结果

### Group A

- Session `run_a0a0aff3a3ad4383b244a7d557fe5f6c`，manifest `986ba9df320fa324438eb4d7310ea12339f4b70339a8db3ec0254a4b3007d726`。继承模式：`incumbent_only`；Agent guidance：`false`。
- 训练终止：`ROUND_BUDGET_EXHAUSTED`；实际评测 100 次；archive 发现条目 84 个。
- 生成候选：85/99 有效；不同有效代码 84 个；重复有效代码 1 个。
- 最好生成训练 fitness：`0.0000`；主要无效原因：`{'candidate_error': 3, 'forbidden_attribute': 11}`。
- Heldout：incumbent_top1=0.0000 (1 evals); archive_topk=0.0000 (10 evals); final_population_set=0.0000 (2 evals).
- 证据包：`C:\Windows\System32\auto-algo-opt\outputs\obp_abcd_real_20260915_01\evidence\A`。

### Group B

- Session `run_bd65318fe4f3467ba44cf23370c1870f`，manifest `780c93a9d9a51e0badc49c626c43a4c79d11a461bdca50da7d2b4e1e4467be17`。继承模式：`incumbent_only`；Agent guidance：`false`。
- 训练终止：`ROUND_BUDGET_EXHAUSTED`；实际评测 100 次；archive 发现条目 82 个。
- 生成候选：90/96 有效；不同有效代码 82 个；重复有效代码 8 个。
- 最好生成训练 fitness：`0.0000`；主要无效原因：`{'candidate_error': 4, 'forbidden_attribute': 1, 'invalid_return': 1}`。
- Heldout：incumbent_top1=0.0000 (1 evals); archive_topk=0.0000 (10 evals); final_population_set=0.0000 (2 evals).
- 证据包：`C:\Windows\System32\auto-algo-opt\outputs\obp_abcd_real_20260915_01\evidence\B`。

### Group C

- Session `run_a1ae909ba4354db28c8e1ea8e35acbb3`，manifest `ec81a9c5cac7867de6e3b46bffa0f236ee29451f7a98d529016f4cbe2182802a`。继承模式：`population_seeds`；Agent guidance：`false`。
- 训练终止：`ROUND_BUDGET_EXHAUSTED`；实际评测 100 次；archive 发现条目 88 个。
- 生成候选：89/96 有效；不同有效代码 88 个；重复有效代码 1 个。
- 最好生成训练 fitness：`0.0000`；主要无效原因：`{'candidate_error': 3, 'forbidden_attribute': 4}`。
- Heldout：incumbent_top1=0.0000 (1 evals); archive_topk=0.0000 (10 evals); final_population_set=0.0000 (2 evals).
- 证据包：`C:\Windows\System32\auto-algo-opt\outputs\obp_abcd_real_20260915_01\evidence\C`。

### Group D

- Session `run_30374b6bd1954fdba613c9096cf0c25b`，manifest `5a2625214836b807bf7f76ca728ffc7d412aab1f400e812e061455e4ffbc3354`。继承模式：`population_seeds`；Agent guidance：`true`。
- 训练终止：`ROUND_BUDGET_EXHAUSTED`；实际评测 100 次；archive 发现条目 92 个。
- 生成候选：92/96 有效；不同有效代码 92 个；重复有效代码 0 个。
- 最好生成训练 fitness：`0.0000`；主要无效原因：`{'candidate_error': 1, 'forbidden_attribute': 3}`。
- Heldout：incumbent_top1=0.0000 (1 evals); archive_topk=0.0000 (10 evals); final_population_set=0.0000 (2 evals).
- 证据包：`C:\Windows\System32\auto-algo-opt\outputs\obp_abcd_real_20260915_01\evidence\D`。

## 解释边界

1. A 使用统一 Session adapter 的单轮 neutral 路径；B 是多轮 incumbent-only；C 是多轮 population-seeds neutral；D 只在 C 的基础上打开 adaptive Agent guidance。
2. A/B 仍同时改变连续搜索与 session 化方式，因此只能解释为 continuous EoH 与 sessionized EoH baseline 的比较；C/D 才是主要的 Agent guidance 对照。
3. 本次每组只有一个真实 run，结果用于验证闭环、继承、预算和证据链，不足以作统计显著性或泛化结论。heldout 分数只对注册的 OBP mini 套件有效。
4. `0.0` 是该 mini 套件上相对 reference 的 mean relative gap；它表示达到该套件 reference，不代表跨数据集或更大实例上的普遍优势。

## 证据索引

- Pilot 根目录：`C:\Windows\System32\auto-algo-opt\outputs\obp_abcd_real_20260915_01`
- 每组 `reports/` 下有 `incumbent_top1`、`archive_topk`、`final_population_set` 的 selection、inputs 和 report。
- 每组 `evidence/` 是可校验的 compact bundle，包含训练事实、种群、预算和 heldout report。
