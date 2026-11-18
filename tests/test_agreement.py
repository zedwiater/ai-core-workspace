"""The privilege agreement (Zak, 2026-11-18): three levels —
observer (no permissions), connected (local organs), all
(shell + file operations, deletion included, disclaimer) —
enforced on tool calls and quick actions, defaulting to
observer, offerings unaffected."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import agreement as ag  # noqa: E402


class LevelTests(unittest.TestCase):
    def test_matrix(self):
        self.assertTrue(ag.allows("observer", "chat"))
        self.assertTrue(ag.allows("observer", "web"))
        self.assertFalse(ag.allows("observer", "services"))
        self.assertFalse(ag.allows("observer", "shell"))
        self.assertTrue(ag.allows("connected", "services"))
        self.assertTrue(ag.allows("connected", "quick"))
        self.assertFalse(ag.allows("connected", "shell"))
        self.assertFalse(ag.allows("connected", "files_write"))
        self.assertTrue(ag.allows("all", "shell"))
        self.assertTrue(ag.allows("all", "files_write"))

    def test_unknowns_fail_closed(self):
        self.assertFalse(ag.allows("bogus", "shell"))
        self.assertTrue(ag.allows("bogus", "chat"))
        self.assertFalse(ag.allows("all", "bogus-capability"))

    def test_gate_for_tool(self):
        self.assertEqual(ag.gate_for_tool("shell", "run"), "shell")
        self.assertEqual(ag.gate_for_tool("files", "read"),
                         "services")
        self.assertEqual(ag.gate_for_tool("files", "delete"),
                         "files_write")
        self.assertEqual(ag.gate_for_tool("files", "write_file"),
                         "files_write")
        self.assertEqual(ag.gate_for_tool("voice", "speak"),
                         "services")

    def test_refusal_names_the_needed_level(self):
        text = ag.refusal("observer", "shell")
        self.assertIn("All", text)
        self.assertIn("Nothing was run", text)

    def test_disclaimer_and_levels_exist(self):
        self.assertEqual([lv["id"] for lv in ag.LEVELS],
                         ["observer", "connected", "all"])
        self.assertIn("delete", ag.DISCLAIMER)


class PersistenceTests(unittest.TestCase):
    def test_roundtrip_preserves_other_keys(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "conduit.json")
            with open(path, "w") as f:
                json.dump({"options": {"service_links": False}}, f)
            ag.save(path, "all")
            self.assertEqual(ag.load(path), "all")
            with open(path) as f:
                data = json.load(f)
            self.assertFalse(data["options"]["service_links"])

    def test_default_is_observer(self):
        self.assertEqual(ag.load("/nonexistent/conduit.json"),
                         "observer")


class WiringTests(unittest.TestCase):
    def test_client_gates_tools_and_quick_actions(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "source", "app",
                                "ai-client.py")).read()
        self.assertIn("agreement_mod.gate_for_tool", src)
        self.assertIn("agreement_mod.refusal", src)
        self.assertIn("on_agreement=self._apply_agreement", src)

    def test_landing_offers_the_three_levels(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "source", "app",
                                "conduit_pages.py")).read()
        self.assertIn("agreement_mod.LEVELS", src)
        self.assertIn("agreement_mod.DISCLAIMER", src)
        self.assertIn("def load_agreement", src)

    def test_installer_prints_the_agreement(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "install.sh")).read()
        self.assertIn("three levels, your choice", src)
        self.assertIn("Observer — no permissions granted", src)


if __name__ == "__main__":
    unittest.main()


class VisibilityTests(unittest.TestCase):
    """Zak (2026-11-18): the permissions setting 'should have
    been a little more obvious — I shouldn't have had to dig
    for it.' The choice sits at the top of the landing, and
    the chat header carries the standing level."""

    def test_landing_reorders_agreement_to_the_top(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "source", "app",
                                "conduit_pages.py")).read()
        self.assertIn("reorder_child_after", src)
        self.assertIn("Permissions — what this app", src)

    def test_header_chip_shows_the_level(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "source", "app",
                                "ai-client.py")).read()
        self.assertIn("perm_btn", src)
        self.assertIn("Permissions: ", src)
        self.assertIn("set_current_page(0)", src)
