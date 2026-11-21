# 离线优化知识库

知识库是一个独立的、版本化的离线资产。它不导入 Session、Memory、EoH、评测器或 benchmark，也不执行模型、solver 或下载代码。Markdown 正文和 JSON sidecar 位于 `knowledge_workspace`；索引、关系表、看板和 manifest 由构建工具派生到 `knowledge_store/releases`。

两层已经合在当前发布包里：

- **工具层**继承 `Knowledge_base_construct.md`（ses_f616）的方案：不可变发布、LF 哈希稳定、字段加权检索与中英文别名、精确 ID 读取、按族/类型/接口过滤、`dashboard.py` v2、发布机制测试与回滚指针。不上向量库，不与 Session Memory 合并。
- **内容层**包括 `main@d6433549` 上按源码整理的条目、120 个文献二级子问题及方法卡（Plan 只读 `## EoH 适配` 进 `operations.mechanism`），以及带来源与实验条件的中期 CVRP 研究条目（`evidence-cvrp-depot-start-phase-h003`、`method-cvrp-s2-r5-spiral`）。

历史基线发布为 `knowledge_store/releases/20260914-main-d6433549-kb-v0`（保持只读不变，每个文件保留原始哈希）；在其之上递增发布 `knowledge_store/releases/20261121-main-audit-kb-v1`（`current` 指向它）。关于问题定义、已注册 Benchmark 与实验数据套件三种入口的区分，见 [基准与问题目录说明](benchmarks_and_problems.md)。

## 工作区字节口径（LF 固定）

`knowledge_workspace/entries/*.md` 与 `entries/*.json` 已在 `.gitattributes` 中显式声明 `text eol=lf`，避免 Windows 默认检出将工作区正文转换为 CRLF 后触发 `content_sha256` 校验失败；同时 `knowledge_store/releases/**` 保留 `-text`，确保已发布的不可变 release（如 `20260914-main-d6433549-kb-v0`）内每个文件的原始字节与哈希不被改动。

## 构建与校验流程

在仓库根目录运行：

~~~powershell
python -m knowledge_tools validate --workspace knowledge_workspace
python -m knowledge_tools build --workspace knowledge_workspace --store knowledge_store --release-id 20261121-main-audit-kb-v1
python -m knowledge_tools validate-release --release knowledge_store/releases/20260914-main-d6433549-kb-v0
python -m knowledge_tools validate-release --release knowledge_store/current
~~~

`inventory` 使用 Git object 读取固定 ref（基线 `d6433549dea055aa3a6ef460686198b3d1888234`），记录全部 tracked 文件、原始 SHA256、角色、问题族、分类置信度以及运行容器解析状态，不 checkout ref。`validate` 校验正文必需章节、sidecar hash、来源 URL、代码路径和代码 hash。`build` 只复制白名单文件，在暂存目录校验后生成不可变 release 并更新 `current` 指针。

## 使用：精确读取、过滤检索与别名

搜索和读取都接受具体 release 路径，也可以接受包含 `current` 的 store：

~~~powershell
# 精确读取文献方法卡（注意真实 ID 为 method-lit-cvrp-local-granular-tabu-search）
python -m knowledge_tools search --release knowledge_store/current --query "CVRP granular tabu" --limit 3
python -m knowledge_tools read --release knowledge_store/current --id method-lit-cvrp-local-granular-tabu-search

# 中文别名与完整版优先命中（Clarke–Wright 并行合并优先命中完整版而非逐点 savings）
python -m knowledge_tools search --release knowledge_store/current --query "Clarke–Wright 并行合并" --limit 3

# 支持按问题族、条目类型、接口与 EoH 适配状态过滤
python -m knowledge_tools search --release knowledge_store/current --query "节约量" --family cvrp --type method --interface select_next_node --limit 5

# 精确读取 CVRP 中期研究条目（H-003 与 R5）
python -m knowledge_tools read --release knowledge_store/current --id evidence-cvrp-depot-start-phase-h003
python -m knowledge_tools read --release knowledge_store/current --id method-cvrp-s2-r5-spiral
~~~

检索语义规则：
1. **无歧义 ID 走精确匹配**：查询字符串若匹配已有条目 ID 则直接精确返回；若符合标准条目 ID 前缀格式（如 `method-nonexistent-xyz`、`evidence-unknown-001`）但不存在，则明确返回 0 条结果而非返回模糊噪音。
2. **上下文弱命中保护**：当查询同时包含问题族上下文（如 `CVRP`）与具体方法词时，若没有任何方法词命中，返回空结果并附带 `weak_match_only: true` 提示，不以仅匹配问题族的条目充数。

## 历史 CVRP 实现源码定位（固定提交）

`knowledge_workspace/entries/impl-cvrp-*.json` 中的 7 条历史实现均按固定提交 `d6433549dea055aa3a6ef460686198b3d1888234` 的 Git 对象路径与原始字节 SHA-256 定位，可随时离线只读核验（`git show d6433549dea055aa3a6ef460686198b3d1888234:<path>`）：

| 条目 ID | 固定提交内路径 | SHA-256（前 12 位） |
|---|---|---|
| `impl-cvrp-expert-router` | `official_eoh/examples/cvrp_expert_router/cvrp_expert_router_problem.py` | `739ca01d69a1` |
| `impl-cvrp-final-batch-best` | `evidence/final_batch_20260630/best_codes/cvrp_construct_best.py` | `5cc54410a993` |
| `impl-cvrp-official-broad` | `official_eoh/examples/cvrp_construct/prob_broad.py` | `96641e4c9676` |
| `impl-cvrp-official-construct` | `official_eoh/examples/cvrp_construct/prob.py` | `aa8954d02d05` |
| `impl-cvrp-outcome-best` | `eoh_rag_workspace/reports/outcomes/cvrp_construct/best_code.py` | `314bc10c14ee` |
| `impl-cvrp-xfer-local` | `reports/strategy_experiments/cross_problem_transfer/best_codes/cvrp_construct_local_only_best.py` | `4cf318851137` |
| `impl-cvrp-xfer-mixed` | `reports/strategy_experiments/cross_problem_transfer/best_codes/cvrp_construct_mixed_abstract_best.py` | `e0330100c438` |

Plan 启动固定版本、记录 manifest hash，再按需最多读取三条方法正文的示例见 `knowledge_workspace/plan_startup.md`。来源登记、查询记录和许可边界见 `knowledge_workspace/sources.json`、`sources.md` 和 `literature_collection.md`。组合优化文献的联网检索协议见 `knowledge_workspace/literature_harvest_scheme.md`。验收记录是宿主操作笔记，不进入发布包。`knowledge_tools` 不打进生产 wheel。

文献检索相关命令（不导入 Session / EoH / 评测器）：

~~~powershell
python -m knowledge_tools literature-catalog --out knowledge_workspace/catalogs
python -m knowledge_tools literature-adapters --out knowledge_workspace/eoh_adapters
python -m knowledge_tools literature-harvest --catalog knowledge_workspace/catalogs/subproblems.json --out knowledge_workspace/literature_queue --family tsp --limit-subproblems 5
python -m knowledge_tools literature-pack-screen --queue knowledge_workspace/literature_queue/tsp/tsp_euclidean.json --prompt-out knowledge_workspace/literature_queue/tsp/tsp_euclidean.screen.md
python -m knowledge_tools literature-ingest --queue ... --screen ... --drafts knowledge_workspace/literature_drafts/tsp_euclidean
~~~

## 回滚

release 不可变，回滚就是把 `current` 重新指向旧 release；`version_diff.json` 的 `previous_release_id` 记录上一个版本。两种模式的 PowerShell 一行式：

有软链接权限时重建 `current` 目录链接：

~~~powershell
Remove-Item knowledge_store/current -Force; New-Item -ItemType SymbolicLink -Path knowledge_store/current -Target knowledge_store/releases/<旧id>
~~~

无软链接权限（或 `core.symlinks=false` 文本链接模式）时回退指针：

~~~powershell
Set-Content -Path knowledge_store/current.path -Value "releases/<旧id>"
~~~

改完用 `python -m knowledge_tools validate-release --release knowledge_store/current` 验证。
