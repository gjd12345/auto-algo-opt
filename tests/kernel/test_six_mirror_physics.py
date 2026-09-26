from __future__ import annotations

import ast
import builtins
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from agent_skill_loop.evaluator import evaluate_candidate_request
from agent_skill_loop.problems.six_mirror_newton import (
    BASELINE_CODE,
    DIMENSION,
    build_suite,
    evaluate_instances,
)
from agent_skill_loop.problems.six_mirror_physics import (
    THREAD_ENV_VARS,
    TREE_SHA256,
    WHEEL_SHA256,
    PinnedNumpyWavefront,
    hash_installed_tree,
)


def _load_baseline():
    import math

    namespace = {"np": np, "math": math}
    exec(BASELINE_CODE, namespace)
    return namespace["select_diagonal_newton_step"]


def _block_optics(monkeypatch, exc: BaseException) -> None:
    real_import = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if str(name).split(".", 1)[0] == "optics_optim":
            raise exc
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)


@pytest.mark.parametrize("kind", ["missing", "scipy"])
def test_missing_physics_module_maps_to_package_missing(monkeypatch, kind):
    if kind == "missing":
        failure = ModuleNotFoundError("No module named 'optics_optim'")
    else:
        failure = ImportError("cannot import name 'scipy'")
    _block_optics(monkeypatch, failure)
    result = evaluate_candidate_request(
        {"problem": "six_mirror_newton", "suite": build_suite(1), "code": BASELINE_CODE}
    )
    assert result["valid"] is False
    assert result["objective"] is None
    assert result["error_code"] == "physics_package_missing"


def test_unpinned_install_does_not_load_prescription(monkeypatch):
    calls: list[str] = []
    fake = types.ModuleType("optics_optim")
    fake.__version__ = "0.1.0"
    fake.__file__ = "optics_optim/__init__.py"

    def load_prescription(version="v2"):
        calls.append(str(version))
        raise AssertionError("load_prescription")

    fake.load_prescription = load_prescription
    fake.encode = load_prescription
    monkeypatch.setitem(sys.modules, "optics_optim", fake)
    for name in THREAD_ENV_VARS:
        monkeypatch.setenv(name, "1")
    suite = build_suite(1)["instances"][0]
    with pytest.raises(ValueError, match="^physics_pin_mismatch$"):
        PinnedNumpyWavefront(
            prescription_version="v2",
            field_indices=list(suite["field_indices"]),
            sample_d=suite["sample_d"],
            constraints=False,
            initial_scale=1.0,
            wheel_sha256=suite["physics_wheel_sha256"],
            tree_sha256=suite["physics_tree_sha256"],
        )
    assert calls == []
    assert TREE_SHA256 in (None, "")


def test_wheel_argument_mismatch_is_pin_mismatch():
    with pytest.raises(ValueError, match="^physics_pin_mismatch$"):
        PinnedNumpyWavefront(
            prescription_version="v2",
            field_indices=[32],
            sample_d=9,
            constraints=False,
            initial_scale=1.0,
            wheel_sha256="0" * 64,
            tree_sha256="",
        )


def test_injected_oracle_does_not_import_optics(monkeypatch):
    real_import = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if str(name).split(".", 1)[0] == "optics_optim":
            raise AssertionError("optics_optim imported")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)
    x0 = np.zeros(DIMENSION, dtype=np.float64)

    def oracle(points):
        rows = np.asarray(points)
        if rows.ndim == 1:
            rows = rows.reshape(1, -1)
        return np.zeros(rows.shape[0], dtype=np.float64)

    objectives, metrics = evaluate_instances(_load_baseline(), build_suite(1)["instances"], oracle, x0)
    assert objectives == [0.0]
    assert metrics["solver_status"] == "gradient_tolerance"


def test_physics_module_does_not_import_optics_at_import_time():
    source = Path(__file__).resolve().parents[2].joinpath(
        "agent_skill_loop", "problems", "six_mirror_physics.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert name.split(".", 1)[0] not in {"optics_optim", "scipy", "torch"}
    assert "load_prescription(version=\"v1\")" not in source
    assert "1e-4" not in source


def test_eval_worker_pins_blas_threads_before_numpy():
    source = Path(__file__).resolve().parents[2].joinpath("agent_skill_loop", "eval_worker.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    pinned: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".", 1)[0] != "numpy" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".", 1)[0] != "numpy"
        elif isinstance(node, ast.Assign):
            segment = ast.get_source_segment(source, node) or ""
            for name in THREAD_ENV_VARS:
                if name in segment and '"1"' in segment:
                    pinned.add(name)
    assert pinned == set(THREAD_ENV_VARS)
    assert WHEEL_SHA256 == "ba8d2b9902bf0ba1260e1d8df32218b256f180499f6fd0ce2061444b917282fa"


def test_tree_hash_covers_sorted_sources_and_both_mat_dirs(tmp_path):
    root = tmp_path / "optics_optim"
    (root / "data" / "v1").mkdir(parents=True)
    (root / "data" / "v2").mkdir(parents=True)
    (root / "b.py").write_bytes(b"b")
    (root / "a.py").write_bytes(b"a")
    (root / "data" / "v1" / "z.mat").write_bytes(b"v1")
    (root / "data" / "v2" / "z.mat").write_bytes(b"v2")
    (root / "data" / "v1" / "ignore.txt").write_bytes(b"no")
    cache = root / "__pycache__"
    cache.mkdir()
    (cache / "a.py").write_bytes(b"cache")
    first = hash_installed_tree(root)
    assert first == hash_installed_tree(root)
    assert len(first) == 64
    (root / "data" / "v2" / "z.mat").write_bytes(b"changed")
    assert hash_installed_tree(root) != first
    assert first != WHEEL_SHA256


def test_tree_hash_rejects_a_missing_mat_tree(tmp_path):
    root = tmp_path / "pkg"
    (root / "data" / "v2").mkdir(parents=True)
    (root / "a.py").write_bytes(b"a")
    (root / "data" / "v2" / "a.mat").write_bytes(b"m")
    with pytest.raises(ValueError, match="^physics_pin_mismatch$"):
        hash_installed_tree(root)
