# 离线优化知识库工作区

这是独立于生产 Session、Memory、EoH、评测器和 benchmark 的知识整理区。inventory.json 来自 main 的固定提交 d6433549dea055aa3a6ef460686198b3d1888234，记录 866 个 tracked 文件、原始内容 SHA256、角色、问题族和运行容器解析状态。

Markdown 是知识正文来源，entries/*.json 是简短元数据 sidecar。正文必须包含定义/步骤、适用条件/限制、来源结论、代码/评测关联、未确认项/冲突证据五个部分。索引、关系表和看板由 python -m knowledge_tools build 派生，不手工编辑发布目录。

当前发布是 `knowledge_store/releases/20260914-main-d6433549-kb-lit8`：方法优先看板，正文可在右侧阅读。对照 `kb-lit7`；文献填充前用 `kb-fix5`。

方法、实现和证据分卡；`run-index:inventory` 不算评测证据。全文深读只统计 `read_depth=full_text_local`。`knowledge_context.json`、验收笔记与 `literature_queue/` 留在工作区，不进入发布包。二级子问题目录在 `catalogs/`，EoH 适配签名在 `eoh_adapters/`，联网检索协议在 `literature_harvest_scheme.md`。
