"""Deterministic bibliographic harvest for the knowledge-base literature queue.

Uses OpenAlex over HTTPS. No model calls, no PDF download, no TLS bypass.
Screening prompts are packed for grok-4.5 subagents. Ingest writes drafts
with Plan-readable EoH adapter skeletons; it does not touch Session or the
evaluator.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .catalog import (
    SCHEMA_VERSION,
    build_catalog,
    catalog_markdown,
    validate_catalog,
)
from .core import sha256_file, write_json
from .doi_seeds import seeds_for

OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"
USER_AGENT = "auto-algo-opt-knowledge/0.1 (literature-harvest; mailto:knowledge@localhost)"
SCREEN_SCHEMA = "literature-screen/v1"
DRAFT_SCHEMA = "literature-draft/v1"
ADAPTER_KINDS = frozenset({
    "next_node_score", "bin_score", "move_selector", "not_mappable",
})
EOH_STATUS = frozenset({"possible", "not_mappable", "not_registered"})
SLUG_RE = re.compile(r"[^a-z0-9]+")

# Exact registered entrypoints. Insertion, merge, Harmonic class bins, FFD
# sorting, and Lin-Kernighan variable-depth search are not these signatures.
ADAPTER_TSP_NEXT_NODE = '''
def select_next_node(current_node: int, start_node: int, unvisited_nodes: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """TSP construct adapter. Evaluator already truncated the candidate list.

    Replace the score using the screened heuristic steps. Returning a city
    that is not in unvisited_nodes is invalid_return. This is not insertion
    into a partial tour and not 2-opt.
    """
    # mechanism: score each unvisited city; pick the best legal index
    return unvisited_nodes[int(np.argmin(distance_matrix[current_node][unvisited_nodes]))]
'''.strip()

ADAPTER_CVRP_NEXT_NODE = '''
def select_next_node(current_node: int, depot: int, unvisited_nodes: np.ndarray,
                     rest_capacity: float, demands: np.ndarray,
                     distance_matrix: np.ndarray) -> int:
    """CVRP construct adapter. unvisited_nodes are already capacity-feasible.

    Return 0 to go back to the depot early. This is not Clarke-Wright merge
    of n singleton routes, not sweep clustering, and not granular tabu.
    """
    # mechanism: score feasible customers; depot return is allowed
    return unvisited_nodes[int(np.argmin(distance_matrix[current_node][unvisited_nodes]))]
'''.strip()

ADAPTER_OBP_SCORE = '''
def score(item: float, bins: np.ndarray) -> np.ndarray:
    """Official-example OBP adapter. bins are feasible residuals only.

    Evaluator does argmax. Template `return bins` is Worst Fit. `-bins` is
    Best-Fit-like. First Fit is not a score over residuals; it is scan order.
    """
    # mechanism: one numeric score per feasible residual
    return -bins
'''.strip()

ADAPTER_OBP_PRIORITY = '''
def priority(item: float, bins: np.ndarray) -> np.ndarray:
    """Frozen/session OBP adapter. Same semantics as score; first maximum wins.

    Empty `bins` means the evaluator opens a new bin. Do not open bins here.
    """
    # mechanism: one numeric priority per feasible residual
    return -bins
'''.strip()

ADAPTER_TSP_2OPT = '''
def select_2opt_move(tour: np.ndarray, distance_matrix: np.ndarray,
                     move_start: np.ndarray, move_end: np.ndarray,
                     move_delta: np.ndarray, remaining_moves: int) -> int:
    """TSP 2-opt move selector. Candidates are already improving 2-opt moves.

    Return an index into move_start/move_end/move_delta. This is not Lin-Kernighan
    variable-depth search and not Or-opt/3-opt unless those moves are in the list.
    """
    # mechanism: pick among improving 2-opt deltas
    return int(np.argmin(move_delta))
'''.strip()


SearchFn = Callable[[str, int, str | None], list[dict[str, Any]]]

# Stronger bibliographic queries for the EoH-mappable gap set.
QUERY_OVERRIDE = {
    "tsp_construct": "Rosenkrantz nearest neighbor traveling salesman heuristic",
    "tsp_local": "Croes 2-opt method solving traveling salesman",
    "tsp_large": "Lin Kernighan effective heuristic traveling salesman",
    "tsp_metric": "Christofides algorithm traveling salesman heuristic",
    "tsp_asymmetric": "asymmetric TSP nearest neighbor directed distances",
    "tsp_open": "open TSP Hamiltonian path nearest neighbor heuristic",
    "cvrp_construct": "Clarke Wright savings algorithm vehicle routing",
    "cvrp_clustered": "cluster-first nearest neighbor vehicle routing",
    "cvrp_large": "large scale capacitated VRP nearest neighbor heuristic",
    "obp_harmonic": "Lee Lee harmonic algorithm online bin packing",
    "obp_bestfit_family": "Best Fit online bin packing Johnson worst case",
    "obp_worstfit_family": "Worst Fit online bin packing algorithm",
    "obp_score": "online bin packing residual scoring heuristic",
    "obp_bounded_space": "bounded space online bin packing Harmonic",
    "obp_irrevocable": "online bin packing Best Fit Worst Fit residual",
    "bp_cardinality": "cardinality constrained bin packing Best Fit",
}


def _boosted_query(sub: Mapping[str, Any]) -> str:
    sid = str(sub.get("id") or "")
    if sid in QUERY_OVERRIDE:
        return QUERY_OVERRIDE[sid]
    query = str(sub.get("search_query") or sub.get("label") or sid)
    for heuristic in sub.get("target_heuristics") or []:
        kind = (heuristic or {}).get("adapter_kind")
        name = (heuristic or {}).get("name")
        if name and kind not in {None, "not_mappable"}:
            return f"{query} {name}"
    return query


def slugify(text: str, limit: int = 48) -> str:
    text = SLUG_RE.sub("-", str(text).lower()).strip("-")
    return (text[:limit].strip("-") or "item")


def dump_catalog(out_dir: Path) -> dict[str, Any]:
    catalog = build_catalog()
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog invalid: " + "; ".join(errors))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "subproblems.json"
    md_path = out_dir / "subproblems.md"
    write_json(json_path, catalog)
    md_path.write_text(catalog_markdown(catalog), encoding="utf-8", newline="\n")
    counts = {
        name: len(spec.get("subproblems") or [])
        for name, spec in catalog["families"].items()
    }
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "json": str(json_path),
        "markdown": str(md_path),
        "counts": counts,
    }


def load_catalog(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or "families" not in payload:
        raise ValueError("catalog must contain families")
    errors = validate_catalog(dict(payload))
    if errors:
        raise ValueError("catalog invalid: " + "; ".join(errors))
    return dict(payload)


def _reconstruct_abstract(index: Any) -> str | None:
    if not isinstance(index, Mapping):
        return None
    positions: list[tuple[int, str]] = []
    for word, locs in index.items():
        if not isinstance(locs, list):
            continue
        for loc in locs:
            if isinstance(loc, int):
                positions.append((loc, str(word)))
    if not positions:
        return None
    positions.sort()
    text = " ".join(word for _, word in positions).strip()
    return text or None


def _http_json(url: str, mailto: str | None, *, retries: int = 3, base_wait: float = 2.0) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    if mailto:
        headers["User-Agent"] = f"auto-algo-opt-knowledge/0.1 (mailto:{mailto})"
    request = urllib.request.Request(url, headers=headers)
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            wait = float(retry_after) if retry_after and str(retry_after).isdigit() else base_wait * (attempt + 1)
            if exc.code not in {429, 500, 502, 503, 504}:
                raise
            time.sleep(min(wait, 20.0))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            time.sleep(base_wait * (attempt + 1))
    if last_error is not None:
        raise last_error
    return {}


def _openalex_search(query: str, rows: int, mailto: str | None) -> list[dict[str, Any]]:
    params = {
        "search": query,
        "per_page": max(1, min(int(rows), 25)),
        "filter": "type:article,has_abstract:true",
        "select": "id,doi,title,authorships,publication_year,primary_location,abstract_inverted_index,cited_by_count",
    }
    if mailto:
        params["mailto"] = mailto
    url = OPENALEX + "?" + urllib.parse.urlencode(params)
    try:
        payload = _http_json(url, mailto, retries=2, base_wait=3.0)
        return _parse_openalex(payload)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return _crossref_search(query, rows, mailto)


def _parse_openalex_work(item: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    authors = []
    for authorship in item.get("authorships") or []:
        author = (authorship or {}).get("author") or {}
        name = author.get("display_name")
        if name:
            authors.append(str(name))
    venue = ((item.get("primary_location") or {}).get("source") or {}).get("display_name")
    doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
    abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))
    return {
        "provider": "openalex",
        "openalex_id": item.get("id"),
        "doi": doi,
        "title": item.get("title"),
        "authors": authors,
        "year": item.get("publication_year"),
        "venue": venue,
        "cited_by_count": item.get("cited_by_count"),
        "abstract": abstract,
        "abstract_missing": not bool(abstract),
        "url": item.get("doi") or item.get("id"),
        "seeded": True,
    }


def _parse_openalex(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    results = []
    seen_doi: set[str] = set()
    for item in payload.get("results") or []:
        parsed = _parse_openalex_work(item)
        if not parsed:
            continue
        doi = parsed.get("doi")
        if doi:
            key = str(doi).lower()
            if key in seen_doi:
                continue
            seen_doi.add(key)
        results.append(parsed)
    return results


def openalex_doi(doi: str, mailto: str | None = None) -> dict[str, Any] | None:
    doi = doi.replace("https://doi.org/", "").strip()
    url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(doi, safe="/:")
    if mailto:
        url += "?" + urllib.parse.urlencode({"mailto": mailto})
    try:
        payload = _http_json(url, mailto, retries=2, base_wait=1.5)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return None
    return _parse_openalex_work(payload)


def _strip_jats(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).replace("  ", " ").strip()


def _crossref_search(query: str, rows: int, mailto: str | None) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "rows": max(1, min(int(rows), 25)),
        "select": "DOI,title,author,issued,container-title,abstract,is-referenced-by-count",
        "filter": "has-abstract:true",
    }
    if mailto:
        params["mailto"] = mailto
    url = CROSSREF + "?" + urllib.parse.urlencode(params)
    payload = _http_json(url, mailto)
    items = ((payload.get("message") or {}).get("items")) or []
    results = []
    seen_doi: set[str] = set()
    for item in items:
        parsed = _parse_crossref_item(item)
        if not parsed:
            continue
        doi = parsed.get("doi")
        if doi:
            key = str(doi).lower()
            if key in seen_doi:
                continue
            seen_doi.add(key)
        results.append(parsed)
    return results


def _parse_crossref_item(item: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    doi = str(item.get("DOI") or "") or None
    authors = []
    for author in item.get("author") or []:
        given = author.get("given") or ""
        family = author.get("family") or ""
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)
    year = None
    parts = ((item.get("issued") or {}).get("date-parts") or [[]])
    if parts and parts[0] and isinstance(parts[0][0], int):
        year = parts[0][0]
    title_parts = item.get("title") or []
    venue_parts = item.get("container-title") or []
    abstract = item.get("abstract")
    if isinstance(abstract, str):
        abstract = _strip_jats(abstract) or None
    else:
        abstract = None
    return {
        "provider": "crossref",
        "openalex_id": None,
        "doi": doi,
        "title": title_parts[0] if title_parts else None,
        "authors": authors,
        "year": year,
        "venue": venue_parts[0] if venue_parts else None,
        "cited_by_count": item.get("is-referenced-by-count"),
        "abstract": abstract,
        "abstract_missing": not bool(abstract),
        "url": f"https://doi.org/{doi}" if doi else None,
        "seeded": False,
    }


def crossref_doi(doi: str, mailto: str | None = None) -> dict[str, Any] | None:
    doi = doi.replace("https://doi.org/", "").strip()
    url = CROSSREF + "/" + urllib.parse.quote(doi, safe="/:")
    try:
        payload = _http_json(url, mailto, retries=2, base_wait=1.5)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return None
    message = payload.get("message")
    if not isinstance(message, Mapping):
        return None
    parsed = _parse_crossref_item(message)
    if parsed:
        parsed["seeded"] = True
    return parsed


def harvest_doi_seeds(
    catalog: Mapping[str, Any],
    out_dir: Path,
    *,
    mailto: str | None = None,
    pause_seconds: float = 0.25,
    only_cannot_classify: bool = True,
) -> dict[str, Any]:
    """Prepend Crossref works for canonical DOIs onto existing queue files."""
    written = 0
    failed: list[str] = []
    skipped = 0
    screens_cleared = 0
    out_dir.mkdir(parents=True, exist_ok=True)
    cache: dict[str, dict[str, Any] | None] = {}
    for name, spec in (catalog.get("families") or {}).items():
        family_dir = out_dir / name
        for sub in spec.get("subproblems") or []:
            if not isinstance(sub, Mapping) or not sub.get("id"):
                continue
            sid = str(sub["id"])
            seeds = seeds_for(sid)
            if not seeds:
                continue
            target = family_dir / f"{sid}.json"
            screen_path = family_dir / f"{sid}.screen.json"
            if only_cannot_classify and screen_path.exists():
                try:
                    screen = json.loads(screen_path.read_text(encoding="utf-8"))
                except (ValueError, UnicodeError):
                    screen = {}
                if screen.get("selected") and not screen.get("cannot_classify"):
                    skipped += 1
                    continue
            if not target.exists():
                write_json(target, {
                    "schema_version": "literature-queue/v1",
                    "family": name,
                    "subproblem": sub,
                    "query": "doi-seed",
                    "harvested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "works": [],
                })
            payload = json.loads(target.read_text(encoding="utf-8"))
            works = list(payload.get("works") or [])
            have = {
                str(w.get("doi") or "").replace("https://doi.org/", "").lower()
                for w in works if isinstance(w, Mapping)
            }
            added = 0
            for doi, hname, kind in seeds:
                key = doi.lower()
                if key in have:
                    continue
                if key not in cache:
                    work = crossref_doi(doi, mailto)
                    if work is None:
                        work = openalex_doi(doi, mailto)
                    cache[key] = work
                    time.sleep(pause_seconds)
                work = cache[key]
                if not work or not work.get("doi"):
                    failed.append(f"{sid}:{doi}")
                    continue
                work = dict(work)
                work["seed_heuristic"] = hname
                work["seed_adapter_kind"] = kind
                works.insert(0, work)
                have.add(key)
                added += 1
            if not added:
                skipped += 1
                continue
            payload["works"] = works
            payload["doi_seeded_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            write_json(target, payload)
            if screen_path.exists():
                try:
                    screen = json.loads(screen_path.read_text(encoding="utf-8"))
                except (ValueError, UnicodeError):
                    screen = {}
                if screen.get("cannot_classify") or not screen.get("selected"):
                    screen_path.unlink()
                    screens_cleared += 1
            written += 1
    return {
        "ok": True,
        "updated": written,
        "skipped": skipped,
        "failed": failed,
        "screens_cleared": screens_cleared,
        "out": str(out_dir),
    }


def harvest_catalog(
    catalog: Mapping[str, Any],
    out_dir: Path,
    *,
    family: str | None = None,
    limit_subproblems: int | None = None,
    per_subproblem: int = 8,
    mailto: str | None = None,
    pause_seconds: float = 1.0,
    dry_run: bool = False,
    search: SearchFn | None = None,
    provider: str = "auto",
    only_ids: list[str] | None = None,
    refresh_if_abstracts_lt: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    families = catalog.get("families") or {}
    names = [family] if family else list(families)
    written = 0
    skipped = 0
    refreshed = 0
    planned: list[str] = []
    failed: list[str] = []
    wanted = {item.strip() for item in (only_ids or []) if item and item.strip()}
    out_dir.mkdir(parents=True, exist_ok=True)
    if search is not None:
        search_fn = search
    elif provider == "crossref":
        search_fn = _crossref_search
    elif provider == "openalex":
        search_fn = _openalex_search
    else:
        search_fn = _openalex_search
    for name in names:
        spec = families.get(name)
        if not isinstance(spec, Mapping):
            failed.append(name)
            continue
        items = list(spec.get("subproblems") or [])
        if limit_subproblems is not None:
            items = items[: max(0, int(limit_subproblems))]
        family_dir = out_dir / name
        family_dir.mkdir(parents=True, exist_ok=True)
        for sub in items:
            if not isinstance(sub, Mapping) or not sub.get("id"):
                continue
            if wanted and str(sub["id"]) not in wanted:
                continue
            target = family_dir / f"{sub['id']}.json"
            query = _boosted_query(sub)
            planned.append(f"{name}/{sub['id']}")
            if dry_run:
                continue
            existing_abstracts = 0
            if target.exists() and not force:
                try:
                    old = json.loads(target.read_text(encoding="utf-8"))
                    existing_abstracts = _abstract_count(old.get("works") or [])
                except (ValueError, UnicodeError):
                    existing_abstracts = 0
                if refresh_if_abstracts_lt is None or existing_abstracts >= refresh_if_abstracts_lt:
                    skipped += 1
                    continue
            try:
                works = search_fn(query, per_subproblem, mailto)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError) as exc:
                failed.append(f"{name}/{sub['id']}:{exc}")
                time.sleep(pause_seconds)
                continue
            new_abstracts = _abstract_count(works)
            if target.exists() and new_abstracts < existing_abstracts:
                skipped += 1
                time.sleep(pause_seconds)
                continue
            write_json(target, {
                "schema_version": "literature-queue/v1",
                "family": name,
                "subproblem": sub,
                "query": query,
                "harvested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "works": works,
            })
            screen_path = family_dir / f"{sub['id']}.screen.json"
            if screen_path.exists():
                try:
                    screen = json.loads(screen_path.read_text(encoding="utf-8"))
                except (ValueError, UnicodeError):
                    screen = {}
                if screen.get("cannot_classify"):
                    screen_path.unlink()
            written += 1
            if existing_abstracts:
                refreshed += 1
            time.sleep(pause_seconds)
    return {
        "ok": not failed,
        "written": written,
        "refreshed": refreshed,
        "skipped_existing": skipped,
        "failed": failed,
        "planned": planned,
        "dry_run": dry_run,
        "out": str(out_dir),
    }


def _screen_prompt_lines(payload: Mapping[str, Any]) -> list[str]:
    sub = payload.get("subproblem") or {}
    works = payload.get("works") or []
    heuristics = sub.get("target_heuristics") or []
    hint = ", ".join(
        f"{h.get('name')} ({h.get('adapter_kind')})" for h in heuristics
    ) or "(none)"
    return [
        "You are a grok-4.5 screening agent for combinatorial-optimisation literature.",
        "Return ONLY one JSON object. Do not download PDFs or write repository files.",
        "Do not invent steps that the abstract does not state.",
        "",
        f"family: {payload.get('family')}",
        f"subproblem_id: {sub.get('id')}",
        f"label: {sub.get('label')}",
        f"definition: {sub.get('definition')}",
        f"eoh_map: {json.dumps(sub.get('eoh_map'), ensure_ascii=False)}",
        f"target_heuristics: {hint}",
        "",
        "Select 0-2 heuristics from the works below. Prefer original algorithmic papers.",
        "Prefer the named target_heuristics when an abstract actually describes them.",
        "Reject exact solvers, commercial tools, and reviews without steps.",
        "If the heuristic cannot map onto the listed EoH entrypoint, set eoh_map to not_mappable",
        "and do not invent a template_program.",
        "Insertion into a partial tour is not select_next_node.",
        "Clarke-Wright merge of singleton routes is not select_next_node.",
        "Harmonic class-dedicated bins are only mappable if expressed as a score over residuals.",
        "FFD/BFD require sorting the full list and are not online score(item, bins).",
        "Lin-Kernighan variable-depth search is not select_2opt_move.",
        "If nothing is classifiable, selected=[] and cannot_classify=true.",
        "Every selected item MUST have a DOI. No DOI => reject.",
        "",
        "JSON shape:",
        '{"schema_version":"literature-screen/v1","subproblem_id":"","selected":[{"doi":"","heuristic_name":"","why":"","steps":[],"eoh_map":"possible|not_mappable|not_registered","adapter_kind":"next_node_score|bin_score|move_selector|not_mappable","not_the_original":""}],"rejected":[{"doi":"","reason":""}],"cannot_classify":false}',
        "",
        "Works:",
    ] + _work_lines(works)


def _clip_abstract(text: Any, limit: int = 700) -> str:
    raw = " ".join(str(text or "").split())
    if not raw:
        return "(missing)"
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "…"


def _abstract_count(works: Any) -> int:
    if not isinstance(works, list):
        return 0
    return sum(1 for work in works if isinstance(work, Mapping) and work.get("abstract"))


def _is_classified(screen_path: Path) -> bool:
    if not screen_path.is_file():
        return False
    try:
        screen = json.loads(screen_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        return False
    return bool(screen.get("selected")) and not screen.get("cannot_classify")


def _compact_works(
    works: list[Any],
    limit: int = 5,
    *,
    require_abstract: bool = False,
) -> list[Mapping[str, Any]]:
    ranked: list[Mapping[str, Any]] = []
    for work in works:
        if not isinstance(work, Mapping):
            continue
        if require_abstract and not work.get("abstract"):
            continue
        ranked.append(work)
    ranked.sort(key=lambda item: (not bool(item.get("abstract")), -(item.get("cited_by_count") or 0)))
    return ranked[: max(0, limit)]


def _work_lines(works: list[Any], clip: int = 700) -> list[str]:
    lines: list[str] = []
    for index, work in enumerate(works, start=1):
        if not isinstance(work, Mapping):
            continue
        lines.append(
            f"{index}. doi={work.get('doi')} year={work.get('year')} title={work.get('title')}"
        )
        lines.append(f"   authors={', '.join(work.get('authors') or [])}")
        lines.append(f"   venue={work.get('venue')} cited_by={work.get('cited_by_count')}")
        lines.append(f"   abstract={_clip_abstract(work.get('abstract'), clip)}")
    return lines


_BATCH_CONTRACT = """You are a grok-4.5 screening agent for combinatorial-optimisation literature.
Do not use tools. Do not download PDFs. Do not write repository files.
Return ONLY one JSON object.

Screen EACH subproblem independently. Select 0-2 heuristics per subproblem. Do not pad.
Prefer original algorithmic papers and the named target_heuristics when the abstract actually describes them.
Reject exact solvers, commercial tools, missing abstracts, and reviews without steps.
No DOI => reject. Do not invent steps the abstract does not state.
Insertion into a partial tour is not select_next_node.
Clarke-Wright merge of singleton routes is not select_next_node.
Harmonic class-dedicated bins are only mappable as a score over residuals.
FFD/BFD require sorting the full list and are not online score(item, bins).
Lin-Kernighan variable-depth search is not select_2opt_move.
If nothing is classifiable for a subproblem: selected=[] and cannot_classify=true.

JSON shape:
{"schema_version":"literature-screen-batch/v1","family":"<family>","screens":[{"schema_version":"literature-screen/v1","subproblem_id":"","selected":[{"doi":"","heuristic_name":"","why":"","steps":[],"eoh_map":"possible|not_mappable|not_registered","adapter_kind":"next_node_score|bin_score|move_selector|not_mappable","not_the_original":""}],"rejected":[{"doi":"","reason":""}],"cannot_classify":false}]}

Emit one screens[] object per subproblem below, same order, matching subproblem_id.
The top-level family field may be "mixed" when several families are packed together; each screen still has its own subproblem_id.
"""


def _iter_queue_payloads(queue_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(queue_dir.rglob("*.json")):
        if path.name.endswith(".screen.json") or path.name.startswith("batch."):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            continue
        if isinstance(payload, Mapping) and payload.get("subproblem"):
            found.append((path, dict(payload)))
    return found


def pack_family_batch(
    queue_dir: Path,
    prompt_out: Path,
    *,
    skip_screened: bool = True,
    skip_classified: bool = False,
    require_abstract: bool = False,
    works_per_subproblem: int = 5,
    abstract_clip: int = 700,
    only_eoh_status: str | None = None,
) -> dict[str, Any]:
    payloads = []
    skipped_no_abstract = 0
    skipped_classified = 0
    for path, payload in _iter_queue_payloads(queue_dir):
        screen_path = path.with_name(path.stem + ".screen.json")
        if skip_classified and _is_classified(screen_path):
            skipped_classified += 1
            continue
        if skip_screened and not skip_classified and screen_path.exists():
            continue
        eoh_status = ((payload.get("subproblem") or {}).get("eoh_map") or {}).get("status")
        if only_eoh_status and eoh_status != only_eoh_status:
            continue
        works = _compact_works(
            list(payload.get("works") or []),
            works_per_subproblem,
            require_abstract=require_abstract,
        )
        if require_abstract and not works:
            skipped_no_abstract += 1
            continue
        payload = dict(payload)
        payload["_packed_works"] = works
        payloads.append(payload)
    if not payloads:
        raise ValueError(f"no abstract-bearing unclassified queue files in {queue_dir}")
    families = sorted({str(item.get("family") or "") for item in payloads})
    family = families[0] if len(families) == 1 else "mixed"
    lines = [_BATCH_CONTRACT.strip(), "", f"family: {family}", ""]
    ids = []
    work_count = 0
    for payload in payloads:
        sub = payload.get("subproblem") or {}
        sid = str(sub.get("id") or "")
        ids.append(sid)
        heuristics = sub.get("target_heuristics") or []
        hint = ", ".join(
            f"{h.get('name')} ({h.get('adapter_kind')})" for h in heuristics
        ) or "(none)"
        works = list(payload.get("_packed_works") or [])
        work_count += len(works)
        lines.extend([
            f"=== {sid} ===",
            f"family: {payload.get('family')}",
            f"label: {sub.get('label')}",
            f"definition: {sub.get('definition')}",
            f"eoh_map: {json.dumps(sub.get('eoh_map'), ensure_ascii=False)}",
            f"target_heuristics: {hint}",
            "Works:",
            *_work_lines(works, clip=abstract_clip),
            "",
        ])
    prompt_out.parent.mkdir(parents=True, exist_ok=True)
    prompt_out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return {
        "ok": True,
        "prompt": str(prompt_out),
        "family": family,
        "subproblem_ids": ids,
        "subproblem_count": len(ids),
        "work_count": work_count,
        "skipped_no_abstract": skipped_no_abstract,
        "skipped_classified": skipped_classified,
    }


def split_batch_screen(batch: Mapping[str, Any], queue_dir: Path) -> dict[str, Any]:
    screens = batch.get("screens")
    if not isinstance(screens, list):
        raise ValueError("batch screen has no screens list")
    written = []
    errors: list[str] = []
    for item in screens:
        if not isinstance(item, Mapping):
            errors.append("non-object screen")
            continue
        sid = str(item.get("subproblem_id") or "")
        if not sid:
            errors.append("screen missing subproblem_id")
            continue
        problems = validate_screen(item, sid)
        if problems:
            errors.extend(f"{sid}:{msg}" for msg in problems)
            continue
        matches = [path for path in queue_dir.rglob(f"{sid}.json") if path.stem == sid]
        if matches:
            target = matches[0].with_name(f"{sid}.screen.json")
        else:
            target = queue_dir / f"{sid}.screen.json"
        write_json(target, dict(item))
        written.append(str(target))
    return {
        "ok": not errors,
        "written": written,
        "errors": errors,
        "count": len(written),
    }


def pack_screen(queue_path: Path, prompt_out: Path) -> dict[str, Any]:
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    lines = _screen_prompt_lines(payload)
    prompt_out.parent.mkdir(parents=True, exist_ok=True)
    prompt_out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {
        "ok": True,
        "prompt": str(prompt_out),
        "work_count": len(payload.get("works") or []),
        "subproblem_id": (payload.get("subproblem") or {}).get("id"),
    }


def pack_screen_dir(queue_dir: Path, out_dir: Path) -> dict[str, Any]:
    written = []
    for path in sorted(queue_dir.rglob("*.json")):
        if path.name.endswith(".screen.json"):
            continue
        rel = path.relative_to(queue_dir)
        prompt_out = out_dir / rel.with_suffix(".screen.md")
        result = pack_screen(path, prompt_out)
        written.append(result["prompt"])
    return {"ok": True, "written": len(written), "prompts": written, "out": str(out_dir)}


def validate_screen(screen: Mapping[str, Any], subproblem_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if screen.get("schema_version") not in {None, SCREEN_SCHEMA}:
        errors.append(f"unexpected screen schema {screen.get('schema_version')!r}")
    selected = screen.get("selected")
    if not isinstance(selected, list):
        errors.append("selected must be a list")
        selected = []
    if len(selected) > 2:
        errors.append("selected longer than 2")
    if screen.get("cannot_classify") and selected:
        errors.append("cannot_classify with non-empty selected")
    expected_id = screen.get("subproblem_id")
    if subproblem_id and expected_id and expected_id != subproblem_id:
        errors.append(f"subproblem_id mismatch {expected_id!r} != {subproblem_id!r}")
    for item in selected:
        if not isinstance(item, Mapping):
            errors.append("selected item is not an object")
            continue
        doi = str(item.get("doi") or "").strip()
        if not doi:
            errors.append("selected item missing DOI")
        eoh = item.get("eoh_map")
        kind = item.get("adapter_kind")
        if eoh not in EOH_STATUS:
            errors.append(f"bad eoh_map {eoh!r} for {doi}")
        if kind not in ADAPTER_KINDS:
            errors.append(f"bad adapter_kind {kind!r} for {doi}")
        if eoh == "possible" and kind == "not_mappable":
            errors.append(f"{doi}: possible map cannot use not_mappable adapter")
        if eoh != "possible" and item.get("template_program"):
            errors.append(f"{doi}: template_program forbidden unless eoh_map=possible")
        if not item.get("heuristic_name"):
            errors.append(f"{doi}: missing heuristic_name")
        steps = item.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{doi}: steps must be a non-empty list")
    return errors


def adapter_code(family: str, adapter_kind: str) -> str | None:
    if adapter_kind == "next_node_score":
        if family == "cvrp":
            return ADAPTER_CVRP_NEXT_NODE
        return ADAPTER_TSP_NEXT_NODE
    if adapter_kind == "bin_score":
        return ADAPTER_OBP_SCORE + "\n\n" + ADAPTER_OBP_PRIORITY
    if adapter_kind == "move_selector":
        return ADAPTER_TSP_2OPT
    return None


def _doi_url(doi: str) -> str:
    doi = doi.replace("https://doi.org/", "").strip()
    return f"https://doi.org/{doi}"


def _lookup_work(works: list[Any], doi: str) -> dict[str, Any]:
    want = doi.replace("https://doi.org/", "").strip().lower()
    for work in works:
        if not isinstance(work, Mapping):
            continue
        have = str(work.get("doi") or "").replace("https://doi.org/", "").strip().lower()
        if have and have == want:
            return dict(work)
    return {}


def _method_markdown(
    *,
    title: str,
    family: str,
    sub: Mapping[str, Any],
    selected: Mapping[str, Any],
    work: Mapping[str, Any],
) -> str:
    eoh = selected.get("eoh_map")
    kind = selected.get("adapter_kind")
    steps = selected.get("steps") or []
    step_lines = "\n".join(f"- {step}" for step in steps)
    code = adapter_code(family, str(kind)) if eoh == "possible" else None
    adapter_section = [
        "## EoH 适配",
        "",
        f"- target_problem_id: { {'tsp': 'tsp_construct', 'cvrp': 'cvrp_construct', 'online_bin_packing': 'obp_online'}.get(family, 'none') }",
        f"- adapter_kind: {kind}",
        f"- mappable: {eoh}",
        f"- not_the_original: {selected.get('not_the_original') or 'not stated'}",
        "",
    ]
    if code:
        adapter_section.extend(["```python", code, "```", ""])
        adapter_section.append(
            "Plan 只把机制写入 `operations[].mechanism`，不要把这段代码粘进 plan.json。"
        )
        adapter_section.append("")
    else:
        adapter_section.append("不可映射到已注册入口，不写 template_program。")
        adapter_section.append("")
    return "\n".join([
        f"# {title}",
        "",
        "Literature method card from an OpenAlex abstract plus grok-4.5 screen. "
        "This is not a main-tree implementation.",
        "",
        "## 定义或方法步骤",
        "",
        step_lines or "- (screen did not supply steps)",
        "",
        f"Why selected: {selected.get('why') or '(not stated)'}",
        "",
        "## 适用条件、假设与限制",
        "",
        f"Subproblem: {sub.get('label')} — {sub.get('definition')}",
        "",
        selected.get("not_the_original") or "Adapter is not the original algorithm unless the abstract already matches the entrypoint.",
        "",
        "## 来源及支持的具体结论",
        "",
        f"{work.get('title') or title} ({work.get('year') or 'year unknown'}). DOI {selected.get('doi')}. "
        "read_depth=abstract. Do not copy publisher PDF into the release.",
        "",
        "## 代码和评测关联",
        "",
        "No local code hash. Evaluator remains the only scorekeeper. "
        "If used as an EoH seed later, mark it as an adapter, not the original algorithm.",
        "",
        "## 未确认项与冲突证据",
        "",
        "Abstract-only. No suite/metric/budget is bound. Historical numbers from the paper stay in the paper.",
        "",
        *adapter_section,
    ])


def _problem_markdown(family: str, sub: Mapping[str, Any]) -> str:
    heur = ", ".join(
        f"{h.get('name')} ({h.get('adapter_kind')})"
        for h in sub.get("target_heuristics") or []
    )
    eoh = sub.get("eoh_map") or {}
    return "\n".join([
        f"# {sub.get('label')} (literature secondary)",
        "",
        "Secondary literature variant, not a new registered EoH problem_id.",
        "",
        "## 定义或方法步骤",
        "",
        str(sub.get("definition") or ""),
        "",
        f"Catalog search query: `{sub.get('search_query')}`.",
        "",
        "## 适用条件、假设与限制",
        "",
        f"Parent family `{family}`. eoh_map={eoh.get('status')}/{eoh.get('adapter_kind')}.",
        "",
        "Do not treat this card as a new evaluator interface.",
        "",
        "## 来源及支持的具体结论",
        "",
        "Catalog-defined variant. Method conclusions live on the screened method cards.",
        "",
        "## 代码和评测关联",
        "",
        f"Target heuristics (search hints only): {heur or '(none)'}.",
        "",
        "## 未确认项与冲突证据",
        "",
        "No suite/metric/budget. Empty until a screened method is attached.",
        "",
    ])


def ingest_screen(
    queue_path: Path,
    screen_path: Path,
    drafts_dir: Path,
    *,
    promote_workspace: Path | None = None,
) -> dict[str, Any]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    sub = queue.get("subproblem") or {}
    family = str(queue.get("family") or "unknown")
    errors = validate_screen(screen, str(sub.get("id") or ""))
    if errors:
        return {"ok": False, "errors": errors, "written": []}
    if screen.get("cannot_classify"):
        return {
            "ok": True,
            "skipped": "cannot_classify",
            "written": [],
            "drafts": str(drafts_dir),
        }
    if not screen.get("selected"):
        return {
            "ok": True,
            "skipped": "no_selected",
            "written": [],
            "drafts": str(drafts_dir),
        }
    works = queue.get("works") or []
    written: list[str] = []
    sources: list[dict[str, Any]] = []
    entries_dir = drafts_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    problem_id = f"problem-lit-{slugify(str(sub.get('id') or 'sub'))}"
    problem_md = _problem_markdown(family, sub)
    problem_md_path = entries_dir / f"{problem_id}.md"
    problem_md_path.write_text(problem_md, encoding="utf-8", newline="\n")
    problem_meta = {
        "id": problem_id,
        "type": "problem",
        "title": f"{sub.get('label')} (literature secondary)",
        "category": "problem",
        "problem_family": family,
        "tags": [family, "literature", "secondary"],
        "status": "reviewed",
        "summary": str(sub.get("definition") or sub.get("label")),
        "attributes": {
            "level": "secondary",
            "parent_family": family,
            "eoh_map": sub.get("eoh_map"),
        },
        "relations": {"methods": [], "sources": []},
        "source_refs": [],
        "evidence_refs": [f"literature-catalog:{sub.get('id')}"],
        "code_refs": [],
    }
    method_ids: list[str] = []
    source_ids: list[str] = []
    for selected in screen.get("selected") or []:
        doi = str(selected.get("doi")).replace("https://doi.org/", "").strip()
        work = _lookup_work(works, doi)
        source_id = "src-lit-" + slugify(doi.replace("/", "-"), 56)
        source_ids.append(source_id)
        authors = work.get("authors") or ["unknown"]
        year = work.get("year") or 0
        has_abstract = bool(str(work.get("abstract") or "").strip())
        provider = str(work.get("provider") or "unknown")
        if has_abstract:
            locator = f"{provider} abstract"
            depth = "abstract"
            availability = "publisher_abstract"
        else:
            locator = f"{provider} bibliographic metadata"
            depth = "metadata_only"
            availability = "bibliographic_only"
        sources.append({
            "id": source_id,
            "title": work.get("title") or selected.get("heuristic_name"),
            "authors": authors,
            "year": year,
            "venue": work.get("venue"),
            "doi": doi,
            "url": _doi_url(doi),
            "kind": "primary_article",
            "accessed_on": datetime.now(timezone.utc).date().isoformat(),
            "availability": availability,
            "license": "copyrighted; release contains citation and autonomous summary only",
            "selected": True,
            "selection_reason": selected.get("why") or "screened heuristic",
            "locator": locator,
            "read_depth": depth,
            "notes": selected.get("not_the_original") or "",
        })
        heuristic = str(selected.get("heuristic_name") or "heuristic")
        method_id = "method-lit-" + slugify(f"{sub.get('id')}-{heuristic}", 72)
        title = heuristic
        markdown = _method_markdown(
            title=title, family=family, sub=sub, selected=selected, work=work,
        )
        md_path = entries_dir / f"{method_id}.md"
        md_path.write_text(markdown, encoding="utf-8", newline="\n")
        meta = {
            "id": method_id,
            "type": "method",
            "title": title,
            "category": "method",
            "problem_family": family,
            "tags": [family, "literature", slugify(heuristic, 24)],
            "status": "reviewed",
            "summary": selected.get("why") or title,
            "attributes": {
                "method_family": "literature",
                "eoh_map": {
                    "status": selected.get("eoh_map"),
                    "adapter_kind": selected.get("adapter_kind"),
                },
                "not_the_original": selected.get("not_the_original"),
                "origin": "openalex+grok-4.5-screen",
            },
            "relations": {
                "problems": [problem_id],
                "sources": [source_id],
                "implementations": [],
            },
            "source_refs": [source_id],
            "evidence_refs": [f"literature:{doi}"],
            "code_refs": [],
            "content_sha256": sha256_file(md_path),
        }
        write_json(entries_dir / f"{method_id}.json", meta)
        written.append(method_id)
        method_ids.append(method_id)
    problem_meta["relations"] = {"methods": method_ids, "sources": source_ids}
    problem_meta["source_refs"] = source_ids
    problem_meta["content_sha256"] = sha256_file(problem_md_path)
    write_json(entries_dir / f"{problem_id}.json", problem_meta)
    written.append(problem_id)
    write_json(drafts_dir / "sources.json", {
        "schema_version": DRAFT_SCHEMA,
        "sources": sources,
    })
    write_json(drafts_dir / "ingest_record.json", {
        "schema_version": DRAFT_SCHEMA,
        "queue": str(queue_path),
        "screen": str(screen_path),
        "family": family,
        "subproblem_id": sub.get("id"),
        "entries": written,
        "sources": source_ids,
    })
    promoted = None
    if promote_workspace is not None:
        promoted = promote_drafts(drafts_dir, promote_workspace)
    return {
        "ok": True,
        "written": written,
        "sources": source_ids,
        "drafts": str(drafts_dir),
        "promoted": promoted,
    }


def promote_drafts(drafts_dir: Path, workspace: Path) -> dict[str, Any]:
    """Copy draft entries into the workspace and merge sources.json.

    Does not run build. Host must validate then build a new release.
    Refuses to overwrite an existing entry id.
    """
    src_entries = drafts_dir / "entries"
    dest_entries = workspace / "entries"
    dest_entries.mkdir(parents=True, exist_ok=True)
    copied = []
    skipped = []
    for path in sorted(src_entries.glob("*")):
        target = dest_entries / path.name
        if target.exists():
            skipped.append(path.name)
            continue
        target.write_bytes(path.read_bytes())
        copied.append(path.name)
    draft_sources = json.loads((drafts_dir / "sources.json").read_text(encoding="utf-8"))
    workspace_sources_path = workspace / "sources.json"
    doc = json.loads(workspace_sources_path.read_text(encoding="utf-8"))
    existing = {item.get("id") for item in doc.get("sources") or []}
    added = []
    for source in draft_sources.get("sources") or []:
        if source.get("id") in existing:
            continue
        doc.setdefault("sources", []).append(source)
        existing.add(source.get("id"))
        added.append(source.get("id"))
    query_log = doc.setdefault("query_log", [])
    record = json.loads((drafts_dir / "ingest_record.json").read_text(encoding="utf-8"))
    query_log.append({
        "date": datetime.now(timezone.utc).date().isoformat(),
        "problem_family": record.get("family"),
        "queries": [f"screen:{record.get('subproblem_id')}"],
        "screened_candidates": len(record.get("entries") or []),
        "selection_note": "Promoted from literature_drafts after grok-4.5 screen.",
    })
    write_json(workspace_sources_path, doc)
    return {"copied": copied, "skipped_existing": skipped, "sources_added": added}


def queue_status(catalog: Mapping[str, Any], queue_dir: Path) -> dict[str, Any]:
    families = {}
    for name, spec in (catalog.get("families") or {}).items():
        items = spec.get("subproblems") or []
        harvested = 0
        screened = 0
        for sub in items:
            sid = sub.get("id")
            if not sid:
                continue
            if (queue_dir / name / f"{sid}.json").exists():
                harvested += 1
            if (queue_dir / name / f"{sid}.screen.json").exists():
                screened += 1
        families[name] = {
            "catalog": len(items),
            "fill_policy": spec.get("fill_policy"),
            "harvested": harvested,
            "screened": screened,
        }
    return {"ok": True, "queue": str(queue_dir), "families": families}


def write_adapter_files(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "next_node_score_tsp.md": _adapter_page(
            "TSP construct — select_next_node",
            "tsp_construct",
            ADAPTER_TSP_NEXT_NODE,
            "Plan copies the scoring idea into operations[].mechanism. "
            "Not insertion, not 2-opt.",
        ),
        "next_node_score_cvrp.md": _adapter_page(
            "CVRP construct — select_next_node",
            "cvrp_construct",
            ADAPTER_CVRP_NEXT_NODE,
            "Capacity filter is owned by the evaluator. Returning 0 is early depot return. "
            "Not Clarke-Wright merge.",
        ),
        "bin_score_obp.md": _adapter_page(
            "Online bin packing — score / priority",
            "obp_online",
            ADAPTER_OBP_SCORE + "\n\n" + ADAPTER_OBP_PRIORITY,
            "Official examples use score+argmax. Frozen/session uses priority+first maximum. "
            "Template return bins is Worst Fit. -bins is Best-Fit-like.",
        ),
        "move_selector_tsp_2opt.md": _adapter_page(
            "TSP 2-opt — select_2opt_move",
            "tsp_2opt",
            ADAPTER_TSP_2OPT,
            "Only improving 2-opt candidates are offered. Not Lin-Kernighan.",
        ),
    }
    written = []
    for name, body in files.items():
        path = out_dir / name
        path.write_text(body, encoding="utf-8", newline="\n")
        written.append(str(path))
    return {"ok": True, "written": written, "out": str(out_dir)}


def _adapter_page(title: str, problem_id: str, code: str, note: str) -> str:
    return "\n".join([
        f"# EoH adapter: {title}",
        "",
        f"Registered problem_id: `{problem_id}`.",
        "",
        note,
        "",
        "Plan JSON cannot contain a `code` field. Put the mechanism in "
        "`operations[].mechanism`. If a later seed is required, use `explicit_seeds` "
        "and label it as an adapter, not the original paper algorithm.",
        "",
        "```python",
        code,
        "```",
        "",
    ])
