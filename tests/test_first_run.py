"""First-run finality (Zak, 2026-11-18): setup must END —
a welcome get-to-know-you card with the Full-or-None choice
up front, blinking tabs that walk Conduit -> Joy -> Chat,
and a greeting seeded in the chat when the walk completes.
Plus the install-time agreement: full permission or none."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
import conduit_pages as cp  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class AboutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (cp.STATE_DIR, cp.CONDUIT_JSON)
        cp.STATE_DIR = self.tmp.name
        cp.CONDUIT_JSON = os.path.join(self.tmp.name,
                                       "conduit.json")

    def tearDown(self):
        cp.STATE_DIR, cp.CONDUIT_JSON = self.old
        self.tmp.cleanup()

    def test_about_roundtrip_and_welcomed(self):
        self.assertFalse(cp.load_welcomed())
        cp.save_about_field("call_name", "Zak")
        self.assertEqual(cp.load_about()["call_name"], "Zak")
        cp.save_welcomed()
        self.assertTrue(cp.load_welcomed())
        # the about answers survive the welcomed write
        self.assertEqual(cp.load_about()["call_name"], "Zak")


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.pages = open(os.path.join(
            ROOT, "source", "app", "conduit_pages.py")).read()
        self.client = open(os.path.join(
            ROOT, "source", "app", "ai-client.py")).read()
        self.install = open(os.path.join(ROOT, "install.sh")).read()

    def test_welcome_card_exists(self):
        self.assertIn("get to know", self.pages)
        self.assertIn("on_welcomed", self.pages)
        self.assertIn("ABOUT_FIELDS", self.pages)

    def test_guide_in_client(self):
        self.assertIn("_guide_pulse", self.client)
        self.assertIn("guide-pulse", self.client)
        self.assertIn("_seed_chat_greeting", self.client)
        self.assertIn("on_welcomed=self._guide_welcomed",
                      self.client)

    def test_install_time_agreement(self):
        self.assertIn("AI_CORE_AGREEMENT", self.install)


if __name__ == "__main__":
    unittest.main()
