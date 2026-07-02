"""
模块：清单驱动的批量实验入口（manifest_runner）
功能：作为一个薄入口，读取实验清单（manifest）并驱动整批 EOH 实验运行，
      具体的解析、展开、执行逻辑全部复用 batch_runner。
职责：
    - 把 batch_runner 中的公开名字（含各类 shared_pool_* 便捷函数、内部辅助函数等）
      重新导出，使本模块拥有与 batch_runner 一致的可调用接口；
    - 作为脚本被直接执行时，调用 main() 启动整个批量流程。
接口：
    - main() -> None：命令行入口，来自 batch_runner，解析参数并驱动批量运行。
输入：
    - 与 batch_runner 相同的命令行参数与环境变量（例如 --manifest 指定的实验清单 JSON、
      EOH_OFFICIAL_PYTHON / EOH_OFFICIAL_ROOT 环境变量、可选的共享池目录等）。
输出：
    - 与 batch_runner 相同：每个实验的输出子目录，以及汇总运行索引 run_index.json。
示例：
    python -m eoh_rag.experiments.manifest_runner --manifest my_manifest.json --dry-run
"""

# 从 batch_runner 批量导入其全部公开名字，使本入口共享同一套函数/常量接口。
from eoh_rag.experiments.batch_runner import *  # noqa: F401,F403

# 显式导入命令行主入口 main，供下方 __main__ 直接调用。
from eoh_rag.experiments.batch_runner import main

if __name__ == "__main__":
    # 作为脚本直接运行时启动整个批量实验流程（参数解析等均在 main 内部完成）。
    main()
