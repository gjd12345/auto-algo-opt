"""
模块：target_spec
功能：定义可被 EOH 演化框架优化的“目标函数”规格，把一个待改进的启发式函数所需的全部元信息集中描述清楚。
职责：以不可变数据结构承载目标函数的名称、签名、输入输出、提示词约束、抽取/替换正则、种子实现路径、检索上下文与安全校验规则。
接口：TargetSpec 冻结数据类（frozen dataclass），仅存放字段、不含方法。
输入：由上层配置在构造时逐字段传入。
输出：一个可传递给演化流程、供生成与替换代码时读取的规格对象。
示例：
    spec = TargetSpec(
        name="online_bin_packing",
        function_name="Score",
        signature="func Score(item float64, bins []float64) []float64",
        inputs=["item", "bins"],
        outputs=["scores"],
        prompt_constraints="只允许修改打分逻辑",
        extract_regex=r"func Score\\(.*?\\}",
        replace_regex_template=r"func Score\\(.*?\\}",
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TargetSpec:
    """一个可被 EOH 框架演化改进的目标函数规格。

    该数据类冻结（frozen）后不可修改，用于集中描述某个待优化启发式函数
    （例如在线装箱、TSP、CVRP、InsertShips 等问题中的核心函数）所需的所有信息，
    包括如何从源码中定位它、如何替换它、生成新实现时要遵守哪些约束等。

    关键字段：
        name: 该目标的人类可读标识（用于区分不同优化任务）。
        function_name: 被演化函数的实际名称。
        signature: 函数的完整签名字符串，作为生成新代码时的模板参考。
        inputs: 输入参数名列表。
        outputs: 输出（返回值）名列表。
        prompt_constraints: 提示词中给模型的硬性约束说明，限定可改动范围。
        extract_regex: 用于从源码中抽取当前函数实现的正则表达式。
        replace_regex_template: 用于在源码中定位并替换该函数的正则模板。
        seed_path: 可选的种子实现文件路径，作为演化起点；无则为 None。
        rag_api_context: 可选的检索增强上下文（相关 API 说明），默认空串。
        guard_checks: 生成结果需通过的安全/合法性校验规则列表，默认空列表。

    返回：构造后即为承载上述元信息的规格实例，供演化流程按字段读取。
    """

    name: str
    function_name: str
    signature: str
    inputs: list[str]
    outputs: list[str]
    prompt_constraints: str
    extract_regex: str
    replace_regex_template: str
    # 种子实现路径：提供演化的起始代码；缺省为 None 表示无种子
    seed_path: str | None = None
    # 检索到的相关 API 上下文，拼入提示词以辅助生成；缺省为空串
    rag_api_context: str = ""
    # 安全校验规则集合；用 default_factory 保证每个实例获得独立的空列表
    guard_checks: list[str] = field(default_factory=list)

