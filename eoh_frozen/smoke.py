"""Offline model fixture exercising the real upstream engine over localhost."""
from __future__ import annotations
import contextlib
import ast
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from agent_skill_loop.problems.base import get_problem


@contextlib.contextmanager
def fixture_provider(problem: str, responder=None):
    spec = get_problem(problem)
    prompts = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = request["messages"][0]["content"]
            prompts.append(prompt)
            if responder:
                status, content = responder(prompt, len(prompts))
            else:
                # Distinct legal implementations prevent upstream duplicate retries.
                tree = ast.parse(spec.baseline_code)
                fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
                fn.body.insert(0, ast.parse(f"fixture_variant = {len(prompts)}").body[0])
                code = ast.unparse(ast.fix_missing_locations(tree))
                content = "2" if prompt == "1+1=?" else "{Offline fixture algorithm}\n```python\n" + code + "\n```"
                status = 200
            body = content if isinstance(content, bytes) else json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions", prompts
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def run_smoke(problem: str, output: Path) -> int:
    from eoh_frozen.__main__ import build_parser, cmd_run
    env_name = "EOH_OFFLINE_FIXTURE_KEY"
    previous = os.environ.get(env_name)
    os.environ[env_name] = "offline-fixture"
    try:
        with fixture_provider(problem) as (endpoint, prompts):
            args = build_parser().parse_args(["run", "--problem", problem, "--model", "offline-fixture",
                "--output", str(output), "--endpoint", endpoint, "--api-key-env", env_name,
                "--pop-size", "2", "--n-pop", "1", "--max-sample-nums", "2", "--max-requests", "7",
                "--count", "1", "--size", "6", "--wall-seconds", "60"])
            args.execution_mode = "fixture"
            return cmd_run(args)
    finally:
        if previous is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = previous
