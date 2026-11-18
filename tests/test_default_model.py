"""Default-model doctrine (Zak, 2026-11-18): the app sets
itself as the default Ollama model; the picker must MEAN
something (whose voice, how big, whether it fits); a model
that cannot fit is never the default while a fitting one
exists; the window's default width is the narrower one he
asked for."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import models  # noqa: E402

CLIENT = os.path.join(os.path.dirname(__file__), "..", "source",
                      "app", "ai-client.py")


class PickTests(unittest.TestCase):
    def test_talking_wins_when_it_fits(self):
        self.assertEqual(
            models.pick_default_model(
                ["qwen3:8b", "ai-core-talking:latest"],
                {"qwen3:8b": 5.2, "ai-core-talking:latest": 2.0},
                avail_gb=3.0),
            "ai-core-talking:latest")

    def test_unfit_talking_yields_to_fitting_stack_top(self):
        self.assertEqual(
            models.pick_default_model(
                ["ai-core-talking:latest", "qwen2.5:3b"],
                {"ai-core-talking:latest": 5.2, "qwen2.5:3b": 2.0},
                avail_gb=3.0, stack_top="qwen2.5:3b"),
            "qwen2.5:3b")

    def test_largest_fitting_without_talking(self):
        self.assertEqual(
            models.pick_default_model(
                ["qwen2.5:3b", "george-14:latest"],
                {"qwen2.5:3b": 2.0, "george-14:latest": 9.0},
                avail_gb=30.0),
            "george-14:latest")

    def test_nothing_fits_falls_back_to_talking(self):
        self.assertEqual(
            models.pick_default_model(
                ["qwen3:8b", "ai-core-talking:latest"],
                {"qwen3:8b": 5.2, "ai-core-talking:latest": 5.2},
                avail_gb=1.0),
            "ai-core-talking:latest")

    def test_empty_shelf(self):
        self.assertIsNone(models.pick_default_model([], {}, 4.0))


class LabelTests(unittest.TestCase):
    def test_label_means_something(self):
        lab = models.model_label("ai-core-talking:latest",
                                 {"ai-core-talking:latest": 2.0},
                                 avail_gb=3.0)
        self.assertIn("app's own voice", lab)
        self.assertIn("2.0 GB", lab)
        self.assertIn("fits", lab)
        bad = models.model_label("qwen3:8b", {"qwen3:8b": 5.2},
                                 avail_gb=3.0)
        self.assertIn("won't fit", bad)


class MemTests(unittest.TestCase):
    def test_meminfo_parse(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("MemTotal: 8000000 kB\n"
                    "MemAvailable: 3000000 kB\n")
            path = f.name
        self.assertAlmostEqual(models.mem_available_gb(path),
                               3000000 / 1048576, places=2)


class ClientPinTests(unittest.TestCase):
    def test_window_default_and_picker_wiring(self):
        src = open(CLIENT).read()
        self.assertIn("set_default_size(900, 660)", src)
        self.assertIn("pick_default_model", src)
        self.assertIn("model_label", src)


if __name__ == "__main__":
    unittest.main()
