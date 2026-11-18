"""Default-model doctrine (Zak, 2026-11-18): the app sets
itself as the default Ollama model; the picker entries stay
SHORT (a dropdown entry sets the window's minimum width);
fit is judged against the MACHINE (total RAM minus the OS
reserve — the pairing's accounting), never against the
moment's free memory, which a busy desktop can eat."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import models  # noqa: E402

CLIENT = os.path.join(os.path.dirname(__file__), "..", "source",
                      "app", "ai-client.py")
LAPTOP_TOTAL = 7.6   # the reference laptop
PC_TOTAL = 48.0


class MachineFitTests(unittest.TestCase):
    def test_paired_3b_fits_the_laptop(self):
        ok, _ = models.machine_fit(1.9, LAPTOP_TOTAL)
        self.assertTrue(ok)

    def test_8b_never_fits_the_laptop(self):
        ok, line = models.machine_fit(5.2, LAPTOP_TOTAL)
        self.assertFalse(ok)
        self.assertIn("too big for this machine", line)

    def test_14b_fits_the_pc(self):
        ok, _ = models.machine_fit(9.0, PC_TOTAL)
        self.assertTrue(ok)


class PickTests(unittest.TestCase):
    def test_talking_wins_on_the_laptop(self):
        self.assertEqual(
            models.pick_default_model(
                ["qwen2.5:3b", "ai-core-talking:latest"],
                {"qwen2.5:3b": 1.9, "ai-core-talking:latest": 1.9},
                total_gb=LAPTOP_TOTAL),
            "ai-core-talking:latest")

    def test_unfit_talking_yields_to_fitting_stack_top(self):
        self.assertEqual(
            models.pick_default_model(
                ["ai-core-talking:latest", "qwen2.5:3b"],
                {"ai-core-talking:latest": 5.2, "qwen2.5:3b": 1.9},
                total_gb=LAPTOP_TOTAL, stack_top="qwen2.5:3b"),
            "qwen2.5:3b")

    def test_largest_fitting_on_the_pc(self):
        self.assertEqual(
            models.pick_default_model(
                ["qwen2.5:3b", "george-14:latest"],
                {"qwen2.5:3b": 1.9, "george-14:latest": 8.4},
                total_gb=PC_TOTAL),
            "george-14:latest")

    def test_nothing_fits_falls_back_to_talking(self):
        self.assertEqual(
            models.pick_default_model(
                ["qwen3:8b", "ai-core-talking:latest"],
                {"qwen3:8b": 5.2, "ai-core-talking:latest": 5.2},
                total_gb=LAPTOP_TOTAL),
            "ai-core-talking:latest")

    def test_empty_shelf(self):
        self.assertIsNone(models.pick_default_model([], {}, 4.0))


class LabelTests(unittest.TestCase):
    def test_label_is_short_and_means_something(self):
        lab = models.model_label("ai-core-talking:latest",
                                 {"ai-core-talking:latest": 1.9},
                                 total_gb=LAPTOP_TOTAL)
        self.assertIn("app voice", lab)
        self.assertIn("1.9 GB", lab)
        # short enough to sit in a dropdown without stretching
        # the window (the long verdict form did exactly that)
        self.assertLess(len(lab), 45)
        self.assertNotIn("won't fit", lab)


class MemTests(unittest.TestCase):
    def test_meminfo_parse(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("MemTotal: 8000000 kB\n"
                    "MemAvailable: 3000000 kB\n")
            path = f.name
        self.assertAlmostEqual(models.mem_available_gb(path),
                               3000000 / 1048576, places=2)
        self.assertAlmostEqual(models.mem_total_gb(path),
                               8000000 / 1048576, places=2)


class ClientPinTests(unittest.TestCase):
    def setUp(self):
        self.src = open(CLIENT).read()

    def test_window_default_and_picker_wiring(self):
        self.assertIn("set_default_size(900, 660)", self.src)
        self.assertIn("pick_default_model", self.src)
        self.assertIn("model_label", self.src)

    def test_header_cannot_stretch_the_window(self):
        # the seat-state label ellipsizes, the duplicate title
        # is gone, and the seat gate is the machine fit
        self.assertIn("set_ellipsize(Pango.EllipsizeMode.END)",
                      self.src)
        self.assertNotIn("AI Core Workspace Engine", self.src)
        self.assertIn("machine_fit", self.src)


if __name__ == "__main__":
    unittest.main()
