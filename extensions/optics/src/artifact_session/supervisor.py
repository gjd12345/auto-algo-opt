"""Process ownership and conservative recovery. Never replay unknown effects."""

import json
import os
from pathlib import Path
import signal
import subprocess
import time

from .store import SessionError, change, config, dumps, event, operation, record, transaction


def process_birth(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            exit_code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
                return None
            values = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *[ctypes.byref(v) for v in values]):
                return None
            return str((values[0].dwHighDateTime << 32) | values[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        fields = text[text.rfind(")") + 2:].split()
        if fields[0] == "Z":
            return None
        return fields[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


def terminate_owned(task):
    if not task["pid"]:
        raise SessionError("STARTING_PROCESS_OWNERSHIP_UNKNOWN")
    current = process_birth(task["pid"])
    if current is None:
        return
    if current != task["birth"]:
        raise SessionError("PID_IDENTITY_MISMATCH")
    if os.name == "nt":
        subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
                        "/PID", str(task["pid"]), "/T", "/F"], capture_output=True, timeout=10)
    else:
        os.killpg(task["pid"], signal.SIGKILL)
    for _ in range(50):
        if process_birth(task["pid"]) is None:
            return
        time.sleep(.05)
    raise SessionError("PROCESS_EXIT_NOT_CONFIRMED")


def stop(run, op, version):
    def mutation(db):
        if record(db)["state"] in ("COMPLETED", "STOPPED"):
            return {"already_terminal": True}
        change(db, state="STOPPING", reason="USER_STOP")
        return {"stopping": True}
    receipt, _ = operation(run, "stop", op, version, {}, mutation)
    if receipt.get("already_terminal"):
        return receipt
    with transaction(run) as db:
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks WHERE state IN ('RUNNING','STARTING')")]
    for task in tasks:
        terminate_owned(task)
    with transaction(run) as db:
        if record(db)["state"] == "STOPPING":
            for item in db.execute("SELECT * FROM effects WHERE state IN ('RESERVED','STARTED')").fetchall():
                detail = {**json.loads(item["detail"]), "process_confirmed_dead": True}
                db.execute("UPDATE effects SET state=?,detail=? WHERE id=?", ("UNKNOWN" if item["state"] == "STARTED" else "CANCELLED_NOT_STARTED", dumps(detail), item["id"]))
            db.execute("UPDATE tasks SET state='CANCELLED' WHERE state IN ('STARTING','RUNNING')")
            change(db, state="STOPPED")
            event(db, "stopped", {})
    return receipt


def recover(run, op, version):
    def mutation(db):
        row, conf = record(db), config(db)
        active = [dict(t) for t in db.execute("SELECT * FROM tasks WHERE state IN ('STARTING','RUNNING')")]
        for task in active:
            if not task["pid"]:
                raise SessionError("STARTING_PROCESS_OWNERSHIP_UNKNOWN")
            if process_birth(task["pid"]) == task["birth"]:
                raise SessionError("TASK_STILL_RUNNING")
        # A finished terminal receipt is collected by the runner transaction; missing
        # receipt is not permission to replay the operation or a profile.
        unknown_online = False
        for item in db.execute("SELECT * FROM effects WHERE state IN ('STARTED','RESERVED')").fetchall():
            detail = {**json.loads(item["detail"]), "process_confirmed_dead": True}
            state = "UNKNOWN" if item["state"] == "STARTED" else "CANCELLED_NOT_STARTED"
            db.execute("UPDATE effects SET state=?,detail=? WHERE id=?", (state, dumps(detail), item["id"]))
            unknown_online |= item["kind"] in ("MODEL_REQUEST", "ONLINE_PROFILE") and state == "UNKNOWN"
        db.execute("UPDATE tasks SET state='INTERRUPTED' WHERE state IN ('STARTING','RUNNING')")
        db.execute("UPDATE assessments SET state='INCOMPLETE' WHERE state='RESERVED'")
        if time.time() >= conf["global_deadline"]:
            change(db, state="STOPPED", reason="GLOBAL_DEADLINE")
        elif row["state"] == "SEARCHING" and active:
            from .runtime import seal
            seal(db, run, "UNKNOWN_SEARCH_EFFECT" if unknown_online else "WORKER_INTERRUPTED")
        elif row["state"] == "FINALIZING" and active:
            # No auto re-launch: finalization continuation requires a new explicit action.
            change(db, state="SEARCH_SEALED", reason="AUDIT_INTERRUPTED")
        else:
            change(db, state=row["state"])
        return {"unknown_effects_preserved": True, "tasks_reconciled": len(active)}
    return operation(run, "recover", op, version, {}, mutation)[0]
