"""
模块：summarize_rag_ablation（RAG 消融实验报告入口）
功能：面向 RAG 消融实验（对比“纯基线运行”与“接入 RAG 的运行”）的汇总报告入口，
      把底层汇总能力以本模块名称对外暴露，方便按“RAG 消融”这一语义直接调用。
职责：
    - 作为 RAG 消融报告的统一入口名，转发底层汇总模块 run_summarizer 的全部公开接口；
    - 底层逻辑会按问题（online bin packing / TSP / CVRP / InsertShips 等）整理每次运行结果，
      并计算相对纯 EOH 基线（pure baseline）的“单位提升率”（per-unit improvement rate）。
接口（均来自 run_summarizer，通过本模块转发）：
    - summarize(input_dir, no_card_memory=False) -> dict：核心汇总逻辑，返回结构化结果字典。
    - main() -> None：命令行入口，解析参数并写出报告文件。
输入：
    - 依赖 run_summarizer 模块所需的输入，主要是实验套件输出目录（内含 run_index.json）
      及各次运行目录下的 official_eoh_run_summary.json。
输出：
    - 由底层接口产出的 Markdown 报告、汇总 JSON 与成功率漏斗 JSON。
示例：
    from eoh_rag.experiments.reports.summarize_rag_ablation import summarize
    result = summarize("/path/to/suite_output")
"""
# 转发 run_summarizer 的全部公开名称（如 summarize、main 等），
# 使调用方可通过本模块名按“RAG 消融报告”语义直接使用同一套汇总能力。
# noqa 注释用于抑制“通配符导入 / 名称未使用”这两类静态检查告警。
from eoh_rag.experiments.reports.run_summarizer import *  # noqa: F401,F403
