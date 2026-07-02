"""
模块：eoh_rag.llm.client
功能：提供一个统一的大语言模型（LLM）调用客户端，对接所有兼容 OpenAI 接口协议的服务。
职责：负责把接口地址补全成标准 URL，组装请求体、设置鉴权头，并在网络出错时做带退避的自动重试。
接口：
    - normalize_endpoint(endpoint: str) -> str：把简写地址补全为完整的 /v1/chat/completions URL。
    - chat_completion(messages, *, api_key, endpoint, model, temperature,
        timeout_s, max_retries, response_format, max_tokens) -> str：发起对话补全请求并返回回复文本。
输入：
    - 参数：对话消息列表、可选的 api_key / endpoint / model 等调用配置。
    - 环境变量：当对应参数为空时回退读取 DEEPSEEK_API_KEY、DEEPSEEK_API_ENDPOINT、DEEPSEEK_MODEL。
输出：模型返回的助手回复内容（字符串）；重试全部失败时抛出 RuntimeError。
示例：
    >>> reply = chat_completion([{"role": "user", "content": "你好"}])
    >>> print(reply)
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from typing import Any


def normalize_endpoint(endpoint: str) -> str:
    """把用户填写的接口地址补全成完整的调用 URL，统一以 /v1/chat/completions 结尾。

    兼容几种常见写法：只填域名、填域名加协议、或填完整路径。

    参数：
        endpoint：原始接口地址，允许为空或带多余的结尾斜杠。
    返回：
        补全后的完整 URL；若传入为空则返回空字符串。
    """
    value = (endpoint or "").strip()
    if not value:
        return ""
    value = value.rstrip("/")  # 去掉结尾多余的斜杠，避免拼接出双斜杠
    if value.startswith(("http://", "https://")):
        # 已带协议：去掉协议头后若还含 "/"，说明已经是完整路径，直接返回
        if "/" in value.removeprefix("https://").removeprefix("http://"):
            return value
        # 只有域名，没有路径，补上标准的接口路径
        return value + "/v1/chat/completions"
    # 未带协议：含 "/" 视为已带路径，只补 https:// 前缀
    if "/" in value:
        return "https://" + value
    # 未带协议且只有域名：既补协议头又补标准接口路径
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
    """调用兼容 OpenAI 协议的对话补全接口，返回助手回复文本。

    当 api_key / endpoint / model 参数为空时，会依次回退读取环境变量
    DEEPSEEK_API_KEY、DEEPSEEK_API_ENDPOINT、DEEPSEEK_MODEL。

    参数：
        messages：对话消息列表，每条形如 {"role": ..., "content": ...}。
        api_key：接口密钥；为空则读环境变量。
        endpoint：接口地址；为空则读环境变量，内部会自动补全为完整 URL。
        model：模型名；为空则读环境变量，默认 deepseek-v4-pro。
        temperature：采样温度，值越大回复越发散。
        timeout_s：单次请求的超时秒数。
        max_retries：最大重试次数（含首次），失败时按指数退避等待后重试。
        response_format：可选的返回格式约束（如要求 JSON）。
        max_tokens：可选的最大生成 token 数。
    返回：
        模型回复的正文内容（字符串）。
    异常：
        缺少密钥或地址时立即抛出 RuntimeError；请求重试全部失败后抛出 RuntimeError。
    """
    # 参数为空时回退到环境变量，方便统一在环境中配置密钥与地址
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    endpoint = endpoint or os.environ.get("DEEPSEEK_API_ENDPOINT", "")
    model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")

    if not api_key:
        raise RuntimeError("LLM API key not provided and DEEPSEEK_API_KEY not set")
    if not endpoint:
        raise RuntimeError("LLM endpoint not provided and DEEPSEEK_API_ENDPOINT not set")

    url = normalize_endpoint(endpoint)  # 把地址补全成完整的请求 URL

    # 组装请求体：模型、消息与温度为必填，其余按需附加
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        body["response_format"] = response_format
    if max_tokens:
        body["max_tokens"] = max_tokens

    payload = json.dumps(body).encode("utf-8")  # 序列化为 UTF-8 字节流用于 POST
    headers = {
        "Authorization": f"Bearer {api_key}",  # Bearer 令牌鉴权
        "Content-Type": "application/json",
        "User-Agent": "eoh-experiment/1.0",
    }

    last_error: Exception | None = None  # 记录最近一次异常，用于最终报错信息
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                # 解码时用 "replace" 容错，避免个别非法字节导致整体解析失败
                parsed = json.loads(resp.read().decode("utf-8", "replace"))
            choices = parsed.get("choices")
            if not choices:
                # 没有 choices 通常意味着服务端返回了错误，尽量提取其中的错误信息
                error_msg = parsed.get("error", {}).get("message", str(parsed))
                raise ValueError(f"API returned no choices: {error_msg}")
            return choices[0]["message"]["content"]  # 取第一条回复的正文
        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避：1s、2s、4s……再重试

    # 所有重试都失败：报错信息里只保留主机名，避免泄露完整 URL 中的敏感路径
    raise RuntimeError(
        f"LLM call failed after {max_retries} attempts (endpoint={re.sub(r'https?://', '', url).split('/')[0]}, "
        f"model={model}): {last_error}"
    )
