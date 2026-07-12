"""Run a command with OpenCode Go credentials mapped to DEEPSEEK_* env vars.

This keeps the existing EOH runner contract unchanged while allowing local
Windows/WSL runs to reuse the user's OpenCode Go subscription.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"


def _candidate_auth_paths() -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get("OPENCODE_AUTH_PATH")
    if explicit:
        paths.append(Path(explicit).expanduser())
    paths.append(Path.home() / ".local" / "share" / "opencode" / "auth.json")

    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        paths.append(Path(userprofile) / ".local" / "share" / "opencode" / "auth.json")

    # WSL can often read the Windows-side opencode login through /mnt/c.
    windows_users = Path("/mnt/c/Users")
    if windows_users.exists():
        paths.extend(windows_users.glob("*/.local/share/opencode/auth.json"))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def load_opencode_go_key() -> tuple[str, Path | None]:
    for path in _candidate_auth_paths():
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entry = data.get("opencode-go") if isinstance(data, dict) else None
        if isinstance(entry, dict):
            key = entry.get("key")
            if isinstance(key, str) and key:
                return key, path
    return "", None


def build_env(model: str, endpoint: str, preserve_existing: bool = False) -> tuple[dict[str, str], Path | None]:
    env = os.environ.copy()
    # 显式环境变量优先，便于 CI 和临时进程注入；auth store 仅作本机回退。
    key = env.get("OPENCODE_GO_API_KEY", "")
    auth_path: Path | None = None
    if not key:
        key, auth_path = load_opencode_go_key()
    if key and (not preserve_existing or not env.get("DEEPSEEK_API_KEY")):
        env["DEEPSEEK_API_KEY"] = key
    if not preserve_existing or not env.get("DEEPSEEK_API_ENDPOINT"):
        env["DEEPSEEK_API_ENDPOINT"] = endpoint
    if not preserve_existing or not env.get("DEEPSEEK_MODEL"):
        env["DEEPSEEK_MODEL"] = model
    return env, auth_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--preserve-existing", action="store_true", help="Do not override existing DEEPSEEK_* variables")
    parser.add_argument("--check", action="store_true", help="Print non-secret environment readiness and exit")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --")
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    env, auth_path = build_env(args.model, args.endpoint, preserve_existing=args.preserve_existing)

    if args.check:
        print(f"auth_path={auth_path if auth_path else ''}")
        print(f"api_key_present={bool(env.get('DEEPSEEK_API_KEY'))}")
        print(f"api_endpoint={env.get('DEEPSEEK_API_ENDPOINT', '')}")
        print(f"model={env.get('DEEPSEEK_MODEL', '')}")
        return 0 if env.get("DEEPSEEK_API_KEY") else 1

    if not command:
        parser.error("missing command; use --check or pass a command after --")

    if not env.get("DEEPSEEK_API_KEY"):
        print("OpenCode Go key not found. Run `opencode providers login` or set OPENCODE_AUTH_PATH.", file=sys.stderr)
        return 2

    completed = subprocess.run(command, env=env)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
