from __future__ import annotations

import unittest

from Agent_EOH.eoh.src.eoh.llm.api_general import _is_quota_or_rate_limit


class TestAPIGeneralQuota(unittest.TestCase):
    def test_quota_status_codes_are_retryable(self) -> None:
        self.assertTrue(_is_quota_or_rate_limit(402, ""))
        self.assertTrue(_is_quota_or_rate_limit(429, ""))

    def test_quota_body_markers_are_retryable(self) -> None:
        self.assertTrue(_is_quota_or_rate_limit(400, "Insufficient Balance"))
        self.assertTrue(_is_quota_or_rate_limit(500, "rate_limit exceeded"))

    def test_normal_error_is_not_quota(self) -> None:
        self.assertFalse(_is_quota_or_rate_limit(401, "unauthorized"))
        self.assertFalse(_is_quota_or_rate_limit(500, "internal server error"))


if __name__ == "__main__":
    unittest.main()
