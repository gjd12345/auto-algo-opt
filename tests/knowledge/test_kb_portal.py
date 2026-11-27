"""Tests for the offline, jargon-free Knowledge Exhibition Portal builder and CLI."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from frontend.build_kb_portal import PORTAL_SRC_DIR, build_kb_portal, scrub_internal_jargon

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = REPO_ROOT / "knowledge_store" / "releases" / "20261127-main-co-workbench-m6-final"

JARGON_PATTERN = re.compile(
    r"(Milestone\s*[1-6]|里程碑[一二三四五六1-6]|Wave\s*[1-4]|Waves\s*1[–-]4|\bM[1-6](?:\.\d+)?\b|\bH-00[1-9][a-z]?\b|\bH-010\b|\bS[12]-?R\d+\b|\barm_b[23]_[a-z0-9_]+\b|\bY_[01]{2}\b|\bIsland605\b)",
    re.I,
)


def test_scrub_internal_jargon_rewrites_codes_cleanly() -> None:
    sample = "M6 Wave 4 B3 arm_b3_2_offline_l3_c2_gated and H-003 (S2-R5, Island605, Y_11)"
    cleaned = scrub_internal_jargon(sample)
    assert not JARGON_PATTERN.search(cleaned), f"Remaining jargon in: {cleaned}"


def test_build_kb_portal_zero_jargon_and_zero_cdn(tmp_path: Path) -> None:
    if not RELEASE_DIR.is_dir():
        pytest.skip(f"Release directory absent: {RELEASE_DIR}")

    out_dir = tmp_path / "portal"
    res = build_kb_portal(release_dir=RELEASE_DIR, output_dir=out_dir)
    assert res["ok"] is True
    assert res["entries_embedded"] == 365
    assert res["sources_embedded"] == 132

    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<(script|link)[^>]+https?://", html_text, re.I)

    js_raw = (out_dir / "portal_data.js").read_text(encoding="utf-8")
    prefix = "window.__KB_PORTAL_DATA__="
    assert js_raw.startswith(prefix)
    payload = json.loads(js_raw[len(prefix) : -2])

    assert len(payload["entries"]) == 365
    assert len(payload["sources"]) == 132

    for entry in payload["entries"]:
        assert not JARGON_PATTERN.search(entry["display_title"]), (
            f"Jargon in display_title of {entry['id']}: {entry['display_title']}"
        )
        assert not JARGON_PATTERN.search(entry["clean_summary"]), (
            f"Jargon in clean_summary of {entry['id']}: {entry['clean_summary']}"
        )
        assert not JARGON_PATTERN.search(entry["clean_body"]), (
            f"Jargon in clean_body of {entry['id']}"
        )

    for src in payload["sources"]:
        assert not JARGON_PATTERN.search(src["display_title"]), (
            f"Jargon in source display_title of {src['id']}: {src['display_title']}"
        )

    for fname in ("app.js", "microlabs.js", "graph_view.js", "renderers.js"):
        src_text = (PORTAL_SRC_DIR / fname).read_text(encoding="utf-8")
        # Strip JS comments before checking visible UI template strings
        no_comments = re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", "", src_text)
        # Allow JSON property lookup IDs like evidence-m6-... or theory-m6-... (internal keys),
        # check strictly for forbidden UI text tokens
        stripped_keys = re.sub(r'"(evidence|theory|method|framework)-[a-z0-9-]+"', '""', no_comments)
        assert not JARGON_PATTERN.search(stripped_keys), f"Jargon found in UI source {fname}"


def test_cli_build_portal_help_and_execution(tmp_path: Path) -> None:
    if not RELEASE_DIR.is_dir():
        pytest.skip(f"Release directory absent: {RELEASE_DIR}")
    out_dir = tmp_path / "cli_portal"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "knowledge_tools",
            "build-portal",
            "--release",
            str(RELEASE_DIR),
            "--output-dir",
            str(out_dir),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert (out_dir / "index.html").is_file()
    assert (out_dir / "portal_data.js").is_file()
