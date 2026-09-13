"""Supervised execution process; no autonomous Plan/Evaluate model calls."""
import os
from pathlib import Path
import sys
import threading

from agent_skill_loop.eval_worker import _watch_parent


def main():
    root,task_id,parent_pid=sys.argv[1:]
    threading.Thread(target=_watch_parent,args=(int(parent_pid),),daemon=True).start()
    if sys.stdin.buffer.readline()!=b"go\n":
        return
    from agent_skill_loop.session_supervisor import execute_task
    execute_task(Path(root),task_id)


if __name__=="__main__":
    main()
