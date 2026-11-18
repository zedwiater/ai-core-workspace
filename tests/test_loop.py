"""Baseline: core.loop — tool dispatch formatting + the cycle itself."""
import unittest

from tests import __init__ as _path  # noqa: F401
from core import loop


def _fake_call_factory(responses):
    def call(port, payload, **kw):
        return responses.get((port, payload.get("action")),
                             {"status": "error", "message": "nope"})
    return call


class TestDispatch(unittest.TestCase):
    def test_files_read(self):
        call = _fake_call_factory(
            {(9101, "read"): {"status": "ok", "size": 3,
                              "content": "abc"}})
        out = loop.execute_tool_payload(
            'TOOL:files:read:{"path": "/x"}', call=call)
        self.assertIn("abc", out)

    def test_memory_get(self):
        call = _fake_call_factory(
            {(9108, "get"): {"status": "ok", "value": "hello"}})
        out = loop.execute_tool_payload(
            'TOOL:memory:get:{"key": "k"}', call=call)
        self.assertEqual(out, "Memory: hello")

    def test_vision_list(self):
        call = _fake_call_factory(
            {(9103, "list"): {"status": "ok", "count": 2,
                              "cameras": ["a", "b"]}})
        out = loop.execute_tool_payload(
            "TOOL:vision:list:{}", call=call)
        self.assertIn("Cameras (2)", out)

    def test_error_surfaces(self):
        call = _fake_call_factory({})
        out = loop.execute_tool_payload(
            'TOOL:files:read:{"path": "/x"}', call=call)
        self.assertIn("Files error: nope", out)

    def test_unknown_tool(self):
        out = loop.execute_tool_payload(
            "TOOL:bogus:act:{}", call=_fake_call_factory({}))
        self.assertEqual(out, "Unknown tool command.")

    def test_malformed_token_is_tool_error(self):
        out = loop.execute_tool_payload("TOOL:broken",
                                        call=_fake_call_factory({}))
        self.assertTrue(out.startswith("Tool error:"))


class TestCycle(unittest.TestCase):
    def test_tool_then_answer(self):
        replies = iter(['TOOL:memory:get:{"key": "k"}', "the answer"])
        emitted = []
        history = []
        loop.run_tool_loop(
            history,
            chat=lambda h: next(replies),
            emit=lambda text, sender: emitted.append((sender, text)),
            execute=lambda tok: "stored-value")
        senders = [s for s, _ in emitted]
        self.assertIn("system", senders)
        self.assertEqual(emitted[-1], ("ai", "the answer"))
        self.assertEqual(history[-1],
                         {"role": "assistant", "content": "the answer"})
        self.assertTrue(any("TOOL_RESULT" in h.get("content", "")
                            for h in history))

    def test_chat_error_breaks_cleanly(self):
        emitted = []

        def bad_chat(h):
            raise RuntimeError("model down")

        loop.run_tool_loop([], chat=bad_chat,
                           emit=lambda t, s: emitted.append(t))
        self.assertTrue(any("model down" in t for t in emitted))


if __name__ == "__main__":
    unittest.main()
