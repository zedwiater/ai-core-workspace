"""Automatic updates (Zak, 2026-11-18): a daily timer updates
when the source moved; the app checks on launch and offers
the update in its header. Pins for both halves."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "source"))
from core import update_check  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
INSTALL = os.path.join(ROOT, "install.sh")
CLIENT = os.path.join(ROOT, "source", "app", "ai-client.py")


class FakeRunner:
    def __init__(self, count):
        self.count = count
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        class R:
            pass
        r = R()
        r.stdout = f"{self.count}\n"
        return r


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stamp = os.path.join(self.tmp.name, "installed.json")
        with open(self.stamp, "w") as f:
            json.dump({"commit": "abc", "src": self.tmp.name,
                       "date": "2026-11-18"}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_behind(self):
        info = update_check.check(self.stamp, runner=FakeRunner(3))
        self.assertEqual(info["state"], "behind")
        self.assertEqual(info["behind"], 3)

    def test_current(self):
        info = update_check.check(self.stamp, runner=FakeRunner(0))
        self.assertEqual(info["state"], "current")

    def test_no_stamp_is_unknown(self):
        info = update_check.check("/nonexistent/x.json",
                                  runner=FakeRunner(0))
        self.assertEqual(info["state"], "unknown")


class InstallerPinTests(unittest.TestCase):
    def setUp(self):
        self.sh = open(INSTALL).read()
        self.client = open(CLIENT).read()

    def test_updater_and_timer_deployed(self):
        self.assertIn("/usr/local/bin/ai-core-update", self.sh)
        self.assertIn("ai-core-update.timer", self.sh)
        self.assertIn("OnCalendar=daily", self.sh)
        self.assertIn("installed.json", self.sh)

    def test_updater_noops_when_unchanged(self):
        # (the comparison is escaped inside the installer's
        # heredoc — match the source form)
        self.assertIn('\\$BEFORE" = "\\$AFTER', self.sh)
        self.assertIn("already current", self.sh)
        self.assertIn("pull --ff-only", self.sh)

    def test_uninstall_removes_them(self):
        un = self.sh.split("UNINSTALL")[1].split("PRIVILEGE")[0]
        self.assertIn("ai-core-update", un)

    def test_client_offers_update(self):
        self.assertIn("_check_update_thread", self.client)
        self.assertIn("pkexec", self.client)
        self.assertIn("update_btn", self.client)


if __name__ == "__main__":
    unittest.main()
