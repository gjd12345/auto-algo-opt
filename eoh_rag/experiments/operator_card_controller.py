"""
模块：operator_card_controller（轨迹条件化算子卡控制器的公开入口）
功能：把 eoh_rag.tocc.controller 里的控制器 API 汇聚到一个稳定的导入路径上，供实验脚本与文档引用直接使用。
职责：只负责统一转发底层控制器的公开对象（诊断结果类与诊断函数），自身不实现业务逻辑，也不持有任何数据。
接口：
    - TOCCDecision：诊断结果的数据类，承载对一次演化运行的判断结论与推荐的算子卡集合查询。
    - diagnose(trace: dict[str, Any]) -> TOCCDecision：读入运行轨迹字典，产出诊断结论。
输入：来自 eoh_rag.tocc.controller 的公开对象；调用方通常传入解析自 official_eoh_run_summary.json 的轨迹字典。
输出：可直接使用的 TOCCDecision 与 diagnose，以及底层模块通过 * 导出的其余公开成员。
说明：该控制器只做基于轨迹的诊断与算子卡推荐，不调用大模型，也不写入任何文件。
"""
# 星号导入：把底层控制器模块的全部公开成员透出到本模块命名空间，形成稳定入口。
from eoh_rag.tocc.controller import *  # noqa: F401,F403
# 显式再导出两个最常用的名字，保证 TOCCDecision 与 diagnose 始终可从本路径导入。
from eoh_rag.tocc.controller import TOCCDecision, diagnose  # noqa: F401
