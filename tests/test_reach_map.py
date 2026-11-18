"""The Nodes reach map (Zak, 2026-11-18): the crawl's organs
and pipes listed with simple switches that pull a device or
task into the hub — dwell and roam read the same switches."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
import conduit_pages as cp  # noqa: E402

CRAWL = {"census": {
    "cameras": [{"device": "/dev/video0", "name": "HP Cam"}],
    "audio": [{"card": "card0", "name": "PCH",
               "capture": True, "playback": True}],
    "reach": [{"id": "vpn", "kind": "network", "found": True,
               "detail": "Tailscale", "suggests": "one hub"},
              {"id": "docker", "kind": "services", "found": False,
               "detail": "no docker", "suggests": "containers"}]}}


class ReachRowsTests(unittest.TestCase):
    def test_rows_cover_organs_and_pipes(self):
        rows = cp.reach_rows(CRAWL)
        ids = [r["id"] for r in rows]
        self.assertIn("camera:/dev/video0", ids)
        self.assertIn("mic:card0", ids)
        self.assertIn("speaker:card0", ids)
        self.assertIn("reach:vpn", ids)
        docker = next(r for r in rows if r["id"] == "reach:docker")
        self.assertFalse(docker["found"])
        for r in rows:
            self.assertTrue(r["suggests"])


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir, self.old_json = cp.STATE_DIR, cp.CONDUIT_JSON
        cp.STATE_DIR = self.tmp.name
        cp.CONDUIT_JSON = os.path.join(self.tmp.name, "conduit.json")

    def tearDown(self):
        cp.STATE_DIR, cp.CONDUIT_JSON = self.old_dir, self.old_json
        self.tmp.cleanup()

    def test_switch_roundtrip(self):
        self.assertEqual(cp.load_reach_enabled(), {})
        cp.save_reach_enabled("camera:/dev/video0", True)
        self.assertEqual(cp.load_reach_enabled(),
                         {"camera:/dev/video0": True})
        cp.save_reach_enabled("camera:/dev/video0", False)
        self.assertFalse(cp.load_reach_enabled()
                         ["camera:/dev/video0"])

    def test_connect_script_found_when_present(self):
        scripts = os.path.join(self.tmp.name, "scripts")
        os.makedirs(scripts)
        p = os.path.join(scripts, "connect-camera--dev-video0.sh")
        with open(p, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(p, 0o755)
        self.assertEqual(cp.connect_script_for("camera:/dev/video0"),
                         p)
        self.assertIsNone(cp.connect_script_for("reach:vpn"))


class DwellSetTests(unittest.TestCase):
    def test_dwell_lists_the_switched_on_rows(self):
        text = cp.dwell_text(None, "", CRAWL,
                             reach_enabled={"mic:card0": True})
        self.assertIn("Microphone — PCH", text)
        self.assertNotIn("Camera — HP Cam", text.split(
            "In the hub's dwell/roam set")[1].split("\n\n")[0])

    def test_dwell_empty_set_says_so(self):
        text = cp.dwell_text(None, "", CRAWL, reach_enabled={})
        self.assertIn("nothing yet", text)


class WiringTests(unittest.TestCase):
    def test_nodes_page_has_switches(self):
        src = open(cp.__file__).read()
        self.assertIn("pop_nodes", src)
        self.assertIn("on_reach_toggle", src)
        self.assertIn('("Nodes", nodes_box)', src)


if __name__ == "__main__":
    unittest.main()
