"""Unified LLM client for OpenAI-compatible APIs."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from typing import Any


def normalize_endpoint(endpoint: str) -> str:
    """Normalize endpoint to a full URL ending in /v1/chat/completions."""
    value = (endpoint or "").strip()
    if not value:
        return ""
    value = value.rstrip("/")
    if value.startswith(("http://", "https://")):
        if "/" in value.removeprefix("https://").removeprefix("http://"):
            return value
        return value + "/v1/chat/completions"
    if "/" in value:
        return "https://" + value
    return "https://" + value + "/v1/chat/completions"


def chat_completion(
    messages: list[dict[str, str]],
    *,
    api_key: str = "",
    endpoint: str = "",
    model: str = "",
    temperature: float = 0.7,
    timeout_s: int = 60,
    max_retries: int = 3,
    response_format: dict[str, Any] | None = None,
    max_tokens: int | None = None,
) -> str:
    """Call an OpenAI-compatible chat completion endpoint.

    Falls back to DEEPSEEK_API_KEY / DEEPSEEK_API_ENDPOINT / DEEPSEEK_MODEL
    environment variables when parameters are empty.

    Returns the assistant message content as a string.
    Raises RuntimeError after max_retries exhausted.
    """
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    endpoint = endpoint or os.environ.get("DEEPSEEK_API_ENDPOINT", "")
    model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")

    if not api_key:
        raise RuntimeError("LLM API key not provided and DEEPSEEK_API_KEY not set")
    if not endpoint:
        raise RuntimeError("LLM endpoint not provided and DEEPSEEK_API_ENDPOINT not set")

    url = normalize_endpoint(endpoint)

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        body["response_format"] = response_format
    if max_tokens:
        body["max_tokens"] = max_tokens

    payload = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "eoh-experiment/1.0",
    }

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                parsed = json.loads(resp.read().decode("utf-8", "replace"))
            choices = parsed.get("choices")
            if not choices:
                error_msg = parsed.get("error", {}).get("message", str(parsed))
                raise ValueError(f"API returned no choices: {error_msg}")
            return choices[0]["message"]["content"]
        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        f"LLM call failed after {max_retries} attempts (endpoint={re.sub(r'https?://', '', url).split('/')[0]}, "
        f"model={model}): {last_error}"
    )
