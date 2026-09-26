"""Pin checks for the six-mirror NumPy package.

Stage 0 hashes the wheel and can measure the full-field zero step. Stage 1
scores ``baseline_code`` twice on the frozen coarse suite through
``SubprocessEvaluator(timeout=300)``. Neither command is a pytest. Neither
calls EoH or reads ``rank_key``. This command does not invoke pip, does not
import torch, and does not write a requirements file.

Stage 1 uses the same interpreter gate as stage 0. A wrong stack exits 2 and
is not a physics failure. While ``TREE_SHA256`` is unset, the measured tree
hash is printed and the process exits 3 before any ray trace.

300 seconds is the per-call measurement cap. It is not a measured elapsed,
not the session ``solver_timeout``, and not the 20 second default. Only a
call that finishes records ``elapsed_seconds``. A timeout does not count as
300 seconds and does not raise ``solver_timeout`` or ``engine_wall_seconds``.
If either call times out, the command stops.

When both calls finish, ``elapsed`` is the maximum of the two
``elapsed_seconds`` values, not the faster one. If a real run has
``4 * elapsed > 120``, the checklist is ``solver_timeout = 4 * elapsed`` and
``engine_wall_seconds >= 8 * solver_timeout + 720``. If that
``solver_timeout`` would exceed 600, the experiment stops and the suite is
not changed. ``4 * elapsed <= 120`` keeps solver timeout 120 and engine wall
1800. This command does not invent ``elapsed``.

``accepted_alphas`` must equal ``[0.03125, 0.125]``, ``accepted_steps`` must
be 2, and ``solver_status`` must be ``max_iterations``. A mismatch fails and
is not loosened. ``parameter_vectors_evaluated`` is recorded. The expected
count is 275. 259 is not required. ``bit_stable`` is whether the two
full-precision finals are bitwise equal. There is no 1e-9 gate.

Reference RMS values are printed only, until a gate exists: initial
0.021483322678436757, after step 1 0.014198835443096334, final
0.010906458907220248. The full-field zero-step reference remains
0.03713648172611783. ``d`` is the maximum of ``abs(delta0)`` and the absolute
errors of those three coarse values. ``delta0`` is the stage 0 residual.
Stage 1 does not trace the full field and does not invent ``delta0``, so it
does not print a numeric ``d``. ``RMS_ABS_GATE`` is not committed. A finite
measurement exits 4 and cannot exit 0.

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
import hashlib
import math
import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

# Set before NumPy is imported. Importing this module does not import NumPy.
_THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
_PUBLISHED_ZERO_STEP_RMS = 0.03713648172611783
_PUBLISHED_INITIAL_RMS = 0.021483322678436757
_PUBLISHED_STEP1_RMS = 0.014198835443096334
_PUBLISHED_FINAL_RMS = 0.010906458907220248
_EXPECTED_ALPHAS = (0.03125, 0.125)
_EXPECTED_VECTORS = 275
_STAGE0_TIMEOUT_SECONDS = 600
# Per-call cap. Not an observed elapsed and not the session solver timeout.
_STAGE1_TIMEOUT_SECONDS = 300
_NOMINAL_SOLVER_TIMEOUT = 120.0
_SOLVER_TIMEOUT_STOP = 600.0
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
    try:
        info = numpy_module.show_config(mode="dicts")
    except TypeError:
        return "unknown"
    if not isinstance(info, dict):
        return "unknown"
    build = info.get("Build Dependencies")
    blas = build.get("blas") if isinstance(build, dict) else None
    if isinstance(blas, dict) and blas.get("name"):
        return str(blas["name"])
    return "unknown"


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
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise ValueError("wheel_unreadable") from exc
    with handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


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
        return _EXIT_FAILURE
    print("rms_gate_uncommitted")
    return _EXIT_GATE


def _committed_pin(wheel: Path, *, echo: bool) -> int | None:
    """Return an exit code, or None when the stack and committed tree pin match.

    An unset tree hash is printed and exits 3. Callers must not trace first.
    """
    _ensure_repo_path()
    stack = _stack_status(echo=echo)
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
    mismatch = _wheel_digest(wheel, WHEEL_SHA256)
    if mismatch:
        return mismatch
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
    return None


def _stage0(args: argparse.Namespace) -> int:
    _ensure_repo_path()
    if args.measure_worker:
        stack = _stack_status(echo=False)
        if stack:
            return stack
        from agent_skill_loop.problems.six_mirror_physics import THREAD_ENV_VARS, WHEEL_SHA256

        if tuple(THREAD_ENV_VARS) != _THREAD_ENV_VARS:
            print("physics_thread_pin_mismatch")
            return _EXIT_FAILURE
        mismatch = _wheel_digest(Path(args.wheel), WHEEL_SHA256)
        if mismatch:
            return mismatch
        return _measure_once()
    pin = _committed_pin(Path(args.wheel), echo=True)
    if pin is not None:
        return pin
    if not args.measure:
        print("rms_gate_uncommitted")
        return _EXIT_GATE
    return _measure_with_timeout(Path(args.wheel))


def _float_bits(value: float) -> bytes:
    return struct.pack("<d", float(value))


def _same_bits(left: float, right: float) -> bool:
    return _float_bits(left) == _float_bits(right)


def _finite_floats(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None
    numbers: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        numbers.append(number)
    return numbers


def _metric_float(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _metric_int(metrics: dict[str, Any], key: str) -> int | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _budget_exit(elapsed: float) -> int | None:
    """Print the session budget for a real elapsed. 1 means the experiment stops."""
    solver_timeout = 4.0 * elapsed
    if solver_timeout > _NOMINAL_SOLVER_TIMEOUT:
        print(f"solver_timeout={solver_timeout!r}")
        print("engine_wall_seconds>=8*solver_timeout+720")
        if solver_timeout > _SOLVER_TIMEOUT_STOP:
            print("experiment_stops")
            return _EXIT_FAILURE
        return None
    print("solver_timeout=120")
    print("engine_wall_seconds=1800")
    return None


def _read_finished_call(result: Any) -> dict[str, float] | int:
    """Record one finished evaluation, or return an exit code. Timeouts never arrive here."""
    metrics = result.metrics if isinstance(result.metrics, dict) else None
    if metrics is None:
        print("metrics_missing")
        return _EXIT_FAILURE
    objective = result.objective
    initial = _metric_float(metrics, "initial_rms_waves")
    final = _metric_float(metrics, "final_rms_waves")
    steps = _metric_int(metrics, "accepted_steps")
    vectors = _metric_int(metrics, "parameter_vectors_evaluated")
    alphas = _finite_floats(metrics.get("accepted_alphas"))
    accepted_rms = _finite_floats(metrics.get("accepted_rms_waves"))
    status = metrics.get("solver_status")
    if (
        isinstance(objective, bool)
        or not isinstance(objective, (int, float))
        or not math.isfinite(float(objective))
        or initial is None
        or final is None
        or steps is None
        or vectors is None
        or accepted_rms is None
    ):
        print("metrics_missing")
        return _EXIT_FAILURE
    objective = float(objective)
    print(f"parameter_vectors_evaluated={vectors}")
    print(f"accepted_alphas={alphas!r}")
    print(f"accepted_steps={steps}")
    print(f"solver_status={status!r}")
    print(f"initial_rms_waves={initial!r}")
    print(f"final_rms_waves={final!r}")
    if alphas != list(_EXPECTED_ALPHAS):
        print("accepted_alphas_mismatch")
        return _EXIT_FAILURE
    if steps != 2:
        print("accepted_steps_mismatch")
        return _EXIT_FAILURE
    if len(accepted_rms) != 2:
        print("metrics_missing")
        return _EXIT_FAILURE
    step1 = accepted_rms[0]
    print(f"step1_rms_waves={step1!r}")
    if status != "max_iterations":
        print("solver_status_mismatch")
        return _EXIT_FAILURE
    if not (objective > 0.0) or not (final > 0.0):
        print("nonpositive_final")
        return _EXIT_FAILURE
    if not _same_bits(final, objective) or not _same_bits(final, accepted_rms[1]):
        print("final_rms_mismatch")
        return _EXIT_FAILURE
    return {
        "elapsed": float(result.elapsed_seconds),
        "initial": initial,
        "step1": step1,
        "final": objective,
    }


def _stage1_calls(evaluate: Callable[[], Any]) -> int:
    """Score two already-pinned baseline calls. ``evaluate`` performs one trace."""
    parsed: list[dict[str, float]] = []
    for index in (1, 2):
        result = evaluate()
        print(f"call={index}")
        if result.error_code == "timeout":
            # The result's elapsed_seconds is the cap wait, not a finished measurement.
            print("stage1_timeout")
            return _EXIT_FAILURE
        if result.error_code or not result.valid:
            print(f"error_code={result.error_code}")
            return _EXIT_FAILURE
        elapsed_seconds = float(result.elapsed_seconds)
        if not math.isfinite(elapsed_seconds):
            print("invalid_elapsed")
            return _EXIT_FAILURE
        print(f"elapsed_seconds={elapsed_seconds!r}")
        outcome = _read_finished_call(result)
        if isinstance(outcome, int):
            return outcome
        parsed.append(outcome)
    elapsed = max(float(item["elapsed"]) for item in parsed)
    print(f"elapsed={elapsed!r}")
    print(f"parameter_vectors_expected={_EXPECTED_VECTORS}")
    stable = _same_bits(float(parsed[0]["final"]), float(parsed[1]["final"]))
    print(f"bit_stable={'true' if stable else 'false'}")
    if not stable:
        print(f"final_abs_difference={abs(float(parsed[0]['final']) - float(parsed[1]['final']))!r}")
    print(f"reference_initial={_PUBLISHED_INITIAL_RMS!r}")
    print(f"reference_step1={_PUBLISHED_STEP1_RMS!r}")
    print(f"reference_final={_PUBLISHED_FINAL_RMS!r}")
    print(f"reference_full_field={_PUBLISHED_ZERO_STEP_RMS!r}")
    initial_abs_error = max(abs(float(item["initial"]) - _PUBLISHED_INITIAL_RMS) for item in parsed)
    step1_abs_error = max(abs(float(item["step1"]) - _PUBLISHED_STEP1_RMS) for item in parsed)
    final_abs_error = max(abs(float(item["final"]) - _PUBLISHED_FINAL_RMS) for item in parsed)
    print(f"initial_abs_error={initial_abs_error!r}")
    print(f"step1_abs_error={step1_abs_error!r}")
    print(f"final_abs_error={final_abs_error!r}")
    # delta0 is stage 0's residual. Do not invent it and do not print a numeric d.
    print("d_rule=max(abs(delta0), initial_abs_error, step1_abs_error, final_abs_error)")
    print("delta0_not_measured")
    stopped = _budget_exit(elapsed)
    # RMS_ABS_GATE is unset. A finite measurement must not exit 0.
    print("rms_gate_uncommitted")
    if stopped is not None:
        return stopped
    return _EXIT_GATE


def _stage1(args: argparse.Namespace) -> int:
    pin = _committed_pin(Path(args.wheel), echo=True)
    if pin is not None:
        return pin
    from agent_skill_loop.evaluator import SubprocessEvaluator
    from agent_skill_loop.problems.six_mirror_newton import BASELINE_CODE, build_suite

    suite = build_suite(1)
    evaluator = SubprocessEvaluator(timeout=_STAGE1_TIMEOUT_SECONDS)
    return _stage1_calls(lambda: evaluator.evaluate(BASELINE_CODE, suite))


def main(argv: list[str] | None = None) -> int:
    _pin_threads()
    parser = argparse.ArgumentParser(
        description="Six-mirror pin checks. Does not call EoH, import torch, or read rank_key."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    stage0 = sub.add_parser("stage0", help="Hash the wheel, check the install, and optionally measure the zero step.")
    stage0.add_argument("--wheel", required=True, help="Path to the optics_gradient_optimization wheel. Not installed by this command.")
    stage0.add_argument("--measure", action="store_true", help="Trace mean_rms(x0) once, with a 600s timeout. Still fail-closed on RMS.")
    stage0.add_argument("--measure-worker", action="store_true", help=argparse.SUPPRESS)
    stage1 = sub.add_parser("stage1", help="Score baseline_code twice on the frozen coarse suite. Not a pytest.")
    stage1.add_argument("--wheel", required=True, help="Path to the optics_gradient_optimization wheel. Not installed by this command.")
    args = parser.parse_args(argv)
    if args.command == "stage0":
        return _stage0(args)
    if args.command == "stage1":
        return _stage1(args)
    return _EXIT_STACK


if __name__ == "__main__":
    raise SystemExit(main())
