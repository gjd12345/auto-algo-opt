"""Command line interface for the offline knowledge base."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    build_release,
    inventory_repository,
    read_entry,
    search_release,
    validate_release,
    validate_workspace,
    write_inventory,
)
from .literature import (
    dump_catalog,
    harvest_catalog,
    harvest_doi_seeds,
    ingest_screen,
    load_catalog,
    pack_family_batch,
    pack_screen,
    pack_screen_dir,
    queue_status,
    write_adapter_files,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge_tools",
        description="Build and inspect an offline optimisation knowledge base",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inventory = sub.add_parser("inventory", help="inventory tracked Git files at a fixed ref")
    inventory.add_argument("--repo", type=Path, required=True)
    inventory.add_argument("--ref", required=True)
    inventory.add_argument("--out", type=Path, required=True)

    validate = sub.add_parser("validate", help="validate workspace metadata and references")
    validate.add_argument("--workspace", type=Path, required=True)

    build = sub.add_parser("build", help="build and publish an immutable release")
    build.add_argument("--workspace", type=Path, required=True)
    build.add_argument("--store", type=Path, required=True)
    build.add_argument("--release-id")

    search = sub.add_parser("search", help="search a release index")
    search.add_argument("--release", type=Path, required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)

    read = sub.add_parser("read", help="read one entry from a fixed release")
    read.add_argument("--release", type=Path, required=True)
    read.add_argument("--id", required=True)

    release_validate = sub.add_parser("validate-release", help="validate an immutable published release")
    release_validate.add_argument("--release", type=Path, required=True)

    catalog = sub.add_parser("literature-catalog", help="write the frozen 30-subproblem catalog")
    catalog.add_argument("--out", type=Path, required=True)

    adapters = sub.add_parser("literature-adapters", help="write Plan-readable EoH adapter skeletons")
    adapters.add_argument("--out", type=Path, required=True)

    harvest = sub.add_parser("literature-harvest", help="fetch OpenAlex abstracts for catalog subproblems")
    harvest.add_argument("--catalog", type=Path, required=True)
    harvest.add_argument("--out", type=Path, required=True)
    harvest.add_argument("--family")
    harvest.add_argument("--limit-subproblems", type=int)
    harvest.add_argument("--per-subproblem", type=int, default=8)
    harvest.add_argument("--mailto")
    harvest.add_argument("--dry-run", action="store_true")
    harvest.add_argument("--provider", choices=("auto", "openalex", "crossref"), default="auto")
    harvest.add_argument("--pause", type=float, default=1.0)
    harvest.add_argument("--ids", help="comma-separated subproblem ids to harvest")
    harvest.add_argument(
        "--refresh-if-abstracts-lt",
        type=int,
        help="re-fetch a queue file when it has fewer than this many abstracts",
    )
    harvest.add_argument("--force", action="store_true", help="re-fetch even if a queue file already exists")

    dois = sub.add_parser("literature-harvest-dois", help="prepend canonical Crossref works by DOI")
    dois.add_argument("--catalog", type=Path, required=True)
    dois.add_argument("--out", type=Path, required=True)
    dois.add_argument("--mailto")
    dois.add_argument("--pause", type=float, default=0.25)

    pack = sub.add_parser("literature-pack-screen", help="pack one queue file into a grok-4.5 screen prompt")
    pack.add_argument("--queue", type=Path)
    pack.add_argument("--prompt-out", type=Path)
    pack.add_argument("--queue-dir", type=Path)
    pack.add_argument("--out-dir", type=Path)
    pack.add_argument("--family-batch", action="store_true",
                      help="one grok-4.5 prompt for unscreened subproblems in --queue-dir")
    pack.add_argument("--require-abstract", action="store_true",
                      help="omit subproblems that have no abstract-bearing works")
    pack.add_argument("--skip-classified", action="store_true",
                      help="omit subproblems already selected in a screen JSON")
    pack.add_argument("--only-eoh-status", help="only pack this eoh_map.status, e.g. possible")

    ingest = sub.add_parser("literature-ingest", help="turn a screen JSON into knowledge drafts")
    ingest.add_argument("--queue", type=Path, required=True)
    ingest.add_argument("--screen", type=Path, required=True)
    ingest.add_argument("--drafts", type=Path, required=True)
    ingest.add_argument("--promote-workspace", type=Path)

    status = sub.add_parser("literature-status", help="summarise catalog vs harvested vs screened")
    status.add_argument("--catalog", type=Path, required=True)
    status.add_argument("--queue", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    args = _parser().parse_args(argv)
    try:
        if args.command == "inventory":
            payload = inventory_repository(args.repo, args.ref)
            json_path, markdown_path = write_inventory(args.out, payload)
            result = {
                "ok": True,
                "json": str(json_path),
                "markdown": str(markdown_path),
                "ref_resolved": payload["ref_resolved"],
                "tracked_file_count": payload["tracked_file_count"],
                "run_containers": len(payload["runs"]),
            }
        elif args.command == "validate":
            result = validate_workspace(args.workspace)
        elif args.command == "build":
            result = build_release(args.workspace, args.store, args.release_id)
        elif args.command == "search":
            result = search_release(args.release, args.query, args.limit)
        elif args.command == "read":
            result = read_entry(args.release, args.id)
        elif args.command == "validate-release":
            result = validate_release(args.release)
        elif args.command == "literature-catalog":
            result = dump_catalog(args.out)
        elif args.command == "literature-adapters":
            result = write_adapter_files(args.out)
        elif args.command == "literature-harvest":
            catalog = load_catalog(args.catalog)
            result = harvest_catalog(
                catalog,
                args.out,
                family=args.family,
                limit_subproblems=args.limit_subproblems,
                per_subproblem=args.per_subproblem,
                mailto=args.mailto,
                dry_run=args.dry_run,
                provider=args.provider,
                pause_seconds=args.pause,
                only_ids=[item.strip() for item in args.ids.split(",") if item.strip()] if args.ids else None,
                refresh_if_abstracts_lt=args.refresh_if_abstracts_lt,
                force=args.force,
            )
        elif args.command == "literature-harvest-dois":
            result = harvest_doi_seeds(
                load_catalog(args.catalog),
                args.out,
                mailto=args.mailto,
                pause_seconds=args.pause,
            )
        elif args.command == "literature-pack-screen":
            if args.family_batch:
                if not args.queue_dir or not args.prompt_out:
                    raise ValueError("family-batch requires --queue-dir and --prompt-out")
                result = pack_family_batch(
                    args.queue_dir,
                    args.prompt_out,
                    skip_screened=not args.skip_classified,
                    skip_classified=args.skip_classified,
                    require_abstract=args.require_abstract,
                    works_per_subproblem=3,
                    abstract_clip=380,
                    only_eoh_status=args.only_eoh_status,
                )
            elif args.queue_dir:
                if not args.out_dir:
                    raise ValueError("literature-pack-screen --queue-dir requires --out-dir")
                result = pack_screen_dir(args.queue_dir, args.out_dir)
            else:
                if not args.queue or not args.prompt_out:
                    raise ValueError("literature-pack-screen requires --queue and --prompt-out")
                result = pack_screen(args.queue, args.prompt_out)
        elif args.command == "literature-ingest":
            result = ingest_screen(
                args.queue,
                args.screen,
                args.drafts,
                promote_workspace=args.promote_workspace,
            )
        elif args.command == "literature-status":
            result = queue_status(load_catalog(args.catalog), args.queue)
        else:  # pragma: no cover
            raise AssertionError(args.command)
    except (OSError, ValueError, KeyError, FileNotFoundError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and result.get("ok") is False:
        return 1
    return 0

