"""Durable, bounded transport wrapper for the interrupted RQ1b run.

The wrapper deliberately checkpoints only complete successful responses.  A
checkpoint makes an exact response replay/audit possible; it is not a full
cell-resume mechanism.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Mapping

from eoh_rag.fme.online_adapters import (
    ChatCompletionTransport,
    EvidenceJournal,
    ProviderFailure,
    digest,
)


_CHECKPOINT_NAME = re.compile(r"^request-(\d{1,20})\.json$")


class DurableTransport(ChatCompletionTransport):
    """Chat transport with durable success checkpoints and finite recovery.

    ``protocol`` is the RQ1b protocol mapping and ``journal`` is the cell's
    existing :class:`EvidenceJournal`.  ``spec`` is accepted for callers that
    already pass the problem specification; it is intentionally not used to
    alter request parameters.
    """

    def __init__(self, protocol: Mapping[str, Any], journal: EvidenceJournal,
                 spec: Mapping[str, Any] | None = None) -> None:
        del spec
        p = protocol
        if p['network_retries'] != 2:
            raise ValueError('durable_transport_requires_two_inner_retries')
        super().__init__(
            p["resolved_model"], journal,
            temperature=p["temperature"],
            generation_tokens=p["generation_max_tokens"],
            analysis_tokens=p["analysis_max_tokens"],
            timeout=p["provider_timeout_seconds"],
            provider=p.get("provider", "model-router"),
            thinking=p.get("thinking"),
            stream=bool(p.get("stream", False)),
            network_retries=2,
        )
        self.protocol = dict(p)
        recovery = p.get("transport_recovery", {})
        if (recovery.get("additional_cycles", 2) != 2 or
                recovery.get("delays_seconds", [10, 30]) != [10, 30] or
                recovery.get("max_http_attempts_per_logical_request", 9) != 9):
            raise ValueError("unsupported_transport_recovery_policy")
        self.checkpoint_root = (journal.directory / "checkpoints").resolve()
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self._ordinal = self._find_next_ordinal()

    def _find_next_ordinal(self) -> int:
        highest = 0
        for path in self.checkpoint_root.glob("request-*.json"):
            match = _CHECKPOINT_NAME.match(path.name)
            if match:
                highest = max(highest, int(match.group(1)))
        return highest + 1

    def _request_spec(self, prompt: str, purpose: str, problem: str) -> dict[str, Any]:
        max_tokens = 64 if purpose == "preflight" else (
            self.analysis_tokens if purpose == "analysis" else self.generation_tokens)
        # This is a non-secret description of the exact request shape sent by
        # ChatCompletionTransport._request_once.
        return {
            "model": self.model,
            "purpose": purpose,
            "problem": problem,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "thinking": self.thinking,
            "stream": self.stream,
            "provider": self.config.name,
            "prompt_hash": digest(prompt),
            "response_format": {"type": "json_object"}
            if purpose == "analysis" and self.model.startswith("deepseek") else None,
            "reasoning": {"effort": "none"}
            if self.config.name == "opencode-go" and self.thinking == "disabled" else None,
            "stream_options": {"include_usage": True} if self.stream else None,
        }

    def _checkpoint(self, ordinal: int, prompt: str, response: str, *,
                    purpose: str, problem: str) -> tuple[Path, str, str]:
        spec = self._request_spec(prompt, purpose, problem)
        spec_hash = digest(spec)
        response_hash = digest(response)
        payload = {
            "schema_version": "rq1b-request-checkpoint/v1",
            "protocol_hash": self.protocol["protocol_hash"],
            "actor": self.journal.actor,
            "ordinal": ordinal,
            "purpose": purpose,
            "problem": problem,
            "prompt_hash": digest(prompt),
            "model": self.model,
            "request_spec_hash": spec_hash,
            "request_spec": spec,
            "prompt": prompt,
            "response": response,
            "response_hash": response_hash,
        }
        target = self.checkpoint_root / f"request-{ordinal:06d}.json"
        temporary = target.with_name(target.name + f".tmp-{os.getpid()}-{time.monotonic_ns()}")
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                             sort_keys=True, indent=2).encode("utf-8")
        try:
            with temporary.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        # A directory fsync closes the rename durability window where the
        # file is durable but its directory entry is not yet persisted.
        try:
            directory_fd = os.open(self.checkpoint_root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
        relative = target.relative_to(self.checkpoint_root).as_posix()
        return target, relative, spec_hash

    def request(self, prompt: str, *, purpose: str, problem: str) -> str:
        # Each outer cycle invokes the base transport unchanged: its own
        # network_retries=2 therefore gives at most 3 HTTP requests per cycle.
        for cycle in range(3):
            delay = (0, 10, 30)[cycle]
            if cycle:
                self.journal.append("recovery_started", {
                    "cycle": cycle + 1,
                    "delay_seconds": delay,
                    "model": self.model,
                    "purpose": purpose,
                    "problem": problem,
                    "prompt_hash": digest(prompt),
                    "boundary": "same_request_spec_retryable_provider_failure_only",
                })
                time.sleep(delay)
            else:
                self.journal.append("recovery_started", {
                    "cycle": 1, "delay_seconds": 0, "model": self.model,
                    "purpose": purpose, "problem": problem,
                    "prompt_hash": digest(prompt),
                    "boundary": "initial_request_cycle",
                })
            try:
                response = super().request(prompt, purpose=purpose, problem=problem)
            except ProviderFailure as exc:
                if not exc.retryable or cycle == 2:
                    raise
                continue
            ordinal = self._ordinal
            target, relative, spec_hash = self._checkpoint(
                ordinal, prompt, response, purpose=purpose, problem=problem)
            self._ordinal += 1
            self.journal.append("checkpoint_saved", {
                "ordinal": ordinal,
                "path": relative,
                "prompt_hash": digest(prompt),
                "response_hash": digest(response),
                "request_spec_hash": spec_hash,
            })
            return response
        raise AssertionError("unreachable_durable_recovery_state")


def read_checkpoint(path: Path, checkpoint_root: Path | None = None) -> dict[str, Any]:
    """Read and validate one checkpoint, rejecting path escapes and hash drift."""
    target = Path(path)
    root = Path(checkpoint_root).resolve() if checkpoint_root is not None else target.parent.resolve()
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("checkpoint_path_outside_root") from exc
    if resolved.name != target.name or not _CHECKPOINT_NAME.match(resolved.name):
        raise ValueError("invalid_checkpoint_path")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if payload.get("prompt_hash") != digest(payload.get("prompt", "")):
        raise ValueError("checkpoint_prompt_hash_invalid")
    if payload.get("response_hash") != digest(payload.get("response", "")):
        raise ValueError("checkpoint_response_hash_invalid")
    if payload.get("request_spec_hash") != digest(payload.get("request_spec")):
        raise ValueError("checkpoint_request_spec_hash_invalid")
    return payload
