"""Source-order guards for the client: things that only work if
they happen before something else in the file."""
import os, unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "source", "app",
                   "ai-client.py")


class TestClientSource(unittest.TestCase):
    def test_renderer_default_precedes_gtk_versions(self):
        text = open(SRC).read()
        self.assertLess(text.index("GSK_RENDERER"),
                        text.index("gi.require_version"))

    def test_single_instance_lock_in_main(self):
        # A second launch — autostart, session restore, a click —
        # must leave, not stack. The lock in __main__ is the guard.
        self.assertIn("client.lock", open(SRC).read())
        self.assertIn("LOCK_NB", open(SRC).read())

    def test_installer_defines_real_home_before_uninstall(self):
        # The uninstall block spends $REAL_HOME; under set -u a
        # definition that arrives later crashes the uninstall
        # itself (reference laptop, 2026-11-17).
        path = os.path.join(os.path.dirname(__file__), "..", "install.sh")
        text = open(path).read()
        self.assertLess(text.index('REAL_HOME=$(getent passwd'),
                        text.index('# --- UNINSTALL ---'))

    def test_installer_no_longer_autostarts_by_default(self):
        path = os.path.join(os.path.dirname(__file__), "..", "install.sh")
        text = open(path).read()
        self.assertNotIn('cp "$DESKTOP_DIR/ai-core.desktop" '
                         '"$REAL_HOME/.config/autostart/"', text)

    def test_alert_callback_takes_gtk_three_arguments(self):
        # PyGObject async callbacks are (source, result, user_data).
        # The two-argument version left the model popup stuck open.
        path = os.path.join(os.path.dirname(__file__), "..", "source",
                            "app", "conduit_pages.py")
        self.assertIn("def done(d, result, _user_data", open(path).read())


if __name__ == "__main__":
    unittest.main()
