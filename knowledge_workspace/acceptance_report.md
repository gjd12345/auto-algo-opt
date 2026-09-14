# 知识库首版验收报告

验收日期：2026-09-14。所有场景均为离线文件/Git 检查，没有运行模型生成或 solver。生产 Session、Memory、EoH、评测器和已有 benchmark 未被知识库工具调用。

## 覆盖数字

| 维度 | 结果 | 解释 |
| --- | ---: | --- |
| main tracked 文件 | 866 / 866 | 固定 SHA d6433549dea055aa3a6ef460686198b3d1888234，与 Git tree 计数一致 |
| 已分类文件 | 814 / 866 | 93.9954%；52 个低置信条目保留在 pending_classification |
| 运行容器发现 | 310 | JSON/JSONL/YAML/CSV/TSV 候选逐项记录 |
| 解析为 run-like | 156 | 仅表示解析到运行字段，不表示证据有效 |
| 重复内容 | 29 | 以 canonical parsed digest 指向首次记录 |
| 缺失引用 | 20 | 清单指向未 tracked 的产物，保留 missing_references |
| 损坏/部分/不支持 | 0 / 0 / 0 | 当前 main 候选中没有这三类；解析器遇到时会保留明确状态 |
| 网络来源详读 | 9 | 每个首批问题族 3 个原始来源，含 URL、定位、许可和选用理由 |
| 首批正文 | 17 | 9 方法、4 问题/边界、1 框架、3 待整理 |
| 有 evidence_refs 的正文 | 17 / 17 | 代码 hash、运行索引或明确 gap 均以引用形式保留 |

盘点完整不等于深度阅读完整；方法卡只覆盖首批三族，历史实现与跨协议成绩仍按原 suite、指标、预算和代码 hash 留缺口。

## 场景检查

- 盘点命令从 Git object 读取固定提交，未 checkout main；逐文件记录原始 SHA256、格式、角色、分类和运行解析状态。
- 分类区分在线/离线 BP、问题形式、方法和优化框架；搜索控制/RAG/Memory/selector/router 在 framework 类，不当作问题启发式。
- validate 检查 JSON sidecar、必需章节、来源 ID/URL、代码路径和 hash；错误代码 hash、缺失正文或篡改正文会失败。
- build 在暂存目录完成白名单复制和 hash 校验，再重命名为 release；旧 release 不覆盖。发布包含 index、relations、manifest、detached manifest hash、看板和启动说明。
- search 与 read 固定到 release ID；read 会比对正文 hash。validate-release 会检查每个发布文件和 manifest.sha256。
- 看板使用 HTML 转义；发布白名单排除密钥、业务明细、未授权全文和临时文件。
- 当前 Windows 环境成功创建目录软链接。无权限环境会写 current.path 并要求使用显式 release 路径，不伪造普通文本目录链接。
- 启动示例解析后固定真实 release；即使 current 后续切换，补读仍使用原路径。

## 待补齐

knapsack、mixer split、insertships routing 只有分类页和路径/哈希事实；离线 BP 的独立 solver、历史“605 次运行”汇总的原始证据、部分 TSP/CVRP 外部确认和跨 suite 分数仍未验证。下一版应先补问题 contract 和原始运行证据，再扩充文献，不以文献数量或旧分数作为成功标准。
