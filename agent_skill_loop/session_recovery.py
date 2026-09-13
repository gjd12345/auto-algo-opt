"""Conservative collection of tasks whose supervisor exited without a receipt.

Recovery never repeats provider or solver work. Parent watchdogs in the HTTP,
EoH and candidate workers close the descendants before a dead task is collected.
"""
from datetime import datetime, timezone
import os
from pathlib import Path

from agent_skill_loop import session_runtime as db


def process_alive(pid, started_at=None):
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        kernel.WaitForSingleObject.restype=wintypes.DWORD
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x100000|0x1000,False,pid)
        if not handle:
            # Access denied is not proof of process death.
            return ctypes.get_last_error()==5
        try:
            if kernel.WaitForSingleObject(handle,0)!=258:
                return False
            if started_at:
                values=[wintypes.FILETIME() for _ in range(4)]
                kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
                if kernel.GetProcessTimes(handle,*[ctypes.byref(v) for v in values]):
                    born=((values[0].dwHighDateTime<<32)|values[0].dwLowDateTime)/10_000_000-11644473600
                    if born>datetime.fromisoformat(started_at.replace("Z","+00:00")).timestamp()+1:
                        return False  # PID belongs to a later process.
            return True
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid,0)
        stat=Path(f"/proc/{pid}/stat")
        return not (stat.exists() and stat.read_text().rsplit(")",1)[-1].strip().startswith("Z"))
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def recover_dead_task(root, con, task):
    """Called under collect's transaction; return a terminal row or None."""
    now=datetime.now(timezone.utc)
    created=datetime.fromisoformat(task["created_at_utc"].replace("Z","+00:00"))
    if task["process_id"] is None and (now-created).total_seconds()<30:
        return None
    if process_alive(task["process_id"],task["started_at_utc"]):
        return None
    observed=task["heartbeat_at_utc"]
    if observed is None:
        con.execute("UPDATE tasks SET heartbeat_at_utc=? WHERE task_id=?",(db._utc_now(),task["task_id"]))
        return None
    if (now-datetime.fromisoformat(observed.replace("Z","+00:00"))).total_seconds()<2:
        return None
    start=datetime.fromisoformat((task["started_at_utc"] or task["created_at_utc"]).replace("Z","+00:00"))
    end=min(now,datetime.fromisoformat(task["hard_deadline_utc"])) if task["hard_deadline_utc"] else now
    elapsed=max(0,(end-start).total_seconds()) if task["external_effect_started"] else 0
    ref=f"rounds/round_{task['round_id']:04d}/tasks/{task['task_id']}/terminal.json"
    text=db._json({"task_id":task["task_id"],"reason":"UNKNOWN","engine_elapsed_seconds":elapsed,"recovered":True})+"\n"
    db._atomic_write(root/ref,text)
    con.execute("UPDATE requests SET state='unknown',input_tokens=NULL,output_tokens=NULL WHERE task_id=? AND state IN ('reserved','sent')",(task["task_id"],))
    con.execute("UPDATE solver_calls SET state='interrupted',objective=NULL,valid=NULL WHERE task_id=? AND state IN ('reserved','started')",(task["task_id"],))
    con.execute("UPDATE tasks SET state='EXITED',terminal_reason='UNKNOWN',terminal_ref=?,terminal_sha256=?,finished_at_utc=?,engine_elapsed_seconds=? WHERE task_id=?",(ref,db._sha256(text),db._utc_now(),elapsed,task["task_id"]))
    return con.execute("SELECT * FROM tasks WHERE task_id=?",(task["task_id"],)).fetchone()
