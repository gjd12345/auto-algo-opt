"""模块：eoh_rag.eoh_runner（EOH 运行器支撑包）

功能：为「用大模型自动进化组合优化启发式」的运行流程，提供问题与目标的规格注册表。
职责：集中管理问题规格（problem_spec）、目标规格（target_spec）以及它们的注册表（registry），
    让运行器能够按名称查到「要优化哪个问题、评估函数是什么、达标目标是多少」。
    支持的组合优化问题包括在线装箱（online bin packing）、TSP、CVRP、InsertShips。
接口：本文件是包的初始化入口，本身不导出符号；具体规格与查询能力由包内子模块
    （如 registry / problem_spec / target_spec）提供。
输入：由包内子模块读取的问题定义与目标阈值。
输出：可被运行器查询的规格对象与注册表。

相关入口：
- RAG 上下文组装：``eoh_rag.experiments.rag_context_builder.build_official_rag_context``。
- 失败案例（failure_case）语料：由 ``eoh_rag.rag.failure_cases`` 提供（人工整理）。
"""
