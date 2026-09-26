"""Pinned NumPy wavefront for one declared six-mirror sampling.

``optics_optim`` is imported inside functions so hermetic tests can import the
evaluator without SciPy. ``TREE_SHA256`` stays unset until a stage-0
measurement commits it. An unset or mismatched pin does not trace.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

WHEEL_SHA256 = "ba8d2b9902bf0ba1260e1d8df32218b256f180499f6fd0ce2061444b917282fa"
# Filled only after tools/verify_six_mirror_pin.py prints a measurement.
TREE_SHA256: str | None = None
THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)

_DISTRIBUTION_NAME = "optics-gradient-optimization"
_DISTRIBUTION_VERSION = "0.1.0"
_ACTIVE_COORDINATES = 62


def _committed_pin(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip().lower()
        if text:
            return text
    return None


def _import_optics_optim() -> Any:
    try:
        import optics_optim
    except ImportError as exc:
        raise ValueError("physics_package_missing") from exc
    return optics_optim


def _require_single_thread() -> None:
    for name in THREAD_ENV_VARS:
        if os.environ.get(name) != "1":
            raise ValueError("physics_thread_pin_mismatch")


def _recorded_wheel_sha256(dist: Any) -> str | None:
    try:
        text = dist.read_text("direct_url.json")
    except (OSError, UnicodeError) as exc:
        raise ValueError("physics_pin_mismatch") from exc
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("physics_pin_mismatch") from exc
    archive = payload.get("archive_info") if isinstance(payload, dict) else None
    if not isinstance(archive, dict):
        return None
    hashes = archive.get("hashes")
    if isinstance(hashes, dict) and hashes.get("sha256"):
        return str(hashes["sha256"]).strip().lower()
    legacy = archive.get("hash")
    if isinstance(legacy, str) and legacy.startswith("sha256="):
        return legacy.split("=", 1)[1].strip().lower()
    return None


def _require_distribution(module: Any) -> None:
    if getattr(module, "__name__", None) != "optics_optim":
        raise ValueError("physics_pin_mismatch")
    if getattr(module, "__version__", None) != _DISTRIBUTION_VERSION:
        raise ValueError("physics_pin_mismatch")
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        dist = distribution(_DISTRIBUTION_NAME)
    except PackageNotFoundError as exc:
        raise ValueError("physics_pin_mismatch") from exc
    if dist.version != _DISTRIBUTION_VERSION:
        raise ValueError("physics_pin_mismatch")
    recorded = _recorded_wheel_sha256(dist)
    if recorded is not None and recorded != WHEEL_SHA256:
        raise ValueError("physics_pin_mismatch")


def hash_installed_tree(package_root: Path) -> str:
    """Hash sorted package ``*.py`` plus ``data/v1/*.mat`` and ``data/v2/*.mat``.

    This digest is not the wheel-file SHA-256. Callers must not compare the
    unpacked bytes to ``WHEEL_SHA256``.
    """
    root = package_root.resolve()
    py_files = [
        path
        for path in root.rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    mats: list[Path] = []
    for version in ("v1", "v2"):
        directory = root / "data" / version
        found = [path for path in directory.glob("*.mat") if path.is_file()] if directory.is_dir() else []
        if not found:
            raise ValueError("physics_pin_mismatch")
        mats.extend(found)
    if not py_files:
        raise ValueError("physics_pin_mismatch")
    files = sorted(set(py_files + mats), key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256()
    for path in files:
        payload = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def _installed_tree_sha256(module: Any) -> str:
    file_name = getattr(module, "__file__", None)
    if not isinstance(file_name, str) or not file_name:
        raise ValueError("physics_pin_mismatch")
    return hash_installed_tree(Path(file_name).resolve().parent)


def measure_installed_tree_sha256() -> str:
    """Return the installed-tree digest without tracing and without inventing one."""
    module = _import_optics_optim()
    _require_distribution(module)
    return _installed_tree_sha256(module)


def _require_tree_pin(module: Any, tree_sha256: object) -> None:
    expected = _committed_pin(TREE_SHA256)
    passed = _committed_pin(tree_sha256)
    if expected is None or passed is None or passed != expected:
        raise ValueError("physics_pin_mismatch")
    if _installed_tree_sha256(module) != expected:
        raise ValueError("physics_pin_mismatch")


def _field_indices(value: object) -> list[int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or not value:
        raise ValueError("invalid_physics_sampling")
    indices: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError("invalid_physics_sampling")
        indices.append(item)
    return indices


class PinnedNumpyWavefront:
    """One pinned NumPy sampling. The search suite and stage 0 both use this class."""

    def __init__(
        self,
        *,
        prescription_version: str,
        field_indices: list[int],
        sample_d: int,
        constraints: bool,
        initial_scale: float,
        wheel_sha256: str,
        tree_sha256: str,
    ) -> None:
        if (
            constraints is not False
            or isinstance(initial_scale, bool)
            or initial_scale != 1.0
            or prescription_version != "v2"
            or isinstance(sample_d, bool)
            or not isinstance(sample_d, int)
        ):
            raise ValueError("invalid_physics_sampling")
        if not isinstance(wheel_sha256, str) or wheel_sha256.strip().lower() != WHEEL_SHA256:
            raise ValueError("physics_pin_mismatch")
        self._field_indices = _field_indices(field_indices)
        self._sample_d = sample_d
        try:
            module = _import_optics_optim()
            _require_single_thread()
            _require_distribution(module)
            _require_tree_pin(module, tree_sha256)
            self._finish_load(module)
        except ImportError as exc:
            raise ValueError("physics_package_missing") from exc

    def _finish_load(self, module: Any) -> None:
        try:
            prescription = module.load_prescription(version="v2")
        except ValueError as exc:
            if "N_Stop" in str(exc):
                raise ValueError("n_stop_mismatch") from exc
            raise
        if int(prescription.n_stop) != 4:
            raise ValueError("n_stop_mismatch")
        from optics_optim.numpy_model import NumpyOpticalModel
        from optics_optim.parameters import decode

        # Bundled v2 encode is the start. initial_scale is a gate, not a multiplier.
        self._distance_ref = np.array(prescription.distance, dtype=np.float64, copy=True)
        self._output_ref = np.array(prescription.output_data, dtype=np.float64, copy=True)
        encoded = module.encode(
            np.array(self._distance_ref, dtype=np.float64, copy=True),
            np.array(self._output_ref, dtype=np.float64, copy=True),
            "numpy",
        )
        self.x0 = np.array(encoded, dtype=np.float64).reshape(-1).copy()
        if self.x0.shape != (_ACTIVE_COORDINATES,) or not np.all(np.isfinite(self.x0)):
            raise ValueError("invalid_instance")
        self._decode = decode
        self._model = NumpyOpticalModel(prescription, self._field_indices, self._sample_d)

    def mean_rms(self, x: np.ndarray) -> np.ndarray:
        """Return one mean RMS per design row.

        ``run_diagonal_newton`` passes shape ``(n, 62)``. A single ``(62,)``
        vector is one row. Finite optical values pass through; nonfinite
        optical values become +inf. Each call decodes new arrays.
        """
        points = np.array(x, dtype=np.float64, copy=True)
        if points.ndim == 1:
            points = points.reshape(1, -1)
        if points.ndim != 2 or points.shape[1] != _ACTIVE_COORDINATES or points.shape[0] < 1:
            raise ValueError("invalid_instance")
        values = np.full(points.shape[0], np.inf, dtype=np.float64)
        finite = np.isfinite(points).all(axis=1)
        if not np.any(finite):
            return values
        distance = np.array(self._distance_ref, dtype=np.float64, copy=True)
        output_data = np.array(self._output_ref, dtype=np.float64, copy=True)
        decoded_distance, decoded_output = self._decode(points[finite], distance, output_data, "numpy")
        losses = self._model.evaluate(decoded_distance, decoded_output).losses
        rms = np.asarray(np.mean(losses, axis=0), dtype=np.float64).reshape(-1)
        if rms.shape != (int(np.count_nonzero(finite)),):
            raise ValueError("invalid_instance")
        values[finite] = np.where(np.isfinite(rms), rms, np.inf)
        return values
