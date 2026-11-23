"""Windows-compatible tmux-style multi-task session multiplexer for evolutionary & benchmark runs.

Manages named concurrent sessions backed by isolated per-pane log files, structured
JSON state, atomic session lock scheduling (--max-concurrent), detached auto-pump
supervisor daemon, live status summaries, tail inspection, optional Windows Terminal
(`wt`) pane viewer, and portable process-tree termination.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

if os.name == "nt":
    import msvcrt
else:
    import fcntl

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_DIR = REPO_ROOT / "build" / "mux_sessions"
SAFE_SESSION_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
_INPROC_LOCKS_GUARD = threading.Lock()
_INPROC_LOCKS: dict[str, threading.RLock] = {}


def _validate_identifier(raw: str, label: str) -> str:
    cleaned = raw.strip()
    if not cleaned or any(ch not in SAFE_SESSION_CHARS for ch in cleaned) or cleaned in (".", ".."):
        raise ValueError(f"Invalid {label}: {raw!r}. Only [A-Za-z0-9_.-] allowed.")
    return cleaned


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _is_pid_alive(pid: int | None) -> bool:
    if pid is None or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == "nt":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            exit_code = ctypes.c_ulong(0)
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(ok and exit_code.value == STILL_ACTIVE)
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _terminate_pids_parallel(pids: list[int | None], wait_timeout: float = 3.0) -> list[int]:
    """Terminate all specified process trees concurrently and return any PIDs still alive."""
    self_pid = os.getpid()
    seen: set[int] = set()
    target_pids: list[int] = []
    for raw_pid in pids:
        if raw_pid is None or isinstance(raw_pid, bool) or raw_pid <= 0 or raw_pid == self_pid:
            continue
        pid = int(raw_pid)
        if pid not in seen:
            seen.add(pid)
            target_pids.append(pid)

    alive_targets = [pid for pid in target_pids if _is_pid_alive(pid)]
    if not alive_targets:
        return []

    deadline = time.monotonic() + max(0.2, float(wait_timeout))
    if os.name == "nt":
        kill_procs: list[subprocess.Popen[bytes]] = []
        for pid in alive_targets:
            try:
                kill_procs.append(
                    subprocess.Popen(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )
            except OSError:
                pass
        try:
            while time.monotonic() < deadline:
                for kp in kill_procs:
                    if kp.poll() is None:
                        continue
                if all(not _is_pid_alive(pid) for pid in alive_targets):
                    break
                time.sleep(0.05)
        finally:
            for kp in kill_procs:
                if kp.poll() is None:
                    try:
                        kp.kill()
                    except OSError:
                        pass
                try:
                    kp.wait(timeout=0.2)
                except (subprocess.TimeoutExpired, OSError):
                    pass
    else:
        for sig in (signal.SIGTERM, getattr(signal, "SIGKILL", signal.SIGTERM)):
            still = [pid for pid in alive_targets if _is_pid_alive(pid)]
            if not still:
                break
            for pid in still:
                sent = False
                if hasattr(os, "killpg"):
                    try:
                        os.killpg(pid, sig)
                        sent = True
                    except OSError:
                        pass
                if not sent:
                    try:
                        os.kill(pid, sig)
                    except OSError:
                        pass
            sig_deadline = min(deadline, time.monotonic() + (0.6 if sig == signal.SIGTERM else max(0.2, deadline - time.monotonic())))
            while time.monotonic() < sig_deadline:
                if all(not _is_pid_alive(pid) for pid in alive_targets):
                    break
                time.sleep(0.05)

    return [pid for pid in alive_targets if _is_pid_alive(pid)]


def _terminate_pid_tree(pid: int | None, wait_timeout: float = 3.0) -> bool:
    return not _terminate_pids_parallel([pid], wait_timeout=wait_timeout)


def _get_inproc_lock(lock_path: Path) -> threading.RLock:
    key = str(lock_path.resolve())
    with _INPROC_LOCKS_GUARD:
        lock = _INPROC_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _INPROC_LOCKS[key] = lock
        return lock


@contextlib.contextmanager
def _session_lock(sess_dir: Path, timeout: float = 10.0, lock_name: str = ".session.lock") -> Iterator[None]:
    """Exclusive reentrant in-process + OS-level lock keyed by lock file path."""
    sess_dir.mkdir(parents=True, exist_ok=True)
    lock_path = sess_dir / lock_name
    inproc_lock = _get_inproc_lock(lock_path)
    if not inproc_lock.acquire(timeout=timeout):
        raise TimeoutError(f"Timed out acquiring in-process mux lock for: {lock_path}")
    fh = None
    locked_os = False
    try:
        fh = open(lock_path, "a+b")
        if fh.tell() == 0:
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"\0")
                fh.flush()
        depth = _get_lock_depth(lock_path)
        if depth == 0:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    if os.name == "nt":
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked_os = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Timed out acquiring OS mux session lock: {lock_path}")
                    time.sleep(0.01)
        _set_lock_depth(lock_path, depth + 1)
        try:
            yield
        finally:
            _set_lock_depth(lock_path, depth)
    finally:
        if fh is not None:
            if locked_os:
                try:
                    if os.name == "nt":
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            try:
                fh.close()
            except OSError:
                pass
        inproc_lock.release()


_THREAD_LOCK_STATE = threading.local()


def _get_lock_depth(lock_path: Path) -> int:
    depths = getattr(_THREAD_LOCK_STATE, "depths", None)
    if depths is None:
        return 0
    return int(depths.get(str(lock_path.resolve()), 0))


def _set_lock_depth(lock_path: Path, value: int) -> None:
    depths = getattr(_THREAD_LOCK_STATE, "depths", None)
    if depths is None:
        depths = {}
        _THREAD_LOCK_STATE.depths = depths
    key = str(lock_path.resolve())
    if value <= 0:
        depths.pop(key, None)
    else:
        depths[key] = value


def _clean_dir_strict(path: Path, *, retries: int = 10, delay: float = 0.05) -> None:
    """Remove an existing session subdirectory strictly, retrying briefly for Windows handle teardown."""
    if not path.exists():
        return
    last_exc: OSError | None = None
    for attempt in range(max(1, retries)):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_exc = exc
            if attempt + 1 < retries:
                time.sleep(delay)
    raise RuntimeError(f"Failed to remove stale session artifacts at {path}: {last_exc}") from last_exc


def _read_last_nonempty_line(log_path: Path, max_len: int = 100) -> str:
    if not log_path.is_file():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        stripped = " ".join(line.split())
        if stripped:
            if len(stripped) <= max_len:
                return stripped
            return stripped[: max_len - 1] + "…"
    return ""


def _load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        jobs = raw.get("panes") or raw.get("jobs")
    elif isinstance(raw, list):
        jobs = raw
    else:
        jobs = None
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("Manifest must be a non-empty list of pane specs or {'panes': [...]}.")

    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(jobs):
        if not isinstance(item, dict):
            raise ValueError(f"Pane entry {idx} must be an object.")
        pane_id = _validate_identifier(str(item.get("id") or f"pane_{idx + 1}"), f"pane id[{idx}]")
        if pane_id in seen_ids:
            raise ValueError(f"Duplicate pane id in manifest: {pane_id!r}")
        seen_ids.add(pane_id)

        cmd = item.get("command")
        if isinstance(cmd, str):
            argv = shlex.split(cmd, posix=(os.name != "nt"))
        elif isinstance(cmd, list) and all(isinstance(x, str) and x for x in cmd):
            argv = list(cmd)
        else:
            raise ValueError(f"Pane {pane_id!r} requires a non-empty 'command' string or list of args.")
        if not argv:
            raise ValueError(f"Pane {pane_id!r} resolved to an empty command.")

        cwd_raw = item.get("cwd")
        cwd = str(Path(cwd_raw).resolve()) if cwd_raw else str(REPO_ROOT)
        env = item.get("env") or {}
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise ValueError(f"Pane {pane_id!r} 'env' must be a string->string dict.")
        normalized.append({"id": pane_id, "command": argv, "cwd": cwd, "env": dict(env)})
    return normalized


def _session_dir(base_dir: Path, session: str) -> Path:
    return base_dir / _validate_identifier(session, "session")


def _pane_state_path(sess_dir: Path, pane_id: str) -> Path:
    return sess_dir / "panes" / f"{pane_id}.json"


def _detached_popen_kwargs(cwd: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(
            subprocess, "DETACHED_PROCESS", 0x00000008
        )
    else:
        kwargs["start_new_session"] = True
    return kwargs


def _spawn_pane(
    base_dir: Path,
    sess_dir: Path,
    session: str,
    pane: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    pane_id = pane["id"]
    log_path = sess_dir / "logs" / f"{pane_id}.log"
    state_path = _pane_state_path(sess_dir, pane_id)
    spec_path = sess_dir / "panes" / f"{pane_id}.spec.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    spec_payload = dict(pane)
    spec_payload["run_id"] = run_id
    _atomic_write_json(spec_path, spec_payload)

    cmd_args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--base-dir",
        str(base_dir),
        "_run-pane",
        "--session",
        session,
        "--pane",
        pane_id,
    ]
    if run_id is not None:
        cmd_args.extend(["--run-id", str(run_id)])

    proc = subprocess.Popen(
        cmd_args,
        **_detached_popen_kwargs(pane["cwd"]),
    )
    claim_state = {
        "id": pane_id,
        "status": "running",
        "cancelled": False,
        "run_id": run_id,
        "wrapper_pid": proc.pid,
        "pid": proc.pid,
        "started_at": time.time(),
        "finished_at": None,
        "returncode": None,
        "log": str(log_path),
    }
    _atomic_write_json(state_path, claim_state)
    return claim_state


def _cmd_run_pane(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    session = _validate_identifier(args.session, "session")
    pane_id = _validate_identifier(args.pane, "pane")
    cli_run_id = getattr(args, "run_id", None)
    sess_dir = _session_dir(base_dir, session)
    spec_path = sess_dir / "panes" / f"{pane_id}.spec.json"
    state_path = _pane_state_path(sess_dir, pane_id)
    log_path = sess_dir / "logs" / f"{pane_id}.log"
    meta_path = sess_dir / "session.json"
    started = time.time()

    with _session_lock(sess_dir):
        if not meta_path.is_file() or not spec_path.is_file():
            return -15
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        cur = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        expected_run_id = cli_run_id if cli_run_id is not None else spec.get("run_id")
        if (
            meta.get("stopped")
            or cur.get("cancelled")
            or meta.get("run_id") != expected_run_id
            or spec.get("run_id") != expected_run_id
        ):
            return -15

        env = os.environ.copy()
        env.update(spec.get("env", {}))
        child_kwargs: dict[str, Any] = {
            "cwd": spec["cwd"],
            "env": env,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            child_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            child_kwargs["start_new_session"] = True

        log_path.parent.mkdir(parents=True, exist_ok=True)
        lf = open(log_path, "w", encoding="utf-8", errors="replace")
        try:
            child = subprocess.Popen(spec["command"], stdout=lf, stderr=subprocess.STDOUT, **child_kwargs)
            init_state = {
                "id": pane_id,
                "status": "running",
                "cancelled": False,
                "run_id": expected_run_id,
                "wrapper_pid": os.getpid(),
                "pid": child.pid,
                "started_at": started,
                "finished_at": None,
                "returncode": None,
                "log": str(log_path),
            }
            _atomic_write_json(state_path, init_state)
        except Exception:
            lf.close()
            raise

    try:
        rc = child.wait()
    finally:
        lf.close()

    fin = time.time()
    with _session_lock(sess_dir):
        if not meta_path.is_file():
            return -15
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        cur = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        if meta.get("run_id") != expected_run_id or cur.get("cancelled"):
            return -15
        done_state = {
            "id": pane_id,
            "status": "done" if rc == 0 else "failed",
            "cancelled": False,
            "run_id": expected_run_id,
            "wrapper_pid": os.getpid(),
            "pid": child.pid,
            "started_at": started,
            "finished_at": fin,
            "returncode": rc,
            "elapsed_s": round(fin - started, 3),
            "log": str(log_path),
        }
        _atomic_write_json(state_path, done_state)
    return int(rc)


def _spawn_supervisor_daemon(base_dir: Path, session: str) -> int:
    proc = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--base-dir",
            str(base_dir),
            "_pump-daemon",
            "--session",
            session,
        ],
        **_detached_popen_kwargs(str(REPO_ROOT)),
    )
    return int(proc.pid)


def _open_wt_tail_panes(sess_dir: Path, panes: list[dict[str, Any]]) -> bool:
    wt_bin = shutil.which("wt")
    if not wt_bin or not panes:
        return False
    args: list[str] = [wt_bin]
    for idx, pane in enumerate(panes):
        log_path = sess_dir / "logs" / f"{pane['id']}.log"
        ps_cmd = f"Get-Content -Path '{log_path}' -Wait -Tail 30"
        if idx > 0:
            args.extend([";", "split-pane", "-H" if idx % 2 else "-V"])
        args.extend(["--title", pane["id"], "powershell", "-NoExit", "-Command", ps_cmd])
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def _inspect_session_unlocked(sess_dir: Path, session: str) -> dict[str, Any]:
    meta_path = sess_dir / "session.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"Unknown session {session!r} at {sess_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    stopped = bool(meta.get("stopped", False))
    rows: list[dict[str, Any]] = []
    counts = {"pending": 0, "running": 0, "done": 0, "failed": 0}
    now = time.time()
    for pane in meta["panes"]:
        pid_key = pane["id"]
        st_path = _pane_state_path(sess_dir, pid_key)
        log_path = sess_dir / "logs" / f"{pid_key}.log"
        if not st_path.is_file():
            status = "failed" if stopped else "pending"
            row = {
                "id": pid_key,
                "status": status,
                "pid": None,
                "returncode": -15 if stopped else None,
                "cancelled": stopped,
                "elapsed_s": 0.0,
                "log": str(log_path),
                "last_line": "",
            }
        else:
            st = json.loads(st_path.read_text(encoding="utf-8"))
            status = st.get("status", "running")
            if status == "running" and not _is_pid_alive(st.get("pid")) and not _is_pid_alive(st.get("wrapper_pid")):
                status = "failed"
                st["status"] = "failed"
                st["finished_at"] = st.get("finished_at") or now
                _atomic_write_json(st_path, st)
            started_at = float(st.get("started_at") or now)
            finished_at = float(st["finished_at"]) if st.get("finished_at") is not None else now
            elapsed = st.get("elapsed_s")
            if elapsed is None:
                elapsed = round(max(0.0, finished_at - started_at), 2)
            row = {
                "id": pid_key,
                "status": status,
                "pid": st.get("pid"),
                "wrapper_pid": st.get("wrapper_pid"),
                "returncode": st.get("returncode"),
                "cancelled": bool(st.get("cancelled", False)),
                "elapsed_s": elapsed,
                "log": str(log_path),
                "last_line": _read_last_nonempty_line(log_path),
            }
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        rows.append(row)
    return {
        "session": session,
        "session_dir": str(sess_dir),
        "max_concurrent": meta["max_concurrent"],
        "stopped": stopped,
        "supervisor_pid": meta.get("supervisor_pid"),
        "counts": counts,
        "all_finished": counts["pending"] == 0 and counts["running"] == 0,
        "panes": rows,
    }


def inspect_session(base_dir: Path, session: str) -> dict[str, Any]:
    sess_dir = _session_dir(base_dir, session)
    with _session_lock(sess_dir):
        return _inspect_session_unlocked(sess_dir, session)


def _pump_pending_slots_unlocked(base_dir: Path, sess_dir: Path, session: str) -> dict[str, Any]:
    meta_path = sess_dir / "session.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"Unknown session {session!r} at {sess_dir}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    snap = _inspect_session_unlocked(sess_dir, session)
    if meta.get("stopped"):
        return snap
    running = snap["counts"]["running"]
    limit = int(meta["max_concurrent"])
    pending_ids = [r["id"] for r in snap["panes"] if r["status"] == "pending"]
    pane_map = {p["id"]: p for p in meta["panes"]}
    spawned_any = False
    for pane_id in pending_ids:
        if running >= limit:
            break
        _spawn_pane(base_dir, sess_dir, session, pane_map[pane_id], run_id=meta.get("run_id"))
        running += 1
        spawned_any = True
    return _inspect_session_unlocked(sess_dir, session) if spawned_any else snap


def _pump_pending_slots(base_dir: Path, session: str) -> dict[str, Any]:
    sess_dir = _session_dir(base_dir, session)
    with _session_lock(sess_dir):
        return _pump_pending_slots_unlocked(base_dir, sess_dir, session)


def _collect_and_mark_kill_unlocked(
    sess_dir: Path,
    session: str,
    *,
    pane: str | None = None,
    quiet: bool = False,
) -> tuple[list[int], list[str]]:
    """Mark targeted panes/session stopped atomically and collect PIDs to kill outside the lock."""
    meta_path = sess_dir / "session.json"
    if not meta_path.is_file():
        if quiet:
            return [], []
        raise FileNotFoundError(f"Unknown session {session!r} at {sess_dir}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    snap = _inspect_session_unlocked(sess_dir, session)
    target_pane = _validate_identifier(pane, "pane") if pane else None

    pids_to_kill: list[int] = []
    if target_pane is None:
        meta["stopped"] = True
        sup_pid = meta.get("supervisor_pid")
        if isinstance(sup_pid, int) and not isinstance(sup_pid, bool) and sup_pid != os.getpid():
            pids_to_kill.append(sup_pid)
        _atomic_write_json(meta_path, meta)

    killed: list[str] = []
    now = time.time()
    for row in snap["panes"]:
        if target_pane and row["id"] != target_pane:
            continue
        st_path = _pane_state_path(sess_dir, row["id"])
        if row["status"] == "running":
            for raw_pid in (row.get("pid"), row.get("wrapper_pid")):
                if isinstance(raw_pid, int) and not isinstance(raw_pid, bool):
                    pids_to_kill.append(raw_pid)
            st = (
                json.loads(st_path.read_text(encoding="utf-8"))
                if st_path.is_file()
                else {"id": row["id"], "started_at": now}
            )
            st["status"] = "failed"
            st["cancelled"] = True
            st["finished_at"] = now
            st["returncode"] = -15
            _atomic_write_json(st_path, st)
            killed.append(row["id"])
        elif row["status"] == "pending":
            cancelled_state = {
                "id": row["id"],
                "status": "failed",
                "cancelled": True,
                "wrapper_pid": None,
                "pid": None,
                "started_at": now,
                "finished_at": now,
                "returncode": -15,
                "elapsed_s": 0.0,
                "log": row["log"],
            }
            _atomic_write_json(st_path, cancelled_state)
            killed.append(row["id"])
    return pids_to_kill, killed


def kill_session(base_dir: Path, session: str, *, pane: str | None = None, quiet: bool = False) -> dict[str, Any]:
    sess_dir = _session_dir(base_dir, session)
    with _session_lock(sess_dir):
        pids_to_kill, killed = _collect_and_mark_kill_unlocked(sess_dir, session, pane=pane, quiet=quiet)
    # Terminate OS process trees outside the metadata lock so other panes/supervisors never stall on taskkill.
    unkilled_pids = _terminate_pids_parallel(pids_to_kill, wait_timeout=3.0)
    return {"session": session, "killed": killed, "unkilled_pids": unkilled_pids}


def cmd_start(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    session = _validate_identifier(args.session, "session")
    sess_dir = _session_dir(base_dir, session)
    panes = _load_manifest(Path(args.manifest))
    max_conc = max(1, int(args.max_concurrent or len(panes)))

    with _session_lock(sess_dir, lock_name=".replace.lock"):
        meta_path = sess_dir / "session.json"
        with _session_lock(sess_dir):
            if meta_path.is_file() and not args.replace:
                raise FileExistsError(f"Session {session!r} already exists at {sess_dir}; pass --replace to overwrite.")
            pids_to_kill = (
                _collect_and_mark_kill_unlocked(sess_dir, session, quiet=True)[0]
                if meta_path.is_file()
                else []
            )

        if pids_to_kill:
            still_alive = _terminate_pids_parallel(pids_to_kill, wait_timeout=3.0)
            if still_alive:
                raise RuntimeError(
                    f"Cannot replace session {session!r}: existing processes remained alive after timeout: {still_alive}"
                )

        with _session_lock(sess_dir):
            for sub_name in ("panes", "logs"):
                _clean_dir_strict(sess_dir / sub_name)

            meta = {
                "session": session,
                "run_id": uuid.uuid4().hex,
                "created_at": time.time(),
                "max_concurrent": max_conc,
                "stopped": False,
                "supervisor_pid": None,
                "panes": panes,
            }
            _atomic_write_json(meta_path, meta)
            snap = _pump_pending_slots_unlocked(base_dir, sess_dir, session)
            if snap["counts"]["pending"] > 0 and not getattr(args, "no_supervisor", False):
                sup_pid = _spawn_supervisor_daemon(base_dir, session)
                meta["supervisor_pid"] = sup_pid
                _atomic_write_json(meta_path, meta)
                snap["supervisor_pid"] = sup_pid

    if args.wt_panes:
        snap["wt_panes_launched"] = _open_wt_tail_panes(sess_dir, panes)
    print(json.dumps(snap, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    snap = _pump_pending_slots(base_dir, args.session) if args.pump else inspect_session(base_dir, args.session)
    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
    else:
        c = snap["counts"]
        print(
            f"[{snap['session']}] pending={c['pending']} running={c['running']} "
            f"done={c['done']} failed={c['failed']} (max_concurrent={snap['max_concurrent']})"
        )
        for row in snap["panes"]:
            print(
                f"  - {row['id']:24s} | {row['status']:7s} | pid={str(row['pid'] or '-'):7s} | "
                f"{row['elapsed_s']:6.2f}s | rc={str(row['returncode']) if row['returncode'] is not None else '-':3s} | "
                f"{row['last_line']}"
            )
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    sess_dir = _session_dir(Path(args.base_dir), args.session)
    pane_id = _validate_identifier(args.pane, "pane")
    log_path = sess_dir / "logs" / f"{pane_id}.log"
    if not log_path.is_file():
        raise FileNotFoundError(f"Log not found: {log_path}")
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail_lines = lines[-max(1, int(args.lines)) :]
    sys.stdout.write("\n".join(tail_lines) + ("\n" if tail_lines else ""))
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    deadline = time.monotonic() + float(args.timeout)
    interval = max(0.05, float(args.interval))
    while True:
        try:
            snap = _pump_pending_slots(base_dir, args.session)
        except TimeoutError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(min(interval, max(0.05, deadline - time.monotonic())))
            continue
        if snap["all_finished"]:
            print(json.dumps(snap, ensure_ascii=False, indent=2))
            return 0 if snap["counts"]["failed"] == 0 else 1
        if time.monotonic() >= deadline:
            print(json.dumps(snap, ensure_ascii=False, indent=2))
            return 2
        time.sleep(min(interval, max(0.05, deadline - time.monotonic())))


def _cmd_pump_daemon(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    session = _validate_identifier(args.session, "session")
    while True:
        try:
            snap = _pump_pending_slots(base_dir, session)
        except FileNotFoundError:
            return 0
        except TimeoutError:
            time.sleep(0.2)
            continue
        if snap["all_finished"] or snap.get("stopped"):
            return 0
        time.sleep(0.2)


def cmd_kill(args: argparse.Namespace) -> int:
    res = kill_session(Path(args.base_dir), args.session, pane=args.pane)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Windows-safe tmux-style multi-task runner and pane monitor.")
    p.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Root folder for mux session logs/state.")
    sub = p.add_subparsers(dest="subcommand", required=True)

    s = sub.add_parser("start", help="Launch a named multi-pane session from a JSON manifest.")
    s.add_argument("--session", required=True)
    s.add_argument("--manifest", required=True)
    s.add_argument("--max-concurrent", type=int, default=0, help="Max concurrent panes (0 = all).")
    s.add_argument("--replace", action="store_true", help="Kill and replace existing session directory.")
    s.add_argument("--wt-panes", action="store_true", help="Open Windows Terminal split-pane tail viewer.")
    s.add_argument("--no-supervisor", action="store_true", help="Disable detached auto-pump daemon on start.")
    s.set_defaults(func=cmd_start)

    st = sub.add_parser("status", help="Show concise status table (or JSON) for all panes.")
    st.add_argument("--session", required=True)
    st.add_argument("--pump", action="store_true", help="Also advance queued pending panes into free slots.")
    st.add_argument("--json", action="store_true")
    st.set_defaults(func=cmd_status)

    t = sub.add_parser("tail", help="Show last N log lines of one pane.")
    t.add_argument("--session", required=True)
    t.add_argument("--pane", required=True)
    t.add_argument("--lines", type=int, default=40)
    t.set_defaults(func=cmd_tail)

    w = sub.add_parser("wait", help="Pump slots until all panes finish and report exit status.")
    w.add_argument("--session", required=True)
    w.add_argument("--timeout", type=float, default=3600.0)
    w.add_argument("--interval", type=float, default=0.5)
    w.set_defaults(func=cmd_wait)

    k = sub.add_parser("kill", help="Terminate running and queued panes in a session (or one pane).")
    k.add_argument("--session", required=True)
    k.add_argument("--pane", default=None)
    k.set_defaults(func=cmd_kill)

    d = sub.add_parser("_pump-daemon", help=argparse.SUPPRESS)
    d.add_argument("--session", required=True)
    d.set_defaults(func=_cmd_pump_daemon)

    r = sub.add_parser("_run-pane", help=argparse.SUPPRESS)
    r.add_argument("--session", required=True)
    r.add_argument("--pane", required=True)
    r.add_argument("--run-id", default=None)
    r.set_defaults(func=_cmd_run_pane)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
