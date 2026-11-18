"""The thinking stream (Zak's play session, 2026-11-17): a sent
chat must show signs of life through the wait — progress beats
before every model call and every tool run, and the client
clears its thinking bubble when the answer (or error) lands."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core.loop import run_tool_loop  # noqa: E402

TOOL = "TOOL:sound:status:{}"  # TOOL:<service>:<action>:<json>


class ProgressTests(unittest.TestCase):
    def test_beats_fire_in_order(self):
        beats = []
        replies = iter([TOOL, "the answer"])
        history = []
        emitted = []
        run_tool_loop(history, lambda h: next(replies),
                      lambda t, s: emitted.append((t, s)),
                      execute=lambda payload: "ok",
                      progress=beats.append)
        self.assertEqual(beats, ["thinking", "tool", "thinking"])
        self.assertEqual(emitted[-1], ("the answer", "ai"))

    def test_no_progress_callback_is_the_old_behavior(self):
        history = []
        emitted = []
        run_tool_loop(history, lambda h: "plain answer",
                      lambda t, s: emitted.append((t, s)))
        self.assertEqual(emitted, [("plain answer", "ai")])

    def test_error_path_still_beats_once_and_emits(self):
        beats = []
        emitted = []

        def boom(h):
            raise RuntimeError("door closed")

        run_tool_loop([], boom, lambda t, s: emitted.append((t, s)),
                      progress=beats.append)
        self.assertEqual(beats, ["thinking"])
        self.assertEqual(len(emitted), 1)


class ClientWiringTests(unittest.TestCase):
    def test_client_shows_updates_and_clears_the_thinking_bubble(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "source", "app",
                                "ai-client.py")).read()
        self.assertIn("progress=self._emit_progress", src)
        self.assertIn("def _show_thinking", src)
        self.assertIn("def _emit_progress", src)
        self.assertIn("GLib.idle_add(self._clear_thinking)", src)
        self.assertIn("Thinking — the model is working", src)


if __name__ == "__main__":
    unittest.main()
