"""Public commitment & isolated sealing for the Milestone 2 blind test suite ``cvrp_m2_blind_120``.

Design rule (audit boundary):
- The public commitment stored under ``benchmarks/cvrp_workbench/manifests/`` contains ONLY:
  stratification spec, generator version + source SHA-256, per-instance IDs + content SHA-256,
  and the overall suite SHA-256. It NEVER contains coordinates, demands, or the raw seed.
- The actual sealed instances and seed are written to an isolated gitignored location
  (default: ``.secrets/m2_blind/cvrp_m2_blind_120_sealed.json``, or any external path via
  ``--sealed-path``) and are NEVER registered in ``benchmarks/cvrp_workbench/registry.json``
  or default workbench/diagnostic loaders.
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
GENERATOR_VERSION = "cvrp_m2_blind_generator/v1"
BLIND_COMMITMENT_PATH = (
    _REPO / "benchmarks" / "cvrp_workbench" / "manifests" / "cvrp_m2_blind_120_commitment.json"
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


def seal_m2_blind_120(
    *,
    commitment_path: Path = BLIND_COMMITMENT_PATH,
    sealed_path: Path = DEFAULT_SEALED_BLIND_PATH,
    seed_token: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate ``cvrp_m2_blind_120``, write public commitment (hashes only) and isolated sealed file."""
    commitment_path = Path(commitment_path).resolve()
    sealed_path = Path(sealed_path).resolve()
    if not overwrite and (commitment_path.exists() or sealed_path.exists()):
        raise FileExistsError(
            f"Blind commitment or sealed file already exists: commitment={commitment_path.exists()}, sealed={sealed_path.exists()}"
        )

    # Fresh cryptographic random seed token by default so nobody can guess it from code.
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
            "instance_id": f"m2blind_{cell}-{idx:03d}",
            "cell": cell,
            "size": size,
            "spatial": spatial,
            "depot_style": depot_style,
            "capacity_level": cap_lvl,
            "demand_dist": ddist,
            "source_tag": "sealed_m2_blind_120",
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
        "schema_version": "cvrp-m2-blind-commitment/v1",
        "suite_id": SEALED_BLIND_SUITE_ID,
        "problem_family": "cvrp",
        "suite_role": "final_blind_acceptance",
        "exposure_status": "locked_m2_blind",
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "created_at": created_at,
        "generator_version": GENERATOR_VERSION,
        "generator_source_sha256": gen_sha,
        "instance_count": len(instances),
        "stratification_spec": strat_counts,
        "suite_content_sha256": suite_content_sha256,
        "seed_disclosure_policy": "withheld_in_isolated_sealed_storage",
        "instances": commitment_rows,
    }

    sealed_payload = {
        "schema_version": "cvrp-m2-blind-sealed/v1",
        "suite_id": SEALED_BLIND_SUITE_ID,
        "problem_family": "cvrp",
        "exposure_status": "locked_m2_blind",
        "distance_convention": "euc_2d_float",
        "vehicle_limit_policy": "unconstrained",
        "created_at": created_at,
        "generator_version": GENERATOR_VERSION,
        "generator_source_sha256": gen_sha,
        "sealed_seed_token": seed_token,
        "suite_content_sha256": suite_content_sha256,
        "instance_count": len(instances),
        "instances": instances,
    }

    commitment_path.parent.mkdir(parents=True, exist_ok=True)
    sealed_path.parent.mkdir(parents=True, exist_ok=True)
    commitment_path.write_text(
        json.dumps(commitment_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sealed_path.write_text(
        json.dumps(sealed_payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return {
        "ok": True,
        "suite_id": SEALED_BLIND_SUITE_ID,
        "instance_count": len(instances),
        "suite_content_sha256": suite_content_sha256,
        "generator_source_sha256": gen_sha,
        "commitment_path": str(commitment_path),
        "sealed_path": str(sealed_path),
    }


def verify_sealed_against_commitment(
    *,
    sealed_path: Path = DEFAULT_SEALED_BLIND_PATH,
    commitment_path: Path = BLIND_COMMITMENT_PATH,
) -> dict[str, Any]:
    """Verify an isolated sealed blind-test file matches its public commitment byte-for-byte."""
    commitment = json.loads(Path(commitment_path).read_text(encoding="utf-8"))
    sealed = json.loads(Path(sealed_path).read_text(encoding="utf-8"))

    # Guardrail: public commitment must never leak raw instance data or seeds
    forbidden_public_keys = {"sealed_seed_token", "seed", "depot", "customer_coordinates", "demands"}
    for key in forbidden_public_keys:
        if key in commitment:
            raise ValueError(f"public_commitment_leaked_key:{key}")
    for row in commitment.get("instances", []):
        for key in ("depot", "customer_coordinates", "demands", "seed", "reference_objective"):
            if key in row:
                raise ValueError(f"public_commitment_row_leaked_key:{key}")

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

    return {
        "ok": True,
        "suite_id": commitment["suite_id"],
        "instance_count": len(instances),
        "suite_content_sha256": recomputed_suite_sha,
        "verified_instances": len(instances),
    }


def assert_suite_not_m2_blind(suite_id: str | None, suite_meta: Mapping[str, Any] | None = None) -> None:
    """Reject accidental use of ``cvrp_m2_blind_120`` in dev/diagnostic/search pipelines."""
    if suite_id == SEALED_BLIND_SUITE_ID:
        raise ValueError("m2_blind_suite_forbidden_in_dev_pipeline")
    if isinstance(suite_meta, Mapping) and suite_meta.get("exposure_status") == "locked_m2_blind":
        raise ValueError("m2_blind_suite_forbidden_in_dev_pipeline")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_seal = sub.add_parser("seal", help="Generate and seal cvrp_m2_blind_120")
    p_seal.add_argument("--commitment-path", type=Path, default=BLIND_COMMITMENT_PATH)
    p_seal.add_argument("--sealed-path", type=Path, default=DEFAULT_SEALED_BLIND_PATH)
    p_seal.add_argument("--overwrite", action="store_true")

    p_ver = sub.add_parser("verify", help="Verify sealed blind file against public commitment")
    p_ver.add_argument("--commitment-path", type=Path, default=BLIND_COMMITMENT_PATH)
    p_ver.add_argument("--sealed-path", type=Path, default=DEFAULT_SEALED_BLIND_PATH)

    args = parser.parse_args(argv)
    if args.cmd == "seal":
        res = seal_m2_blind_120(
            commitment_path=args.commitment_path,
            sealed_path=args.sealed_path,
            overwrite=args.overwrite,
        )
    else:
        res = verify_sealed_against_commitment(
            sealed_path=args.sealed_path,
            commitment_path=args.commitment_path,
        )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
