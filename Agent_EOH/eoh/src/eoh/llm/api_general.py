import http.client
import json
import os
import time
from urllib.parse import urlparse


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _is_quota_or_rate_limit(status, body):
    text = (body or "").lower()
    if status in {402, 429}:
        return True
    markers = (
        "quota",
        "rate limit",
        "rate_limit",
        "too many requests",
        "insufficient balance",
        "insufficient_balance",
        "exceeded",
    )
    return any(marker in text for marker in markers)


class InterfaceAPI:
    def __init__(self, api_endpoint, api_key, model_LLM, debug_mode):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.model_LLM = model_LLM
        self.debug_mode = debug_mode
        self.n_trial = 5
        self.quota_auto_wait = _env_bool("EOH_API_QUOTA_AUTO_WAIT", True)
        self.quota_pause_seconds = max(60, _env_int("EOH_API_QUOTA_PAUSE_SECONDS", 1800))
        self.quota_max_pauses = max(0, _env_int("EOH_API_QUOTA_MAX_PAUSES", 0))

        parsed = urlparse(api_endpoint) if "//" in api_endpoint else urlparse("https://" + api_endpoint)
        self._use_https = parsed.scheme == "https" or (parsed.scheme == "" and "//" not in api_endpoint)
        self._host = parsed.hostname or parsed.path or api_endpoint
        self._path = parsed.path if parsed.path and parsed.path != "/" else "/v1/chat/completions"

    def get_response(self, prompt_content):
        payload_explanation = json.dumps(
            {
                "model": self.model_LLM,
                "messages": [
                    {"role": "user", "content": prompt_content}
                ],
            }
        )

        headers = {
            "Authorization": "Bearer " + self.api_key,
            "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
            "Content-Type": "application/json",
            "x-api2d-no-cache": 1,
        }
        
        response = None
        n_trial = 1
        quota_pauses = 0
        while True:
            n_trial += 1
            if n_trial > self.n_trial:
                return response
            try:
                conn = http.client.HTTPSConnection(self._host) if self._use_https else http.client.HTTPConnection(self._host)
                conn.request("POST", self._path, payload_explanation, headers)
                res = conn.getresponse()
                status = res.status
                data = res.read()
                body = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
                if status >= 400:
                    if self.quota_auto_wait and _is_quota_or_rate_limit(status, body):
                        quota_pauses += 1
                        if self.quota_max_pauses and quota_pauses > self.quota_max_pauses:
                            return response
                        print(
                            "LLM API quota/rate limit reached; pausing "
                            f"{self.quota_pause_seconds}s before retry "
                            f"(pause #{quota_pauses})."
                        )
                        time.sleep(self.quota_pause_seconds)
                        n_trial = 1
                        continue
                    raise RuntimeError(f"LLM API HTTP {status}")
                json_data = json.loads(body)
                response = json_data["choices"][0]["message"]["content"]
                break
            except Exception:
                if self.debug_mode:
                    print("Error in API. Restarting the process...")
                continue
            

        return response
