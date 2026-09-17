"""One-shot, bounded provider transport. Raw response precedes validation."""

import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from optics_backend.artifacts import save, strict
from artifact_session.store import connect, config


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with connect(args.run) as db:
        conf = config(db)
    request = strict(args.request.read_bytes())
    timeout = min(conf["budgets"]["request_timeout"], conf["search_deadline"] - time.time())
    start = time.monotonic()
    try:
        if timeout <= 0:
            raise TimeoutError("SEARCH_DEADLINE")
        key = os.environ.get(conf["credential_env_name"])
        if not key:
            save(args.output / "provider.json", {"status": "provider_failed", "error": "CREDENTIAL_MISSING",
                 "input_tokens": None, "output_tokens": None, "external_request": False})
            return 4
        body = json.dumps({"model": conf["model"], "messages": request["messages"], **conf["provider_parameters"]}).encode()
        req = urllib.request.Request(conf["endpoint"], data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(2_000_001)
        (args.output / "provider_response.raw").write_bytes(raw)
        if len(raw) > 2_000_000:
            raise ValueError("PROVIDER_RESPONSE_TOO_LARGE")
        envelope = strict(raw, 2_000_000)
        choice = envelope["choices"][0]
        message = choice["message"]
        content = message.get("content")
        usage = envelope.get("usage") or {}
        status = "complete" if isinstance(content, str) and choice.get("finish_reason") != "length" else "generation_failed"
        if isinstance(content, str):
            (args.output / "model_reply.json").write_bytes(content.encode())
        save(args.output / "provider.json", {"status": status, "finish_reason": choice.get("finish_reason"),
             "content_source": "content", "input_tokens": usage.get("prompt_tokens"),
             "output_tokens": usage.get("completion_tokens"), "elapsed_seconds": time.monotonic() - start,
             "external_request": True, "model": conf["model"]})
        return 0
    except urllib.error.HTTPError as exc:
        (args.output / "provider_response.raw").write_bytes(exc.read(2_000_000))
        save(args.output / "provider.json", {"status": "provider_failed", "http_status": exc.code,
             "input_tokens": None, "output_tokens": None, "elapsed_seconds": time.monotonic() - start,
             "external_request": True})
        return 4
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        save(args.output / "provider.json", {"status": "unknown", "error_type": type(exc).__name__,
             "input_tokens": None, "output_tokens": None, "elapsed_seconds": time.monotonic() - start,
             "external_request": True})
        return 5
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        save(args.output / "provider.json", {"status": "generation_failed", "error_type": type(exc).__name__,
             "input_tokens": None, "output_tokens": None, "elapsed_seconds": time.monotonic() - start,
             "external_request": True})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
