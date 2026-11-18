"""Quick Actions (Zak's design, approved 2026-11-18): the
generalized house hits, each organ-aware — the button says
when its organ is absent instead of failing sideways."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import quick_actions as qa  # noqa: E402

CAM = {"device": "/dev/video0", "name": "HP Wide Vision HD Camera"}


class AvailabilityTests(unittest.TestCase):
    def test_no_camera_marks_both_camera_actions(self):
        avail = qa.availability(cameras=(), voice_ok=True)
        self.assertFalse(avail["camera"][0])
        self.assertFalse(avail["grab5"][0])
        self.assertIn("no camera was found", avail["camera"][1])
        self.assertTrue(avail["status"][0])  # status needs no organ

    def test_button_label_states_the_absence(self):
        avail = qa.availability(cameras=(), voice_ok=True)
        cam_action = qa.ACTIONS[0]
        self.assertIn("(no camera)", qa.button_label(cam_action, avail))
        avail2 = qa.availability(cameras=[CAM], voice_ok=True)
        self.assertEqual(qa.button_label(cam_action, avail2),
                         cam_action["title"])

    def test_voice_absence(self):
        avail = qa.availability(cameras=[CAM], voice_ok=False)
        self.assertFalse(avail["say"][0])
        self.assertIn("voice service", qa.button_label(
            qa.ACTIONS[2], avail))


class CameraTests(unittest.TestCase):
    def test_still_without_ffmpeg_names_the_missing_piece(self):
        import core.quick_actions as m
        old = m.shutil.which
        m.shutil.which = lambda _x: None
        try:
            ok, line = qa.camera_still(CAM)
        finally:
            m.shutil.which = old
        self.assertFalse(ok)
        self.assertIn("ffmpeg", line)

    def test_still_command_shape_and_success(self):
        calls = []

        class R:
            returncode = 0

        def runner(cmd, capture_output, timeout):
            calls.append(cmd)
            # the fake "capture" creates the file
            open(cmd[-1], "w").write("jpg")
            return R()

        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ok, line = qa.camera_still(CAM, out_dir=d, runner=runner)
        self.assertTrue(ok)
        self.assertEqual(calls[0][:5], ["ffmpeg", "-y", "-f", "v4l2", "-i"])
        self.assertIn("/dev/video0", calls[0])
        self.assertIn("quick-camera.jpg", line)

    def test_clip_command_shape(self):
        calls = []

        def popen(cmd, **kw):
            calls.append((cmd, kw))
            return object()

        import core.quick_actions as m
        old = m.shutil.which
        m.shutil.which = lambda _x: "/usr/bin/ffmpeg"
        try:
            ok, line = qa.camera_clip(CAM, popen=popen)
        finally:
            m.shutil.which = old
        self.assertTrue(ok)
        self.assertIn("-t", calls[0][0])
        self.assertIn("300", calls[0][0])
        self.assertTrue(calls[0][1]["start_new_session"])


class CompositionTests(unittest.TestCase):
    def test_status_lines(self):
        lines = qa.system_status("lap", 4, 3.1, 35, ["qwen2.5:3b"],
                                 "8 of 8 MCP services answering")
        joined = "\n".join(lines)
        self.assertIn("qwen2.5:3b", joined)
        self.assertIn("nothing", qa.system_status(
            "lap", 4, 3.1, 35, [], "x")[1])

    def test_web_lines_empty_and_full(self):
        self.assertIn("No results", qa.web_lines("q", [])[0])
        lines = qa.web_lines("q", [{"title": "T", "snippet": "S",
                                    "url": "http://x"}])
        self.assertIn("• T", lines[1])
        self.assertIn("leads, not", lines[0])


class ClientWiringTests(unittest.TestCase):
    def test_row_built_and_handlers_present(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "source", "app",
                                "ai-client.py")).read()
        self.assertIn("quick_actions.ACTIONS", src)
        self.assertIn("def _on_quick", src)
        self.assertIn("def _refresh_quick_actions", src)
        self.assertIn('"action": "speak"', src)
        self.assertIn("websearch_mod.search", src)


if __name__ == "__main__":
    unittest.main()
