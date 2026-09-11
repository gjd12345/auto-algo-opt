from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agent_skill_loop.evaluator import SubprocessEvaluator
from agent_skill_loop.importer import import_skill
from agent_skill_loop.problems.cvrp import BASELINE_CODE
from agent_skill_loop.skill_store import load_skill, sha256_text


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_import_file_accepts_and_reevaluates(tmp_path):
    source = _write(tmp_path / "candidate.py", BASELINE_CODE)
    out = tmp_path / "import"
    record = import_skill(
        problem_id="cvrp_construct",
        output_dir=out,
        source={"kind": "file", "path": str(source)},
    )
    assert record["accepted"] is True
    assert record["counts_as_generated"] is False
    assert record["source"]["kind"] == "file"
    assert record["source"]["source_sha256"] == sha256_text(BASELINE_CODE)
    assert record["source"]["license"] == "unspecified"
    assert record["skill_dir"] is not None and record["skill_dir"].startswith("skills/imported_")

    skill = load_skill(out / "exported_skill")
    assert skill.code == BASELINE_CODE
    assert skill.problem == "cvrp_construct"
    suite = json.loads((out / "dev_suite.json").read_text(encoding="utf-8"))
    re_eval = SubprocessEvaluator(timeout=10.0).evaluate(skill.code, suite)
    assert re_eval.valid is True
    assert re_eval.objective == skill.mean_objective
    assert skill.suite_hash == record["suite_hash"]


def test_import_rejects_incompatible_code(tmp_path):
    source = _write(
        tmp_path / "bad.py",
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    return 'nope'\n",
    )
    out = tmp_path / "reject"
    record = import_skill(
        problem_id="cvrp_construct",
        output_dir=out,
        source={"kind": "file", "path": str(source)},
    )
    assert record["accepted"] is False
    assert record["evaluation"]["error_code"] == "invalid_return"
    assert record["skill_dir"] is None
    assert not (out / "skills").exists()
    assert not (out / "exported_skill").exists()
    assert (out / "import_record.json").is_file()


def test_import_from_git_snapshot(tmp_path):
    repo = tmp_path / "snapshot"
    repo.mkdir()
    _write(repo / "best.py", BASELINE_CODE)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "best.py"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed"],
        cwd=repo,
        check=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    out = tmp_path / "gitimport"
    record = import_skill(
        problem_id="cvrp_construct",
        output_dir=out,
        source={"kind": "git", "repo": str(repo), "ref": "HEAD", "path": "best.py"},
        license="MIT",
    )
    assert record["accepted"] is True
    assert record["source"]["kind"] == "git"
    assert record["source"]["commit"] == commit
    assert record["source"]["ref"] == "HEAD"
    assert record["source"]["path"] == "best.py"
    assert record["source"]["license"] == "MIT"
    assert load_skill(out / "exported_skill").code == BASELINE_CODE


def test_import_unknown_problem_raises(tmp_path):
    with pytest.raises(ValueError, match="unsupported_problem"):
        import_skill(
            problem_id="nope",
            output_dir=tmp_path / "x",
            source={"kind": "file", "path": str(tmp_path / "missing.py")},
        )


def test_import_missing_source_file_raises(tmp_path):
    with pytest.raises(ValueError, match="source_file_missing"):
        import_skill(
            problem_id="cvrp_construct",
            output_dir=tmp_path / "x",
            source={"kind": "file", "path": str(tmp_path / "missing.py")},
        )


def test_import_skill_cli(tmp_path, capsys):
    from agent_skill_loop.__main__ import main

    source = _write(tmp_path / "candidate.py", BASELINE_CODE)
    out = tmp_path / "cli_import"
    code = main([
        "import-skill",
        "--problem", "cvrp_construct",
        "--output", str(out),
        "--file", str(source),
        "--license", "test",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is True
    assert payload["source"]["license"] == "test"

    bad = _write(
        tmp_path / "bad.py",
        "def select_next_node(current_node, depot, unvisited_nodes, rest_capacity, demands, distance_matrix):\n"
        "    return 'nope'\n",
    )
    code = main([
        "import-skill",
        "--problem", "cvrp_construct",
        "--output", str(tmp_path / "cli_reject"),
        "--file", str(bad),
    ])
    assert code == 1
