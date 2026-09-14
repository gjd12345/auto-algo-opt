"""Provider settings shared by experiment identity and the outbound bridge."""
from urllib.parse import urlsplit


def generation_parameters(endpoint, thinking="provider-default", *, repair=False):
    result = {"temperature": 0.2 if repair else 1.0,
              "max_tokens": 8192 if repair else 16384}
    if (urlsplit(endpoint).hostname or "").endswith("opencode.ai"):
        result.update(thinking={"type": "disabled"}, reasoning={"effort": "none"})
    if thinking != "provider-default":
        result["thinking"] = {"type": thinking}
    if repair:
        result["response_format"] = {"type": "json_object"}
    return result


def generation_contract(model, endpoint, thinking, timeout):
    parameters = generation_parameters(endpoint, thinking)
    return {"protocol_version": "openai-path-bridge/v1", "model": model,
            "endpoint_identity": endpoint, "thinking": parameters.get("thinking", "provider-default"),
            "temperature": parameters["temperature"], "max_output_tokens": parameters["max_tokens"],
            "request_timeout_seconds": timeout, "concurrency": 1, "provider_seed": None,
            "generation_parameters": parameters,
            "repair_parameters": generation_parameters(endpoint, thinking, repair=True),
            "response_policy": "content_only_complete_v1"}
