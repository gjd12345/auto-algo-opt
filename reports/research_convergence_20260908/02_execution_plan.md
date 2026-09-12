# 历史执行计划 v3（已废止，仅供追溯）

当前执行状态以 [当前审计验收](../audit_20260912/acceptance.md) 为准。下文的固定算子、旧入口及待实施指令均不适用于当前生产实现。

日期：2026-09-08。历史源码基线：`Refactor0830` / `c8cb66cd09d3829bfdf254d00d117fe35cfd6410`。

本版落实用户对 journal、输入记忆、同步测试、分支隔离和 Python 版本的约束，替代上一版“在 FME 包内增加小入口”的方案。本文件是待实施计划；新包、CLI、测试和 smoke 尚未实现或执行。本轮仅修订未提交的报告文件。

本版进一步以用户最新定义为准：给定一个问题，循环自己生成、独立进程评测、根据真实反馈再生成，并在预算用尽时停止。**闭环是否完成与是否有有效候选是两个不同维度；全失败可以跑通闭环。** 不要求incumbent优于基线或任何历史方法。

## 0. 唯一完成定义

| 验收项 | 必须看到的证据 |
|---|---|
| 输入是问题 | 调用方给出 `cvrp_construct`，程序使用固定3个开发实例；无RQ、臂、前瞻分析、科研协议必填项 |
| 多轮自动生成与实测 | 正常预算下完成3次候选尝试；候选代码交给独立进程评测，结果或错误送入后续请求。只评基线、只生成一次均不能证明完整闭环 |
| 反馈实际消费 | 记录父版本/失败版本、本轮分数或错误、下一轮实际请求的prompt文本与hash；能逐条定位被消费的内容，不仅是feedback ID或hash |
| skill可重载 | 有效的生成候选导出 `code.py` + 元数据，由新的进程加载并重评同一套件，分数一致；非法代码保存错误，不进入可复用集合 |
| 预算与故障终态 | 次数、请求数、墙钟任一达到上限即停；认证故障单列 `provider_failed`，不算算法无效 |

有效skill的导出验收是条件性的：真实运行全失败时，合法结果是 `no_valid_candidate`、无生成skill导出；保存/重载能力由含有效候选的fixture内核测试证明，不要求为得到有效结果追加真API。原始nearest-neighbor基线或外部父本即使合法，也不计入本次生成的valid_candidates，不包装成进化成功。

明确不验收：相对官方13.519或Island 12.356的提升、行为准确率、Potential-AUC、held-out、跨问题迁移、RAG、策略卡、反例、科研控制器、统计显著、多模型、多种子。论文主张和新颖性不属于当前工程验收。

## 1. 分支与运行范围

- `Refactor0830` 保留为历史快照，重构不在该分支提交、删除或改写源码。
- 实施时从上述固定提交创建独立工作分支，建议名 `agent-skill-loop-0908`；全部代码抽取、删除和 CI 修改都在新分支进行。
- 当前未提交的研究报告、光学材料先单独保全；不能假定它们已被旧分支提交保存。禁止清理整个 reports 目录来获得“干净工作树”。
- 远程默认分支、`origin/HEAD` 和旧分支 upstream 保持现状；本阶段不推送或调整远程默认。新分支 no-API smoke 通过只是允许讨论切换的前提，不是自动切换授权。
- 开发验收和 CI 固定 Python 3.11。本机全局 Python 3.14 不作为本次验收环境，不在重构中升级 Python。
- 第一版只支持 CVRP 小规模合成实例；单模型接口、固定循环、有限候选预算，不训练控制器、不优化提示模板、不运行历史矩阵。
- Fixture先过，只证明接线；之后等待用户授权真API。现有服务配置或环境密钥不构成授权；只有真实模型的多轮运行才能证明“给问题，让模型自己转”。

## 2. 优化对象与输入白名单

skill 定义为“可执行启发式代码 + 不可变版本 + 父本谱系 + 本次真实评测”，不是插件、研究报告或自然语言策略卡。

初始算法来源只有两个互斥选择：

1. 仓内确定性基线；
2. 用户通过 `--parent-skill` 显式指定的一个父 skill。

父 skill 必须在本次冻结的新套件上重新评测，然后才可参与生成/选择；不能复用历史分数。Island 605、Q3、RQ1b 中实际存在且接口兼容的候选代码，可在用户显式选择后转为一个父 skill。报告文本、失败结论、卡片内容、旧描述与旧分数均不进入 prompt；只有失败记录而无代码的材料不能充当父代码。

prompt 的运行时上下文白名单：

- 固定问题说明、函数签名及执行约束；
- 本轮选中的一个父代码及其本次实测分数（无父时为空）；
- 当前运行中需要修订的失败代码和对应实际错误，或前轮实际数值反馈。

当前运行产生的有效 skill 可以成为下一轮父本；这属于本次循环内部反馈。首版没有历史报告检索、RAG、策略卡、自动挑选历史父本或跨问题知识注入。skill 的 description/provenance 仅存储，不自动序列化进 prompt。

算子语义固定为：`i1` 无父生成、`e1` 单父改进、`m1` 携带实际失败代码与错误进行修订。基线可以作为初始 incumbent，但 i1 请求不携带基线父代码；若携带父代码，应明确记录为 e1。m1 不得只传 incumbent 而遗漏失败代码，也不伪造失败候选的有效分数。每次生成和修订都占一个候选额度。

## 3. 新内核与旧能力的迁移

采用独立 Python 包 `agent_skill_loop`（建议名称，待实施），只保留正常生成、失败修订和预算停止。新包不能导入旧 `eoh_rag.fme` 来获得方便的 wrapper，否则其包入口会重新加载分析、档案与冷启动等旧依赖。

| 能力 | 历史参考 | 新版做法 |
|---|---|---|
| CVRP接口、实例、基线 | `eoh_rag/fme/pilot_evaluation.py` | 抽取到新问题模块，显式保存接口与固定套件；解除对旧包和官方例题文件路径的隐式依赖 |
| 真实评测、接口约束、超时 | 同文件与 `scripts/fme_pilot_eval_worker.py` | 新包内自包含 worker；独立进程执行；同步落地四组保护测试 |
| 候选提示与代码提取 | `EOHGeneratorAdapter`、vendored EoH | 抽取必要逻辑，明确 i1/e1/m1；不实例化整个旧 Evolution 引擎或触发官方包的自动导入；保留所复制代码的许可证与出处 |
| 模型访问与错误分类 | transport、provider代码 | 新的可注入 client；真实调用与 fake transport 共用接口；零隐藏预检，失败也计入成本 |
| 单步执行、预算、停止 | `FMEResearchLoop` 的设计 | 重写小型 `AgentLoop`，不继承其机制主张、反例档案或 action 信用状态 |
| 记账 | `EvidenceJournal` 的能力 | **重写新 journal，不保留原类，不调用旧 verify_journal** |
| skill持久化 | 候选资产格式作为参考 | 新 skill store；一个不可变版本绑定代码、suite hash、评测器版本和谱系；保存/加载同步测试 |

预算独立计数：candidate attempts、LLM requests、solver calls、wall time。solver 批调用和候选尝试不是同一单位。基线、父本重新评测和独立加载评测均计入 solver 成本。

拟定最小结构：

```text
agent_skill_loop/
  __init__.py
  __main__.py
  loop.py
  contracts.py
  generator.py
  client.py
  evaluator.py
  eval_worker.py
  journal.py
  skill_store.py
  problems/cvrp.py
configs/cvrp_smoke.json
tests/kernel/
pyproject.toml
README.md
```

这里是目标目录，不代表文件已经存在。

## 4. 新 journal 与 skill 合同

新 journal schema 名为 `agent-skill-journal/v1`，只承担 hash 链、attempt 事件、代码落盘、成本字段。事件名使用 `attempt_started`、`attempt_result`、`run_finished` 等新命名；不使用 `candidate_evaluation`，不设置 prospective-analysis 关联字段或前瞻分析校验。

最小事件字段：

- sequence、previous_hash、content_hash；
- run_id、attempt_id、operator；
- parent_version_id、failed_code_hash（如有）、prompt_hash、feedback_attempt_id；
- 实际发给transport的完整prompt文本或本地请求文件路径；保存白名单内容并计算hash，不含凭据/认证头；该记录用于证明上一轮分数或错误确实进入下一次请求；
- candidate_code_hash/path、实际评测结果、错误类别、采纳决定；
- llm_requests、input/output tokens、solver_calls、elapsed_seconds；用量未知为 null，不能写成零。

验证器只检查新事件合同、hash/顺序、attempt起止关联、代码身份及成本字段一致性。失败也有 attempt_result；中断缺终态则报告 incomplete。schema 内没有分析字段，也不会通过校验回调触发任何 LLM 请求。允许明确重复候选但不能伪增 skill 数。

一个 skill 由 `code.py` 与 `skill.json` 构成。必需字段为 schema_version、version_id、problem、entrypoint、code_sha256、parent_version_id、suite_hash、evaluator_version/hash、valid、逐实例目标及均值、来源 attempt。历史来源说明仅作元数据。加载时核对源码身份；用于新的运行前重新评测，禁止直接接受历史成绩。

本轮生成出的合法但更差的 skill 仍可保存为 evaluated；incumbent 按本次开发集最小均值更新。非法候选保留代码和错误，但不作为有效 skill。重复代码仍消耗尝试预算。

## 5. 同步落地的四组内核测试

这些是用户明确要求的首版必需检查，抽取核心代码时同步实现，无需再次申请测试范围。旧测试删除前，相应新保护必须已存在并通过。测试全部在 Python 3.11、无 API 条件下进行，使用真实新评测器与 fake transport，不安装/运行旧科研框架。

| 测试组 | 最小断言 | 防止什么问题 |
|---|---|---|
| 套件 hash 稳定 | 固定seed/配置重复构造，序列化再加载后hash一致；实际实例内容变化应改变hash | 同名不同数据、格式变化或加载漂移 |
| 非法代码、超时、接口失败 | 非法源码返回明确失败；合法语法的无限循环在有界时间内终止；缺入口或返回类型/范围错误不能成为valid | worker挂死、无效候选被当成功；不能只测AST拒绝来冒充超时测试 |
| i1/e1/m1 请求合同 | fake transport捕获实际prompt：i1无父，e1包含唯一父代码和新分数，m1包含本次失败代码/错误；实际执行算子与日志一致 | 算子只有标签、修错代码、历史文本进入prompt |
| skill 保存/加载一致 | 合法代码实测→保存→加载→在同一套件重评，源码身份、逐实例目标和均值一致 | 仅比对保存的JSON而未真正重执行 |

i1/e1/m1 的合同检查同时断言没有旧报告/策略卡上下文；测试输入中可设置不可混淆的标记，检查最终请求。no-API smoke 的 transport 禁止网络，出现真实请求直接失败，不因本机已有密钥改走线上。

smoke在同一小型内核测试集中覆盖：有效候选可导出重载；3次全无效仍消费错误并以no_valid_candidate停止；次数/请求上限/墙钟停止；模拟认证失败为provider_failed。使用fake transport和可注入时钟检查预算分支，不真实等待墙钟上限；真实子进程超时由上面的专门用例覆盖。这些是完成定义要求的有限保护，不扩展成科研实验或全仓库回归。

新包可 import 与四组 pytest 通过后，只处理具体失败，不扩展成全仓库测试、反复跑已通过测试或科研消融。

## 6. 新分支清理顺序与删除门槛

| 阶段 | 工作 | 完成证据 |
|---|---|---|
| P0 | 保全未提交材料，创建新分支，记录旧commit与远程状态；配置3.11 | 旧分支提交未变，远程默认/upstream未改，目标工作区明确 |
| P1 | 抽取CVRP问题/评测、生成接口、新journal和skill store；同步写四组测试 | 新包独立import，四组内核pytest通过；没有导入旧FME/EOH包或真实网络请求 |
| P2 | 在新分支移出历史框架、旧manifest、旧测试与依赖；接小loop/CLI | 删除后的新包仍可import，受影响的新内核检查通过；旧分支保留历史材料 |
| P3 | 新循环no-API smoke：fixture生成、真实solver、保存/重载、反馈消费与停止 | 终态、预算、事件与score一致；API请求数0；不把fixture称为真实模型结果 |
| P4 | P3通过后，获得用户真API授权，显式配置一个模型并按小预算运行 | 多轮真实生成→独立评测→反馈被消费→预算停止；允许全无效，终态no_valid_candidate；与fixture结果单列 |

P1和P2的检查针对删除前后的不同依赖状态，属于必要覆盖，不是无变化重复测试。P3可作为内核pytest中的集成项，CI一次执行覆盖；无需再反复运行相同smoke。通过P3后才讨论远程默认分支切换，任何切换另行决定。

新分支可移出的对象：`Agent_EOH/`、`go_solver/`、旧TOCC/operator/search_control/solver_adapter、路由/selector、FME分析/反例/潜力/order-regime/RQ1b恢复、旧batch/island入口、93个manifest及对应一次性脚本/测试。旧 `official_eoh/` 在必要生成逻辑和许可抽取完毕、新包不依赖其导入后也可移出。

旧报告/卡片/实验结果退出新运行路径；不建立一个仍被新包读取的legacy记忆目录。保留历史分支索引与本方案即可。删除具体文件前仍需核对目标位于新分支工作目录；不能操作冻结旧分支的独立checkout。

## 7. 首轮规模与验收语义

no-API smoke使用固定fixture响应和真实评测器，覆盖生成→评测→实际反馈→修订/下一代→skill落盘→重载→停止。含合法fixture的场景证明保存/重载接线，全失败场景证明错误反馈和终态；两者均不证明真模型自主生成。四组测试验证错误分支，不为增加“结果好看”扩大实例数。

后续真实调用的小预算建议：CVRP规模20、3个固定实例、seed 20260908；3次候选尝试、3次模型请求、0次独立分析、0次网络重试。1次基线或显式父本重评 + 最多3次候选 + 1次导出重载 = 最多5次solver批调用。每批20秒、每请求90秒，总上限420秒，单次timeout受剩余总预算限制。

真实运行全无效也可证明自动反馈闭环跑通，终态必须为 `no_valid_candidate`，不能用原始基线替代。终态字段分离：`execution_mode=fixture|live`、`loop_completed`、`status`、`stop_reason`、`generated_valid_candidates`、`exported_skill_ids`。例如3次全无效且错误被后续prompt消费：`loop_completed=true/status=no_valid_candidate/stop_reason=candidate_limit/generated_valid_candidates=0`。认证失败则为 `loop_completed=false/status=provider_failed`，即使此前有合法候选也保留这一故障终态及已保存产物。

`stop_reason`分别记录candidate_limit、request_limit、wall_time_limit或provider_error；`status`表示候选结果或服务故障，不互相覆盖。墙钟过早到期而尚未发生反馈后的再次生成，只证明预算停止有效，不能宣称多轮真实反馈验收完成。不以“无改善”提前停止，也不因全失败追加候选预算。固定seed不保证在线模型逐token重现。

## 8. 实施后的验收命令（当前尚不存在）

以下名称是实施合同。先使用Python 3.11创建并激活独立虚拟环境，安装新包及其dev依赖，再执行：

```powershell
python -c "import sys; assert sys.version_info[:2] == (3, 11); import agent_skill_loop"
python -m pytest tests/kernel -q
```

CI继续使用 `actions/setup-python` 的 `python-version: '3.11'`，安装精简后的新包，执行上面两个命令。CI触发范围需覆盖新分支的push/PR，不能照搬仅对旧main触发的配置而漏掉新内核。四组保护和no-API smoke均纳入 `tests/kernel`，不需要API密钥。

建议CLI合同：

```powershell
# 仅准备新配置/套件，无API
python -m agent_skill_loop prepare --problem cvrp_construct --output outputs/agent_skill/prepare

# no-API smoke独立人工入口；与pytest共享同一实现，通过后不重复跑
python -m agent_skill_loop smoke --problem cvrp_construct --output outputs/agent_skill/smoke

# Fixture通过且用户授权之后，指定一个已配置的真实模型
python -m agent_skill_loop run --problem cvrp_construct --model MODEL_NAME --output outputs/agent_skill/live

# 只接受用户指定的一个父skill；自动在本次套件上重评
python -m agent_skill_loop run --problem cvrp_construct --model MODEL_NAME --parent-skill PATH_TO_ONE_SKILL --output outputs/agent_skill/child
```

固定3实例和3候选等默认值由新包配置提供，调用方不必提交配置文件，更不填写科研协议。运行输出包括实际配置快照、dev套件、新schema事件、实际请求prompt、候选源码、skills和summary，输出目录必须全新。未实现的CLI不能当成已有功能；测试和smoke未执行前不能宣称验收通过。

## 9. 后续科研边界

工程验收通过后，才研究“同预算下，本轮真实执行反馈是否比无反馈重复生成更有效”。首版的默认输入白名单持续有效；历史失败经验检索、多skill自动检索、提示进化、主动反例、工作流搜索和跨问题迁移均为后续独立变更，不会通过journal、parent元数据或验收规则隐式接回。
