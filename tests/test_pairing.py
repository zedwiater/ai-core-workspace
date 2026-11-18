"""The base function: aptitude -> known model + layers + tiers.

Cases are the reference machines' shapes: the tuned PC (advisory —
its resident outranks any fresh pairing), the bottom-end laptop,
and the VM floor.
"""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from core import pairing


def census(ram_mb, gpus):
    return {"ram": {"effective_mb": ram_mb}, "gpus": gpus}


class TestPairing(unittest.TestCase):
    def test_pc_class_split_14b(self):
        p = pairing.pair(census(48062, [{"vendor": "AMD", "vram_gb": 2},
                                        {"vendor": "AMD", "vram_gb": 7}]))
        self.assertEqual(p["model"], "qwen2.5:14b")
        self.assertEqual(p["mode"], "GPU+CPU split seat")
        self.assertTrue(0 < p["gpu_layers"] < 48)

    def test_laptop_class_cpu_seat(self):
        # 7 GB RAM, no discrete VRAM: after the desktop's reserve,
        # the honest pair is the 3B on a CPU seat — an 8B here left
        # the machine nothing and hard-locked it (2026-11-17).
        p = pairing.pair(census(7168, []))
        self.assertEqual(p["mode"], "CPU seat")
        self.assertEqual(p["model"], "qwen2.5:3b")
        self.assertEqual(p["gpu_layers"], 0)

    def test_desktop_16gb_still_pairs_14b(self):
        p = pairing.pair(census(16384, []))
        self.assertEqual(p["model"], "qwen2.5:14b")

    def test_big_gpu_full_seat(self):
        p = pairing.pair(census(32768, [{"vendor": "NVIDIA", "vram_gb": 24}]))
        self.assertEqual(p["mode"], "full GPU seat")
        self.assertEqual(p["gpu_layers"], p["total_layers"])

    def test_floor_still_pairs(self):
        # Below even the smallest known model's honest CPU fit:
        # the floor pairs anyway, and says the fit is nominal.
        p = pairing.pair(census(1024, []))
        self.assertEqual(p["model"], "qwen2.5:1.5b")
        self.assertIn("nominal", p["mode"])


if __name__ == "__main__":
    unittest.main()
