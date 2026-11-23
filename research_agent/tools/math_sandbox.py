"""Isolated subprocess mathematical diagnostic sandbox for Research Agent."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from agent_skill_loop.evaluator import kill_process_tree
from agent_skill_loop.interface_design.runtime import _worker_environment
from research_agent.contracts import atomic_write_json, utc_now

_REPO = Path(__file__).resolve().parents[2]
MAX_SANDBOX_OUTPUT_BYTES = 8192


class MathSandboxTool:
    """Run AST-whitelisted Python/NumPy scripts in an API-key-free 15s subprocess."""

    def __init__(self, run_dir: Path, *, timeout_s: float = 15.0, repo_root: Path = _REPO) -> None:
        self.run_dir = Path(run_dir).resolve()
        self.timeout_s = float(timeout_s)
        self.repo_root = Path(repo_root).resolve()
        self.sandbox_dir = self.run_dir / "agent_artifacts" / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def run(self, *, script: str) -> dict[str, Any]:
        self._seq += 1
        req = json.dumps({"script": script, "parent_pid": os.getpid()}, ensure_ascii=False).encode("utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-m", "research_agent.sandbox_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tempfile.gettempdir(),
            env=_worker_environment(self.repo_root),
        )
        timed_out = False
        try:
            stdout_b, stderr_b = proc.communicate(req, timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_process_tree(proc)
            stdout_b, stderr_b = b"", b""

        if timed_out:
            raw_res: dict[str, Any] = {
                "ok": False,
                "error_code": "SandboxTimeout",
                "error_detail": f"Sandbox script exceeded hard timeout {self.timeout_s:.1f}s.",
                "stdout": "",
                "result": None,
                "elapsed_ms": self.timeout_s * 1000.0,
            }
        else:
            try:
                raw_res = json.loads((stdout_b or b"").decode("utf-8"))
            except Exception as exc:
                err_txt = (stderr_b or b"").decode("utf-8", errors="replace")[:512]
                raw_res = {
                    "ok": False,
                    "error_code": "SandboxWorkerError",
                    "error_detail": f"{exc}: {err_txt}",
                    "stdout": "",
                    "result": None,
                    "elapsed_ms": 0.0,
                }

        stdout_str = str(raw_res.get("stdout") or "")
        truncated = False
        if len(stdout_str.encode("utf-8")) > MAX_SANDBOX_OUTPUT_BYTES // 2:
            stdout_str = stdout_str[: MAX_SANDBOX_OUTPUT_BYTES // 2] + "\n...[TRUNCATED]"
            truncated = True
        raw_res["stdout"] = stdout_str

        res_json = json.dumps(raw_res.get("result"), ensure_ascii=False, default=str)
        if len(res_json.encode("utf-8")) > MAX_SANDBOX_OUTPUT_BYTES // 2:
            raw_res["result"] = res_json[: MAX_SANDBOX_OUTPUT_BYTES // 2] + "...[TRUNCATED]"
            truncated = True
        raw_res["output_truncated"] = truncated

        rel_path = f"agent_artifacts/sandbox/run_{self._seq:04d}.json"
        payload = {"executed_at": utc_now(), **raw_res}
        sha = atomic_write_json(self.run_dir / rel_path, payload)
        return {"artifact_ref": rel_path, "artifact_sha256": sha, **raw_res}
