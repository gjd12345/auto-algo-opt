"""实验 Provider 配置、脱敏审计和错误分类。"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

@dataclass(frozen=True)
class ProviderConfig:
    name: str
    endpoint: str
    model: str
    api_key_env: str

    def audit_record(self) -> dict[str, object]:
        """只暴露 host 与密钥是否存在，避免认证信息进入证据。"""
        return {"provider_name": self.name, "endpoint_host": urlsplit(self.endpoint).hostname or "", "model": self.model, "key_present": bool(os.environ.get(self.api_key_env))}

def get_provider_config(name: str) -> ProviderConfig:
    if name == "opencode-go":
        return ProviderConfig(name, "https://opencode.ai/zen/go/v1/chat/completions", "deepseek-v4-flash", "OPENCODE_GO_API_KEY")
    if name == "deepseek":
        return ProviderConfig(name, "https://api.deepseek.com/chat/completions", "deepseek-chat", "DEEPSEEK_API_KEY")
    raise ValueError(f"unsupported provider: {name}")

def classify_provider_error(status_code: int | None, message: str) -> str:
    normalized = message.lower()
    if status_code in {401, 403} or any(
        token in normalized
        for token in (
            "http_status=401",
            "http_status=403",
            "authentication fails",
            "invalid api key",
            "invalid_api_key",
        )
    ):
        return "provider_auth_invalid"
    if status_code == 429 or "rate limit" in normalized:
        return "provider_rate_limited"
    if any(token in normalized for token in ("quota", "insufficient balance", "credits exhausted")):
        return "provider_quota_exhausted"
    return "provider_error"

def probe_provider(
    name: str,
    timeout: int = 30,
    model: str | None = None,
) -> dict[str, object]:
    """在创建正式 run 坐标前执行一次脱敏连通性预检。

    预检只返回 Provider、模型、HTTP 状态和错误类别，不保留响应正文或密钥。
    它用于阻止无效认证、额度或网络故障扩散成一批不完整正式坐标。
    """
    config = get_provider_config(name)
    audit = config.audit_record()
    effective_model = (model or "").strip() or config.model
    audit["model"] = effective_model
    api_key = os.environ.get(config.api_key_env, "")
    result: dict[str, object] = {
        **audit,
        "ok": False,
        "http_status": None,
        "error_class": None,
        "error_code": None,
    }
    if not api_key:
        result["error_class"] = "provider_auth_missing"
        return result

    payload = json.dumps(
        {
            "model": effective_model,
            "messages": [{"role": "user", "content": "Reply with only 2: 1+1=?"}],
            "max_tokens": 8,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        config.endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agent-ad-provider-preflight/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8", "replace"))
            result["http_status"] = int(response.status)
            if parsed.get("choices"):
                result["ok"] = True
                return result
            error = parsed.get("error") or {}
            result["error_code"] = error.get("type") or error.get("code") or "missing_choices"
            result["error_class"] = classify_provider_error(
                int(response.status),
                str(error.get("message", "")),
            )
    except urllib.error.HTTPError as exc:
        result["http_status"] = int(exc.code)
        raw_body = exc.read().decode("utf-8", "replace")
        try:
            error = json.loads(raw_body).get("error") or {}
        except (json.JSONDecodeError, AttributeError):
            error = {}
        error_message = str(error.get("message", ""))
        result["error_code"] = error.get("type") or error.get("code") or "http_error"
        result["error_class"] = classify_provider_error(int(exc.code), error_message)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        result["error_code"] = type(exc).__name__
        result["error_class"] = "provider_connectivity_error"
    except (json.JSONDecodeError, TypeError, ValueError, UnicodeDecodeError) as exc:
        result["error_code"] = type(exc).__name__
        result["error_class"] = "provider_protocol_error"
    return result

def temperature_for(schedule: str, generation: int, total_generations: int, base: float | None) -> float | None:
    if schedule == "fixed" or base is None:
        return base
    progress = min(max(generation, 0), max(total_generations - 1, 0)) / max(total_generations - 1, 1)
    if schedule == "linear":
        return max(0.0, base * (1.0 - progress))
    if schedule == "step-down":
        return base if progress < 0.5 else base * 0.5
    raise ValueError(f"unsupported temperature schedule: {schedule}")
