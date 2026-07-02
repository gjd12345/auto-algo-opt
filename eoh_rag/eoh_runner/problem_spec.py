"""
模块：problem_spec
功能：定义一个基准优化问题（及其评测边界）的规格描述，供 C+L+V 评测框架统一识别与调度。
职责：以数据类形式集中管理某个问题的元信息——问题名、实现语言、源码文件清单、主程序（可执行入口）、优化目标方向（最小化/最大化）、评测函数、基准数据集与默认指标口径。
接口：
    - ProblemSpec：不可变数据类，描述一个待优化问题（如 online bin packing、TSP、CVRP、InsertShips）。
    - ProblemSpec.resolve_source_files(root)：把相对源码路径解析为基于给定根目录的绝对路径列表。
    - Evaluator：评测函数类型别名，接受任意参数并返回指标字典。
输入：问题的静态描述字段；resolve_source_files 依赖一个根目录（字符串或 Path）。
输出：一个可传递给评测框架的 ProblemSpec 实例；resolve_source_files 输出解析后的绝对路径列表。
示例：
    spec = ProblemSpec(
        name="online_bin_packing", language="python",
        source_files=["solver.py"], main_binary="run.py",
        objective_direction="min",
    )
    paths = spec.resolve_source_files("/path/to/repo")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


# 评测函数类型别名：接受任意入参，返回“指标名 -> 指标值”的字典（如 {"cost": 123.4}）。
Evaluator = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ProblemSpec:
    """
    描述一个基准优化问题及其评测边界，供 C+L+V 评测框架统一识别与调度。

    该数据类为不可变（frozen），一旦创建字段不可修改，可安全地在框架各处传递与缓存。
    适用于本框架支持的各类问题，例如 online bin packing、TSP、CVRP、InsertShips 等。

    字段说明：
        name: 问题名称（唯一标识，用于查找/日志）。
        language: 问题实现所用语言（如 "python"、"cpp"）。
        source_files: 相对源码文件路径列表（相对于问题根目录）。
        main_binary: 主程序/可执行入口（评测时实际运行的目标）。
        objective_direction: 优化目标方向，"min" 表示越小越好，"max" 表示越大越好。
        evaluator: 可选的评测函数；为 None 时表示由框架外部提供评测逻辑。
        benchmark_data: 基准数据集，每个元素为一条测试样例的描述字典。
        default_metrics: 默认指标口径，primary 为主指标、secondary 为次指标。
    """

    name: str
    language: str
    source_files: list[str]
    main_binary: str
    objective_direction: str
    evaluator: Evaluator | None = None
    benchmark_data: list[dict[str, Any]] = field(default_factory=list)
    # 默认以 cost 为主指标、valid_rate（有效率）为次指标；用工厂函数避免可变默认值被共享。
    default_metrics: dict[str, str] = field(default_factory=lambda: {"primary": "cost", "secondary": "valid_rate"})

    def resolve_source_files(self, root: str | Path) -> list[Path]:
        """
        将相对的源码文件路径解析为基于给定根目录的绝对路径列表。

        参数 root：问题根目录（字符串或 Path），会被规范化为绝对路径。
        返回：与 source_files 一一对应的绝对路径列表（每项均已 resolve 规范化）。
        """
        # 先把根目录规范化为绝对路径，作为拼接各相对源码路径的基准。
        root_path = Path(root).resolve()
        # 逐个拼接并规范化，得到每个源码文件的最终绝对路径。
        return [(root_path / path).resolve() for path in self.source_files]

