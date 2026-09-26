"""Stage 0 pin check for the six-mirror NumPy package.

Stage 1, the two-step baseline, is not implemented here. This command does not
invoke pip, does not import torch, and does not write a requirements file.

``py -3.12`` only selects the 3.12 series. After the venv exists, this command
reads ``sys.version`` and exits nonzero unless it is exactly CPython 3.12.14.
A wrong interpreter, NumPy, or SciPy version is a stack failure (exit 2), not
a physics-pin failure.

Install order, outside this repository:

1. ``py -3.12 -m venv .venv-six-mirror``
2. ``.venv-six-mirror\\Scripts\\python -m pip install numpy==2.5.3 scipy==1.18.1``
3. Write a one-line requirements file outside the repo. The path after
   ``file:///`` is an absolute path with forward slashes, not a second
   ``file://`` wrapper::

       optics-gradient-optimization @ file:///<forward-slash absolute path> --hash=sha256:ba8d2b9902bf0ba1260e1d8df32218b256f180499f6fd0ce2061444b917282fa

4. ``.venv-six-mirror\\Scripts\\python -m pip install --require-hashes --no-deps -r <that-file>``

Do not pass ``--require-hashes`` to a bare wheel path: pip does not attach a
hash to a path argument and exits before the package is installed. Do not put
that requirements file or the wheel in git.

This command hashes the given ``.whl`` before those install checks and hashes
the same file again after them. It never compares unpacked ``*.py`` or ``.mat``
bytes to the wheel digest. The installed tree hash is a separate digest. While
``TREE_SHA256`` is unset, the measured tree hash is printed and the process
exits 3. ``RMS_ABS_GATE`` is not committed, so a measurement cannot exit 0.

Exit codes: 2 stack mismatch, 3 tree hash uncommitted, 4 RMS gate uncommitted,
1 any other pin, package, thread, timeout, v1, ``N_Stop``, or nonfinite failure.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import math
import os
import subprocess
import sys
from pathlib import Path

# Set before NumPy is imported. Importing this module does not import NumPy.
_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
_PUBLISHED_ZERO_STEP_RMS = 0.03713648172611783
_STAGE0_TIMEOUT_SECONDS = 600
# Not a passing threshold. The command must not exit 0 by comparing RMS.
RMS_ABS_GATE = None

_EXIT_FAILURE = 1
_EXIT_STACK = 2
_EXIT_TREE_UNSET = 3
_EXIT_GATE = 4


def _pin_threads() -> None:
    for name in _THREAD_ENV_VARS:
        os.environ[name] = "1"


def _ensure_repo_path() -> None:
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)


def _blas_name(numpy_module) -> str:
    info = None
    try:
        info = numpy_module.show_config(mode="dicts")
    except TypeError:
        info = None
    if isinstance(info, dict):
        build = info.get("Build Dependencies")
        blas = build.get("blas") if isinstance(build, dict) else None
        if isinstance(blas, dict) and blas.get("name"):
            return str(blas["name"])
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        numpy_module.show_config()
    for line in buffer.getvalue().splitlines():
        lowered = line.lower()
        if "blas" in lowered and "name" in lowered and ":" in line:
            return line.split(":", 1)[1].strip()
    rows = [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]
    return rows[0] if rows else "unknown"


def _stack_status(*, echo: bool) -> int:
    numpy_version = "missing"
    scipy_version = "missing"
    blas = "missing"
    try:
        import numpy as np

        numpy_version = str(np.__version__)
        blas = _blas_name(np)
    except Exception as exc:
        numpy_version = "missing:" + type(exc).__name__
    try:
        import scipy

        scipy_version = str(scipy.__version__)
    except Exception as exc:
        scipy_version = "missing:" + type(exc).__name__
    if echo:
        print(f"sys.version={sys.version}")
        print(f"numpy={numpy_version}")
        print(f"scipy={scipy_version}")
        print(f"blas={blas}")
    release_ok = sys.version_info[:3] == (3, 12, 14) and sys.version_info.releaselevel == "final"
    if not release_ok or numpy_version != "2.5.3" or scipy_version != "1.18.1":
        print("stack_mismatch")
        return _EXIT_STACK
    return 0


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise ValueError("wheel_unreadable") from exc
    with handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wheel_digest(path: Path, expected: str) -> int | None:
    try:
        digest = _file_sha256(path)
    except ValueError as exc:
        print(str(exc))
        return _EXIT_FAILURE
    if digest != expected:
        print("physics_pin_mismatch")
        return _EXIT_FAILURE
    return None


def _measure_once() -> int:
    import numpy as np

    from agent_skill_loop.problems.six_mirror_physics import TREE_SHA256, WHEEL_SHA256, PinnedNumpyWavefront

    try:
        wavefront = PinnedNumpyWavefront(
            prescription_version="v2",
            field_indices=list(range(65)),
            sample_d=64,
            constraints=False,
            initial_scale=1.0,
            wheel_sha256=WHEEL_SHA256,
            tree_sha256=TREE_SHA256 if isinstance(TREE_SHA256, str) and TREE_SHA256 else "",
        )
        values = np.asarray(wavefront.mean_rms(wavefront.x0), dtype=np.float64).reshape(-1)
    except ValueError as exc:
        print(str(exc))
        return _EXIT_FAILURE
    if values.shape != (1,):
        print("invalid_measurement")
        return _EXIT_FAILURE
    measured = float(values[0])
    print(f"measured={measured!r}")
    if not math.isfinite(measured):
        print("nonfinite_result")
        return _EXIT_FAILURE
    # Internal worker: a finite trace is still not an accepted RMS comparison.
    return _EXIT_GATE


def _parse_measured(text: str) -> float | None:
    found = None
    for line in text.splitlines():
        if line.startswith("measured="):
            found = float(line.split("=", 1)[1])
    return found


def _measure_with_timeout(wheel: Path) -> int:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "stage0",
        "--wheel",
        str(wheel),
        "--measure-worker",
    ]
    env = os.environ.copy()
    for name in _THREAD_ENV_VARS:
        env[name] = "1"
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        stdout, stderr = proc.communicate(timeout=_STAGE0_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        print("stage0_timeout")
        return _EXIT_FAILURE
    if stdout:
        sys.stdout.write(stdout)
        if not stdout.endswith("\n"):
            sys.stdout.write("\n")
    if stderr:
        sys.stderr.write(stderr)
    measured = _parse_measured(stdout or "")
    if measured is None:
        return proc.returncode if proc.returncode else _EXIT_FAILURE
    print(f"delta0={measured - _PUBLISHED_ZERO_STEP_RMS!r}")
    if not math.isfinite(measured):
        if "nonfinite_result" not in (stdout or ""):
            print("nonfinite_result")
        return _EXIT_FAILURE
    if RMS_ABS_GATE is None or "rms_gate_uncommitted" not in (stdout or ""):
        print("rms_gate_uncommitted")
    return _EXIT_GATE


def _stage0(args: argparse.Namespace) -> int:
    _ensure_repo_path()
    stack = _stack_status(echo=not args.measure_worker)
    if stack:
        return stack
    from agent_skill_loop.problems.six_mirror_physics import (
        THREAD_ENV_VARS,
        TREE_SHA256,
        WHEEL_SHA256,
        measure_installed_tree_sha256,
    )

    if tuple(THREAD_ENV_VARS) != _THREAD_ENV_VARS:
        print("physics_thread_pin_mismatch")
        return _EXIT_FAILURE
    wheel = Path(args.wheel)
    mismatch = _wheel_digest(wheel, WHEEL_SHA256)
    if mismatch:
        return mismatch
    if args.measure_worker:
        return _measure_once()
    try:
        measured_tree = measure_installed_tree_sha256()
    except ValueError as exc:
        print(str(exc))
        return _EXIT_FAILURE
    mismatch = _wheel_digest(wheel, WHEEL_SHA256)
    if mismatch:
        return mismatch
    if not isinstance(TREE_SHA256, str) or not TREE_SHA256:
        print(f"tree_sha256={measured_tree}")
        return _EXIT_TREE_UNSET
    if measured_tree != TREE_SHA256.strip().lower():
        print("physics_pin_mismatch")
        return _EXIT_FAILURE
    if not args.measure:
        print("rms_gate_uncommitted")
        return _EXIT_GATE
    return _measure_with_timeout(wheel)


def main(argv: list[str] | None = None) -> int:
    _pin_threads()
    parser = argparse.ArgumentParser(description="Stage 0 six-mirror pin check. Does not run Newton or import torch.")
    sub = parser.add_subparsers(dest="command", required=True)
    stage0 = sub.add_parser("stage0", help="Hash the wheel, check the install, and optionally measure the zero step.")
    stage0.add_argument("--wheel", required=True, help="Path to the optics_gradient_optimization wheel. Not installed by this command.")
    stage0.add_argument("--measure", action="store_true", help="Trace mean_rms(x0) once, with a 600s timeout. Still fail-closed on RMS.")
    stage0.add_argument("--measure-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.command != "stage0":
        return _EXIT_STACK
    return _stage0(args)


if __name__ == "__main__":
    raise SystemExit(main())
