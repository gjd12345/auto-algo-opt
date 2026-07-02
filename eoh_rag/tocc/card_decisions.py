"""
模块：card_decisions（TOCC 卡片先验决策工具）
功能：读取一份「卡片先验决策」文件，告诉控制器对每张 RAG 语料卡片应采取的处置方式（接受 / 降权 / 拆分）。
职责：定位决策文件路径、按 card_id 加载并缓存决策记录、根据 card_id 查询单条决策及其状态。
接口：
    - resolve_decision_path(path=None) -> Path：把相对/缺省路径解析为绝对路径。
    - load_card_prior_decisions(path=None) -> dict[card_id, 决策记录]：加载并缓存整个决策表。
    - decision_for_card(card_id, decisions=None) -> 决策记录 | None：取某张卡片的完整决策。
    - decision_status(card_id, decisions=None) -> str | None：取某张卡片的决策状态字符串。
输入：一份 JSONL 决策文件（每行一个 JSON 对象，必含 card_id 字段），默认路径见 DEFAULT_CARD_PRIOR_DECISIONS。
输出：以 card_id 为键的字典、单条决策记录或决策状态字符串。
说明：决策文件由跑批之后的审计流程产出。它与 RAG 语料本身相互独立：
    语料卡片描述「可能的先验」，本模块则记录「控制器应接受、降权还是拆分」这些先验。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


# 决策文件的默认相对路径（相对于项目根目录），指向审计流程产出的 JSONL 文件。
DEFAULT_CARD_PRIOR_DECISIONS = (
    Path("eoh_rag_workspace")
    / "reports"
    / "auto_experiment_reports"
    / "tocc_history_card_audit_20260619"
    / "card_prior_decisions.jsonl"
)

# 三类决策状态取值，供上层控制器判断如何处置某张卡片：
HARD_BLOCK_DECISIONS = {"split_required", "split_or_deprioritize"}  # 需拆分（硬性拦截）
DEPRIORITIZED_DECISIONS = {"candidate_deprioritized"}              # 降权处理
WATCHLIST_DECISIONS = {"candidate_watchlist"}                      # 列入观察名单


def _project_root() -> Path:
    """返回项目根目录。

    本文件位于 <项目根>/eoh_rag/tocc/ 下，故向上跳两级即为项目根目录。
    """
    return Path(__file__).resolve().parents[2]


def resolve_decision_path(path: str | Path | None = None) -> Path:
    """把决策文件路径解析为绝对路径。

    参数 path：
        - 绝对路径：原样返回；
        - 相对路径：视为相对项目根目录再解析；
        - None：使用默认路径 DEFAULT_CARD_PRIOR_DECISIONS。
    返回：解析后的绝对 Path（不保证文件真实存在）。
    """
    if path:
        raw = Path(path)
        # 绝对路径直接用；相对路径则拼接到项目根目录下。
        return raw if raw.is_absolute() else (_project_root() / raw).resolve()
    return (_project_root() / DEFAULT_CARD_PRIOR_DECISIONS).resolve()


@lru_cache(maxsize=8)
def load_card_prior_decisions(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """加载 JSONL 决策文件，返回以 card_id 为键的决策字典。

    参数 path：决策文件路径（用法见 resolve_decision_path）；None 表示默认路径。
    返回：{card_id: 该行 JSON 对象}；文件不存在时返回空字典。
    异常：某行缺少 card_id 时抛出 ValueError。
    说明：结果按 path 做 LRU 缓存（最多 8 项），重复调用不会重新读盘。
    """
    decision_path = resolve_decision_path(path)
    if not decision_path.exists():
        return {}

    decisions: dict[str, dict[str, Any]] = {}
    # 逐行解析 JSONL；line_no 从 1 计数，便于报错时定位行号。
    for line_no, line in enumerate(decision_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue  # 跳过空行
        item = json.loads(line)
        card_id = str(item.get("card_id", "")).strip()
        if not card_id:
            raise ValueError(f"Missing card_id in {decision_path}:{line_no}")
        # 同一 card_id 若重复出现，以后出现的记录覆盖先前记录。
        decisions[card_id] = item
    return decisions


def decision_for_card(card_id: str, decisions: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """查询某张卡片的完整决策记录。

    参数 decisions：已加载的决策字典；为 None 时自动从默认路径加载。
    返回：对应的决策记录（dict），不存在则返回 None。
    """
    if decisions is None:
        decisions = load_card_prior_decisions()
    return decisions.get(card_id)


def decision_status(card_id: str, decisions: dict[str, dict[str, Any]] | None = None) -> str | None:
    """查询某张卡片的决策状态字符串（decision 字段）。

    返回：形如 "split_required" / "candidate_deprioritized" 等状态字符串；
    该卡片无决策记录时返回 None。可与 HARD_BLOCK_DECISIONS 等集合配合判断处置方式。
    """
    decision = decision_for_card(card_id, decisions)
    return str(decision.get("decision")) if decision else None
