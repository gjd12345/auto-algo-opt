"""
模块：TOCC Gatekeeper（守门员 / 提案校验器）
功能：用一套固定规则检查 LLM 生成的“提案”是否安全、字段是否合法，只做校验、放行或修正，绝不真正执行任何跑数任务。
职责：
    - 归一化提案字段（把不同别名统一成规范名，如把 candidate_card_ids/selected_card_ids 统一为候选卡片池）。
    - 按 R0~R12 一系列规则逐条检查：卡片是否存在、是否匹配当前问题、数量是否合理、诊断/动作是否合法、
      查询串是否安全、是否含有被禁止的字段、卡片先验决策是否允许使用等。
    - 命中硬性问题时拒绝（accepted=False）；命中可修复问题时给出修正版 fixed 并记录 warnings。
    - 校验通过后组装出一个 safe_arm（可安全下发给执行侧的实验臂配置）。
接口：
    - validate_proposal(proposal, *, problem, available_card_ids=None, arm="literature_rag",
      card_prior_decisions=None) -> dict：核心校验函数，返回 accepted/violations/warnings/fixed/safe_arm。
    - main() -> None：命令行入口，从 JSON 文件读入提案并打印校验结果。
输入：
    - 一个提案字典 proposal（通常来自 LLM 输出，含 cards、query、diagnosis、next_action、why、risk 等字段）。
    - problem：当前优化问题名，支持 tsp_construct、cvrp_construct、bp_online、insertships 等。
    - 可选的可用卡片列表、实验臂名、卡片先验决策表。
    - 命令行模式下：--proposal（提案 JSON 路径）、--problem、--available-cards、--card-prior-decisions、--output。
输出：
    - 一个结果字典：{accepted, violations, warnings, fixed, safe_arm}。
    - 命令行模式下把结果打印或写入文件；未通过校验时进程以退出码 1 结束。
示例：
    result = validate_proposal(proposal, problem="tsp_construct", available_card_ids=cards)
    if result["accepted"]:
        run(result["safe_arm"])
"""

from __future__ import annotations

from typing import Any

import json

from eoh_rag.tocc.controller import (
    BASELINE_OVERLAP_CARDS,   # 各问题的“基线家族”卡片集合，用于 R8 判断是否与基线过度重叠
    CARD_QUERIES,
)
from eoh_rag.tocc.card_decisions import (
    DEPRIORITIZED_DECISIONS,  # 被降级的卡片决策状态集合（使用时需给出明确理由）
    HARD_BLOCK_DECISIONS,     # 被硬性禁用的卡片决策状态集合（一旦命中直接拒绝）
    WATCHLIST_DECISIONS,      # 观察名单卡片决策状态集合（可用但只做有限度试跑）
    load_card_prior_decisions,  # 加载卡片先验决策表的函数
)
from eoh_rag.tocc.contracts import TOCC_CANDIDATE_POOL_STRATEGY  # 候选池上下文策略的固定标识

VALID_DIAGNOSES = {
    "baseline_overlap", "wrong_bias", "low_diversity",
    "context_truncated", "valid_collapse", "api_failure",
    "budget_mismatch", "no_issue",
    "weak_negative", "inconclusive",
}
# 允许出现的“诊断结论”取值集合。提案里的 diagnosis 字段必须落在这个集合内，否则会被回退成 no_issue。

VALID_ACTIONS = {
    "run_init_only", "retry", "expand_generations",
    "maintain", "manual_review", "run_repeat",
}
# 允许出现的“下一步动作”取值集合。提案里的 next_action 必须落在这个集合内，否则会被回退成 manual_review。

# 各优化问题对应的卡片 ID 前缀：卡片 ID 必须以对应前缀开头，用来防止跨问题误用卡片。
PROBLEM_PREFIXES = {
    "tsp_construct": "tsp_",
    "cvrp_construct": "cvrp_",
    "bp_online": "obp_",
}

# 禁止出现在提案里的字段：这些字段涉及执行/资源/密钥/文件与命令等敏感控制项，
# 守门员只做校验不做执行，因此一旦出现就会被剥离（记入 warnings）。
FORBIDDEN_FIELDS = {
    "pop_size", "generations", "repeats", "max_runs",
    "api_key", "endpoint", "model", "llm_model",
    "output_dir", "shell_command", "shell_cmd", "command",
    "file_write", "file_write_action", "git_operation", "git",
    "env", "environment",
}

# 字段别名到规范字段名的映射：把多种写法统一成规范名，便于后续按统一字段处理。
FIELD_ALIASES = {
    "candidate_card_ids": "cards",
    "selected_card_ids": "cards",
    "rag_query": "query",
}

MAX_CARDS = 10                    # 候选卡片数量上限，超过则截断
MIN_CARDS = 2                     # 候选卡片数量下限，不足则直接拒绝
MAX_CANDIDATE_CARDS = MAX_CARDS   # 候选池上限的别名，语义等同 MAX_CARDS
MIN_CANDIDATE_CARDS = MIN_CARDS   # 候选池下限的别名，语义等同 MIN_CARDS
MAX_QUERY_CHARS = 500             # 查询串最大字符数，超过只告警不拒绝


def _dedupe_preserve_order(values: Any) -> tuple[list[str], list[str]]:
    """按原始顺序去重，并把去掉的重复项单独收集起来。

    对传入的可迭代对象逐个转成字符串并去空白，空串跳过；首次出现的值保留，
    再次出现的值记入 duplicates。

    返回：(去重后的列表, 被去掉的重复值列表)。
    """
    seen: set[str] = set()
    deduped: list[str] = []
    duplicates: list[str] = []
    if not values:
        return deduped, duplicates
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        if value in seen:
            duplicates.append(value)
            continue
        seen.add(value)
        deduped.append(value)
    return deduped, duplicates


def _proposal_cards(proposal: dict[str, Any]) -> tuple[list[str], str, list[str]]:
    """从提案中取出候选卡片列表，并标明来源字段。

    依次尝试 candidate_card_ids、selected_card_ids、cards 三个字段，取第一个非空的作为卡片来源，
    随后去重。

    返回：(去重后的卡片列表, 命中的来源字段名, 被去掉的重复卡片列表)；三者都空时来源标为 "none"。
    """
    for source in ("candidate_card_ids", "selected_card_ids", "cards"):
        if proposal.get(source):
            cards, duplicates = _dedupe_preserve_order(proposal.get(source))
            return cards, source, duplicates
    return [], "none", []


def validate_proposal(
    proposal: dict[str, Any],
    *,
    problem: str,
    available_card_ids: list[str] | None = None,
    arm: str = "literature_rag",
    card_prior_decisions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """对一个提案逐条执行 R0~R12 规则校验，返回校验结论。

    工作流程：
      1. 先归一化字段（统一卡片字段名、查询串字段名），并复制一份 proposal 避免改动入参。
      2. 依次执行各条规则；硬性问题记入 violations 并立即返回拒绝，可修复问题记入 warnings 并写入 fixed。
      3. 全部通过后，用生效的卡片和查询组装 safe_arm 一并返回。

    关键参数：
      proposal：待校验的提案字典。
      problem：当前优化问题名（如 tsp_construct、cvrp_construct、bp_online、insertships），决定卡片前缀与基线集合。
      available_card_ids：可选的合法卡片白名单；提供时会校验卡片是否都在白名单内。
      arm：写入 safe_arm 的执行臂名，默认使用文献检索臂。
      card_prior_decisions：可选的卡片先验决策表；不传则自动加载。

    返回：字典 {accepted(是否放行), violations(硬性违规列表), warnings(告警列表),
    fixed(修正后的提案，可能为 None), safe_arm(放行时的实验臂配置，否则 None)}。
    """
    violations: list[str] = []   # 硬性违规，任一命中即拒绝
    warnings: list[str] = []     # 软性告警，不阻断放行
    fixed: dict[str, Any] | None = None  # 若发生自动修正，则存放修正后的提案副本

    # 归一化字段别名：把候选卡片统一到 candidate_card_ids/cards，把查询统一到 query。
    cards, card_source, duplicate_cards = _proposal_cards(proposal)
    query_raw = proposal.get("query") or proposal.get("rag_query", "")
    proposal = dict(proposal)  # 拷贝一份，后续修改不影响调用方传入的原字典
    proposal["candidate_card_ids"] = list(cards)
    proposal["cards"] = list(cards)
    proposal["query"] = str(query_raw)

    diagnosis = str(proposal.get("diagnosis", ""))
    query = str(proposal.get("query", ""))
    next_action = str(proposal.get("next_action", ""))
    if duplicate_cards:
        # R0：候选卡片存在重复，已去重，仅告警
        warnings.append(f"R0: deduped duplicate candidate cards: {duplicate_cards}")

    # R1：卡片存在性——提供了白名单时，卡片必须都在白名单内
    if available_card_ids:
        unknown = [c for c in cards if c not in available_card_ids]
        if unknown:
            violations.append(f"R1: unknown card IDs: {unknown}")
            return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}

    # R2：问题前缀匹配——卡片 ID 必须匹配当前问题的前缀，或匹配允许的历史卡片前缀
    prefix = PROBLEM_PREFIXES.get(problem, "")
    if prefix:
        family = problem.split("_", 1)[0]  # 取问题名首段作为“家族”名
        allowed_history_prefixes = (f"history_{problem}_", f"history_{family}_")
        mismatched = [
            c for c in cards
            if not (c.startswith(prefix) or c.startswith(allowed_history_prefixes))
        ]
        if mismatched:
            violations.append(f"R2: card IDs do not match problem prefix {prefix!r}: {mismatched}")
            return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}

    # R3：卡片非空——数量低于下限直接拒绝；虽达标但偏少（<4）时给出建议告警
    if len(cards) < MIN_CARDS:
        violations.append(f"R3: candidate_card_ids has {len(cards)} cards (min {MIN_CARDS})")
        return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}
    if len(cards) < 4:
        warnings.append(f"R3: candidate_card_ids has {len(cards)} cards; recommended range is 4-8 when available")

    # R4：卡片数量上限——超过上限时自动截断并记入 fixed
    if len(cards) > MAX_CARDS:
        cards = cards[:MAX_CARDS]
        fixed = dict(proposal)
        fixed["cards"] = cards
        fixed["candidate_card_ids"] = cards
        warnings.append(f"R4: truncated candidate_card_ids from {len(proposal['cards'])} to {MAX_CARDS}")

    # R5：诊断合法性——不在允许集合内时回退为 no_issue 并记入 fixed
    if diagnosis not in VALID_DIAGNOSES:
        warnings.append(f"R5: unknown diagnosis {diagnosis!r}, set to no_issue")
        diagnosis = "no_issue"
        if fixed is None:
            fixed = dict(proposal)
        fixed["diagnosis"] = "no_issue"

    # R6：动作合法性——不在允许集合内时回退为 manual_review 并记入 fixed
    if next_action not in VALID_ACTIONS:
        warnings.append(f"R6: unknown next_action {next_action!r}, set to manual_review")
        next_action = "manual_review"
        if fixed is None:
            fixed = dict(proposal)
        fixed["next_action"] = "manual_review"

    # R7：查询串安全——空查询直接拒绝；过长仅告警
    if not query or not query.strip():
        violations.append("R7: query is empty")
        return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}
    if len(query) > MAX_QUERY_CHARS:
        warnings.append(f"R7: query exceeds {MAX_QUERY_CHARS} chars ({len(query)})")

    # R8：基线重叠检查——诊断非 baseline_overlap 却选用了基线家族卡片时告警
    if diagnosis != "baseline_overlap":
        baseline_set = BASELINE_OVERLAP_CARDS.get(problem, set())
        overlap = set(cards) & baseline_set
        if overlap:
            warnings.append(f"R8: cards overlap baseline family {sorted(overlap)} but diagnosis is {diagnosis}")

    # R9：why/risk 说明字段是否齐全——缺失仅告警
    if not proposal.get("why"):
        warnings.append("R9: missing why field")
    if not proposal.get("risk"):
        warnings.append("R9: missing risk field")

    # R10：剥离禁止字段——命中的敏感字段从 fixed 中移除
    has_forbidden = [k for k in FORBIDDEN_FIELDS if k in proposal]
    if has_forbidden:
        warnings.append(f"R10: stripped forbidden fields: {has_forbidden}")
        if fixed is None:
            fixed = dict(proposal)
        for k in has_forbidden:
            fixed.pop(k, None)

    # R11：失败诊断与动作的一致性检查——不一致仅告警
    if diagnosis == "api_failure" and next_action != "retry":
        warnings.append("R11: api_failure diagnosis should use retry action")
    if diagnosis == "valid_collapse" and len(cards) > 2:
        warnings.append("R11: valid_collapse suggests simpler cards (<=2)")

    # R12：卡片先验决策闸门——按每张卡片的历史决策状态决定拒绝或告警
    decisions = card_prior_decisions if card_prior_decisions is not None else load_card_prior_decisions()
    why_text = " ".join(str(item) for item in proposal.get("why", []))  # 拼接 why 文本，供后续判断是否给出明确理由
    for card_id in cards:
        prior = decisions.get(card_id)
        if not prior:
            continue
        status = str(prior.get("decision", ""))
        if status in HARD_BLOCK_DECISIONS:
            # 硬禁用卡片：直接拒绝
            violations.append(f"R12: card {card_id} is marked {status}; split or replace before use")
        elif status in DEPRIORITIZED_DECISIONS:
            # 降级卡片：必须在 why 中给出明确、可追溯的理由才允许使用
            explicit = (
                card_id in why_text
                or "deprioritized" in why_text.lower()
                or "审计" in why_text
                or "trace" in why_text.lower()
            )
            if not explicit:
                violations.append(f"R12: card {card_id} is {status}; proposal must include explicit trace-backed why")
        elif status in WATCHLIST_DECISIONS:
            # 观察名单卡片：允许使用，但只做有限度的试跑
            warnings.append(f"R12: card {card_id} is watchlist; run bounded smoke only")
    if violations:
        return {"accepted": False, "violations": violations, "warnings": warnings, "fixed": None, "safe_arm": None}

    # 组装 safe_arm：优先使用修正后的卡片与查询（若发生过修正）
    effective_cards = fixed["candidate_card_ids"] if fixed else cards
    effective_query = fixed.get("query", query) if fixed else query

    safe_arm = {
        "name": f"agent_proposed_{diagnosis}",
        "runner_arm": arm,
        "context_strategy": TOCC_CANDIDATE_POOL_STRATEGY,
        "rag_query": effective_query,
        "candidate_card_ids": effective_cards,
        "candidate_card_source": card_source,
    }
    accepted = len(violations) == 0

    return {
        "accepted": accepted,
        "violations": violations,
        "warnings": warnings,
        "fixed": fixed,
        "safe_arm": safe_arm if accepted else None,
    }


def main() -> None:
    """命令行入口：从 JSON 文件读入提案，执行校验，把结果打印或写入文件。

    读取 --proposal 指向的提案 JSON，按 --problem 指定的问题名调用 validate_proposal，
    可选地传入 --available-cards（逗号分隔的白名单）和 --card-prior-decisions（先验决策文件）。
    结果以带缩进的 JSON 输出到 --output（默认标准输出）。若校验未通过，进程以退出码 1 结束，
    便于在脚本或流水线中据此判断放行与否。
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="TOCC Gatekeeper — validate LLM proposals")
    parser.add_argument("--proposal", required=True, help="Path to proposal JSON")
    parser.add_argument("--problem", required=True, help="Problem name (tsp_construct, cvrp_construct, bp_online)")
    parser.add_argument("--available-cards", help="Comma-separated list of valid card IDs")
    parser.add_argument("--card-prior-decisions", help="Path to card_prior_decisions.jsonl")
    parser.add_argument("--output", default="-", help="Output path (default: stdout)")
    args = parser.parse_args()

    proposal = json.loads(open(args.proposal).read())
    # 把逗号分隔的白名单字符串拆成去空白的列表；未提供则为 None（表示不做白名单校验）
    available = [c.strip() for c in args.available_cards.split(",")] if args.available_cards else None

    decisions = load_card_prior_decisions(args.card_prior_decisions) if args.card_prior_decisions else None
    result = validate_proposal(
        proposal,
        problem=args.problem,
        available_card_ids=available,
        card_prior_decisions=decisions,
    )

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output_text)
    else:
        open(args.output, "w").write(output_text + "\n")

    if not result["accepted"]:
        sys.exit(1)  # 校验未通过时以非零退出码结束，方便上游脚本据此拦截


if __name__ == "__main__":
    main()
