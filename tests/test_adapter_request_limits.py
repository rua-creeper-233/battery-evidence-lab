"""Reject invalid lengths before reading or tokenizing a request body."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finetune.serve_adapter import Handler, request_rejection  # noqa: E402


class NeverRead:
    def read(self, size):
        raise AssertionError(f"invalid request reached body read: {size}")


class FakeHandler:
    path = "/v1/chat/completions"
    rfile = NeverRead()

    def __init__(self, length, **headers):
        base = {"Host": "127.0.0.1:8766", "Content-Type": "application/json"}
        base.update(headers)
        self.headers = base if length is None else {**base, "Content-Length": length}
        self.result = None

    def _json(self, payload, status=200):
        self.result = payload, status


class AdapterRequestLimitTests(unittest.TestCase):
    def test_invalid_lengths_do_not_read_body(self):
        for length in (None, "0", "-1", str(2 * 1024 * 1024 + 1), "invalid"):
            with self.subTest(length=length):
                handler = FakeHandler(length)
                Handler.do_POST(handler)
                payload, status = handler.result
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["type"], "ValueError")


    def test_cross_site_and_rebinding_requests_are_refused_before_reading(self):
        cases = (
            {"Origin": "https://evil.example"},
            {"Host": "attacker.example:8766"},
            {"Content-Type": "text/plain"},
        )
        for headers in cases:
            with self.subTest(headers=headers):
                handler = FakeHandler("10", **headers)
                Handler.do_POST(handler)
                payload, status = handler.result
                self.assertEqual(status, 403)
                self.assertEqual(payload["error"]["type"], "forbidden")

    def test_optional_token_is_enforced(self):
        good = {"Host": "localhost:8766", "Content-Type": "application/json", "Authorization": "Bearer s3cret-token"}
        self.assertEqual(request_rejection(good, "s3cret-token"), "")
        self.assertIn("token", request_rejection({**good, "Authorization": "Bearer nope"}, "s3cret-token"))
        self.assertEqual(request_rejection({"Host": "[::1]:8766", "Content-Type": "application/json"}), "")


if __name__ == "__main__":
    unittest.main()
