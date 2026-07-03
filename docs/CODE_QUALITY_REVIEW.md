# 代码质量审查报告与修复记录

> 审查日期：2026-07-03
> 审查范围：`eoh_rag/`、`scripts/`、`docs/` 中与本轮质检报告相关的 Python/Markdown 文件
> 审查视角：代码质量、Windows/WSL 可移植性、并发写入、错误处理、数据持久化
> 当前结论：原报告发现的问题方向基本正确，但严重度分级偏重、部分行号已漂移、少量表述不够精确。本轮已按真实代码状态完成修正和代码修复。

## 总体判断

代码库没有发现 `shell=True`、`pickle`、直接密钥落盘等高危安全问题。主要风险集中在三类：

| 风险类别 | 原报告判断 | 复核结论 | 本轮状态 |
|---|---|---|---|
| Windows/WSL 编码与句柄 | 多处 `open/read_text/write_text` 缺少 UTF-8 或未关闭句柄 | 属实，但部分行号过期，`run_summarizer` 已有 encoding 但句柄未显式关闭 | 已修复 |
| 静默失败与可观测性 | 多处 `except Exception: pass` 或只 `print("[WARN]")` | 属实；副作用路径不应中断主流程，但应保留 traceback | 已修复为收窄异常或 `logger.exception` |
| 并发与持久化 | `failure_memory` 与 shared pool 存在并发覆盖/半行读取风险 | 属实；原报告建议合理 | 已增加跨平台锁与合并写入 |

风险评级从原报告的“存在 CRITICAL”调整为：**中风险，已完成本轮可执行修复，建议合并**。理由是这些问题主要影响稳定性、可观测性和 Windows/WSL 可移植性，不属于远程代码执行、密钥泄露或默认生产中断级别。

## 已修复问题

| ID | 文件 | 问题 | 修复 |
|---|---|---|---|
| F1 | `eoh_rag/tocc/gatekeeper.py` | CLI 入口使用裸 `open(args.proposal).read()` 和 `open(args.output, "w").write()` | 改为 `with open(..., encoding="utf-8")` 和 `json.load` |
| F2 | `eoh_rag/tocc/loop.py` | proposer stdout JSON 解析失败会直接抛异常；manifest/history 写入缺 encoding；dry-run 子进程不检查返回码；外部 JSON 使用 `[]` 取字段 | 增加 JSONDecodeError 记录、UTF-8 写入、dry-run returncode 检查、`.get()` 防护 |
| F3 | `eoh_rag/experiments/eoh_single_runner.py` | 官方 EOH 子运行脚本中 seed 注入 `read_text()` 缺 encoding，异常被吞 | 加 UTF-8，收窄异常类型并写 warning |
| F4 | `eoh_rag/experiments/training/extract_rerank_traces.py` | outcome/summary 读取异常过宽或缺少编码 | 加 logging、UTF-8、收窄异常范围 |
| F5 | `eoh_rag/experiments/reports/run_summarizer.py` | `Path(...).open()` 传给 `json.dump`，句柄生命周期不清晰；副作用异常只 print | 改为 `with open(..., encoding="utf-8")`，副作用异常改 `logger.exception` |
| F6 | `eoh_rag/experiments/hooks.py`、`batch_runner.py`、`rag/llm_reranker.py` | best-effort 副作用失败只 print 或缺 traceback | 保持不中断主流程，改为 logger 记录 traceback |
| F7 | `eoh_rag/operator/failure_memory.py` | 读取失败静默清空，写入缺少并发保护 | 读取失败记录 warning；读写加 `exclusive_lock`；保存时合并本进程增量，降低 last-writer-wins 覆盖风险 |
| F8 | `eoh_rag/experiments/pool_api.py`、`eoh_rag/utils/file_lock.py` | JSONL 读侧无锁；注释仍写 `fcntl`；Windows lock 错误缺上下文 | 读侧加锁；注释改为跨平台锁；Windows 锁失败抛带上下文的 RuntimeError |
| F9 | `eoh_rag/experiments/interpretability/replay_bp.py` | 硬编码字符串通过 `exec` 生成 score 函数 | 改为直接定义并返回 `score` 函数 |
| F10 | `eoh_rag/experiments/interpretability/behavior_plot.py`、`training/train_rerank_sft.py` | 报告未覆盖的 `write_text` 缺 encoding | 补 `encoding="utf-8"` |
| F11 | `docs/ISOLATION.md`、`docs/specs/POOL_API_SPEC.md` | 文档引用不存在的 `go_solver.py`，POOL API spec 仍写 `fcntl` | 修正文档漂移 |

## 对原报告的修正

| 原报告项 | 修正意见 |
|---|---|
| `tocc/gatekeeper.py:330/346` | 问题属实，但当前文件行号为 330/346 附近而非固定旧行号；报告应避免把过期行号当作证据。 |
| `run_summarizer.py:572/578` | 不是编码缺失，而是句柄未显式关闭；严重度应从 HIGH 降为 MEDIUM。 |
| `except Exception as e: print("[WARN]...")` | 对 card synthesis/outcome update 这类副作用路径，不应改成抛出；正确修法是 `logger.exception` 后继续主流程。 |
| `llm_reranker.py` 的 broad exception | LLM 调用边界允许保留 broad catch 作为回退保护，但必须记录 traceback 或失败上下文。 |
| `replay_bp.py exec` | 当前不是立即可利用漏洞，因为输入是硬编码；但删除 `exec` 可降低未来演进为 RCE sink 的风险。 |
| `所有 read_text/write_text 必须同一行含 encoding` | 这是质检 grep 规则的误判风险。多行调用只要参数中包含 `encoding="utf-8"` 即可。 |

## 剩余风险

| 风险 | 说明 | 建议 |
|---|---|---|
| broad exception 仍存在 | `llm/client.py`、官方 EOH 子脚本 API 调用等位置保留 broad catch 用于重试/回退 | 可接受；这些属于外部调用边界，已有错误上下文 |
| `failure_memory` 并发合并是增量保护，不是数据库级事务 | 多进程极端竞争下仍不如 SQLite/append-only log 强 | 若未来高并发写入频繁，建议迁移为 append-only JSONL 或 SQLite |
| 源码注释存在历史 mojibake | 本轮只修报告和相关代码，未批量重写所有文件头注释 | 可作为单独文档/编码清理任务处理 |

## 验证结果

已执行：

```powershell
python -m compileall -q eoh_rag scripts\opencode_go_env.py
python -m pytest tests/test_pool_api.py tests/test_hooks.py tests/test_smart_operator.py tests/test_tocc_v3_loop.py tests/test_summarize_manifest_runs.py tests/test_official_eoh_run.py -q
python -m pytest tests -q
```

结果：

```text
90 passed in 0.59s
347 passed, 1 skipped in 8.64s
```

辅助扫描：

```powershell
rg --pcre2 -n "open\([^\n]*\)\.read|open\([^\n]*\)\.write|read_text\(\)|write_text\((?![^\n]*encoding=)|except Exception:\s*pass|exec\(" eoh_rag docs scripts
rg -n "fcntl|adaptive_operators|shared_failures|go_solver\.py|BEST_CODE|exec\(" eoh_rag docs scripts
```

说明：第一条扫描仍会命中多行 `write_text(..., encoding="utf-8")` 的格式化误报；第二条仅剩 `eoh_rag/utils/file_lock.py` 中 Unix 分支对 `fcntl` 的真实平台适配引用。
