"""兼容官方 EoH 的 ``prob.py`` 约定，具体类定义使用唯一模块名。"""

from cvrp_expert_router_problem import CVRPEXPERTROUTER, compute_instance_features

__all__ = ["CVRPEXPERTROUTER", "compute_instance_features"]
