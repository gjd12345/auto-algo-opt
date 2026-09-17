"""Import only the reviewed independent verifier into a private offline directory."""
import argparse
from pathlib import Path, PurePosixPath
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from optics_backend.artifacts import digest, save
from optics_backend.sources import PACKAGE_ROOT, TASKS

parser = argparse.ArgumentParser()
parser.add_argument("--archive", type=Path, required=True)
parser.add_argument("--source-sha256", required=True)
parser.add_argument("--task", choices=sorted(TASKS), required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if digest(args.archive.read_bytes()) != args.source_sha256:
    raise ValueError("SOURCE_PACKAGE_HASH_MISMATCH")
prefix = f"02_harbor_tasks/tasks/physical-sciences/physics/{args.task}/tests/"
payloads = {}
with zipfile.ZipFile(args.archive) as source:
    if len(source.namelist()) != len(set(source.namelist())):
        raise ValueError("DUPLICATE_ZIP_ENTRY")
    sums = {name.lstrip(" *"): sha for sha, name in (line.split(None, 1) for line in source.read(PACKAGE_ROOT + "SHA256SUMS.txt").decode().splitlines() if line.strip())}
    for entry in source.infolist():
        if not entry.filename.startswith(PACKAGE_ROOT + prefix) or entry.is_dir():
            continue
        relative = entry.filename[len(PACKAGE_ROOT + prefix):]
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative or entry.file_size > 8_000_000:
            raise ValueError("UNSAFE_VERIFIER_ENTRY")
        body = source.read(entry)
        if digest(body) != sums[entry.filename[len(PACKAGE_ROOT):]]:
            raise ValueError("VERIFIER_FILE_HASH_MISMATCH")
        payloads[relative] = body
args.output.mkdir(parents=True, exist_ok=False)
for name, body in payloads.items():
    target = args.output / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(body)
save(args.output / "import_receipt.json", {"source_sha256": args.source_sha256,
     "task": args.task, "files": {name: digest(body) for name, body in payloads.items()},
     "scope": "independent_verifier_only_not_search_context"})
print(f"Imported {len(payloads)} verified files; no provider or physics calls")
