# kb-lit7 前后端检查记录

检查日期：2026-09-14。目标：knowledge_store/releases/20260914-main-d6433549-kb-lit7，current 也指向该版本。仅审查并添加复现记录；没有修改知识正文、构建代码或发布入口。

## 验证结果

- manifest SHA256：a876a59f4e94581f4c84f88a4968e853a74b9be0d833118a9c0e374e7e343eb4。
- validate-release、validate_workspace 均通过；发布包含 297 条条目（126 问题、140 方法、30 实现、1 框架），104 条来源，全部标注 read_depth=abstract。
- python -m pytest tests/knowledge -q：38 passed in 0.47s。在沙箱外获批运行；沙箱内 pytest 因无法导入 pygments 未完成。
- Edge 无窗口实际渲染检查：1440×1000 主页面及 #detail-method-lit-tsp-colored-colored-traveling-salesman 深链接正常显示，没有观察到中文乱码。截图 overview.png、detail.png。
- 当前生成器与发布 HTML 的差异仅为 FAMILY_LABELS 对象键顺序；忽略该顺序后全文相同。
- 当前条目关系中的 problems/methods/implementations 均能找到目标条目。
- 未进行线上论文全文复核，也未运行模型或 solver；文献问题依据本地来源元数据、采集队列与正文之间的直接矛盾判断。

## P1：错误 DOI 种子已形成错误方法正文

knowledge_tools/doi_seeds.py:68、91、155 把 DOI 分别绑定到 Colored TSP、Khuller gas-station、Site-dependent VRP，但发布来源题名实际是 Robust equilibria in location games、Optimizing a Computational Method for Length Lower Bounds for Reflecting Sequences、Validation of a model to support the decision to transfer management control systems。

对应方法条目：method-lit-tsp-colored-colored-traveling-salesman、method-lit-tsp-fuel-khuller-gas-station-refueling、method-lit-cvrp-site-site-dependent-vrp。正文出现 “Apply Colored traveling salesman as introduced in Robust equilibria in location games (2015)” 等不受该来源支持的断言。它们仍标为 reviewed，在前端显示“已整理”。

建议：核对种子的题名/作者/DOI，撤回或降级受影响条目，允许不能分类；不能用 DOI 存在代替算法来源匹配。保留旧 release，修订工作区后发布新版本。

## P1：导入强制标记已读摘要，未核实摘要存在

knowledge_tools/literature.py:1081 查询匹配 work 后，1100–1101 无条件写 locator=OpenAlex abstract、read_depth=abstract；来源可能来自 Crossref，且代码未验证 work.abstract。当前队列按 DOI 汇总后，有 18 条 src-lit 来源没有可用摘要却被发布为 abstract。这里的 18 是当前本地可核查性缺口，不推断其他未登记阅读途径。

建议：核验所选 DOI 属于对应候选集，要求非空摘要和真实 provider/定位/摘要 hash；没有摘要时拒绝摘要方法提炼或标记 metadata_only，保留缺口。

## P1：证据与关系校验可被字符串绕过

knowledge_tools/core.py:800、933、973 仅对 evidence_refs 做形状和通用 run-index 排除；没有解析 evaluation 引用并检查报告、suite、metric、budget。relations 的对象存在性也未校验。

复现：通过 mock 在内存中把一个条目设为 validated，evidence_refs 改为 evaluation:missing-report-without-suite-metric-budget，relations.problems 改为 problem-does-not-exist；validate_workspace 仍返回 ok=true。没有修改真实条目。因此界面“评测”计数也可能只反映前缀字符串。

建议：引入可定位证据记录及必需协议字段；validated 必须依赖可核对证据，gap 不应被当作验证证据；校验关系目标。

## P2：前端详情缺少正文、来源链接和适配信息

knowledge_tools/dashboard.py:200、645–697 只输出摘要、基本字段及引用字符串；没有正文步骤、适用边界、eoh_map/not_the_original/read_depth，也没有可点击的正文及 DOI 链接。底部 CLI 示例还缺少必需的 --release。

Edge 详情截图证实：错误 Colored TSP 卡被显示为“已整理”，用户无法在面板内阅读完整方法或看到摘要深度；必须自行寻找文件或命令行。

建议：展示经过转义的正文/可点击固定版本正文、DOI、阅读深度、EoH 适配状态和限制；提供含 --release 的可复制命令。

## P2：前后端关键词检索语义不一致

knowledge_tools/dashboard.py:256、612 使用有限字段和整段 substring；core.search_release 使用分词、别名及加权字段。用发布数据和前端同一 data-search 生成逻辑复现：TSP 2-opt 前端 1 条，后端 total=82。后端结果数不等于全部相关；这里用于说明查询语义不同。前端也无法搜索正文中的关键约束。

建议：统一分词、2-opt 归一化和中文别名规则，明确匹配范围；前端至少匹配逐词查询。

## P2：版本差异漏报元数据；构建去重遗漏输入

core.py:1228 的 diff 仅比较 content_sha256，修改 status/source_refs/relations 而不改正文会显示零变化（复现 metadata_only_diff=0）。lit6 到 lit7 实际修改 dashboard、index、README、relations、taxonomy、version_diff，但看板变更列表为零。

core.py:1331 的 content_digest 未覆盖完整 inventory/classification、README 和构建器/前端版本；只修分类清单或前端时可能触发 identical content already published，无法正常发布修订。

建议：条目 diff 同时比较 metadata_sha256；另列来源、分类、协议和界面变化。构建指纹覆盖所有发布输入和工具版本。

## 次要显示问题与测试边界

左栏“全部问题族 297”表示所有条目，单个问题族旁的数字却是 method_count，口径不一致。Insertships 显示 0，但矩阵中有问题和实现条目。建议标明“方法 0”或统一为条目总数。

已检查桌面渲染及详情深链接；未把截图检查等同于完整交互/移动端/键盘无障碍验收。38 项现有测试通过不代表上述证据语义已经验证。

离线复现：python -m reports.kb_lit7_review.reproduce。
