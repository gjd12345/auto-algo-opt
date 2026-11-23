"""Public commitment & isolated external-custody sealing for blind test suites.

Supports ``cvrp_m2_blind_120``, ``cvrp_m3_blind_120``, and future sealed suites.

Design rule (audit boundary):
- The public commitment stored under ``benchmarks/cvrp_workbench/manifests/`` contains ONLY:
  stratification spec, generator version + source SHA-256, per-instance IDs + content SHA-256,
  and the overall suite SHA-256. It NEVER contains coordinates, demands, or the raw seed.
- The actual sealed instances and seed MUST be written to an external restricted-custody path
  outside the repository (via ``require_external_custody_path``) and are NEVER registered in
  ``benchmarks/cvrp_workbench/registry.json`` or accessible to dev/diagnostic/sandbox roles.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Mapping

from agent_skill_loop.cvrp_workbench.solvers import evaluate_algorithm_on_instance

_REPO = Path(__file__).resolve().parents[2]

SEALED_BLIND_SUITE_ID = "cvrp_m2_blind_120"
SEALED_M3_BLIND_SUITE_ID = "cvrp_m3_blind_120"
SEALED_M32_BLIND_SUITE_ID = "cvrp_m32_blind_120"
ALL_BLIND_SUITE_IDS: frozenset[str] = frozenset({
    SEALED_BLIND_SUITE_ID,
    SEALED_M3_BLIND_SUITE_ID,
    SEALED_M32_BLIND_SUITE_ID,
})
GENERATOR_VERSION = "cvrp_m2_blind_generator/v1"
M3_GENERATOR_VERSION = "cvrp_m3_blind_generator/v1"
BLIND_COMMITMENT_PATH = (
    _REPO / "benchmarks" / "cvrp_workbench" / "manifests" / "cvrp_m2_blind_120_commitment.json"
)
M3_BLIND_COMMITMENT_PATH = (
    _REPO / "benchmarks" / "cvrp_workbench" / "manifests" / "cvrp_m3_blind_120_commitment.json"
)
DEFAULT_SEALED_BLIND_PATH = _REPO / ".secrets" / "m2_blind" / "cvrp_m2_blind_120_sealed.json"

_CAPACITY_LEVELS = {"loose": 45, "tight": 28}


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _generator_source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _seeded_rng(seed_token: str, cell: str, index: int) -> random.Random:
    digest = hashlib.sha256(f"{seed_token}|{cell}|{index}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _gen_coords(spatial: str, rng: random.Random, size: int) -> list[list[float]]:
    if spatial == "uniform":
        return [[round(rng.random(), 8), round(rng.random(), 8)] for _ in range(size)]
    if spatial == "clustered":
        centres = [(rng.random(), rng.random()) for _ in range(4)]
        coords = []
        for _ in range(size):
            cx, cy = centres[rng.randrange(4)]
            coords.append([
                round(min(1.0, max(0.0, rng.gauss(cx, 0.06))), 8),
                round(min(1.0, max(0.0, rng.gauss(cy, 0.06))), 8),
            ])
        return coords
    if spatial == "mixed":
        n_cl = size // 2
        n_un = size - n_cl
        centres = [(rng.random(), rng.random()) for _ in range(4)]
        coords = []
        for _ in range(n_cl):
            cx, cy = centres[rng.randrange(4)]
            coords.append([
                round(min(1.0, max(0.0, rng.gauss(cx, 0.06))), 8),
                round(min(1.0, max(0.0, rng.gauss(cy, 0.06))), 8),
            ])
        for _ in range(n_un):
            coords.append([round(rng.random(), 8), round(rng.random(), 8)])
        rng.shuffle(coords)
        return coords
    raise ValueError(f"unsupported_spatial:{spatial}")


def _gen_demands(dist: str, rng: random.Random, size: int) -> list[int]:
    if dist == "uniform":
        return [rng.randint(1, 9) for _ in range(size)]
    if dist == "bimodal":
        choices = (1, 2, 8, 9)
        return [choices[rng.randrange(4)] for _ in range(size)]
    raise ValueError(f"unsupported_demand_dist:{dist}")


def build_m2_blind_120_design() -> list[tuple[int, str, str, str, str]]:
    """Return the exact 120-instance stratified factorial design across n in {50, 100, 200}.

    Each size (50, 100, 200) receives 40 instances:
      - Full 24-cell factorial: 3 spatial x 2 depot x 2 capacity x 2 demand = 24
      - Balanced 16-cell secondary replicate (cycling spatial across the 16 non-spatial cells)
    Total = 3 * 40 = 120 instances.
    """
    full_24 = [
        (sp, dp, cp, dd)
        for sp in ("uniform", "clustered", "mixed")
        for dp in ("centre", "eccentric")
        for cp in ("loose", "tight")
        for dd in ("uniform", "bimodal")
    ]
    base_16 = [
        (dp, cp, dd)
        for dp in ("centre", "eccentric")
        for cp in ("loose", "tight")
        for dd in ("uniform", "bimodal")
    ]
    spatial_cycle = ("uniform", "clustered", "mixed")
    design: list[tuple[int, str, str, str, str]] = []
    for s_idx, size in enumerate((50, 100, 200)):
        for sp, dp, cp, dd in full_24:
            design.append((size, sp, dp, cp, dd))
        for r_idx in range(16):
            dp, cp, dd = base_16[r_idx % len(base_16)]
            sp = spatial_cycle[(r_idx + s_idx) % 3]
            design.append((size, sp, dp, cp, dd))
    assert len(design) == 120
    return design


def _seal_cvrp_blind_120_suite(
    *,
    suite_id: str,
    exposure_status: str,
    schema_prefix: str,
    id_prefix: str,
    source_tag: str,
    generator_version: str,
    commitment_path: Path,
    sealed_path: Path,
    seed_token: str | None = None,
    overwrite: bool = False,
    require_external_custody: bool = False,
    repo_root: Path = _REPO,
) -> dict[str, Any]:
    """Parameterized 120-instance blind CVRP suite generator and cryptographic commitment writer."""
    commitment_path = Path(commitment_path).resolve()
    sealed_path = require_external_custody_path(sealed_path, repo_root=repo_root) if require_external_custody else Path(sealed_path).resolve()
    if commitment_path == sealed_path:
        raise ValueError("blind_commitment_and_private_paths_must_differ")
    if not overwrite and (commitment_path.exists() or sealed_path.exists()):
        raise FileExistsError(
            f"Blind commitment or sealed file already exists: commitment={commitment_path.exists()}, sealed={sealed_path.exists()}"
        )

    if seed_token is None:
        seed_token = hashlib.sha256(random.SystemRandom().randbytes(32)).hexdigest()

    design = build_m2_blind_120_design()
    instances: list[dict[str, Any]] = []
    commitment_rows: list[dict[str, Any]] = []

    strat_counts: dict[str, dict[str, int]] = {
        "by_size": {},
        "by_spatial": {},
        "by_depot_style": {},
        "by_capacity_level": {},
        "by_demand_dist": {},
    }

    for idx, (size, spatial, depot_style, cap_lvl, ddist) in enumerate(design):
        cell = f"n{size}_{spatial}_{depot_style}_{cap_lvl}_{ddist}"
        rng = _seeded_rng(seed_token, cell, idx)
        depot = [0.5, 0.5] if depot_style == "centre" else [0.05, 0.95]
        inst: dict[str, Any] = {
            "instance_id": f"{id_prefix}_{cell}-{idx:03d}",
            "cell": cell,
            "size": size,
            "spatial": spatial,
            "depot_style": depot_style,
            "capacity_level": cap_lvl,
            "demand_dist": ddist,
            "source_tag": source_tag,
            "depot": depot,
            "customer_coordinates": _gen_coords(spatial, rng, size),
            "demands": _gen_demands(ddist, rng, size),
            "capacity": _CAPACITY_LEVELS[cap_lvl],
        }
        nn_res = evaluate_algorithm_on_instance("nn", inst, distance_convention="euc_2d_float", record_trace=False)
        if not nn_res["valid"] or nn_res["tour_length"] is None:
            raise RuntimeError(f"nn_reference_failed:{inst['instance_id']}")
        inst["reference_objective"] = float(nn_res["tour_length"])
        inst["reference_kind"] = "solver_reference"

        inst_sha = _sha256_payload(inst)
        instances.append(inst)
        commitment_rows.append({
            "instance_id": inst["instance_id"],
            "cell": cell,
            "size": size,
            "spatial": spatial,
            "depot_style": depot_style,
            "capacity_level": cap_lvl,
            "demand_dist": ddist,
            "instance_sha256": inst_sha,
        })

        strat_counts["by_size"][str(size)] = strat_counts["by_size"].get(str(size), 0) + 1
        strat_counts["by_spatial"][spatial] = strat_counts["by_spatial"].get(spatial, 0) + 1
        strat_counts["by_depot_style"][depot_style] = strat_counts["by_depot_style"].get(depot_style, 0) + 1
        strat_counts["by_capacity_level"][cap_lvl] = strat_counts["by_capacity_level"].get(cap_lvl, 0) + 1
        strat_counts["by_demand_dist"][ddist] = strat_counts["by_demand_dist"].get(ddist, 0) + 1

    suite_content_sha256 = _sha256_payload(instances)
    gen_sha = _generator_source_sha256()
    created_at = _utc_now()

    commitment_payload = {
        "schema_version": f"{schema_prefix}-commitment/v1",
        "suite_id": suite_id,
        "problem_family": "cvrp",
        "suite_role": "final_blind_acceptance",
        "exposure_status": exposure_status,
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "created_at": created_at,
        "generator_version": generator_version,
        "generator_source_sha256": gen_sha,
        "instance_count": len(instances),
        "stratification_spec": strat_counts,
        "suite_content_sha256": suite_content_sha256,
        "seed_disclosure_policy": "withheld_in_external_restricted_custody",
        "instances": commitment_rows,
    }

    sealed_payload = {
        "schema_version": f"{schema_prefix}-sealed/v1",
        "suite_id": suite_id,
        "problem_family": "cvrp",
        "exposure_status": exposure_status,
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "created_at": created_at,
        "generator_version": generator_version,
        "generator_source_sha256": gen_sha,
        "sealed_seed_token": seed_token,
        "suite_content_sha256": suite_content_sha256,
        "instance_count": len(instances),
        "instances": instances,
    }

    commitment_path.parent.mkdir(parents=True, exist_ok=True)
    sealed_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with sealed_path.open(mode, encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(sealed_payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    with commitment_path.open(mode, encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(commitment_payload, ensure_ascii=False, indent=2) + "\n")

    return {
        "ok": True,
        "suite_id": suite_id,
        "instance_count": len(instances),
        "suite_content_sha256": suite_content_sha256,
        "generator_source_sha256": gen_sha,
        "commitment_path": str(commitment_path),
        "sealed_path": str(sealed_path),
    }


def seal_m2_blind_120(
    *,
    commitment_path: Path = BLIND_COMMITMENT_PATH,
    sealed_path: Path,
    seed_token: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate ``cvrp_m2_blind_120``, write public commitment (hashes only) and isolated sealed file."""
    return _seal_cvrp_blind_120_suite(
        suite_id=SEALED_BLIND_SUITE_ID,
        exposure_status="locked_m2_blind",
        schema_prefix="cvrp-m2-blind",
        id_prefix="m2blind",
        source_tag="sealed_m2_blind_120",
        generator_version=GENERATOR_VERSION,
        commitment_path=commitment_path,
        sealed_path=sealed_path,
        seed_token=seed_token,
        overwrite=overwrite,
        require_external_custody=False,
    )


def seal_m3_blind_120(
    *,
    commitment_path: Path = M3_BLIND_COMMITMENT_PATH,
    sealed_path: Path,
    seed_token: str | None = None,
    overwrite: bool = False,
    require_external_custody: bool = True,
    repo_root: Path = _REPO,
) -> dict[str, Any]:
    """Generate ``cvrp_m3_blind_120`` with mandatory external custody for the sealed file."""
    return _seal_cvrp_blind_120_suite(
        suite_id=SEALED_M3_BLIND_SUITE_ID,
        exposure_status="locked_m3_blind",
        schema_prefix="cvrp-m3-blind",
        id_prefix="m3blind",
        source_tag="sealed_m3_blind_120",
        generator_version=M3_GENERATOR_VERSION,
        commitment_path=commitment_path,
        sealed_path=sealed_path,
        seed_token=seed_token,
        overwrite=overwrite,
        require_external_custody=require_external_custody,
        repo_root=repo_root,
    )


def read_public_blind_commitment(
    commitment_path: Path = BLIND_COMMITMENT_PATH,
    *,
    expected_sha256: str | None = None,
    expected_suite_id: str | None = None,
) -> dict[str, Any]:
    """Read and check the public commitment without opening the private instances."""
    payload = Path(commitment_path).read_bytes()
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("pre_blind_commitment_file_hash_mismatch")
    commitment = json.loads(payload)

    # Guardrail: public commitment must never leak raw instance data or seeds
    forbidden_public_keys = {"sealed_seed_token", "seed", "depot", "customer_coordinates", "demands"}
    for key in forbidden_public_keys:
        if key in commitment:
            raise ValueError(f"public_commitment_leaked_key:{key}")
    for row in commitment.get("instances", []):
        for key in ("depot", "customer_coordinates", "demands", "seed", "reference_objective"):
            if key in row:
                raise ValueError(f"public_commitment_row_leaked_key:{key}")
    sid = commitment.get("suite_id")
    allowed_ids = {expected_suite_id} if expected_suite_id is not None else ALL_BLIND_SUITE_IDS
    if sid not in allowed_ids or len(commitment["instances"]) != commitment["instance_count"]:
        raise ValueError("invalid_blind_commitment")
    return commitment


def require_external_custody_path(path: Path, repo_root: Path = _REPO) -> Path:
    path = Path(path).resolve()
    if path.is_relative_to(Path(repo_root).resolve()):
        raise ValueError("blind_custody_path_must_be_outside_repository")
    return path


def verify_sealed_against_commitment(
    *,
    sealed_path: Path,
    commitment_path: Path = BLIND_COMMITMENT_PATH,
) -> dict[str, Any]:
    """Verify the private instances against their public content digests."""
    _, _, verification = read_verified_blind_payload(sealed_path=sealed_path, commitment_path=commitment_path)
    return verification


def read_verified_blind_payload(
    *, sealed_path: Path, commitment_path: Path, expected_commitment_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return the exact private and public payloads used by verification."""
    commitment = read_public_blind_commitment(commitment_path, expected_sha256=expected_commitment_sha256)
    sealed = json.loads(Path(sealed_path).read_text(encoding="utf-8"))
    for field in ("suite_id", "distance_convention", "vehicle_limit_policy"):
        if sealed.get(field) != commitment.get(field):
            raise ValueError(f"blind_protocol_field_mismatch:{field}")

    instances = sealed.get("instances", [])
    comm_rows = commitment.get("instances", [])
    if len(instances) != len(comm_rows) or len(instances) != int(commitment["instance_count"]):
        raise ValueError("blind_instance_count_mismatch")

    recomputed_suite_sha = _sha256_payload(instances)
    if recomputed_suite_sha != commitment["suite_content_sha256"]:
        raise ValueError("blind_suite_sha256_mismatch")

    for inst, comm in zip(instances, comm_rows):
        if inst["instance_id"] != comm["instance_id"]:
            raise ValueError(f"blind_instance_id_mismatch:{inst['instance_id']}!={comm['instance_id']}")
        if _sha256_payload(inst) != comm["instance_sha256"]:
            raise ValueError(f"blind_instance_sha256_mismatch:{inst['instance_id']}")

    return sealed, commitment, {
        "ok": True,
        "suite_id": commitment["suite_id"],
        "instance_count": len(instances),
        "suite_content_sha256": recomputed_suite_sha,
        "verified_instances": len(instances),
    }


def assert_suite_not_blind(suite_id: str | None, suite_meta: Mapping[str, Any] | None = None) -> None:
    """Reject accidental use of ANY sealed blind suite (M2/M3/M3.2/locked) in dev/diagnostic/search roles."""
    if suite_id == SEALED_BLIND_SUITE_ID or (
        isinstance(suite_meta, Mapping) and suite_meta.get("exposure_status") == "locked_m2_blind"
    ):
        raise ValueError(f"m2_blind_suite_forbidden_in_dev_pipeline:{suite_id or 'locked_m2_blind'}")
    if suite_id in ALL_BLIND_SUITE_IDS or (
        isinstance(suite_id, str) and suite_id.startswith("locked_") and suite_id.endswith("_blind")
    ):
        raise ValueError(f"blind_suite_forbidden_in_dev_pipeline:{suite_id}")
    if isinstance(suite_meta, Mapping):
        exp = str(suite_meta.get("exposure_status") or "")
        role = str(suite_meta.get("suite_role") or "")
        if (exp.startswith("locked_") and exp.endswith("_blind")) or role == "final_blind_acceptance":
            raise ValueError(f"blind_suite_forbidden_in_dev_pipeline:{suite_id or exp or role}")


def assert_suite_not_m2_blind(suite_id: str | None, suite_meta: Mapping[str, Any] | None = None) -> None:
    """Backward-compatible wrapper delegating to ``assert_suite_not_blind``."""
    assert_suite_not_blind(suite_id, suite_meta)


def assert_suite_allowed_for_interactive_role(
    suite_id: str | None,
    suite_meta: Mapping[str, Any] | None = None,
    *,
    role: str = "interactive_sandbox",
) -> None:
    """Enforce split isolation: interactive sandboxes/archives may read dev_24, NEVER blind or selection splits."""
    assert_suite_not_blind(suite_id, suite_meta)
    if role in {"interactive_sandbox", "feedback_archive", "diagnostic_interactive"}:
        if suite_id == "cvrp_select_multiscale_64" or (
            isinstance(suite_meta, Mapping) and suite_meta.get("suite_role") == "selection"
        ):
            raise ValueError(f"selection_suite_forbidden_in_interactive_role:{suite_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_seal = sub.add_parser("seal", help="Generate and seal a blind CVRP 120-instance suite")
    p_seal.add_argument(
        "--suite-id",
        default=SEALED_M3_BLIND_SUITE_ID,
        choices=(SEALED_BLIND_SUITE_ID, SEALED_M3_BLIND_SUITE_ID),
    )
    p_seal.add_argument("--commitment-path", type=Path, default=None)
    p_seal.add_argument("--sealed-path", type=Path, required=True)

    p_ver = sub.add_parser("verify", help="Verify sealed blind file against public commitment")
    p_ver.add_argument(
        "--suite-id",
        default=SEALED_M3_BLIND_SUITE_ID,
        choices=(SEALED_BLIND_SUITE_ID, SEALED_M3_BLIND_SUITE_ID),
    )
    p_ver.add_argument("--commitment-path", type=Path, default=None)
    p_ver.add_argument("--sealed-path", type=Path, required=True)

    args = parser.parse_args(argv)
    default_comm = M3_BLIND_COMMITMENT_PATH if args.suite_id == SEALED_M3_BLIND_SUITE_ID else BLIND_COMMITMENT_PATH
    comm_path = args.commitment_path or default_comm
    ext_sealed = require_external_custody_path(args.sealed_path)
    if args.cmd == "seal":
        if args.suite_id == SEALED_M3_BLIND_SUITE_ID:
            res = seal_m3_blind_120(commitment_path=comm_path, sealed_path=ext_sealed)
        else:
            res = seal_m2_blind_120(commitment_path=comm_path, sealed_path=ext_sealed)
    else:
        res = verify_sealed_against_commitment(sealed_path=ext_sealed, commitment_path=comm_path)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
