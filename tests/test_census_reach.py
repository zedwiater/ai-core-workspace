"""Audio + reach discovery (Zak, 2026-11-18): the crawl must
look for the connections and pipes the system already has —
audio, sensors, system logs, network, vpn, ssh — and carry a
suggested use for each, for the user to confirm."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import census  # noqa: E402


class AudioProbeTests(unittest.TestCase):
    def test_cards_with_capabilities_and_names(self):
        with tempfile.TemporaryDirectory() as d:
            sys_root = os.path.join(d, "sound")
            os.makedirs(os.path.join(sys_root, "card0"))
            open(os.path.join(sys_root, "card0", "pcmC0D0c"),
                 "w").close()
            open(os.path.join(sys_root, "card0", "pcmC0D0p"),
                 "w").close()
            cards_file = os.path.join(d, "cards")
            with open(cards_file, "w") as f:
                f.write(" 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n")
            cards = census.audio_probe(sys_root, cards_file)
        self.assertEqual(len(cards), 1)
        self.assertTrue(cards[0]["capture"])
        self.assertTrue(cards[0]["playback"])
        self.assertIn("HDA Intel PCH", cards[0]["name"])

    def test_no_audio_is_an_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(census.audio_probe(
                os.path.join(d, "none"),
                os.path.join(d, "none2")), [])


class ReachProbeTests(unittest.TestCase):
    def test_structure_and_suggestions(self):
        items = census.reach_probe(which=lambda _n: None,
                                   home="/nonexistent-home")
        ids = {i["id"] for i in items}
        self.assertEqual(ids, {"vpn", "ssh-server", "ssh-keys",
                               "system-logs", "sensors-serial",
                               "sensors-hwmon", "docker", "network"})
        for i in items:
            self.assertIsInstance(i["found"], bool)
            self.assertTrue(i["suggests"])
            self.assertTrue(i["detail"])

    def test_vpn_and_keys_found(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".ssh"))
            open(os.path.join(home, ".ssh", "id.pub"), "w").close()
            items = census.reach_probe(
                which=lambda n: "/usr/bin/tailscale"
                if n == "tailscale" else None,
                home=home)
        by_id = {i["id"]: i for i in items}
        self.assertTrue(by_id["vpn"]["found"])
        self.assertIn("Tailscale", by_id["vpn"]["detail"])
        self.assertTrue(by_id["ssh-keys"]["found"])
        self.assertIn("1 public key", by_id["ssh-keys"]["detail"])


if __name__ == "__main__":
    unittest.main()
