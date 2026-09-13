"""Local OS-owned locks: process exit releases ownership, not the pathname.

Never unlink a lock file: waiters must continue locking the same inode.
The metadata is diagnostic; the kernel lock is the authority for ownership.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os


@contextmanager
def exclusive_file_lock(path, *, busy="writer_busy", legacy_pid=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise ValueError(busy) from None
        previous = os.read(fd, 4096).decode("utf-8", errors="replace").strip()
        if legacy_pid and previous and not previous.startswith("{"):
            # Old O_EXCL owners do not take an OS lock. Only adopt their file
            # when the recorded PID is provably dead; unknown metadata is busy.
            from agent_skill_loop.session_recovery import process_alive
            if not previous.isdecimal() or process_alive(int(previous)):
                raise ValueError(busy)
        metadata = json.dumps({"protocol": "os-lock/v1", "pid": os.getpid(),
                               "acquired_at": datetime.now(timezone.utc).isoformat()}).encode()
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, metadata)
        os.ftruncate(fd, len(metadata))
        os.fsync(fd)
        yield
    finally:
        if locked:
            os.lseek(fd, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
