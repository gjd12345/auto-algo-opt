"""One-shot HTTP POST worker. The parent may kill this process at the deadline."""

from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    try:
        spec = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        url = spec["url"]
        headers = spec["headers"]
        body = base64.b64decode(spec["body_b64"])
        timeout = float(spec["timeout"])
        max_bytes = int(spec.get("max_bytes") or 4 * 1024 * 1024)
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        from agent_skill_loop.client import ProviderFailure, _open_url_with_deadline

        status, raw = _open_url_with_deadline(request, timeout, max_bytes=max_bytes)
        result = {
            "ok": True,
            "status": status,
            "body_b64": base64.b64encode(raw).decode("ascii"),
            "error_code": None,
        }
    except urllib.error.HTTPError as exc:
        result = {
            "ok": False,
            "status": exc.code,
            "body_b64": None,
            "error_code": "provider_auth_invalid" if exc.code in {401, 403} else f"http_{exc.code}",
        }
    except Exception as exc:
        error_code = getattr(exc, "error_code", None)
        if error_code == "request_deadline":
            code = "request_deadline"
        elif error_code:
            code = str(error_code)
        else:
            code = "provider_connectivity_or_protocol_error"
        result = {"ok": False, "status": None, "body_b64": None, "error_code": code}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
