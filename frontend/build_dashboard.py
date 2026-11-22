"""Build offline self-contained Multi-Problem Research Workbench ``dashboard.html``.

Generates:
  - ``<output_dir>/dashboard.html`` (single-file inline CSS + JS, zero external CDN/runtime)
  - ``<output_dir>/workbench_data/core.js`` (release metadata, suites index, summary, selection,
    algorithms, published_results, and full structured knowledge base)
  - ``<output_dir>/workbench_data/suite_<suite_id>.js`` (per-suite lazy-loaded JSON bundles
    mirroring the exact release ``suites/``, ``routes/``, ``traces/``, and per-suite slice of
    ``results/per_instance_records.json`` so opening ``dashboard.html`` directly via ``file://``
    works 100% offline with zero CORS errors and zero data drift).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


FRONTEND_SRC_DIR = Path(__file__).resolve().parent / "src"
H003_DATA_JS_PATH = Path(__file__).resolve().parent / "h003_preview" / "data.js"

JS_LOAD_ORDER: tuple[str, ...] = (
    "labels.js",
    "exporters.js",
    "overview_view.js",
    "benchmarks_view.js",
    "knowledge_view.js",
    "comparator_view.js",
    "results_view.js",
    "app.js",
)


def _load_h003_preview() -> dict[str, Any] | None:
    if not H003_DATA_JS_PATH.is_file():
        return None
    raw = H003_DATA_JS_PATH.read_text(encoding="utf-8")
    if "=" not in raw:
        return None
    body = raw.split("=", 1)[1].strip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_js_json(payload: Any) -> str:
    """Serialize JSON safely for inline/external JS assignment (escaping </script> & line seps)."""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        raw.replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _load_kb_entries(workspace_dir: Path) -> list[dict[str, Any]]:
    entries_dir = workspace_dir / "entries"
    entries: list[dict[str, Any]] = []
    for json_path in sorted(entries_dir.glob("*.json")):
        meta = _load_json(json_path)
        md_path = json_path.with_suffix(".md")
        body = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
        meta["body"] = body
        entries.append(meta)
    return entries


def build_dashboard(
    *,
    bundle_dir: Path,
    workspace_dir: Path,
    output_dir: Path,
    release_id: str,
) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    workspace_dir = workspace_dir.resolve()
    output_dir = output_dir.resolve()
    data_dir = output_dir / "workbench_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    suites_index = _load_json(bundle_dir / "suites" / "index.json")
    algorithms_doc = _load_json(bundle_dir / "algorithms.json")
    summary_doc = _load_json(bundle_dir / "results" / "summary.json")
    selection_doc = _load_json(bundle_dir / "results" / "selection_records.json")
    stress_doc = _load_json(bundle_dir / "results" / "scale_stress_records.json")
    per_inst_doc = _load_json(bundle_dir / "results" / "per_instance_records.json")
    pub_index = _load_json(bundle_dir / "published_results" / "index.json")
    kb_entries = _load_kb_entries(workspace_dir)
    sources_doc = _load_json(workspace_dir / "sources.json")

    # Slice per_instance_records.json strictly by suite_id (zero drift)
    records_by_suite: dict[str, list[dict[str, Any]]] = {}
    for rec in per_inst_doc.get("records", []):
        records_by_suite.setdefault(str(rec["suite_id"]), []).append(rec)

    core_payload = {
        "schema_version": "co-workbench-frontend-core/v3",
        "release_id": release_id,
        "generated_at": summary_doc.get("generated_at"),
        "budget_id": summary_doc.get("budget_id", "standard_500ms"),
        "budget_ms": summary_doc.get("budget_ms", 500.0),
        "suites": suites_index.get("suites", []),
        "algorithms": algorithms_doc.get("algorithms", []),
        "summary": summary_doc,
        "selection": selection_doc,
        "scale_stress": stress_doc,
        "published_results": pub_index,
        "kb_entries": kb_entries,
        "sources": sources_doc.get("sources", []),
        "sources_count": len(sources_doc.get("sources", [])),
        "h003_preview": _load_h003_preview(),
    }

    core_js = f"window.__WB_CORE__={_safe_js_json(core_payload)};\n"
    core_path = data_dir / "core.js"
    core_path.write_text(core_js, encoding="utf-8", newline="\n")

    suite_files: dict[str, int] = {}
    for s_meta in suites_index.get("suites", []):
        sid = str(s_meta["suite_id"])
        suite_payload = _load_json(bundle_dir / "suites" / f"{sid}.json")
        routes_payload = _load_json(bundle_dir / "routes" / f"{sid}.json")
        trace_path = bundle_dir / "traces" / f"{sid}.json"
        traces_payload = _load_json(trace_path) if trace_path.is_file() else None
        wrapper_payload = {
            "suite": suite_payload,
            "routes": routes_payload,
            "traces": traces_payload,
            "records": records_by_suite.get(sid, []),
        }
        js_text = (
            "window.__WB_SUITE_BUNDLES__=window.__WB_SUITE_BUNDLES__||{};"
            f"window.__WB_SUITE_BUNDLES__[{json.dumps(sid)}]={_safe_js_json(wrapper_payload)};\n"
        )
        out_js = data_dir / f"suite_{sid}.js"
        out_js.write_text(js_text, encoding="utf-8", newline="\n")
        suite_files[sid] = out_js.stat().st_size

    css_text = (FRONTEND_SRC_DIR / "styles.css").read_text(encoding="utf-8")
    js_blocks = "\n\n".join(
        f"/* === {name} === */\n" + (FRONTEND_SRC_DIR / name).read_text(encoding="utf-8")
        for name in JS_LOAD_ORDER
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OptBench · 组合优化研究工作台 ({release_id})</title>
<style>
{css_text}
</style>
</head>
<body>
<header id="app-topbar" class="topbar"></header>
<main id="app-main" class="main">
  <div class="panel">正在初始化研究工作台 ({release_id}) ...</div>
</main>
<script src="./workbench_data/core.js"></script>
<script>
{js_blocks}
</script>
</body>
</html>
"""
    html_path = output_dir / "dashboard.html"
    html_path.write_text(html, encoding="utf-8", newline="\n")

    return {
        "ok": True,
        "release_id": release_id,
        "dashboard_html": str(html_path),
        "dashboard_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
        "dashboard_bytes": html_path.stat().st_size,
        "core_js_bytes": core_path.stat().st_size,
        "suite_bundle_count": len(suite_files),
        "suite_bundles_total_bytes": sum(suite_files.values()),
        "kb_entries_embedded": len(kb_entries),
        "published_results_embedded": len(pub_index.get("records", [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args(argv)
    res = build_dashboard(
        bundle_dir=args.bundle_dir,
        workspace_dir=args.workspace,
        output_dir=args.output_dir,
        release_id=args.release_id,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
