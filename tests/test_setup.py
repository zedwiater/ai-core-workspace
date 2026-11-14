"""core.setup — plan engine over synthetic hardware profiles."""
import json
import unittest

from tests import __init__ as _path  # noqa: F401
from core import setup

CHROMEBOOK = {"os_id": "debian", "pkg_mgr": "apt", "cores": 4,
              "ram_gb": 4.0, "gpu": None, "disk_free_gb": 12.0,
              "home": "/home/kid", "arch": "x86_64"}
MID = {"os_id": "arch", "pkg_mgr": "pacman", "cores": 8,
       "ram_gb": 16.0, "gpu": None, "disk_free_gb": 200.0,
       "home": "/home/mid", "arch": "x86_64"}
BIGGPU = {"os_id": "fedora", "pkg_mgr": "dnf", "cores": 16,
          "ram_gb": 64.0,
          "gpu": {"vendor": "nvidia", "name": "RTX 4090",
                  "vram_gb": 24.0},
          "disk_free_gb": 900.0, "home": "/home/big",
          "arch": "x86_64"}
CHOICES = {"mode": "home", "brain": "ollama", "network": "local",
           "api_tiers": False, "chat_doors": False, "pair": False,
           "role": "parent"}


class TestSizing(unittest.TestCase):
    def test_chromebook_gets_small_models(self):
        rec = setup.recommend_models(CHROMEBOOK)
        self.assertEqual(rec["chat"]["model"], "gemma3:1b")
        self.assertEqual(rec["basis"], "RAM")

    def test_mid_gets_7b_chat(self):
        rec = setup.recommend_models(MID)
        self.assertEqual(rec["chat"]["model"], "qwen2.5:7b")
        self.assertEqual(rec["reason"]["model"], "qwen2.5:14b")

    def test_big_gpu_sizes_by_vram(self):
        rec = setup.recommend_models(BIGGPU)
        self.assertEqual(rec["basis"], "VRAM")
        self.assertEqual(rec["chat"]["model"], "qwen2.5:14b")
        self.assertEqual(rec["reason"]["model"], "qwen2.5:32b")

    def test_reasoning_is_shown(self):
        rec = setup.recommend_models(MID)
        for slot in ("chat", "reason", "summarizer"):
            self.assertTrue(rec[slot]["why"])


class TestPlan(unittest.TestCase):
    def test_package_manager_branches(self):
        for prof, frag in ((CHROMEBOOK, "apt-get"),
                           (MID, "pacman"), (BIGGPU, "dnf")):
            plan = setup.build_plan(prof, CHOICES, src_dir="/src")
            cmds = " ".join(c for s in plan["steps"]
                            for c in s["commands"])
            self.assertIn(frag, cmds)

    def test_home_minimum_footprint_math(self):
        plan = setup.build_plan(CHROMEBOOK, CHOICES, src_dir="/src")
        t = plan["totals"]
        expect = round(sum(s["disk_gb"] for s in plan["steps"]), 2)
        self.assertEqual(t["disk_gb"], expect)
        self.assertIn("~/ai-core", plan["footprint"])
        self.assertIn("$0", t["money"])

    def test_no_sudo_below_its_level(self):
        for prof in (CHROMEBOOK, MID, BIGGPU):
            for mode in ("home", "system"):
                plan = setup.build_plan(
                    prof, dict(CHOICES, mode=mode), src_dir="/src")
                for s in plan["steps"]:
                    if any(c.startswith("sudo")
                           for c in s["commands"]):
                        self.assertGreaterEqual(
                            s["min_level"], 2,
                            f"{mode}/{s['id']} sudo below level 2")
                        self.assertEqual(s["needs"], "sudo")
                    if s["min_level"] == 0:
                        self.assertEqual(s["commands"], [])

    def test_level_gates_hold_sudo_steps(self):
        plan = setup.build_plan(MID, dict(CHOICES, mode="system"),
                                src_dir="/src")
        runnable, held = setup.steps_for_level(plan, 1)
        self.assertTrue(all(s["min_level"] <= 1 for s in runnable))
        self.assertTrue(any(s["needs"] == "sudo" for s in held))
        runnable3, held3 = setup.steps_for_level(plan, 3)
        self.assertEqual(held3, [])
        self.assertEqual(len(runnable3), len(plan["steps"]))

    def test_dry_run_shows_held_and_costs(self):
        plan = setup.build_plan(MID, dict(CHOICES, mode="system"),
                                src_dir="/src")
        script = setup.render_script(plan, 1)
        self.assertIn("HELD at level 1", script)
        self.assertIn("Cost up front", script)
        full = setup.render_script(plan, 3)
        self.assertNotIn("HELD", full)
        self.assertIn("install.sh", full)

    def test_tailnet_adds_steps(self):
        plan = setup.build_plan(
            MID, dict(CHOICES, network="tailnet"), src_dir="/src")
        ids = [s["id"] for s in plan["steps"]]
        self.assertIn("tailscale-install", ids)
        up = next(s for s in plan["steps"]
                  if s["id"] == "tailscale-up")
        self.assertEqual(up["kind"], "guided")

    def test_llamacpp_and_none_brains(self):
        plan = setup.build_plan(
            MID, dict(CHOICES, brain="llamacpp"), src_dir="/src")
        brain = next(s for s in plan["steps"] if s["id"] == "brain")
        self.assertTrue(any("llama.cpp" in c
                            for c in brain["commands"]))
        plan2 = setup.build_plan(
            MID, dict(CHOICES, brain="none"), src_dir="/src")
        self.assertFalse(any(s["id"] == "models"
                             for s in plan2["steps"]))


class TestPairing(unittest.TestCase):
    KEY = ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAABAgMEBQYHCAkK"
           "CwwNDg8QERITFBUWFxgZGhscHR4f test@box")

    def test_fingerprint_shape(self):
        fp = setup.key_fingerprint(self.KEY)
        self.assertTrue(fp.startswith("SHA256:"))
        self.assertEqual(fp, setup.key_fingerprint(self.KEY))

    def test_pairer_restricts_to_tailnet(self):
        script = setup.pairer_script(self.KEY, "Muse")
        self.assertIn('from="100.64.0.0/10"', script)
        self.assertIn("authorized_keys", script)
        self.assertIn(setup.key_fingerprint(self.KEY), script)

    def test_pairer_rejects_garbage(self):
        with self.assertRaises(ValueError):
            setup.pairer_script("hello world", "x")
        with self.assertRaises(ValueError):
            setup.pairer_script("ssh-ed25519 AAAA'; rm -rf /", "x")


class TestSecretsAndEditors(unittest.TestCase):
    def test_secret_roundtrip_0600(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "secrets.json")
            setup.save_secret("telegram-token", "abc123", base=path)
            self.assertEqual(
                setup.load_secret("telegram-token", base=path),
                "abc123")
            self.assertEqual(
                oct(os.stat(path).st_mode & 0o777), "0o600")
            self.assertIsNone(setup.load_secret("nope", base=path))

    def test_validate_config(self):
        ok, problems = setup.validate_config_text(
            json.dumps({"mcp_ports": {"files": 9101}}))
        self.assertFalse(ok)  # keys differ from the full registry
        self.assertTrue(any("differ" in p for p in problems))
        from core.protocol import SERVICE_PORTS
        ok, problems = setup.validate_config_text(
            json.dumps({"mcp_ports": dict(SERVICE_PORTS)}))
        self.assertTrue(ok, problems)
        ok, _p = setup.validate_config_text("{not json")
        self.assertFalse(ok)

    def test_probe_lines(self):
        def fake(port, payload, timeout=2):
            return {"status": "ok", "service": "x", "port": port}
        lines = setup.probe_config_ports(
            json.dumps({"mcp_ports": {"files": 9999}}), call=fake)
        self.assertTrue(any("MISMATCH" in ln for ln in lines))
        self.assertTrue(any(ln.startswith("files:") for ln in lines))


class TestMinimumsAndLimits(unittest.TestCase):
    def test_plan_carries_floor_row_and_two_limits(self):
        plan = setup.build_plan(CHROMEBOOK, CHOICES,
                                src_dir="/src")
        self.assertIn("1.5B", plan["minimums"]["chat"])
        self.assertIn("glazing_chromebook_success",
                      plan["minimums"]["evidence"])
        lim = plan["limits"]
        self.assertEqual(lim["declared"]["chat_model"],
                         plan["recommendations"]["chat"]["model"])
        self.assertEqual(lim["actual"]["cores"],
                         CHROMEBOOK["cores"])
        self.assertIn("power and data", lim["rule"])


if __name__ == "__main__":
    unittest.main()
