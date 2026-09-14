import json

import pytest

from tools.export_benchmark_evidence import digest, encoded, verify_bundle


def test_bundle_rejects_tampering_extra_files_and_escape(tmp_path):
    raw = encoded({"objective": 0.2})
    (tmp_path / "facts.json").write_bytes(raw)
    manifest = tmp_path / "SHA256SUMS.json"
    manifest.write_bytes(encoded({"facts.json": digest(raw)}))
    assert verify_bundle(tmp_path)["verified"]
    (tmp_path / "facts.json").write_bytes(encoded({"objective": 0.0}))
    with pytest.raises(ValueError, match="hash_mismatch"):
        verify_bundle(tmp_path)
    (tmp_path / "facts.json").write_bytes(raw)
    (tmp_path / "unexpected.json").write_text("{}")
    with pytest.raises(ValueError, match="inventory_mismatch"):
        verify_bundle(tmp_path)
    manifest.write_text(json.dumps({"../outside.json": digest(raw)}))
    with pytest.raises(ValueError):
        verify_bundle(tmp_path)
