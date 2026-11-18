"""Window chrome pins (field report, Zak, 2026-11-18): the
window had no titlebar — nothing to drag, no X to close it —
and its sizing was weird. The cause: set_content(notebook)
with no header bar anywhere (GTK4 on Wayland draws no
server-side decoration to fall back on), plus a
non-scrollable 13-tab notebook and natural-size propagation
forcing the window's minimum."""
import os
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "source",
                   "app", "ai-client.py")
PAGES = os.path.join(os.path.dirname(__file__), "..", "source",
                     "app", "conduit_pages.py")


class ChromeTests(unittest.TestCase):
    def setUp(self):
        self.src = open(SRC).read()
        self.pages = open(PAGES).read()

    def test_header_bar_present(self):
        self.assertIn("Adw.ToolbarView", self.src)
        self.assertIn("Adw.HeaderBar", self.src)
        self.assertIn("add_top_bar", self.src)
        self.assertIn("toolbar.set_content(self.notebook)",
                      self.src)
        # the bare no-chrome set_content survives only as the
        # fallback path (exactly one occurrence, in the except)
        self.assertEqual(
            self.src.count("self.win.set_content(self.notebook)"),
            1)

    def test_titlebar_fallback(self):
        self.assertIn("set_titlebar(Gtk.HeaderBar())", self.src)

    def test_sizing_guards(self):
        self.assertIn("set_scrollable(True)", self.src)
        self.assertIn("set_size_request(720, 480)", self.src)
        self.assertIn("set_propagate_natural_height(False)",
                      self.src)
        self.assertIn("set_propagate_natural_width(False)",
                      self.pages)


if __name__ == "__main__":
    unittest.main()
