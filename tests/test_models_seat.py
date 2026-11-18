"""Seat-on-select (Zak's play session, 2026-11-17): selecting a
model must actually seat it in Ollama, proven via /api/ps — and
the app must refuse a seat the machine cannot hold BEFORE the
kernel kills the Ollama service doing it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import models  # noqa: E402


class FitCheckTests(unittest.TestCase):
    def test_the_laptop_case_refuses_the_8b(self):
        ok, line = models.fit_check(5.2, 3.1)
        self.assertFalse(ok)
        self.assertIn("killed by the kernel", line)
        self.assertIn("6.8", line)  # 5.2 x 1.3, named

    def test_the_paired_3b_fits(self):
        ok, line = models.fit_check(2.0, 3.1)
        self.assertTrue(ok)
        self.assertIn("fits", line)

    def test_boundary_is_the_need(self):
        ok, _line = models.fit_check(2.0, 2.6)
        self.assertTrue(ok)
        ok, _line = models.fit_check(2.0, 2.59)
        self.assertFalse(ok)


class FakeOpener:
    def __init__(self, ps_models=(), fail_generate=False):
        self.calls = []
        self.ps_models = list(ps_models)
        self.fail_generate = fail_generate

    def __call__(self, method, url, payload=None, timeout=5,
                 headers=None):
        self.calls.append((method, url, payload))
        if url.endswith("/api/generate"):
            if self.fail_generate:
                raise ConnectionError("EOF")
            return 200, {"done": True}
        if url.endswith("/api/ps"):
            return 200, {"models": self.ps_models}
        if url.endswith("/api/tags"):
            return 200, {"models": [
                {"name": "qwen2.5:3b", "size": 2 * 1024 ** 3}]}
        raise AssertionError(url)


class SeatTests(unittest.TestCase):
    def test_seat_loads_then_proves_via_ps(self):
        op = FakeOpener(ps_models=[
            {"name": "qwen2.5:3b", "size": 2 * 1024 ** 3,
             "details": {"family": "qwen2"}}])
        ok, line = models.seat_model("qwen2.5:3b", opener=op)
        self.assertTrue(ok)
        self.assertIn("Seated", line)
        gen = [c for c in op.calls if c[1].endswith("/api/generate")]
        self.assertEqual(gen[0][2]["keep_alive"], "30m")
        self.assertEqual(gen[0][2]["prompt"], "")

    def test_unproven_seat_is_reported_not_claimed(self):
        op = FakeOpener(ps_models=[])
        ok, line = models.seat_model("qwen2.5:3b", opener=op)
        self.assertFalse(ok)
        self.assertIn("not seated", line)

    def test_generate_failure_is_honest(self):
        op = FakeOpener(fail_generate=True)
        ok, line = models.seat_model("qwen2.5:3b", opener=op)
        self.assertFalse(ok)
        self.assertIn("could not be seated", line)

    def test_discover_sizes(self):
        sizes = models.discover_sizes(opener=FakeOpener())
        self.assertEqual(sizes, {"qwen2.5:3b": 2.0})


class ClientWiringTests(unittest.TestCase):
    def test_selection_seats_and_the_header_says_so(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "source", "app",
                                "ai-client.py")).read()
        self.assertIn("target=self._seat_current_model", src)
        self.assertIn("model_stacks.seat_model(name)", src)
        self.assertIn("model_stacks.fit_check(size, avail)", src)
        self.assertIn("Not seated", src)


if __name__ == "__main__":
    unittest.main()
