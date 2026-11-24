"""Guard problem-specific memory text with disjoint term families."""

from __future__ import annotations

import re
import unicodedata


_ALIASES = {
    "cvrp": {"cvrp", "cvrp_construct"},
    "tsp": {"tsp", "tsp_construct", "tsp_2opt", "tsp_2opt_move"},
    "online_obp": {"bp_online", "bp_online_island605", "obp", "obp_online", "online_obp"},
    "offline_bpp": {"bpp", "bpp_offline", "bp_offline", "offline_bpp"},
    "optics": {"optics", "optics_cluster", "optics_clustering"},
}
_TERMS = {
    "cvrp": (
        "cvrp", "capacitated vehicle routing", "vehicle routing", "vehicle count",
        "fleet size", "exact k fleet", "free fleet", "depot", "vehicle capacity",
        "车辆路径", "车辆数", "车队规模", "回仓",
    ),
    "tsp": ("tsp", "traveling salesman", "travelling salesman", "hamiltonian tour", "旅行商", "哈密顿回路"),
    "online_obp": (
        "obp", "bp online", "obp online", "online bin packing", "prefix invariance",
        "no future lookahead", "zero future lookahead", "item arrival", "item stream",
        "在线装箱", "前缀不变性",
    ),
    "offline_bpp": (
        "bpp", "bp offline", "bpp offline", "offline bin packing",
        "first fit decreasing", "best fit decreasing", "ffd", "bfd", "sort all items", "离线装箱",
    ),
    "optics": (
        "optics", "ordering points to identify the clustering structure",
        "reachability distance", "reachability plot", "core distance", "min samples",
        "可达距离", "核心距离",
    ),
}


def _normalize(value: str) -> str:
    return re.sub(r"[\s_\-–—]+", " ", unicodedata.normalize("NFKC", value).casefold())


def _term_pattern(term: str) -> str:
    # Chinese terms can be adjacent to ordinary sentence characters.
    escaped = re.escape(term)
    return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])" if term.isascii() else escaped


_TERM_FAMILY = {term: family for family, terms in _TERMS.items() for term in terms}
_VOCABULARY = re.compile("|".join(
    _term_pattern(term) for term in sorted(_TERM_FAMILY, key=len, reverse=True)
))


def problem_family(problem: str) -> str | None:
    alias = _normalize(problem).replace(" ", "_")
    return next((family for family, aliases in _ALIASES.items() if alias in aliases), None)


def validate_problem_vocab(problem: str, *texts: str) -> None:
    """Reject vocabulary owned by another recognized problem family."""
    family = problem_family(problem)
    if family is None:
        return
    for text in texts:
        for match in _VOCABULARY.finditer(_normalize(text)):
            term = match.group()
            if _TERM_FAMILY[term] != family:
                raise ValueError(f"memory_problem_vocab_mismatch:{term}")
