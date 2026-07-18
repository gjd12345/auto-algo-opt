"""实验 Provider 配置、脱敏审计和错误分类。"""
from __future__ import annotations
import os
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

def temperature_for(schedule: str, generation: int, total_generations: int, base: float | None) -> float | None:
    if schedule == "fixed" or base is None:
        return base
    progress = min(max(generation, 0), max(total_generations - 1, 0)) / max(total_generations - 1, 1)
    if schedule == "linear":
        return max(0.0, base * (1.0 - progress))
    if schedule == "step-down":
        return base if progress < 0.5 else base * 0.5
    raise ValueError(f"unsupported temperature schedule: {schedule}")
