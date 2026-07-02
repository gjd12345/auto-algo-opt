"""
模块：summarize_manifest_runs（清单运行结果汇总入口）
功能：作为对外统一入口，把 run_summarizer 里的公开接口暴露到本模块命名空间，方便按 `summarize_manifest_runs` 这个更贴近业务语义的名字来调用。
职责：不实现任何汇总逻辑，只负责重新导出；真正读取 run_index.json、逐个运行结果并生成中文 Markdown 报告的实现都在 run_summarizer 中。
接口：通过通配导入，把 run_summarizer 中所有公开的类与函数（如报告生成相关的入口函数）原样转发；调用方可直接 `from ...summarize_manifest_runs import <名称>`。
输入：依赖同目录的 run_summarizer 模块及其所需的实验清单文件（如 run_index.json、各运行目录下的汇总 JSON）。
输出：本模块自身不产出文件；被导出的接口在运行时生成中文 Markdown 实验报告（含每个优化问题的表格、代码片段、卡片决策与后续动作）。
示例：
    from eoh_rag.experiments.reports.summarize_manifest_runs import *
"""
# 通配导入 run_summarizer 的全部公开符号；noqa 抑制未用/星号导入的静态检查告警
from eoh_rag.experiments.reports.run_summarizer import *  # noqa: F401,F403
