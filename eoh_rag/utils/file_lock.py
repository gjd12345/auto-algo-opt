"""Cross-platform advisory file locks."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import IO, Iterator


if os.name == "nt":
    import msvcrt

    @contextmanager
    def exclusive_lock(file_obj: IO[str]) -> Iterator[None]:
        """Hold an exclusive advisory lock for the duration of the context."""
        original_pos = file_obj.tell()
        file_obj.seek(0)
        try:
            msvcrt.locking(file_obj.fileno(), msvcrt.LK_LOCK, 1)
        except OSError as exc:
            raise RuntimeError(f"failed to lock file descriptor {file_obj.fileno()}") from exc
        try:
            file_obj.seek(original_pos)
            yield
            file_obj.flush()
        finally:
            unlock_pos = file_obj.tell()
            file_obj.seek(0)
            try:
                msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError as exc:
                raise RuntimeError(f"failed to unlock file descriptor {file_obj.fileno()}") from exc
            file_obj.seek(unlock_pos)

else:
    import fcntl

    @contextmanager
    def exclusive_lock(file_obj: IO[str]) -> Iterator[None]:
        """Hold an exclusive advisory lock for the duration of the context."""
        fcntl.flock(file_obj, fcntl.LOCK_EX)
        try:
            yield
            file_obj.flush()
        finally:
            fcntl.flock(file_obj, fcntl.LOCK_UN)


__all__ = ["exclusive_lock"]
