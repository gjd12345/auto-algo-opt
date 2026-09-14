"""Derive public response diagnostics from ledger-linked exchange evidence."""
import hashlib
import json
from statistics import median


def derive_generation_diagnostics(root, requests):
    exchanges = {}
    for path in root.glob("rounds/*/eoh_run/results/exchanges/request_*.json"):
        raw = path.read_bytes()
        exchange = json.loads(raw)
        request_id = exchange.get("request_id")
        if request_id in exchanges:
            raise ValueError("duplicate_exchange_request_identity")
        exchanges[request_id] = (path, raw, exchange)
    rows = []
    for request in requests:
        row = {key: request[key] for key in ("sequence", "round_id", "purpose", "state", "error_code", "finish_reason")}
        row.update(response_chars=None, response_bytes=None, source_ref=None, source_sha256=None)
        match = exchanges.get(request["request_id"])
        if match:
            path, raw, exchange = match
            response = exchange["response"]
            if (exchange["request_index"] != request["sequence"] or exchange["purpose"] != request["purpose"]
                    or exchange["response_sha256"] != hashlib.sha256(response.encode()).hexdigest()
                    or exchange.get("finish_reason") != request["finish_reason"]):
                raise ValueError("diagnostic_exchange_identity_mismatch")
            row.update(response_chars=len(response), response_bytes=len(response.encode()),
                       source_ref=path.relative_to(root).as_posix(), source_sha256=hashlib.sha256(raw).hexdigest())
        rows.append(row)
    generation = [r for r in rows if r["purpose"] == "eoh_generation"]
    lengths = [r["response_chars"] for r in generation if r["response_chars"] is not None]
    completed = sum(r["state"] == "complete" for r in generation)
    truncated = sum(r["finish_reason"] == "length" for r in generation)
    return {"schema_version": "generation-diagnostics/v1", "requests": rows,
            "generation": {"completed": completed, "truncated": truncated,
                "truncated_fraction_of_completed": truncated / completed if completed else None,
                "empty": sum(r["response_chars"] == 0 for r in generation),
                "missing_response_evidence": sum(r["response_chars"] is None for r in generation),
                "unknown": sum(r["state"] in {"unknown", "sent", "reserved"} for r in generation),
                "repair_requests": sum(r["purpose"] == "eoh_repair" for r in rows),
                "parse_failed": None, "recovered": None,
                "recovery_observability": "upstream_retry_lineage_not_recorded; not inferred from adjacent requests",
                "response_chars": {"min": min(lengths) if lengths else None,
                    "median": median(lengths) if lengths else None, "max": max(lengths) if lengths else None}}}
