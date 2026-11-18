"""The crawl checks for a camera (Zak, 2026-11-18: it did not
find the laptop's webcam because it never looked)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source", "app"))
from core import census  # noqa: E402
import conduit_pages  # noqa: E402


class CameraProbeTests(unittest.TestCase):
    def test_named_and_unnamed_devices(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "video0"))
            with open(os.path.join(d, "video0", "name"), "w") as f:
                f.write("HP Wide Vision HD Camera\n")
            os.makedirs(os.path.join(d, "video1"))
            cams = census.camera_probe(d)
        self.assertEqual(cams[0], {"device": "/dev/video0",
                                   "name": "HP Wide Vision HD Camera"})
        self.assertEqual(cams[1]["name"], "/dev/video1")

    def test_no_cameras_is_an_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(census.camera_probe(d), [])


class GreetingTests(unittest.TestCase):
    def test_greeting_names_the_camera_when_present(self):
        crawl = {"census": {
            "host": "lap", "os": "Linux", "cpu": {"effective_threads": 4},
            "ram": {"effective_mb": 7600}, "gpus": [],
            "disk_free_gb": 35,
            "cameras": [{"device": "/dev/video0",
                         "name": "HP Wide Vision HD Camera"}],
            "expectations": {"budget": {"max_parallel_model_tasks": 1},
                             "tiers": []}}}
        text = "\n".join(conduit_pages.greeting_lines(crawl))
        self.assertIn("HP Wide Vision HD Camera", text)


if __name__ == "__main__":
    unittest.main()
