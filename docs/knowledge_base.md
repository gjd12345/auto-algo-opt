# 离线优化知识库

知识库是一个独立的、版本化的离线资产。它不导入 Session、Memory、EoH、评测器或 benchmark，也不执行模型、solver 或下载代码。Markdown 正文和 JSON sidecar 位于 knowledge_workspace；索引、关系表、看板和 manifest 由构建工具派生到 knowledge_store/releases。

两层已经合在当前发布包里：

- **工具层**继承 `Knowledge_base_construct.md`（ses_f616）的方案：不可变发布、CRLF 安全的 `read`、字段加权检索与族别名、`dashboard.py` v2（搜索框/深链/关联/待整理）、发布机制测试、回滚指针。不上向量库，不与 Session Memory 合并。
- **内容层**是 main 上按代码整理的条目，加上 120 个文献二级子问题及方法卡（Plan 只读 `## EoH 适配` 进 `operations.mechanism`）。

展示看板与内容基线为 `knowledge_store/releases/20260914-main-d6433549-kb-v0`（`current` 指向它）。过时中间包已清理；新发布应在 v0 之上递增。

## 构建流程

在仓库根目录运行：

~~~powershell
python -m knowledge_tools inventory --repo . --ref d6433549dea055aa3a6ef460686198b3d1888234 --out knowledge_workspace
python -m knowledge_tools validate --workspace knowledge_workspace
python -m knowledge_tools build --workspace knowledge_workspace --store knowledge_store --release-id 20260914-main-d6433549-kb-lit6
python -m knowledge_tools validate-release --release knowledge_store/current
~~~

inventory 使用 Git object 读取固定 ref，记录全部 tracked 文件、原始 SHA256、角色、问题族、分类置信度以及 JSON/JSONL/YAML/CSV 运行容器的解析/重复/缺失状态。它不 checkout ref。validate 校验正文必需章节、sidecar hash、来源 URL、代码路径和代码 hash。build 只复制白名单文件，在暂存目录校验后生成不可变 release，并更新 current 目录软链接；无 Windows 软链接权限时使用 current.path，不能将普通文本伪装成目录链接。

## 使用

搜索和读取都接受具体 release 路径，也可以接受包含 current 的 store：

~~~powershell
python -m knowledge_tools search --release knowledge_store/current --query "CVRP granular tabu" --limit 3
python -m knowledge_tools read --release knowledge_store/current --id method-cvrp-granular-tabu
~~~

Plan 启动固定版本、记录 manifest hash，再按需最多读取三条方法正文的示例见 knowledge_workspace/plan_startup.md。来源登记、查询记录和许可边界见 knowledge_workspace/sources.json、sources.md 和 literature_collection.md。组合优化文献的联网检索协议（OpenAlex 脚本 + grok-4.5 筛读 + EoH 适配骨架）见 knowledge_workspace/literature_harvest_scheme.md。验收记录是宿主操作笔记，不进入发布包。`knowledge_tools` 不打进生产 wheel。

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

无软链接权限时把 `releases/<旧id>` 写进 `current.path`：

~~~powershell
Set-Content -Path knowledge_store/current.path -Value "releases/<旧id>"
~~~

改完用 `python -m knowledge_tools validate-release --release knowledge_store/current` 验证。
