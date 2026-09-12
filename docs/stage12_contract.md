# 阶段 1、2：官方 EoH 运行与资产合同

生效日期：2026-09-11。替代旧固定 i1/e1/m1 方案。Plan / Execute / Evaluate 角色及 Memory 属于后续阶段。

## 唯一生产链路

两个 run 命令共用参数及监督实现：

```text
CLI → 监督进程（问题、预算、deadline、证据与资产）
      ├─ localhost bridge → HTTP worker → 模型服务
      └─ 官方 EoH worker → 官方种群/父本/算子 → FrozenProblem → 隔离候选 worker
```

官方 commit 锁定 472545785c936dcfc863d2bc0d6109cf23c7ce62；启动核验来源、commit 和安装 RECORD，记录适配层源码 hash。生产不替换上游算子/提示或修改 site-packages。e1/e2 使用官方多父本机制，m1/m2 使用官方变异语义。串行 sampler/evaluator 是本次证据关联的执行约束。

支持 cvrp_construct、tsp_construct、tsp_2opt；问题、接口、suite 和 evaluator 身份贯穿配置、评测、资产。

## 参数和停止

| 参数/计数 | 含义 |
|---|---|
| pop-size | 官方种群大小，至少 2 |
| n-pop | 未指定 max-sample-nums 时决定进化尝试数 |
| max-sample-nums | 初始化后的进化尝试数，允许为 0 |
| initialization_samples | 冷启动为 2 × pop-size；显式 seed 走官方种子初始化 |
| max-requests | 全部真实 HTTP 尝试上限，默认 32，包含探活及重试 |
| wall-seconds | 全局网络/计算期限，默认 420 秒 |
| solver-timeout | 单次评测上限，同时受剩余墙钟限制 |
| evaluated_generated_candidates | 实际形成可信评测记录的生成候选数 |
| generation_requests | 已保存完整响应的生成请求数 |
| http_requests | 失败、探活和重试均计入的 HTTP 尝试数 |

旧 candidate-attempts/max-llm-requests 参数被拒绝，不作不同语义的隐式换算。小请求预算可以有意提前停止；官方内部空 sample 不计入实际生成候选数。

监督进程在期限或终止性错误发生时关闭引擎及进程树，嵌套评测另有父进程 watchdog。deadline 后不新增 solver/模型调用，只清理进程并序列化已有证据。操作系统清理和磁盘写入可能产生少量收尾时间。

认证失败、未知请求结果及协议损坏关闭转发；串行锁阻止重试与尚未完成的请求重叠。仅明确可重试的 429/5xx 可在剩余总预算内重试。探活单列为 eoh_probe。

终态区分 completed、stopped、provider_failed、invalid_input、evaluation_failed、engine_failed、no_valid_candidate、export_failed/storage_failed；request_limit 与 wall_time_limit 分别记录，导出错误不冒充 provider 错误。

## 证据与资产

二次修复补充：任何原状态下的导出失败均使 loop_completed=false、退出码为 2，保留 prior_status / prior_stop_reason。skill 的代码、元数据与 evidence.json 在同一临时目录写齐后整体原子发布。

评测前原子保存 evaluation_starts/<evaluation_id>.json，完成记录携带同一 ID。引擎停止后对账，未完成项写入 evaluation_interruptions.json，记录 cancelled/interrupted 和停止原因，不伪造分数。solver_calls 与 solver_calls_started 表示已登记进入评测流程的次数（不保证子进程创建成功），solver_calls_completed/interrupted 分别表示完成和中断数。零墙钟不登记启动。

exchanges/request_N.json 保存实际 prompt、模型正文和 hash；requests.jsonl 保存预留/终态，不含认证头。evaluations.jsonl 保存实际代码、逐实例结果、合法性、错误、成本、问题/接口、代码/suite/evaluator hash 和请求关联。

baseline、explicit_parent、generated 分开记录。父本先在当前套件验证，通过后才创建 seed 文件及复用资产，随后仍经过官方 seed 评测。历史分数不继承。无效父代码不进入本轮可复用集合。

每个有效生成候选保存为不可变 skill，并附 evidence.json。best_generated_path 仅指 generated；exported_skill 指向整体 incumbent，可指向基线或父本。仅种子运行的生成计数为 0，best_generated_path 必须为空。

checkpoint 工具统一比较 pops_best、samples、pops 中的有限有效目标值。生产收尾根据已完成的本地评测证据选优，不启动额外重评；单独调用 checkpoint 导出工具则重评后发布。保留官方舍入分数与本地精确分数。

上游不输出父本 ID，因此生成资产的 lineage 明确记录 upstream_parent_ids_not_exposed，保存实际请求与评测引用，不伪造单父谱系。显式父资产记录用户来源版本。后续 3+1 需在自己的计划合同中增加可验证的修改对象。

新 ref 使用 algorithm-skill-ref/v2。原 v1 仍可读：原本未声明的 problem/entrypoint 从目标读取，其余身份及所有已经声明的字段必须一致。循环引用被拒绝，旧文件不被静默改写。目录不可变发布和 ref 替换失败不得先删旧资产。

数值 AST 对未知属性默认拒绝，覆盖容器、解包和参数别名，并禁止重绑定受限模块；合法数值和容器方法仍受白名单约束。它与隔离进程/超时构成受限执行环境，不宣称为操作系统安全沙箱。

## 验收与历史边界

使用 Python 3.11。kernel 无需安装 EoH；EoH 专项必须安装 pinned extra。CI 在 Ubuntu、Windows 上执行真实官方引擎、localhost 模型、隔离评测及 skill 重载测试。

tests/fixtures 保留旧循环测试辅助代码，setuptools 不打包，生产不提供旧入口。研究报告、运行产物、git 历史保留追溯用途，不作为当前执行指引，也不自动导入为算法或记忆。

13 项证据和真实 API 结果见 [验收报告](../reports/stage12_acceptance_20260911.md)。认证失败不能证明真实模型多轮进化成功。
