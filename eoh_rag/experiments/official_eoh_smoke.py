"""
模块：official_eoh_smoke（官方 EOH 冒烟测试入口）
功能：作为对外统一入口，把问题注册表的全部公开内容原样暴露出来，方便调用方一处导入即可拿到所有能力。
职责：不自行定义任何逻辑，只负责转发 eoh_rag.experiments.problem_registry 中定义的问题规格、结果解析器与冒烟运行流程。
接口：星号导入 problem_registry 的全部公开名字，主要包括：
    - OfficialProblemSpec：单个优化问题的规格数据类（名称、样例目录、指标、优化方向、目标函数名）。
    - PROBLEMS：受支持问题的字典（在线装箱、TSP、CVRP 等；本框架同样支持 InsertShips 问题）。
    - parse_* / PARSERS：各问题运行输出的文本解析器。
    - run_problem / run_smoke / main：对单个问题或全部问题跑一遍轻量端到端冒烟测试的入口。
输入：依赖同目录下的 problem_registry 模块；运行时进一步依赖各问题的样例目录与可执行的 Python 解释器（由 problem_registry 内部处理）。
输出：本模块本身不产出数据，仅把上述名字提供给调用方；实际的冒烟结果与 Markdown 报告由被转发的函数生成。
示例：
    from eoh_rag.experiments.official_eoh_smoke import PROBLEMS, run_smoke
    # 等价于直接从 problem_registry 导入，二者可互换使用。
"""
# 从问题注册表整体转发所有公开名字；noqa 用于关闭“通配导入/名字未使用”这类静态检查告警。
from eoh_rag.experiments.problem_registry import *  # noqa: F401,F403
