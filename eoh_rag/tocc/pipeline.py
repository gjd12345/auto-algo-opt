"""
模块：TOCC V2 Pipeline（tocc/pipeline.py）
功能：串联“智能体提案 → 守门员校验”的一次完整评审流程，为启发式演化提供一份经过校验的改进方案。
职责：读取一次演化运行留下的 trace（轨迹）记录，调用智能体生成提案，再交给守门员做合法性/安全性判定，并把整条链路的结果汇总成一份可复核的审计字典。
接口：
    - run_tocc_v2_cycle(trace_path, *, problem=None, output_dir=None, available_cards=None, strict=True) -> dict[str, Any]
      跑完整个评审流程，只产出并校验方案，不执行任何实际运行。
    - main() -> None
      命令行入口，解析参数后调用上面的函数并输出结果。
输入：
    - trace_path：一份运行摘要 JSON 的路径（形如 official_eoh_run_summary.json）。
    - problem：可选的问题名称（如 online bin packing、TSP、CVRP、InsertShips 等）；缺省时从 trace 文件里自动读取。
    - available_cards：可选的合法卡片 ID 列表，供守门员核对提案是否引用了允许范围内的卡片。
输出：
    - 一份审计字典，包含提案内容、守门员判定、是否被接受、兜底方案（safe_arm）以及可能的错误信息。
    - 通过命令行运行时，把该字典以 JSON 形式打印到标准输出或写入指定文件。
示例：
    python -m eoh_rag.tocc.pipeline --trace official_eoh_run_summary.json --problem "online bin packing"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_tocc_v2_cycle(
    trace_path: str,
    *,
    problem: str | None = None,
    output_dir: str | None = None,
    available_cards: list[str] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """完整跑一遍 V2 评审流程：读取 trace → 智能体生成提案 → 守门员校验。

    该函数只负责“产出并校验方案”，不会真正执行任何运行（不跑基准、不评测）。

    参数：
        trace_path：运行摘要 JSON 的路径，作为智能体分析的输入依据。
        problem：问题名称；若为空，则从 trace 文件中读取 "problem" 字段自动补全。
        output_dir：预留的输出目录参数（当前流程内不直接使用）。
        available_cards：允许引用的卡片 ID 列表，交给守门员核对提案合法性。
        strict：严格模式开关（保留参数，供上层控制校验宽严）。

    返回：
        一份审计字典，键包括 trace_path、proposal（提案）、gatekeeper（守门员判定详情）、
        accepted（是否被接受）、safe_arm（未通过时的兜底方案）、error（错误信息，无错误则为 None）。
    """
    # 延迟导入：仅在真正执行流程时才加载智能体与守门员，避免模块加载期产生额外依赖开销
    from eoh_rag.tocc.agent import propose
    from eoh_rag.tocc.gatekeeper import validate_proposal

    # 预置审计字典的全部字段，保证无论中途在哪一步返回，结构都完整一致
    result: dict[str, Any] = {
        "trace_path": trace_path,
        "proposal": None,
        "gatekeeper": None,
        "accepted": False,
        "safe_arm": None,
        "error": None,
    }

    # 第一步：让智能体基于 trace 生成提案；若提案阶段就出错，直接带着错误信息提前返回
    agent_result = propose(trace_path)
    if agent_result.get("error"):
        result["error"] = agent_result["error"]
        return result

    proposal = agent_result["proposal"]
    result["proposal"] = proposal

    # 若调用方未指定问题名称，则从 trace 文件里回读 "problem" 字段作为守门员的判定上下文
    if not problem:
        payload = json.loads(Path(trace_path).read_text(encoding="utf-8"))
        problem = payload.get("problem", "")

    # 第二步：守门员校验提案是否合法/安全，并把判定结论回填进审计字典
    gk = validate_proposal(proposal, problem=problem, available_card_ids=available_cards)
    result["gatekeeper"] = gk
    result["accepted"] = gk["accepted"]
    result["safe_arm"] = gk["safe_arm"]

    return result


def main() -> None:
    """命令行入口：解析参数、跑一遍评审流程，并输出审计结果。

    通过 --trace 指定运行摘要文件，--problem 可选地指定问题名称，
    --output 决定结果打印到标准输出还是写入文件，--available-cards 传入允许的卡片 ID。
    当流程出错或提案未被接受时，以非零退出码结束，便于脚本/流水线据此判断成败。
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="TOCC V2 pipeline — agent propose + gatekeeper validate")
    parser.add_argument("--trace", required=True, help="Path to official_eoh_run_summary.json")
    parser.add_argument("--problem", help="Problem name (auto-detected if omitted)")
    parser.add_argument("--output", default="-", help="Output path (default: stdout)")
    parser.add_argument("--available-cards", help="Comma-separated valid card IDs")
    args = parser.parse_args()

    # 把逗号分隔的卡片 ID 字符串拆成列表并去除首尾空白；未提供时保持为 None
    cards = [c.strip() for c in args.available_cards.split(",")] if args.available_cards else None

    result = run_tocc_v2_cycle(args.trace, problem=args.problem, available_cards=cards)

    # 以带缩进、保留中文的 JSON 形式序列化结果，便于人工阅读
    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output_text)  # "-" 表示直接打印到标准输出
    else:
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")

    # 出错或提案未被接受，均视为失败，返回非零退出码供上层流程识别
    if result.get("error") or not result.get("accepted"):
        sys.exit(1)


if __name__ == "__main__":
    main()
