"""core.setup — the WiCi brain: fulcrum split, combined-pool
sizing, leg assignments, feed bound, patience cost, faux rule."""
import math
import unittest

from tests import __init__ as _path  # noqa: F401
from core import setup
from tests.test_setup import BIGGPU, CHOICES

RTX4060 = {"os_id": "ubuntu", "pkg_mgr": "apt", "cores": 8,
           "ram_gb": 32.0,
           "gpu": {"vendor": "nvidia", "name": "RTX 4060",
                   "vram_gb": 8.0},
           "disk_free_gb": 500.0, "home": "/home/gpu",
           "arch": "x86_64"}
AMD = {"os_id": "arch", "pkg_mgr": "pacman", "cores": 8,
       "ram_gb": 16.0,
       "gpu": {"vendor": "amd", "name": "RX 6600 XT",
               "vram_gb": 8.0},
       "disk_free_gb": 200.0, "home": "/home/amd",
       "arch": "x86_64"}
NOGPU = {"os_id": "debian", "pkg_mgr": "apt", "cores": 4,
         "ram_gb": 4.0, "gpu": None, "disk_free_gb": 12.0,
         "home": "/home/kid", "arch": "x86_64"}
MANYCORE = {"os_id": "debian", "pkg_mgr": "apt", "cores": 32,
            "ram_gb": 64.0,
            "gpu": {"vendor": "nvidia", "name": "RTX 3050",
                    "vram_gb": 4.0},
            "disk_free_gb": 500.0, "home": "/home/mc",
            "arch": "x86_64"}
WICI = dict(CHOICES, brain="wici")


def _plan(profile):
    return setup.build_plan(profile, WICI, src_dir="/src")


def _legs(plan):
    return {leg["slot"]: leg["legs"] for leg in plan["wici"]["legs"]}


class TestFulcrum(unittest.TestCase):
    def test_fulcrum_math(self):
        self.assertEqual(setup.wici_fulcrum(25, 100), 0.2)
        self.assertEqual(setup.wici_fulcrum(100, 100), 0.5)
        self.assertGreater(setup.wici_fulcrum(200, 100), 0.5)


class TestCombinedPoolSizing(unittest.TestCase):
    def test_4060_reason_uses_combined_pool(self):
        plan = _plan(RTX4060)
        w = plan["wici"]
        ollama_reason = setup.recommend_models(
            RTX4060)["reason"]["model"]
        # The combined VRAM+RAM pool buys a larger-class
        # reasoner than the VRAM-only ollama path picks.
        self.assertNotEqual(plan["recommendations"]["reason"]
                            ["model"], ollama_reason)
        self.assertGreater(
            setup._MODEL_SIZE_GB[
                plan["recommendations"]["reason"]["model"]],
            setup._MODEL_SIZE_GB[ollama_reason])
        # The footprint splits at beta*, and the GPU leg's
        # share genuinely fits the card.
        self.assertAlmostEqual(w["gpu_gb"] + w["cpu_gb"],
                               w["reason_gb"])
        self.assertTrue(0 < w["beta"] < 1)
        self.assertLessEqual(w["gpu_gb"], 8.0)

    def test_4090_real_with_feed_bound(self):
        plan = _plan(BIGGPU)
        w = plan["wici"]
        self.assertFalse(w["faux"])
        bound = w["feed"]["bound_tok_s"]
        self.assertTrue(math.isfinite(bound) and bound > 0)
        self.assertEqual(w["feed"]["streamed_gb_per_token"],
                         round(w["reason_gb"] * 0.15, 3))
        self.assertIn("ASSUMED", w["rate_basis"])
        self.assertIn("seesaw",
                      [s["id"] for s in plan["steps"]])


class TestLegsAndPatience(unittest.TestCase):
    def test_summarizer_rides_cpu_leg(self):
        legs = _legs(_plan(BIGGPU))
        self.assertEqual(legs["summarizer"], ["cpu"])
        self.assertEqual(legs["chat"], ["gpu"])
        self.assertEqual(set(legs["reason"]), {"gpu", "cpu"})

    def test_patience_cost_is_numeric(self):
        w = _plan(BIGGPU)["wici"]
        delta = w["patience_cost"]["est_latency_delta_pct"]
        self.assertIsInstance(delta, (int, float))
        self.assertIn("patience", w["patience_cost"]["note"])

    def test_free_range_inversion(self):
        plan = _plan(MANYCORE)
        w = plan["wici"]
        self.assertGreater(w["beta"], 0.5)
        self.assertEqual(w["lead_leg"], "cpu")
        script = setup.render_script(plan, 3)
        self.assertIn("free-range inversion", script)


class TestFauxRule(unittest.TestCase):
    def test_amd_is_faux_and_fetches_nothing(self):
        plan = _plan(AMD)
        self.assertTrue(plan["wici"]["faux"])
        cmds = " ".join(c for s in plan["steps"]
                        for c in s["commands"])
        self.assertNotIn("InferSSD", cmds)
        ids = [s["id"] for s in plan["steps"]]
        self.assertNotIn("models", ids)
        self.assertNotIn("seesaw", ids)
        brain = next(s for s in plan["steps"]
                     if s["id"] == "brain")
        self.assertEqual(brain["kind"], "guided")
        self.assertIn("FAUX", brain["title"] + brain["why"])
        self.assertTrue(all(leg["legs"] == ["cpu"]
                            for leg in plan["wici"]["legs"]))

    def test_no_gpu_is_faux(self):
        self.assertTrue(_plan(NOGPU)["wici"]["faux"])

    def test_declared_limits_carry_the_split(self):
        declared = _plan(RTX4060)["limits"]["declared"]
        for key in ("brain", "wici_beta", "wici_gpu_gb",
                    "wici_cpu_gb", "wici_feed_tok_s",
                    "wici_patience_delta_pct"):
            self.assertIn(key, declared)
        self.assertIn("wici", declared["brain"])
        faux_declared = _plan(AMD)["limits"]["declared"]
        self.assertIn("FAUX", faux_declared["brain"])

    def test_rendered_dry_run_carries_numbers_and_labels(self):
        script = setup.render_script(_plan(RTX4060), 3)
        self.assertIn("WiCi feed bound", script)
        self.assertIn("ASSUMED", script)
        self.assertIn("WiCi legs", script)
        faux_script = setup.render_script(_plan(AMD), 3)
        self.assertIn("FAUX", faux_script)


class TestNoLeakage(unittest.TestCase):
    def test_other_brains_have_no_wici_key(self):
        for brain in ("ollama", "llamacpp", "none"):
            plan = setup.build_plan(
                BIGGPU, dict(CHOICES, brain=brain),
                src_dir="/src")
            self.assertNotIn("wici", plan)
            self.assertNotIn("wici_beta",
                             plan["limits"]["declared"])


if __name__ == "__main__":
    unittest.main()
