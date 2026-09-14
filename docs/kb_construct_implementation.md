# 知识库评审对照实施方案

对照 `Knowledge_base_construct.md` 两份评审（后端 bug/检索/测试 + 看板 P0–P3）。**不改**不可变发布管线、manifest detached hash、content_digest 去重、`current.path` 降级、run 容器只观察、validate 严格性。不上向量库，不合并 Session Memory。

## 已落地（本轮只复核，不重写）

| 项 | 证据 |
| --- | --- |
| Bug 1 CRLF `read_entry` | `sha256_file(body_path)`；`test_read_entry_crlf` |
| Bug 2 孤儿 md | `orphan Markdown body without metadata sidecar`；`test_orphan_md_flagged` |
| Bug 3 指针 backup | `installed` 标志，仅成功才 unlink；`test_atomic_pointer_fallback` |
| Bug 4 `_safe_rel` | 拒绝 `\\` 与盘符；`test_safe_rel_rejects_traversal` |
| Bug 5 YAML TypeError | except 含 `TypeError`；`test_yaml_typeerror_is_corrupt_not_crash` |
| Bug 6 attributes 检索 | `_SEARCH_FIELD_WEIGHTS["attributes"]=2`；`test_search_attributes_interface_hit` |
| 字段加权 / 2-opt 归一 / 丢单字符 / `total` | `search_release`；`test_search_2opt_normalization` 等 |
| CLI UTF-8 | `sys.stdout.reconfigure` |
| 拆 `dashboard.py` | core 只 `from .dashboard import dashboard_html` |
| 回滚文档 | `docs/knowledge_base.md` 回滚节 |
| 发布测试 | `tests/knowledge/test_release_mechanics.py` |
| 看板 P0–P3 主体 | 热力只给矩阵、卡片中性、`data-label`、待整理区块、矩阵高亮、搜索框、`#detail-`、关联、变更列表、overlay、其他 tab、JSON 按需渲染 |

## 本轮补齐

1. `FAMILY_INFO` + `taxonomy.json` 双语 aliases；search 读取 taxonomy aliases；词表 `构造`→construct。
2. 测试：`装箱` 命中 OBP 族；`构造` 命中含 construct 的条目。
3. 看板：`data-search` 含摘要；关闭详情后焦点回到触发卡片。
4. 重建发布包以刷新 `dashboard.html` 与 taxonomy。

## 执行顺序

Bug 已锁契约 → 补中文别名与测试 → 看板两点 → `validate`/`build`/`validate-release` + `tests/knowledge`。
