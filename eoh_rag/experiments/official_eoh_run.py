"""
模块：official_eoh_run（官方 EoH 单次运行入口）
功能：作为命令行入口，触发一次官方 EoH 启发式进化实验。
职责：把实际逻辑全部委托给 eoh_single_runner，本文件只负责作为可执行入口被直接运行。
接口：main()——解析命令行参数、执行一次实验并打印结果 payload（由 eoh_single_runner 提供）。
输入：命令行参数（问题类型、实验分支 arm、种群规模、代数、RAG 参数、超时等）与相关 API 环境变量。
输出：一次 EoH 运行的结果摘要（JSON / Markdown）及中间产物，均由被委托模块写出。
示例：
    python -m eoh_rag.experiments.official_eoh_run \
        --problem bp_online --arm pure_eoh --pop-size 2 --generations 1
"""
# 通配导入 eoh_single_runner 的公开符号，使本入口在被其他脚本 import 时能透传其全部接口；
# noqa 抑制“未使用/星号导入”类静态检查告警。
from eoh_rag.experiments.eoh_single_runner import *  # noqa: F401,F403
# 单独显式导入 main，确保命令行入口一定能拿到主函数（不依赖星号导入的 __all__ 约定）。
from eoh_rag.experiments.eoh_single_runner import main

# 仅在本文件被直接执行（而非被 import）时才启动一次完整实验流程。
if __name__ == "__main__":
    main()
