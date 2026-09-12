# agent_skill_loop
本包提供问题合同、隔离评测、模型 HTTP 传输、journal、不可变 skill 存取和显式历史代码导入。生产 run 共用 eoh_frozen 的官方引擎监督实现。

当前操作及边界以 [审计验收报告](../reports/audit_20260912/acceptance.md) 与代码合同为准。旧 AgentLoop、policy、generator、report 和相关循环数据结构不属于当前运行时；生产不提供旧循环兼容入口。prepare 生成官方搜索身份的套件配置，smoke 使用真正的官方 EoH 和 localhost 模型 fixture，需要安装 [eoh] extra。

```powershell
py -3.11 -m agent_skill_loop import-skill --problem cvrp_construct --file PATH_TO_CODE --license "SOURCE_LICENSE" --output outputs/imported
py -3.11 -m agent_skill_loop evaluate-skill --skill outputs/imported/exported_skill --suite outputs/imported/dev_suite.json
```

import-skill 保存来源、代码身份和当前重评证据；无效代码不进入可复用 skill 集合。新导出引用使用 algorithm-skill-ref/v2；v1 原始引用仍可读，其已声明字段必须匹配目标资产，缺少问题/接口字段时使用目标资产身份并在使用前重新校验和评测。
