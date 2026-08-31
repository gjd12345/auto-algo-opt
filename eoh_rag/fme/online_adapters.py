"""FME 在线适配器：有账本的模型请求、EOH 纯生成缝和追加式证据。"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit

from eoh_rag.experiments.provider import get_provider_config
from eoh_rag.fme.mainline import GeneratedCandidate, GenerationRequest

ROOT = Path(__file__).resolve().parents[2]


def digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class EvidenceJournal:
    """每条事件绑定前一条哈希；prospective 事件 fsync 后才允许评估。"""

    def __init__(self, directory: Path, *, actor: str) -> None:
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.actor = actor
        self.path = directory / "events.jsonl"
        self.sequence = 0
        self.previous_hash = "0" * 64

    def append(self, kind: str, payload: object) -> str:
        self.sequence += 1
        record = {"sequence": self.sequence, "kind": kind, "actor": self.actor,
                  "previous_hash": self.previous_hash, "payload": payload}
        record["content_hash"] = digest(record)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.previous_hash = str(record["content_hash"])
        return self.previous_hash

    def save_candidate(self, candidate_id: str, code: str) -> str:
        # 原始候选只保存在忽略的 run 目录，不进入正式精简证据或 Git。
        target = self.directory / "candidates" / f"{candidate_id}.py"
        target.parent.mkdir(exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8") != code:
            raise ValueError("candidate_identity_collision")
        target.write_text(code, encoding="utf-8")
        return str(target.relative_to(self.directory))


class ProviderFailure(RuntimeError):
    def __init__(self, error_code: str, status: int | None = None, *, retryable: bool = False) -> None:
        self.error_code = error_code
        self.status = status
        self.retryable = retryable
        super().__init__(error_code)


class ChatCompletionTransport:
    """不隐藏重试、不保存原始响应；每次 HTTP 请求都有成本与终态。"""

    def __init__(self, model: str, journal: EvidenceJournal, *, temperature: float,
                 generation_tokens: int, analysis_tokens: int, timeout: int = 90,
                 provider: str = "model-router", thinking: str | None = None,
                 stream: bool = False, network_retries: int = 0) -> None:
        self.config = get_provider_config(provider)
        self.thinking = thinking
        self.stream = stream
        self.model = model
        self.journal = journal
        self.temperature = temperature
        self.generation_tokens = generation_tokens
        self.analysis_tokens = analysis_tokens
        self.timeout = timeout
        if not isinstance(network_retries, int) or not 0 <= network_retries <= 2:
            raise ValueError("network_retries_must_be_zero_to_two")
        self.network_retries = network_retries
        self.usage: list[dict[str, Any]] = []

    def request(self, prompt: str, *, purpose: str, problem: str) -> str:
        # 只补偿未交付完整响应的传输故障；不因代码/分析质量重采样。
        # 完整请求参数保持相同，每次真实 HTTP 尝试都记账，失败用量未知不算零。
        for attempt in range(self.network_retries + 1):
            try:
                return self._request_once(prompt, purpose=purpose, problem=problem,
                                          transport_attempt=attempt + 1)
            except ProviderFailure as exc:
                if not exc.retryable or attempt == self.network_retries:
                    raise
                delay = 2 ** (attempt + 1)
                self.journal.append("transport_retry_scheduled", {
                    "model": self.model, "purpose": purpose, "prompt_hash": digest(prompt),
                    "failed_transport_attempt": attempt + 1, "delay_seconds": delay,
                    "error_code": exc.error_code, "boundary": "no_complete_response_was_delivered"})
                time.sleep(delay)
        raise AssertionError("unreachable_transport_retry_state")

    def _request_once(self, prompt: str, *, purpose: str, problem: str,
                      transport_attempt: int) -> str:
        api_key = os.environ.get(self.config.api_key_env, "")
        if not api_key or not self.model:
            raise ProviderFailure("missing_model_or_key")
        endpoint = urlsplit(self.config.endpoint)
        authorized_host = {"model-router": "model-router.edu-aliyun.com", "opencode-zen": "opencode.ai",
                           "opencode-go": "opencode.ai"}.get(self.config.name)
        if endpoint.scheme != "https" or endpoint.hostname != authorized_host:
            raise ProviderFailure("provider_endpoint_outside_authorized_host")
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                   "temperature": self.temperature,
                   "max_tokens": 64 if purpose == "preflight" else (
                       self.analysis_tokens if purpose == "analysis" else self.generation_tokens)}
        if self.thinking is not None:
            payload["thinking"] = {"type": self.thinking}
        if self.config.name == "opencode-go" and self.thinking == "disabled":
            # Go 网关兼容字段；两模型相同发送，并记录 reasoning 是否仍有输出。
            payload["reasoning"] = {"effort": "none"}
        if purpose == "analysis" and self.model.startswith("deepseek"):
            payload["response_format"] = {"type": "json_object"}
        if self.stream:
            payload.update(stream=True, stream_options={"include_usage": True})
        request = urllib.request.Request(self.config.endpoint, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                     "User-Agent": "agent-ad-provider-preflight/1.0"}, method="POST")
        receipt: dict[str, Any] = {"provider": self.config.name, "model": self.model, "problem": problem, "purpose": purpose,
            "prompt_hash": digest(prompt), "http_status": None, "ok": False,
            "input_tokens": None, "output_tokens": None, "error_code": None,
            "reasoning_characters": 0, "stream": self.stream,
            "transport_attempt": transport_attempt}
        started = time.monotonic()
        self.journal.append("model_request_started", {"model": self.model, "purpose": purpose,
            "prompt_hash": digest(prompt), "stream": self.stream, "transport_attempt": transport_attempt})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                receipt["http_status"] = response.status
                if self.stream:
                    parts, usage, model, finish_reason = [], {}, None, None
                    text_size = 0
                    complete = False
                    for line in response:
                        if time.monotonic()-started > self.timeout:
                            raise ProviderFailure("stream_total_timeout", retryable=True)
                        if not line.startswith(b"data:"):
                            continue
                        value = line[5:].strip()
                        if value == b"[DONE]":
                            complete = True
                            break
                        chunk = json.loads(value)
                        if chunk.get("error"):
                            raise ProviderFailure("stream_provider_error", response.status)
                        model = chunk.get("model") or model
                        usage = chunk.get("usage") or usage
                        for choice in chunk.get("choices", []):
                            finish_reason = choice.get("finish_reason") or finish_reason
                            receipt["reasoning_characters"] += len(choice.get("delta", {}).get("reasoning_content") or "")
                            part = choice.get("delta", {}).get("content")
                            if part:
                                if not isinstance(part, str):
                                    raise ProviderFailure("nontext_stream_chunk")
                                if not parts:
                                    receipt["first_text_seconds"] = round(time.monotonic()-started, 4)
                                parts.append(part)
                                text_size += len(part)
                                if text_size > 4*1024*1024:
                                    raise ProviderFailure("response_size_limit")
                    if not complete:
                        raise ProviderFailure("stream_missing_terminal_marker", retryable=True)
                    parsed = {"model": model, "usage": usage,
                        "choices": [{"message": {"content": "".join(parts)}, "finish_reason": finish_reason}]}
                else:
                    parsed = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
            choices = parsed.get("choices", [])
            content = choices[0].get("message", {}).get("content") if choices else None
            usage = parsed.get("usage") or {}
            receipt["response_model"] = parsed.get("model")
            receipt["finish_reason"] = choices[0].get("finish_reason") if choices else None
            receipt["input_tokens"] = usage.get("prompt_tokens")
            receipt["output_tokens"] = usage.get("completion_tokens")
            if not isinstance(content, str) or not content.strip():
                raise ProviderFailure("empty_or_nontext_completion", receipt["http_status"])
            receipt["ok"] = True
            return content
        except urllib.error.HTTPError as exc:
            receipt["http_status"] = exc.code
            # 不把网关原始正文写到异常/日志，避免认证信息或响应内容泄漏。
            receipt["error_code"] = "model_or_permission_denied" if exc.code in {401, 403} else f"http_{exc.code}"
            raise ProviderFailure(receipt["error_code"], exc.code,
                                  retryable=exc.code in {408, 429, 500, 502, 503, 504}) from None
        except ProviderFailure as exc:
            receipt["error_code"] = exc.error_code
            raise
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            receipt["error_code"] = type(exc).__name__
            raise ProviderFailure("provider_connectivity_or_protocol_error",
                                  retryable=isinstance(exc, OSError)) from None
        finally:
            receipt["elapsed_seconds"] = round(time.monotonic() - started, 4)
            self.usage.append(receipt)
            self.journal.append("model_request", receipt)


class FixtureTransport:
    """仅用于显式 integration-smoke；不是模型发现，也不产生研究结论。"""

    def __init__(self, model: str, journal: EvidenceJournal, spec: dict[str, str]) -> None:
        self.model, self.journal, self.spec = model, journal, spec
        self.usage: list[dict[str, Any]] = []
        self.generations = 0

    def request(self, prompt: str, *, purpose: str, problem: str) -> str:
        receipt = {"purpose": purpose, "problem": problem, "model": self.model,
                   "prompt_hash": digest(prompt), "ok": True, "network_request": False,
                   "input_tokens": None, "output_tokens": None, "elapsed_seconds": 0.0}
        self.usage.append(receipt)
        self.journal.append("fixture_request", receipt)
        if purpose == "analysis":
            return json.dumps({"observation": "integration fixture; no scientific claim",
                "mechanism_hypothesis": "exercise prospective-record wiring only",
                "predicted_effect": -0.01, "predicted_success_probability": 0.25,
                "predicted_regime": "frozen development suite", "predicted_risk": "fixture can regress",
                "cheapest_falsification": "compare on the independent development probe",
                "next_action": "repair_failed_mechanism"})
        self.generations += 1
        code = self.spec["baseline_code"]
        if self.generations % 2 == 0:
            code = code.replace("argmin", "argmax")
            if problem == "bp_online":
                code = code.replace("return -(bins - item)", "return bins - item")
        return "{Deterministic integration fixture, not model discovery}\n```python\n" + code + "\n```"


class EOHGeneratorAdapter:
    """复用 vendored EOH 的 prompt/extraction，不创建或运行 EOH 主控制器。"""

    def __init__(self, spec: dict[str, str], transport: Any) -> None:
        official_src = str(ROOT / "official_eoh" / "eoh" / "src")
        if official_src not in sys.path:
            sys.path.insert(0, official_src)
        from eoh.eoh.evolution import Evolution
        # 离线构造只为避开 InterfaceLLM.__init__ 中隐藏的连通性请求；所有实际模型调用
        # 都走上方有账本的 transport。不会调用 n1 或启动 EOH.evolve。
        config = SimpleNamespace(debug=False, n_parents=2, feedback_policy="objective_aware", operators=["n1"])
        problem = SimpleNamespace(**spec, n_processes=1, timeout=20)
        self.eoh = Evolution(config, problem)
        self.transport = transport
        self.parents: list[dict[str, Any]] = []
        self.last_prompt_hash = ""

    def generate(self, request: GenerationRequest) -> tuple[GeneratedCandidate, ...]:
        if not self.parents:
            operator, parents = "i1", None
        elif request.scientific_action == "repair_failed_mechanism":
            operator, parents = "m1", self.parents[0]
        else:
            operator, parents = "e1", self.parents[:2]
        prompt = self.eoh._build_prompt(operator, parents)
        prompt += "\nNUMERIC EXECUTION CONTRACT: numpy/math only; no files, network, reflection or imports of other modules.\n"
        prompt += request.context
        self.last_prompt_hash = digest(prompt)
        response = self.transport.request(prompt, purpose="generation", problem=request.problem)
        algorithms, codes = self.eoh._extract(response)
        if not codes:
            return ()
        if not algorithms:
            # 一些模型只返回代码。说明缺失不等于算法无效；机制分析由独立前瞻调用完成。
            # 这里仅标记缺失，不能替模型编造科学解释。
            algorithms = ["Candidate program; no separate algorithm description was supplied."]
        self.transport.journal.append("generation_extraction", {"operator": operator,
            "code_count": len(codes), "separate_description_present": algorithms[0] != "Candidate program; no separate algorithm description was supplied."})
        return (GeneratedCandidate(code=self.eoh._prepend_imports(codes[0]), algorithm=algorithms[0],
            parent_candidate_ids=request.parent_candidate_ids, operator=operator),)


def verify_journal(path: Path) -> dict[str, Any]:
    previous = "0" * 64
    prospective: dict[str, tuple[str, str]] = {}
    count = 0
    for count, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(line)
        signature = record.pop("content_hash")
        if record["sequence"] != count or record["previous_hash"] != previous or digest(record) != signature:
            raise ValueError("journal_hash_chain_invalid")
        payload = record["payload"]
        if record["kind"] == "prospective_analysis":
            prospective[signature] = (payload["candidate_id"], payload["analysis_id"])
        if record["kind"] == "candidate_evaluation":
            if prospective.get(payload["analysis_event_hash"]) != (payload["candidate_id"], payload["analysis_id"]):
                raise ValueError("evaluation_without_matching_prospective_analysis")
        previous = signature
    return {"event_count": count, "terminal_hash": previous, "prospective_count": len(prospective)}
