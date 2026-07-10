#!/usr/bin/env python3
"""准备 Q3 BP 消融所需的 HiFo held-out 数据。

默认从固定的 HiFo 上游提交下载 1k、5k、10k 三份 C100 测试集。也可以从
已有的 HiFo 工作树导入，或仅校验目标目录中的现有文件。所有写入都先在临时
文件中完成 SHA-256 校验，避免网络中断或错误数据覆盖已验证资产。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Iterable


UPSTREAM_REPOSITORY = "Challenger-XJTU/HiFo-Prompt"
UPSTREAM_COMMIT = "e64ce9edbfb4c8ebffd652b785b0c87261785586"
UPSTREAM_DATA_DIRECTORY = Path("examples/bp_online/evaluation/testingdata")
RAW_BASE_URL = (
    f"https://raw.githubusercontent.com/{UPSTREAM_REPOSITORY}/{UPSTREAM_COMMIT}/"
    f"{UPSTREAM_DATA_DIRECTORY.as_posix()}"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "eoh_rag_workspace/problems/bp_online/held_out"


class DatasetPreparationError(RuntimeError):
    """表示数据缺失、下载失败或校验不通过。"""


@dataclass(frozen=True)
class DatasetSpec:
    """描述一份固定上游数据及其仓内目标名称。"""

    size_label: str
    upstream_filename: str
    destination_filename: str
    sha256: str


DATASET_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        size_label="1k",
        upstream_filename="test_dataset_1k.pkl",
        destination_filename="hifo_1k_C100.pkl",
        sha256="889fbc931ac7a5f94895e1e2dfa2cf4d762969bbfbfe0902f93867b74d363795",
    ),
    DatasetSpec(
        size_label="5k",
        upstream_filename="test_dataset_5k.pkl",
        destination_filename="hifo_5k_C100.pkl",
        sha256="172f86591a29ccba94ffc6b711b2f8283aff560c2c9718c9f3c23c93fda0d668",
    ),
    DatasetSpec(
        size_label="10k",
        upstream_filename="test_dataset_10k.pkl",
        destination_filename="hifo_10k_C100.pkl",
        sha256="cecc30e87b286fd6223ffb51624769242d306be6b383c843d6dadc57f3b81eb3",
    ),
)


def calculate_sha256(path: Path) -> str:
    """流式计算文件 SHA-256，避免把较大的数据文件一次性读入内存。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_dataset(path: Path, spec: DatasetSpec) -> None:
    """校验数据文件存在且哈希与固定上游提交一致。"""

    if not path.is_file():
        raise DatasetPreparationError(f"{spec.size_label} dataset is missing: {path}")

    actual_hash = calculate_sha256(path)
    if actual_hash != spec.sha256:
        raise DatasetPreparationError(
            f"{spec.size_label} dataset SHA-256 mismatch: expected {spec.sha256}, "
            f"got {actual_hash} ({path})"
        )


def _source_candidates(source_directory: Path, spec: DatasetSpec) -> Iterable[Path]:
    """兼容直接指向 testingdata、held_out 或 HiFo 仓库根目录的导入路径。"""

    candidates = (
        source_directory / spec.upstream_filename,
        source_directory / spec.destination_filename,
        source_directory / UPSTREAM_DATA_DIRECTORY / spec.upstream_filename,
        source_directory / "testingdata" / spec.upstream_filename,
    )
    seen: set[Path] = set()
    for candidate in candidates:
        resolved_candidate = candidate.resolve()
        if resolved_candidate not in seen:
            seen.add(resolved_candidate)
            yield resolved_candidate


def find_source_dataset(source_directory: Path, spec: DatasetSpec) -> Path:
    """定位导入源；若缺失则列出已尝试路径，便于用户修正参数。"""

    candidates = list(_source_candidates(source_directory, spec))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    attempted = "\n  - ".join(str(path) for path in candidates)
    raise DatasetPreparationError(
        f"cannot find {spec.size_label} dataset under {source_directory}; tried:\n  - {attempted}"
    )


def _download_to_handle(
    url: str,
    destination: BinaryIO,
    timeout_seconds: float,
    opener: Callable[..., object] | None = None,
) -> None:
    """把 URL 内容写入句柄；opener 可注入，测试时不会访问真实网络。"""

    open_url = opener or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": "auto-algo-opt-data-preparer"})
    try:
        with open_url(request, timeout=timeout_seconds) as response:
            shutil.copyfileobj(response, destination)
    except Exception as exc:  # urllib 的异常类型较多，统一转换为面向用户的错误
        raise DatasetPreparationError(f"failed to download {url}: {exc}") from exc


def _copy_file_to_handle(source_path: Path, destination: BinaryIO) -> None:
    """复制本地文件并及时关闭源句柄，兼容 Windows 后续归档或删除。"""

    with source_path.open("rb") as source_file:
        shutil.copyfileobj(source_file, destination)


def _stage_and_install(
    destination: Path,
    spec: DatasetSpec,
    writer: Callable[[BinaryIO], None],
) -> None:
    """先写临时文件并校验，再原子替换目标，避免留下半截数据。"""

    destination.parent.mkdir(parents=True, exist_ok=True)
    staged_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as staged_file:
            staged_path = Path(staged_file.name)
            writer(staged_file)
            staged_file.flush()
            os.fsync(staged_file.fileno())

        verify_dataset(staged_path, spec)
        os.replace(staged_path, destination)
        staged_path = None
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)


def prepare_datasets(
    output_directory: Path,
    *,
    source_directory: Path | None = None,
    verify_only: bool = False,
    timeout_seconds: float = 60.0,
    opener: Callable[..., object] | None = None,
    dataset_specs: Iterable[DatasetSpec] = DATASET_SPECS,
) -> list[Path]:
    """下载、导入或只校验三份 held-out 数据，返回目标文件路径。"""

    output_directory = output_directory.expanduser().resolve()
    source_directory = source_directory.expanduser().resolve() if source_directory else None
    prepared_paths: list[Path] = []

    for spec in dataset_specs:
        destination = output_directory / spec.destination_filename

        if verify_only:
            verify_dataset(destination, spec)
            print(f"[OK] {spec.size_label}: {destination}")
            prepared_paths.append(destination)
            continue

        if destination.is_file():
            try:
                verify_dataset(destination, spec)
            except DatasetPreparationError:
                # 本地错误文件只有在新数据完成校验后才会被原子替换。
                pass
            else:
                print(f"[SKIP] {spec.size_label}: already verified ({destination})")
                prepared_paths.append(destination)
                continue

        if source_directory is not None:
            source_path = find_source_dataset(source_directory, spec)
            _stage_and_install(
                destination,
                spec,
                lambda handle, source_path=source_path: _copy_file_to_handle(source_path, handle),
            )
            action = f"imported from {source_path}"
        else:
            url = f"{RAW_BASE_URL}/{spec.upstream_filename}"
            _stage_and_install(
                destination,
                spec,
                lambda handle, url=url: _download_to_handle(
                    url, handle, timeout_seconds, opener=opener
                ),
            )
            action = f"downloaded from {url}"

        verify_dataset(destination, spec)
        print(f"[OK] {spec.size_label}: {action} -> {destination}")
        prepared_paths.append(destination)

    return prepared_paths


def build_argument_parser() -> argparse.ArgumentParser:
    """构造命令行参数，三种模式保持互斥以避免误解执行意图。"""

    parser = argparse.ArgumentParser(
        description=(
            "Prepare HiFo BP 1k/5k/10k C100 held-out datasets from the fixed "
            f"upstream commit {UPSTREAM_COMMIT}."
        )
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--source-dir",
        type=Path,
        help="Import from an existing HiFo repository, testingdata directory, or held_out directory.",
    )
    mode_group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing target files without downloading or copying.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=f"Target directory (default: {DEFAULT_OUTPUT_DIRECTORY}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-download network timeout in seconds (default: 60).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口；错误时返回非零状态并保留已验证文件。"""

    args = build_argument_parser().parse_args(argv)
    if args.timeout <= 0:
        print("ERROR: --timeout must be greater than zero", file=sys.stderr)
        return 2

    try:
        prepared_paths = prepare_datasets(
            args.output_dir,
            source_directory=args.source_dir,
            verify_only=args.verify_only,
            timeout_seconds=args.timeout,
        )
    except DatasetPreparationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"Prepared {len(prepared_paths)} HiFo BP datasets from commit {UPSTREAM_COMMIT}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
