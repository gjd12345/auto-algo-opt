# v0 看板复审

日期：2026-09-14。目标为 knowledge_store/releases/20260914-main-d6433549-kb-v0。current 实际指向该目录；本次没有修改代码、知识条目或发布入口。

## 通过项

- 发布哈希校验通过，manifest SHA256 为 bdfc8037c1880431d59586260b939609e6759350068a7a889962ef14cde0a634。
- 当前 dashboard.py 以 v0 输入重新生成 HTML，与 v0/dashboard.html 全文一致。
- 工作区校验通过，知识库专项测试 43 passed in 0.43s。
- Edge 实际测试桌面 1440×1000、手机 390×844：基本布局、筛选、正文、代码块、文献页、覆盖页、手机打开关闭正常，无浏览器异常。截图和 browser-results.json 保存在本目录。
- 来源阅读深度已改为 86 条 abstract、18 条 metadata_only；此前三条明显错配方法标为 unverified/unread，工作区校验会给出提示。不能再沿用“全部104条来源均标摘要”的旧结论。
- 证据与 relations 校验已有增强；本次不重复把已修复的旧行为列为新缺陷。

## P1：Plan 启动示例没有固定真实 release

位置：knowledge_store/releases/20260914-main-d6433549-kb-v0/plan_startup.md:12（工作区同名文件）。

实际执行 (Resolve-Path knowledge_store/current).Path 得到 C:\Windows\System32\auto-algo-opt\knowledge_store\current；Python Path.resolve() 才得到 releases/20260914-main-d6433549-kb-v0。示例随后保存 $release 并用于后续读取，因此 current 一旦切换仍会跟随新版本，与文档声称的固定路径不一致。当前已存在的 knowledge_context.json 显式指向 v0，不受此示例缺陷影响。

建议：解析符号链接真实目标，确认目录名与 manifest.release_id 一致，再保存路径和 manifest hash；用 current 切换后的读取测试锁定行为。

## P2：筛选结果与阅读对象可能互相矛盾

位置：knowledge_tools/dashboard.py:375–388、397–398。

复现：打开 TSP 方法，然后切换 CVRP。列表变为 CVRP，右栏仍是 TSP，selectedVisible=false。再经关联打开其他类型条目时，同样不会更新或明确提示筛选与正文的关系。本次进一步复现 kindFilter=method、familyFilter=cvrp，但 readerKind=implementation、readerFamily=tsp。

建议：筛选排除当前阅读对象后清空或选中首个匹配项；关联跳转需显式说明“正在阅读筛选外条目”，或同步筛选并显示选中对象。

## P2：手机无法选择具体问题形式

位置：knowledge_tools/dashboard.py:304–305、437。

在 390px 宽度，.tree 被隐藏；替代控件只有 familyFilter，没有具体问题形式控件。浏览器记录 treeVisible=false、problemSelectorsOutsideTree=0。桌面左栏可选的子问题在手机无法按同样方式定位。

建议：提供可展开分类抽屉，或增加“问题形式”下拉及清除子问题筛选入口。

## P2：手机长正文的返回按钮不固定

位置：knowledge_tools/dashboard.py:291–292、305、373。

打开长正文并滚到底部后，closeTop=-1410.125，closeVisible=false。手机用户必须滚回顶部才能返回；Escape 仅适用于有键盘设备。此前短正文“打开/关闭”测试未覆盖这个场景。

建议：将返回操作置于 sticky 阅读工具栏，或提供固定底部返回按钮；对长正文滚动后关闭增加浏览器断言。

## P2：版本变更基准已不存在

位置：knowledge_store/releases/20260914-main-d6433549-kb-v0/version_diff.json:2。

v0 仍把 kb-ui9 记录为 previous_release_id，但本地 releases 仅剩 v0。变更页显示从 ui9 到 v0，用户无法重载该基准版本。建议将 v0 定义为新基线并在下一修订中明确显示，或恢复归档版本用于比较；不直接改写不可变发布包。

## 内容与语言仍需后续整理

297 条中 140 条方法；英文原文依然占主体，15 个代表方法仅做了显示名称翻译。另有 72 篇正文包含 “Apply ... as introduced in ...” 模板，计数仅用于定位潜在浅层整理，不等于72项算法结论已被判错。需按条核对步骤是否足够具体；前端排版无法替代内容提炼。

## 复现

node reports/kb_v0_review/browser-check.cjs

浏览器异常/基础通过项见 browser-results.json；新增缺陷的数值复现见 review-probes.json。此次保持 v0 固定，仅新增复审记录。
